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
_MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
_CLIENT = None
_AVAILABLE = False

try:
    from google import genai
    if _API_KEY:
        _CLIENT = genai.Client(api_key=_API_KEY)
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
    """Run a single completion. Returns the text, or None on any failure."""
    if not _AVAILABLE:
        return None
    try:
        from google.genai import types
        resp = _CLIENT.models.generate_content(
            model=_MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=max_tokens, temperature=0.4,
            ),
        )
        return (resp.text or "").strip() or None
    except Exception as exc:  # noqa: BLE001
        log.warning("Gemini 生成失敗 (%s)；退回樣板。", exc)
        return None


def summarize_news_what_why_sowhat(items, domain_label=""):
    """Turn a list of {title, summary} dicts into a What/Why/So-What digest.

    Returns a dict {what, why, so_what} of strings, or None to signal the
    caller to use its template fallback.
    """
    if not items or not _AVAILABLE:
        return None
    bullets = "\n".join(f"- {it.get('title','')}" for it in items[:6])
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
