#!/usr/bin/env python3
"""Optional LLM layer (Google Gemini) for narrative enrichment.

Uses the current official ``google-genai`` SDK. Designed to degrade gracefully
at three levels so the pipeline runs identically with or without an LLM:

  1. ``GEMINI_API_KEY`` not set  -> functions return None (caller uses template)
  2. ``google-genai`` not installed -> same
  3. API call fails / times out   -> same

The CI workflow does NOT set the key, so it exercises the no-LLM path; locally
or in production the key unlocks real summaries.

Model: Gemini 2.5 Flash (fast, cheap). Override with ``GEMINI_MODEL``.
"""
import os
import logging

log = logging.getLogger("llm")


# ---- free-tier budget guard (keep daily usage well under the quota) --------
# Counts every Gemini API call (probes + generations) in data/llm_usage.json,
# persisted across CI runs. When the day's count reaches GEMINI_DAILY_LIMIT the
# LLM path degrades to the template instead of burning the remaining quota.
_DAILY_LIMIT = int(os.environ.get("GEMINI_DAILY_LIMIT", "60"))
_USAGE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "llm_usage.json")


def _usage_state():
    import datetime as _dt
    import json as _json
    today = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8))).strftime("%Y-%m-%d")
    try:
        state = {}
        if os.path.isfile(_USAGE_FILE):
            with open(_USAGE_FILE, encoding="utf-8") as f:
                state = _json.load(f) or {}
        if state.get("date") != today:
            state = {"date": today}
        return state
    except Exception:  # noqa: BLE001 — bookkeeping must never block the pipeline
        return {"date": today}


def _write_state(state):
    import json as _json
    try:
        os.makedirs(os.path.dirname(_USAGE_FILE), exist_ok=True)
        with open(_USAGE_FILE, "w", encoding="utf-8") as f:
            _json.dump(state, f)
    except Exception as exc:  # noqa: BLE001
        log.info("llm usage bookkeeping failed (%s)", exc)


def _allow_call(tick=False):
    """True while under the daily budget; ``tick`` also increments the count."""
    state = _usage_state()
    ok = state.get("count", 0) < _DAILY_LIMIT
    if ok and tick:
        state["count"] = state.get("count", 0) + 1
        _write_state(state)
    elif not ok:
        log.info("Gemini daily budget reached (%d calls); using template.", _DAILY_LIMIT)
    return ok


def _load_model_cache():
    return _usage_state().get("model")


def _save_model_cache(name):
    state = _usage_state()
    state["model"] = name
    _write_state(state)


_API_KEY = os.environ.get("GEMINI_API_KEY")
_DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
_CLIENT = None
_AVAILABLE = False
_MODEL_NAME = _DEFAULT_MODEL
_USER_SET = bool(os.environ.get("GEMINI_MODEL"))


def _pick_model(client, preferred, user_set):
    """Find a Gemini flash model that actually generates.

    Models get deprecated/renamed (gemini-2.5-flash is unavailable to new keys),
    so we list flash variants and probe each with a 1-token call, returning the
    first that works. ``preferred`` is tried first only when the user explicitly
    set GEMINI_MODEL. Falls back to ``preferred`` if nothing probes successfully.
    """
    from google.genai import types as _gtypes
    names = []
    try:
        for m in client.models.list():
            short = (getattr(m, "name", "") or "").split("/")[-1]
            if ("flash" in short and "gemini" in short
                    and not any(x in short for x in
                                ("image", "tts", "embedding", "vision", "preview", "exp"))):
                names.append(short)
    except Exception as exc:  # noqa: BLE001
        log.info("Gemini model list failed (%s); using %s", exc, preferred)
        return preferred
    order = sorted(set(names), reverse=True)
    if user_set and preferred in order:
        order = [preferred] + [n for n in order if n != preferred]
    cached = _load_model_cache()
    if cached and cached in order:
        order = [cached] + [n for n in order if n != cached]
    for name in order:
        if not _allow_call(tick=True):
            break
        try:
            client.models.generate_content(
                model=name, contents=".",
                config=_gtypes.GenerateContentConfig(max_output_tokens=1))
            if name != preferred:
                log.info("Gemini model: %s (default %s unavailable, auto-selected)",
                         name, preferred)
            _save_model_cache(name)
            return name
        except Exception:  # noqa: BLE001 — try the next candidate
            continue
    log.info("no working Gemini flash model found; using %s", preferred)
    return preferred


try:
    from google import genai
    if _API_KEY:
        _CLIENT = genai.Client(api_key=_API_KEY)
        _MODEL_NAME = _pick_model(_CLIENT, _DEFAULT_MODEL, _USER_SET)
        if _MODEL_NAME != _DEFAULT_MODEL:
            log.info("Gemini model: %s (default %s unavailable, auto-selected)",
                     _MODEL_NAME, _DEFAULT_MODEL)
        _AVAILABLE = True
    else:
        log.info("GEMINI_API_KEY 未設定，LLM 摘要停用（使用樣板）。")
except ImportError:
    log.info("google-genai 未安裝，LLM 摘要停用。")
except Exception as exc:  # noqa: BLE001
    log.warning("Gemini 初始化失敗 (%s)，LLM 摘要停用。", exc)


def is_available():
    """True only if the SDK imported AND a key is configured."""
    return _AVAILABLE


def generate(prompt, max_tokens=600):
    """Run a single completion. Returns the text, or None on any failure.

    Retries once on a 429 (free-tier rate limit) after a short backoff.
    """
    if not _AVAILABLE:
        return None
    if not _allow_call(tick=True):
        return None
    from google.genai import types
    for attempt in range(2):
        try:
            resp = _CLIENT.models.generate_content(
                model=_MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=max_tokens, temperature=0.4,
                ),
            )
            return (resp.text or "").strip() or None
        except Exception as exc:  # noqa: BLE001
            if attempt == 0 and "429" in str(exc):
                import time as _t
                log.info("Gemini 429 限流，20 秒後重試一次。")
                _t.sleep(20)
                continue
            log.warning("Gemini 生成失敗 (%s)；退回樣板。", exc)
            return None
    return None


def _item_bullet(it, max_summary=200):
    """Format one news item as '- title — summary' (summary truncated).

    The RSS ``summary`` blurb is the part that actually carries context; using
    it (not just the headline) is what lets the model write a meaningful
    What/Why/So-What instead of guessing from titles alone.
    """
    title = (it.get("title") or "").strip()
    summary = (it.get("summary") or "").strip()
    if summary:
        summary = summary[:max_summary]
        return f"- {title} — {summary}" if title else f"- {summary}"
    return f"- {title}"


def summarize_news_what_why_sowhat(items, domain_label=""):
    """Turn a list of {title, summary} dicts into a What/Why/So-What digest.

    Returns a dict {what, why, so_what} of strings, or None to signal the
    caller to use its template fallback.
    """
    if not items or not _AVAILABLE:
        return None
    bullets = "\n".join(_item_bullet(it) for it in items[:6])
    prompt = (
        f"你是智庫級情報分析師。以下為「{domain_label}」領域今日快訊：\n{bullets}\n\n"
        "請用繁體中文，各以一到兩句產出三個欄位，嚴格用下列格式：\n"
        "WHAT: ...（事實概要）\n"
        "WHY: ...（脈絡與影響）\n"
        "SO_WHAT: ...（對台灣產業的啟示）"
    )
    text = generate(prompt)
    if not text:
        return None
    out = {"what": "", "why": "", "so_what": ""}
    for line in text.splitlines():
        low = line.strip()
        for key in out:
            if low.upper().startswith(key):
                v = low.split(":", 1)[-1].strip()
                out[key] = v[:60] + "…" if len(v) > 60 else v
    return out if out["what"] else None


def parse_topic_blocks(text, n):
    """Parse "[N] WHAT:/WHY:/SO_WHAT:" blocks out of an LLM reply.

    Tolerates markdown decoration (asterisks, backticks, headers, `>` quotes)
    and SO WHAT / SO_WHAT variants — flash-class models often add `**` bold
    even when told not to, which broke the earlier strict parser. Returns a
    list of length n (None where a block failed to parse), or None when
    nothing parsed at all.
    """
    import re as _re
    strip = "*_#`>~ \t"
    out = [None] * n
    idx, cur = None, None

    def flush():
        if cur is not None and cur["what"] and idx is not None and 0 <= idx < n:
            out[idx] = cur

    for raw in (text or "").splitlines():
        line = raw.strip().strip(strip).strip()
        if not line:
            continue
        up = line.upper()
        header = _re.match(r"^[\[(]?(\d{1,2})[\]\).:\-]*$", up)
        if header and not up.startswith(("WHAT", "WHY", "SO")):
            flush()
            i = int(header.group(1)) - 1
            idx, cur = (i, {"what": "", "why": "", "so_what": ""}) if 0 <= i < n else (None, None)
            continue
        if cur is None:
            continue
        key = up.replace(" ", "_")

        def _val(ln):
            v = ln.split(":", 1)[-1].strip().strip(strip)
            return v[:110] + "…" if len(v) > 110 else v
        if key.startswith("WHAT"):
            cur["what"] = _val(line)
        elif key.startswith("WHY"):
            cur["why"] = _val(line)
        elif key.startswith("SO"):
            cur["so_what"] = _val(line)
    flush()
    return out if any(out) else None


def summarize_topics_what_why_sowhat(topics, domain_label=""):
    """Batch N topics into N {what,why,so_what} dicts in a SINGLE Gemini call.

    ``topics`` = list of (org, focus, analysis). Returns a list aligned to the
    input (None where a block didn't parse). One call instead of N keeps the
    daily report within free-tier rate limits.
    """
    if not topics or not _AVAILABLE:
        return None
    lines = [f"[{i}] 來源：{org} / 焦點：{focus} / 摘要：{(analysis or '')[:200]}"
             for i, (org, focus, analysis) in enumerate(topics, 1)]
    prompt = (
        f"你是智庫級情報分析師。以下為「{domain_label}」領域的數則報告：\n"
        + "\n".join(lines) + "\n\n"
        "請用繁體中文，為「每一則」各產出 WHAT / WHY / SO_WHAT 三欄。"
        "每欄一到兩句、合計 60 字以內，需引用具體數字或機構名。\n"
        "嚴格依下列純文字格式（不要使用任何 Markdown 符號，不要 **、#、`）：\n"
        "[1]\nWHAT: ...（事實概要）\nWHY: ...（脈絡與影響）\nSO_WHAT: ...（對台灣產業的啟示）\n"
        "[2]\nWHAT: ...\nWHY: ...\nSO_WHAT: ...\n"
    )
    text = generate(prompt, max_tokens=250 + 320 * len(topics))
    if not text:
        return None
    return parse_topic_blocks(text, len(topics))
