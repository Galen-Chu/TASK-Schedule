"""Cross-domain daily briefing — the (G) route item.

Fuses two independent signal streams into one analyst-style lead card:

  * Financial quantitative signals (signal score/rating, VIX, Fear & Greed,
    treasury 10Y + 2s10s spread, DXY/USDTWD, gold, BTC, NFP when fresh)
  * Global retrieval-corpus trends (week-over-week domain heat, trending
    keywords, top market headlines)

Output is a {what, why, so_what} dict rendered as the lead card of the
Financial report's Market Intelligence page (P1). Follows the house rule:
without GEMINI_API_KEY (or on any API/parse failure) every function
returns None and the caller simply omits the card — CI runs identically.
"""
import logging

log = logging.getLogger("cross_domain")

_DOMAIN_ZH = {
    "geopolitics": "地緣政治",
    "macro": "總經金融",
    "it_ai": "AI/半導體",
    "biotech": "生技醫療",
    "hardware": "硬體能源",
    "aerospace": "航太量子",
    "spiritual": "靈性",
}


def _fmt(v, suffix=""):
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.2f}{suffix}"
    return f"{v}{suffix}"


def signal_lines(fin):
    """Compress the financial data dict into a few short prompt lines."""
    out = []
    pairs = [
        ("綜合訊號", f'{fin.get("signal_score", "?")}/100（{fin.get("signal_rating", "")}）'),
        ("VIX 恐慌指數", _fmt(fin.get("vix"))),
        ("恐貪指數", _fmt(fin.get("fear_and_greed"))),
        ("美債 10Y", _fmt(fin.get("treasury_10y"), "%")),
        ("2Y10Y 利差", _fmt(fin.get("spread_10y2y"), "pp")),
        ("美元指數 DXY", _fmt(fin.get("dxy"))),
        ("USD/TWD", _fmt(fin.get("usdtwd"))),
        ("黃金", _fmt(fin.get("gold"), " USD")),
        ("比特幣", _fmt(fin.get("btc"), " USD")),
    ]
    nfp = (fin.get("macro") or {}).get("nfp") or {}
    if nfp.get("value") is not None:
        pairs.append(("非農就業 NFP",
                      f'{nfp.get("value")} 千人（{nfp.get("period_name", "")} {nfp.get("year", "")}）'))
    for label, val in pairs:
        if val and val != "None":
            out.append(f"- {label}：{val}")
    return out


def trend_lines(trends):
    """Compress domain_trends/trending_keywords output into prompt lines."""
    out = []
    domains = (trends or {}).get("domains") or {}
    ranked = sorted(domains.items(),
                    key=lambda kv: abs(kv[1].get("change_pct") or 0), reverse=True)
    for dom, st in ranked[:4]:
        zh = _DOMAIN_ZH.get(dom, dom)
        chg = st.get("change_pct")
        if chg is None:
            continue
        arrow = "↑" if chg > 0 else "↓" if chg < 0 else "→"
        out.append(f"- {zh}聲量週比 {arrow}{abs(chg):.0f}%"
                   f"（本週 {st.get('this_week', 0)} 則 / 上週 {st.get('last_week', 0)} 則）")
    for k in (trends or {}).get("keywords") or []:
        kw, hits, chg = k["keyword"], k.get("this_week", 0), k.get("change", 0)
        if hits >= 3:
            out.append(f"- 發燒詞：「{kw}」本週 {hits} 則（+{chg}）")
    return out


def parse_what_why_sowhat(text):
    """Parse a WHAT/WHY/SO_WHAT reply into a dict, tolerating markdown
    decoration (*, `, #, >) the same way llm.parse_topic_blocks does."""
    import re as _re
    strip = "*_#`>~ \t"
    out = {"what": "", "why": "", "so_what": ""}
    for raw in (text or "").splitlines():
        line = raw.strip().strip(strip).strip()
        if not line:
            continue
        key = line.upper().replace(" ", "_")
        if key.startswith("WHAT"):
            field = "what"
        elif key.startswith("WHY"):
            field = "why"
        elif key.startswith("SO"):
            field = "so_what"
        else:
            continue
        v = line.split(":", 1)[-1].strip().strip(strip)
        out[field] = v[:140] + "…" if len(v) > 140 else v
    return out if out["what"] else None


def daily_briefing(fin, trends, headlines=None):
    """One Gemini call → {what, why, so_what}, or None to skip the card."""
    from core import llm
    if not llm.is_available():
        return None

    lines = ["【今日量化訊號】"] + signal_lines(fin)
    tl = trend_lines(trends)
    if tl:
        lines += ["", "【全球情報語料趨勢（本週 vs 上週）】"] + tl
    hl = [(h.get("title") or "").strip() for h in (headlines or [])[:3]]
    hl = [h for h in hl if h]
    if hl:
        lines += ["", "今日頭條："] + [f"- {h[:90]}" for h in hl]

    prompt = (
        "你是跨域情報分析師，為台灣投資人撰寫每日報告的頭版摘要。\n"
        "請把「量化市場訊號」與「全球新聞語料趨勢」關聯起來——"
        "找出彼此印證或矛盾之處，不要只是複述數字。\n\n"
        + "\n".join(lines) + "\n\n"
        "請用繁體中文，各一到兩句產生三個欄位，嚴格用下列純文字格式"
        "（不要 Markdown 符號）：\n"
        "WHAT: ...（今日市場與情報的全貌，一句話）\n"
        "WHY: ...（訊號與新聞趨勢的關聯與解讀）\n"
        "SO_WHAT: ...（對台灣投資人的具體啟示）"
    )
    text = llm.generate(prompt, max_tokens=420)
    if not text:
        return None
    parsed = parse_what_why_sowhat(text)
    if not parsed:
        log.info("cross-domain briefing unparsable: %.200s", text.replace("\n", " | "))
    return parsed
