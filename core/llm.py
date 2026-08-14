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
    for name in order:
        try:
            client.models.generate_content(
                model=name, contents=".",
                config=_gtypes.GenerateContentConfig(max_output_tokens=1))
            if name != preferred:
                log.info("Gemini model: %s (default %s unavailable, auto-selected)",
                         name, preferred)
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
                out[key] = low.split(":", 1)[-1].strip()
    return out if out["what"] else None


def summarize_topics_what_why_sowhat(topics, domain_label=""):
    """Batch N topics into N {what,why,so_what} dicts in a SINGLE Gemini call.

    ``topics`` = list of (org, focus, analysis). Returns a list aligned to the
    input (None where a block didn't parse). One call instead of N keeps the
    daily report within free-tier rate limits.
    """
    import re as _re
    if not topics or not _AVAILABLE:
        return None
    lines = [f"[{i}] 來源：{org} / 焦點：{focus} / 摘要：{(analysis or '')[:200]}"
             for i, (org, focus, analysis) in enumerate(topics, 1)]
    prompt = (
        f"你是智庫級情報分析師。以下為「{domain_label}」領域的數則報告：\n"
        + "\n".join(lines) + "\n\n"
        "請用繁體中文，為「每一則」各產出 WHAT / WHY / SO_WHAT 三欄（各一到兩句），"
        "嚴格依下列格式，[N] 對應輸入編號：\n"
        "[1]\nWHAT: ...（事實概要）\nWHY: ...（脈絡與影響）\nSO_WHAT: ...（對台灣產業的啟示）\n"
        "[2]\nWHAT: ...\nWHY: ...\nSO_WHAT: ...\n"
    )
    text = generate(prompt, max_tokens=200 + 250 * len(topics))
    if not text:
        return None
    out = [None] * len(topics)
    parts = _re.split(r"\n*\[(\d+)\]", text)
    for j in range(1, len(parts) - 1, 2):
        try:
            idx = int(parts[j]) - 1
        except ValueError:
            continue
        d = {"what": "", "why": "", "so_what": ""}
        for line in parts[j + 1].splitlines():
            low = line.strip()
            for key in d:
                if low.upper().startswith(key):
                    d[key] = low.split(":", 1)[-1].strip()
        if d["what"] and 0 <= idx < len(out):
            out[idx] = d
    return out if any(x for x in out) else None
