"""TTL cache for slowly-changing macro series (BLS monthly, Treasury daily).

``data/macro_cache.json`` is committed back by the CI workflow (same pattern
as the retrieval corpus and the llm usage counter), so the cache persists
across ephemeral runners. Daily runs then serve monthly-frequency data from
cache and only refetch when the TTL expires.
"""
import json
import os
import logging
from datetime import datetime, timedelta, timezone

log = logging.getLogger("macro_cache")

_TZ = timezone(timedelta(hours=8))  # Asia/Taipei
_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "macro_cache.json")


def _load():
    try:
        if os.path.isfile(_PATH):
            with open(_PATH, encoding="utf-8") as f:
                return json.load(f) or {}
    except Exception:  # noqa: BLE001
        pass
    return {}


def _save(state):
    try:
        os.makedirs(os.path.dirname(_PATH), exist_ok=True)
        with open(_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        log.info("macro cache write failed (%s)", exc)


def cached(key, ttl_days, fn):
    """Return ``fn()``'s value, served from cache while younger than ttl_days.

    On refresh failure a stale entry is still served (better than nothing);
    returns None only when there has never been a good value.
    """
    now = datetime.now(_TZ)
    state = _load()
    entry = state.get(key)
    if entry:
        try:
            age = (now - datetime.fromisoformat(entry["fetched_at"])).days
            if age < ttl_days:
                return entry["value"]
        except (KeyError, ValueError, TypeError):
            pass
    value = fn()
    if value is None:
        return entry.get("value") if entry else None
    state[key] = {"fetched_at": now.isoformat(timespec="seconds"), "value": value}
    _save(state)
    return value
