#!/usr/bin/env python3
"""Optional LLM layer (Google Gemini) for narrative enrichment.

Uses the current official ``google-genai`` SDK. Designed to degrade gracefully
at three levels so the pipeline runs identically with or without an LLM:

  1. ``GEMINI_API_KEY`` not set  -> functions return None (caller uses template)
  2. ``google-genai`` not installed -> same
  3. API call fails / times out / reply comes back empty -> same

CI sets the key; local runs without it exercise the no-LLM path.

Model: auto-picked flash variant (resolves to gemini-flash-lite-latest today).
Override with ``GEMINI_MODEL``.

THINKING-BUDGET LANDMINE (found 2026-08-31): flash-lite models cannot turn
thinking off (floor: 512 tokens) and thinking tokens are counted inside
``max_output_tokens``. Every call ceiling must exceed thinking floor + the
visible reply, or generate() returns None on every single run while CI stays
green — that is what silently erased the three-part briefs for weeks while
parser fixes chased the wrong cause. generate() therefore pins the lite
budget to 512 and warns (with finish_reason/thoughts count) on empty replies.
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


def _gen_configs(max_tokens, temperature):
    """GenerateContentConfig candidates, best first.

    Flash-lite can't disable thinking (floor 512) and dynamic thinking on a
    multi-block task can balloon past 1k tokens, all counted inside
    max_output_tokens. Pinning lite to its floor makes the visible reply's
    share deterministic; a plain config follows in case the pin is rejected
    (older SDK or a model whose budget semantics differ).
    """
    from google.genai import types
    base = dict(max_output_tokens=max_tokens, temperature=temperature)
    plain = types.GenerateContentConfig(**base)
    try:
        if "lite" in _MODEL_NAME.lower():
            pinned = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=512),
                **base)
            return [pinned, plain]
    except Exception:  # noqa: BLE001 — SDK without ThinkingConfig
        pass
    return [plain]


def _warn_empty(resp, max_tokens):
    """Say WHY a reply is empty — finish reason + thinking spend vs the cap."""
    try:
        cand = (resp.candidates or [None])[0]
        fr = getattr(cand, "finish_reason", None)
        um = getattr(resp, "usage_metadata", None)
        thoughts = getattr(um, "thoughts_token_count", None)
        log.warning("Gemini 回應為空（finish_reason=%s, thoughts=%s tokens, "
                    "max_output_tokens=%d）— 思考預算吃掉上限，請調高 max_tokens。",
                    fr, thoughts, max_tokens)
    except Exception:  # noqa: BLE001
        log.warning("Gemini 回應為空（max_output_tokens=%d）。", max_tokens)


def generate(prompt, max_tokens=1600):
    """Run a single completion. Returns the text, or None on any failure.

    Retries once on a 429 (free-tier rate limit) after a short backoff.
    ``max_tokens`` must cover thinking (512 floor on flash-lite) plus the
    visible reply — see the module docstring's thinking-budget landmine.
    """
    if not _AVAILABLE:
        return None
    if not _allow_call(tick=True):
        return None
    configs = _gen_configs(max_tokens, 0.4)
    last = configs[-1]
    for config in configs:
        for attempt in range(2):
            try:
                resp = _CLIENT.models.generate_content(
                    model=_MODEL_NAME,
                    contents=prompt,
                    config=config,
                )
                try:
                    text = (resp.text or "").strip() or None
                except ValueError:  # thought-only candidate: no text part
                    text = None
                if text is None:
                    _warn_empty(resp, max_tokens)
                return text
            except Exception as exc:  # noqa: BLE001
                if attempt == 0 and "429" in str(exc):
                    import time as _t
                    log.info("Gemini 429 限流，20 秒後重試一次。")
                    _t.sleep(20)
                    continue
                if config is not last and "thinking" in str(exc).lower():
                    log.info("thinking 設定被拒（%s）；改用未釘選設定重試。", exc)
                    break  # fall through to the plain config
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


def summarize_news_given_when_then(items, domain_label=""):
    """Turn a list of {title, summary} dicts into a GIVEN/WHEN/THEN digest.

    Returns a dict {given, when, then} of strings, or None to signal the
    caller to use its template fallback.
    """
    if not items or not _AVAILABLE:
        return None
    bullets = "\n".join(_item_bullet(it) for it in items[:6])
    prompt = (
        f"你是智庫級情報分析師。以下為「{domain_label}」領域今日快訊：\n{bullets}\n\n"
        "請用繁體中文，各以一到兩句產出三個欄位，嚴格用下列格式：\n"
        "GIVEN: ...（前提態勢：既有格局與背景）\n"
        "WHEN: ...（關鍵觸發事件：今日最重要的變化）\n"
        "THEN: ...（後續影響：對台灣產業的推演與啟示）"
    )
    text = generate(prompt)
    if not text:
        return None
    # Tolerant parse (same lesson as parse_topic_blocks): flash-class models
    # decorate replies with **bold**, numbering prefixes, or the full-width
    # colon even when told not to. The old strict prefix match threw the whole
    # digest away on the first stray character — and the Global report silently
    # lost its three-part brief while CI stayed green (2026-08-28).
    import re as _re
    out = {"given": "", "when": "", "then": ""}
    deco = "*_#`>~ \t·•"
    for raw in text.splitlines():
        line = raw.strip().strip(deco).strip()
        if not line:
            continue
        up = _re.sub(r"^[\[\(（]?\d{1,2}[\]\).、．:：\-]*\s*", "", line.upper())
        up = up.replace(" ", "_")
        for key in out:
            if up.startswith(key.upper()):
                v = _re.split(r"[:：]", line, maxsplit=1)[-1].strip().strip(deco).strip()
                if v:
                    out[key] = v[:60] + "…" if len(v) > 60 else v
    if not out["given"]:
        log.info("digest reply unparsed; head: %.300s", text.replace("\n", " | "))
    return out if out["given"] else None


def parse_topic_blocks(text, n):
    """Parse "[N] GIVEN:/WHEN:/THEN:" blocks out of an LLM reply.

    Tolerates markdown decoration (asterisks, backticks, headers, `>` quotes)
    and full-width colons — flash-class models often add `**` bold even when
    told not to, which broke the earlier strict parser. Returns a list of
    length n (None where a block failed to parse), or None when nothing
    parsed at all.
    """
    import re as _re
    strip = "*_#`>~ \t"
    out = [None] * n
    idx, cur = None, None

    def flush():
        if cur is not None and cur["given"] and idx is not None and 0 <= idx < n:
            out[idx] = cur

    for raw in (text or "").splitlines():
        line = raw.strip().strip(strip).strip()
        if not line:
            continue
        up = line.upper()
        header = _re.match(r"^[\[(]?(\d{1,2})[\]\).:\-]*$", up)
        if header and not up.startswith(("GIVEN", "WHEN", "THEN")):
            flush()
            i = int(header.group(1)) - 1
            idx, cur = (i, {"given": "", "when": "", "then": ""}) if 0 <= i < n else (None, None)
            continue
        if cur is None:
            continue
        key = up.replace(" ", "_")

        def _val(ln):
            v = _re.split(r"[:：]", ln, maxsplit=1)[-1].strip().strip(strip)
            return v[:110] + "…" if len(v) > 110 else v
        if key.startswith("GIVEN"):
            cur["given"] = _val(line)
        elif key.startswith("WHEN"):
            cur["when"] = _val(line)
        elif key.startswith("THEN"):
            cur["then"] = _val(line)
    flush()
    return out if any(out) else None


def summarize_topics_given_when_then(topics, domain_label=""):
    """Batch N topics into N {given,when,then} dicts in a SINGLE Gemini call.

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
        "請用繁體中文，為「每一則」各產出 GIVEN / WHEN / THEN 三欄。"
        "GIVEN 是該則新聞的背景脈絡、WHEN 是觸發事件本身、THEN 是後續影響"
        "（聚焦對台灣產業）。每欄一句、40 字以內，需引用具體數字或機構名。\n"
        "嚴格依下列純文字格式（不要使用任何 Markdown 符號，不要 **、#、`）：\n"
        "[1]\nGIVEN: ...（背景脈絡）\nWHEN: ...（觸發事件）\nTHEN: ...（後續影響）\n"
        "[2]\nGIVEN: ...\nWHEN: ...\nTHEN: ...\n"
    )
    # 800 thinking headroom (lite floor 512) + ~320 tokens per topic block.
    text = generate(prompt, max_tokens=800 + 320 * len(topics))
    if not text:
        return None
    parsed = parse_topic_blocks(text, len(topics))
    n_ok = sum(1 for x in parsed or [] if x)
    log.info("GWT parsed %d/%d topics", n_ok, len(topics))
    if not n_ok:
        log.info("unparsed reply head: %.300s", text.replace("\n", " | "))
    return parsed
