"""Persistent corpus store — Phase 1 JSONL backend.

The store is committed to the repo (``data/retrieval/*.jsonl``) so it survives
across GitHub Actions runs (runners are ephemeral). Dedup is exact (id hash)
plus near-duplicate title detection (token Jaccard). ``compact()`` bounds size
by dropping items older than ``keep_days``.

The public interface (``add`` / ``all`` / ``compact``) is the contract; a
future Phase 2 can swap the JSONL persistence for a remote store (GCP /
Supabase) without changing callers.
"""
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone

log = logging.getLogger("retrieval.store")

_TZ = timezone(timedelta(hours=8))  # Asia/Taipei


def now_iso():
    return datetime.now(_TZ).isoformat(timespec="seconds")


def item_id(title, link):
    """Stable id from normalized title + link (exact-dedup key)."""
    raw = (title or "").strip().lower() + "|" + (link or "").strip()
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


class CorpusStore:
    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        if not os.path.isfile(path):
            open(path, "a", encoding="utf-8").close()

    def all(self):
        out = []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError as exc:  # noqa: BLE001
            log.warning("corpus read failed (%s)", exc)
        return out

    @staticmethod
    def _near_dup(title_tokens, existing_token_sets):
        """Overlap-coefficient near-dup: |A∩B| / min(|A|,|B|).

        Better than Jaccard for headline variants, where the shorter title is
        often a near-substring of the longer one (Jaccard penalizes the size
        difference; overlap does not).
        """
        th = set(title_tokens)
        if not th:
            return False
        for eh in existing_token_sets:
            if not eh:
                continue
            denom = min(len(th), len(eh))
            if denom and len(th & eh) / denom >= 0.8:
                return True
        return False

    def add(self, items):
        """Add items (dicts with title/link/summary/source). Dedup by id and
        near-duplicate title. Returns the number of NEW items written."""
        from core.retrieval.retrieve import tokenize  # lazy: avoid import cycle

        existing = self.all()
        seen_ids = {it.get("id") for it in existing}
        existing_title_tokens = [set(tokenize(it.get("title", ""))) for it in existing]
        new = []
        for raw in items:
            title = raw.get("title", "")
            link = raw.get("link", "")
            iid = item_id(title, link)
            if iid in seen_ids:
                continue
            ttoks = set(tokenize(title))
            if self._near_dup(ttoks, existing_title_tokens):
                continue
            rec = {
                "id": iid,
                "title": title,
                "link": link,
                "summary": (raw.get("summary") or "")[:500],
                "source": raw.get("source", ""),
                "domain_tag": raw.get("domain_tag", ""),
                "fetched_at": raw.get("fetched_at") or now_iso(),
                "published": raw.get("published", ""),
            }
            new.append(rec)
            seen_ids.add(iid)
            existing_title_tokens.append(ttoks)
        if new:
            try:
                with open(self.path, "a", encoding="utf-8") as f:
                    for rec in new:
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            except OSError as exc:  # noqa: BLE001
                log.warning("corpus write failed (%s)", exc)
                return 0
        log.info("corpus +%d (total %d)", len(new), len(existing) + len(new))
        return len(new)

    def save_all(self, records):
        """Atomically rewrite the corpus with the given records (embeddings
        and semantic tags are attached in place by the caller)."""
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            for it in records:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
        os.replace(tmp, self.path)

    def compact(self, keep_days=30, now=None):
        """Drop items whose fetched_at is older than keep_days. Returns count removed."""
        now = now or datetime.now(_TZ)
        kept, removed = [], 0
        for it in self.all():
            try:
                fa = datetime.fromisoformat(it.get("fetched_at", ""))
            except ValueError:
                kept.append(it)
                continue
            if fa.tzinfo is None:
                fa = fa.replace(tzinfo=_TZ)
            if (now - fa).days <= keep_days:
                kept.append(it)
            else:
                removed += 1
        if removed:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                for it in kept:
                    f.write(json.dumps(it, ensure_ascii=False) + "\n")
            os.replace(tmp, self.path)
            log.info("corpus compacted: -%d (kept %d)", removed, len(kept))
        return removed

    def purge_source(self, domain_fragment):
        """Remove all items whose `source` contains the given domain fragment.
        Use to immediately clean up items from removed/deprecated feeds,
        instead of waiting for the 30-day retention to expire.

        Returns the number of items removed.
        """
        kept, removed = [], 0
        for it in self.all():
            if domain_fragment.lower() in (it.get("source", "") or "").lower():
                removed += 1
            else:
                kept.append(it)
        if removed:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                for it in kept:
                    f.write(json.dumps(it, ensure_ascii=False) + "\n")
            os.replace(tmp, self.path)
            log.info("corpus purged source '%s': -%d (kept %d)", domain_fragment, removed, len(kept))
        return removed
