#!/usr/bin/env python3
"""Financial Intelligence — PDF report generator (5-page A4).

Refactored to build on :mod:`core.pdf_engine` / :mod:`core.design_tokens`:
font registration, the dual-font ``en()`` helper, header/footer and the master
palette all come from the shared core. Only the Financial-specific content
(market section palette, the dashboard layout and the editorial analysis
tables) lives here.

The headline numbers (rating banner, the four KPI cards and the five-market
monitor) are wired to the ``data`` dict so a real data feed drives the report;
the deeper analysis tables remain editorial commentary.
"""
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from reportlab.lib import colors
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak

from core import design_tokens as T
from core.fonts import FONT_CJK
from core.pdf_engine import en, standard_styles, make_title_row, footer_factory, new_doc

# ---- Financial section palette (Typography Guide brand family) -------------
COLOR_TW_STOCK = T.CORAL    # 台股 — 活力橘紅
COLOR_US_STOCK = T.TEAL     # 美股 — 科技青
COLOR_BOND     = T.AMBER    # 債券 — 暖琥珀
COLOR_FOREX    = T.SAGE     # 外匯 — 抹茶綠
COLOR_CRYPTO   = T.INK      # 商品/加密 — 墨藍黑

DISCLAIMER = "本報告為自動化數據監控測試版，僅供量化指標研究與策略測試參考，不構成任何投資建議。"

_PAGE_TOTAL = 7


def calculate_signal_score(data):
    """Quantitative signal score (0-100) per the documented model.

    Base 50; +15 if the TW market-wide margin balance (lots) is under the
    ceiling (default 9,000,000 — mid-market calibration, overridable via the
    ``tw_margin_ceiling`` data key); +10 if VIX > 25; +10 if the 10Y-2Y spread
    is positive (curve un-inverted); foreign-futures OI band.
    Replaces the old hardcoded ``72`` so the headline always matches the model.
    """
    score = 50
    ceiling = data.get("tw_margin_ceiling", 9_000_000)
    if data.get("tw_margin_balance", ceiling) < ceiling:
        score += 15
    if data.get("vix", 0) > 25:
        score += 10
    if data.get("spread_10y2y", 0) > 0:
        score += 10
    oi = data.get("futures_net_oi", 0)
    if oi > -10000:
        score += 5
    elif oi < -30000:
        score -= 10
    return max(0, min(100, score))


def rating_from_score(score):
    if score >= 65:
        return "🟢 偏多進場 / 尋找超跌加碼點"
    if score >= 45:
        return "🟡 中性觀望 / 等待訊號確認"
    return "🔴 偏空減碼 / 提高現金比重"


def _market_verdicts(data):
    """Per-market trading verdicts from live data — rule-based, transparent.

    Thresholds mirror the ones already documented in the detail tables and
    calculate_signal_score, so the banner can never contradict the model.
    Returns {key: (name, light, headline, reason)} where light is one of
    buy / hold / sell / neutral ("neutral" when the rule's input is missing).
    """
    out = {}

    twm = data.get("tw_margin_balance")
    ceiling = data.get("tw_margin_ceiling", 9_000_000)
    if twm is None:
        out["tw"] = ("台股", "neutral", "數據待補", "融資餘額未取得")
    elif twm < ceiling:
        out["tw"] = ("台股", "buy", "分批進場",
                     f"融資 {twm/10000:.0f} 萬張 < 門檻 {ceiling/10000:.0f} 萬張")
    elif twm < ceiling * 1.05:
        out["tw"] = ("台股", "hold", "觀望",
                     f"融資 {twm/10000:.0f} 萬張貼近門檻，槓桿偏熱")
    else:
        out["tw"] = ("台股", "sell", "減碼",
                     f"融資 {twm/10000:.0f} 萬張顯著超越門檻，斷頭風險升")

    vix = data.get("vix")
    if vix is None:
        out["us"] = ("美股", "neutral", "數據待補", "VIX 未取得")
    elif vix > 25:
        out["us"] = ("美股", "buy", "恐慌區・中長線買點", f"VIX {vix} > 25，情緒極端通常為買點")
    elif vix >= 15:
        out["us"] = ("美股", "buy", "分批進場", f"VIX {vix} 中性偏低，波動可控")
    else:
        out["us"] = ("美股", "hold", "低波動觀望", f"VIX {vix} < 15，無恐慌財")

    spread = data.get("spread_10y2y")
    if spread is None:
        out["bond"] = ("債券", "neutral", "數據待補", "利差未取得")
    elif spread > 0:
        out["bond"] = ("債券", "buy", "鎖定高票息", f"10Y-2Y 利差 {spread:+.2f}pp，曲線未倒掛")
    elif spread > -0.5:
        out["bond"] = ("債券", "hold", "倒掛觀察", f"10Y-2Y 利差 {spread:+.2f}pp 輕度倒掛")
    else:
        out["bond"] = ("債券", "sell", "深度倒掛警戒", f"10Y-2Y 利差 {spread:+.2f}pp 深度倒掛")

    dxy = data.get("dxy")
    if dxy is None:
        out["forex"] = ("外匯", "neutral", "數據待補", "DXY 未取得")
    elif dxy >= 104.5:
        out["forex"] = ("外匯", "hold", "美元強勢", f"DXY {dxy} 逼近阻力 104.5，新興市場承壓")
    elif dxy <= 101:
        out["forex"] = ("外匯", "buy", "美元轉弱", f"DXY {dxy} 位於支撐 101 之下，利多風險性資產")
    else:
        out["forex"] = ("外匯", "hold", "區間震盪", f"DXY {dxy} 於 101–104.5 區間內")

    fg = data.get("fear_and_greed")
    if fg is None:
        out["cmdty"] = ("商品", "neutral", "數據待補", "恐貪指數未取得")
        out["crypto"] = ("加密", "neutral", "數據待補", "恐貪指數未取得")
    elif fg <= 25:
        out["cmdty"] = ("商品", "buy", "極端恐慌・逆向布局", f"恐貪指數 {fg} 落於極度恐慌區")
        out["crypto"] = ("加密", "buy", "極端恐慌・逆向布局", f"恐貪指數 {fg} 落於極度恐慌區")
    elif fg >= 75:
        out["cmdty"] = ("商品", "hold", "極端貪婪・逢高減碼", f"恐貪指數 {fg} 落於極度貪婪區")
        out["crypto"] = ("加密", "hold", "極端貪婪・逢高減碼", f"恐貪指數 {fg} 落於極度貪婪區")
    else:
        out["cmdty"] = ("商品", "hold", "中性區間", f"恐貪指數 {fg} 位於中性區")
        out["crypto"] = ("加密", "hold", "中性區間", f"恐貪指數 {fg} 位於中性區")

    score = calculate_signal_score(data)
    light = "buy" if score >= 65 else ("hold" if score >= 45 else "sell")
    out["overall"] = ("綜合評級", light, rating_from_score(score).split(" ", 1)[1],
                      f"Signal Score {score}/100（量化模型綜合評分）")
    return out


_VERDICT_STYLE = {
    "buy":     (T.SIGNAL_BUY, T.SIGNAL_BUY_TINT),
    "hold":    (T.SIGNAL_HOLD, T.SIGNAL_HOLD_TINT),
    "sell":    (T.SIGNAL_SELL, T.SIGNAL_SELL_TINT),
    "neutral": (T.TEXT_MUTED, colors.HexColor("#F3F4F6")),
}


def _verdict_banner(verdicts, s):
    """One-row colored trading-verdict strip for a report page.

    ● uses the signal colors (the 🟢 emoji renders as a .notdef box in the
    bundled CJK fonts, so lights are drawn as colored ● glyphs instead).
    Returns a list of flowables to extend into the story.
    """
    from reportlab.lib.styles import ParagraphStyle
    cells = []
    for name, light, headline, reason in verdicts:
        fg, bg = _VERDICT_STYLE[light]
        fg_hex = "#" + fg.hexval()[2:]
        cells.append(Paragraph(
            en(f'<font color="{fg_hex}"><b>●</b></font> '
               f"<b>{name}｜{headline}</b> — {reason}"),
            ParagraphStyle("vb", fontName=FONT_CJK, fontSize=8.2,
                           leading=11.5, textColor=T.TEXT_BODY)))
    t = Table([cells], colWidths=[T.PRINTABLE_WIDTH / len(cells)] * len(cells))
    style = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for i, (_, light, _, _) in enumerate(verdicts):
        fg, bg = _VERDICT_STYLE[light]
        style.append(("BACKGROUND", (i, 0), (i, 0), bg))
        style.append(("LINEABOVE", (i, 0), (i, 0), 2, fg))
    t.setStyle(TableStyle(style))
    return [t, Spacer(1, 8)]


def _g(data, key, default):
    return (data or {}).get(key, default)


_MON = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


def _yoy_series(history):
    """YoY % series from index levels; input is BLS newest-first order.

    Skips non-numeric entries (BLS uses '-' for missing months) and matches
    each point against the same calendar month a year earlier, so gaps don't
    shift the comparison. Returns (values, labels) oldest→newest with labels
    like "26/08", or None when fewer than 6 points resolve.
    """
    try:
        pts = {}
        for x in history or []:
            v = str(x.get("value", ""))
            if not v.replace(".", "").isdigit():
                continue
            m = _MON.get(str(x.get("period_name", ""))[:3])
            y = int(x.get("year"))
            if m:
                pts[(y, m)] = float(v)
        vals, labels = [], []
        for (y, m) in sorted(pts):
            prev = pts.get((y - 1, m))
            if prev:
                vals.append(round((pts[(y, m)] / prev - 1) * 100, 2))
                labels.append(f"{y % 100:02d}/{m:02d}")
        return (vals, labels) if len(vals) >= 6 else None
    except (ValueError, TypeError):
        return None


def _nice_ticks(lo, hi, n=5):
    """~n round tick values spanning [lo, hi] (1/2/2.5/5 × 10^k steps)."""
    import math
    if hi <= lo:
        hi = lo + 1.0
    raw = (hi - lo) / (n - 1)
    mag = 10 ** math.floor(math.log10(raw))
    step = 10 * mag
    for m in (1, 2, 2.5, 5, 10):
        if m * mag >= raw:
            step = m * mag
            break
    start = math.floor(lo / step) * step
    end = math.ceil(hi / step) * step
    out, v = [], start
    while v <= end + step * 0.01:
        out.append(round(v, 6))
        v += step
    return out


def _nfp_monthly_changes(nfp_hist):
    """(diffs, labels) oldest→newest of month-over-month employment change.

    Input is BLS newest-first LEVEL history (CES0000000001, thousands) — the
    chart must show monthly additions (就業動能), not the near-flat ~158M
    level. 'Annual' (M13) rows and non-numeric values are skipped.
    """
    pts = []
    for x in nfp_hist or []:
        v = str(x.get("value", ""))
        period = str(x.get("period_name", ""))
        if period.lower().startswith("annual"):
            continue
        if not v.replace(".", "").replace("-", "").isdigit():
            continue
        pts.append((float(v), f"{period[:3]} {str(x.get('year', ''))[-2:]}"))
    pts.reverse()  # oldest → newest
    diffs = [round(pts[i][0] - pts[i - 1][0], 1) for i in range(1, len(pts))]
    labels = [p[1] for p in pts[1:]]
    return (diffs, labels) if len(diffs) >= 6 else None


def _line_chart(labels, series, height=175, y_unit="", y_fmt="{:.2f}", x_unit=""):
    """Brand-styled line chart with readable axis scales and unit labels.

    The value axis gets explicit round ticks (the old auto-range often drew
    only 3); units are appended to ticks when short (%, 千人) and always
    annotated at the axis top, with the category-axis unit bottom-right.
    """
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.graphics.charts.linecharts import HorizontalLineChart
    width = T.PRINTABLE_WIDTH
    d = Drawing(width, height)
    ch = HorizontalLineChart()
    ch.x, ch.y = 44, 30
    ch.width, ch.height = width - 66, height - 60
    ch.data = series
    ch.categoryAxis.categoryNames = labels
    ch.categoryAxis.labels.fontName = FONT_CJK
    ch.categoryAxis.labels.fontSize = 7
    ch.valueAxis.labels.fontName = FONT_CJK
    ch.valueAxis.labels.fontSize = 7
    allv = [v for s in series for v in s]
    pad = max(0.15, (max(allv) - min(allv)) * 0.15)
    ticks = _nice_ticks(min(allv) - pad, max(allv) + pad, 5)
    ch.valueAxis.valueMin, ch.valueAxis.valueMax = ticks[0], ticks[-1]
    ch.valueAxis.valueSteps = ticks
    tick_unit = y_unit if len(y_unit) <= 3 else ""
    ch.valueAxis.labelTextFormat = (lambda v: y_fmt.format(v) + tick_unit)
    ch.joinedLines = 1
    for i, c in enumerate([T.TEAL, T.AMBER]):
        if i < len(ch.lines):
            ch.lines[i].strokeColor = c
            ch.lines[i].strokeWidth = 1.4
    d.add(ch)
    if y_unit:
        d.add(String(2, height - 10, f"單位：{y_unit}", fontName=FONT_CJK,
                     fontSize=7, fillColor=T.TEXT_MUTED))
    if x_unit:
        d.add(String(width - 4, 8, f"（{x_unit}）", fontName=FONT_CJK,
                     fontSize=7, fillColor=T.TEXT_MUTED, textAnchor="end"))
    return d


def generate_daily_pdf(filename, data=None, date_str=None):
    """Build the 5-page Financial PDF. Returns ``filename``."""
    data = data or {}
    date_str = date_str or data.get("date") or "2026-08-10"
    score = calculate_signal_score(data)
    rating = rating_from_score(score)

    twm   = _g(data, "tw_margin_balance", 8970000)
    tws   = _g(data, "tw_short_balance", 214000)
    oi    = _g(data, "futures_net_oi", -18500)
    vix   = _g(data, "vix", 28.4)
    fg    = _g(data, "fear_and_greed", 24)
    t10   = _g(data, "treasury_10y", 3.85)
    t2    = _g(data, "treasury_2y", 3.73)
    spread= _g(data, "spread_10y2y", 0.12)
    dxy   = _g(data, "dxy", 102.4)
    twd   = _g(data, "usdtwd", 32.15)
    gold  = _g(data, "gold", 2450)
    btc   = _g(data, "btc", 58500)

    s = standard_styles()
    story = []

    story.extend(make_title_row(
        "每日投資趨勢報告",
        "市場情報速讀 ＋ 台股融資餘額・美股 VIX・美債殖利率・外匯・商品與加密",
        date_str, T.GOLD, s, eyebrow_text="Financial Intelligence",
    ))

    # ======================= P1a — Market Intelligence (news cards) =======
    market_intel = data.get("market_intel") or []
    if market_intel:
        import re as _re
        from html import unescape as _html_unescape
        from urllib.parse import urlparse as _urlparse
        from core.fonts import FONT_CJK as _FONT_CJK
        from reportlab.lib.styles import ParagraphStyle as _PS

        _tag_re = _re.compile(r"<[^>]+>")
        _fin_src = {
            "finance.yahoo.com": "YAHOO FINANCE",
            "feeds.content.dowjones.io": "MARKETWATCH",
            "www.cnbc.com": "CNBC",
            "search.cnbc.com": "CNBC",
            "www.ft.com": "FINANCIAL TIMES",
            "seekingalpha.com": "SEEKING ALPHA",
            "feeds.bbci.co.uk": "BBC",
            "www.reuters.com": "REUTERS",
        }

        def _fsrc(url):
            try:
                nl = _urlparse(url).netloc.lower()
            except Exception:
                return "RSS"
            return _fin_src.get(nl, nl.split(".")[0].upper() if nl else "RSS")

        def _fclean(text):
            if not text:
                return ""
            return _re.sub(r"\s+", " ", _tag_re.sub(" ", text)).strip()

        def _ftime(item):
            pub = item.get("published", "")
            if pub:
                try:
                    from email.utils import parsedate_to_datetime as _pdt
                    import datetime as _dt
                    dt = _pdt(pub)
                    _tz = _dt.timezone(_dt.timedelta(hours=8))
                    return dt.astimezone(_tz).strftime("%m-%d %H:%M")
                except Exception:
                    pass
            return (item.get("fetched_at", "") or "")[:10] or "—"

        # (G) Cross-domain briefing — analyst lead card fusing this report's
        # quantitative signals with the shared corpus' weekly trends. Only
        # present when GEMINI_API_KEY produced one; CI omits it entirely.
        briefing = data.get("cross_domain_briefing")
        if briefing:
            from core.design_tokens import RAMP_TEAL
            story.append(Paragraph(en("<b>🧭 今日情報摘要（Cross-Domain Briefing）</b>"), s["h1"]))
            bf_label = _PS("bf_label", fontName=_FONT_CJK, fontSize=8.0,
                           leading=10.5, textColor=T.TEAL)
            bf_body = _PS("bf_body", fontName=_FONT_CJK, fontSize=8.6,
                          leading=12.0, textColor=T.TEXT_BODY)
            bf_rows = [
                ("WHAT · 市場全貌", briefing.get("what", "")),
                ("WHY · 訊號×趨勢", briefing.get("why", "")),
                ("SO WHAT · 投資啟示", briefing.get("so_what", "")),
            ]
            bf_table = Table(
                [[Paragraph(en(f"<b>{lab}</b>"), bf_label),
                  Paragraph(en(txt), bf_body)] for lab, txt in bf_rows if txt],
                colWidths=[110, T.PRINTABLE_WIDTH - 16 - 110])
            bf_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(RAMP_TEAL[0])),
                ("LINEBEFORE", (0, 0), (0, -1), 3, T.TEAL),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            bf_card = Table([[bf_table]], colWidths=[T.PRINTABLE_WIDTH])
            bf_card.setStyle(TableStyle([
                ("BOX", (0, 0), (-1, -1), 0.5, T.BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.append(bf_card)
            story.append(Paragraph(en("<i>🤖 AI 生成：量化訊號 × 語料趨勢關聯（Gemini）</i>"),
                                   _PS("bf_note", fontName=_FONT_CJK, fontSize=7.5,
                                       leading=10, textColor=T.TEXT_MUTED, alignment=2)))
            story.append(Spacer(1, 4))

        story.append(Paragraph(en("<b>📰 市場情報速讀（Market Intelligence）</b>"), s["h1"]))
        card_body = _PS("fmi_body", fontName=_FONT_CJK, fontSize=8.0,
                         leading=10.0, textColor=T.TEXT_BODY)
        card_meta = _PS("fmi_meta", fontName=_FONT_CJK, fontSize=7.8,
                          leading=10, textColor=T.TEXT_MUTED, alignment=2)
        card_title = _PS("fmi_title", fontName=_FONT_CJK, fontSize=9.2,
                           leading=12.0, textColor=T.CORAL, spaceBefore=1, spaceAfter=1)

        for item in market_intel[:5]:
            org = _fsrc(item.get("source", ""))
            focus = _fclean(item.get("title", ""))[:80]
            when = _ftime(item)
            summary = _fclean(item.get("summary", ""))[:200] or focus
            link = item.get("link", "")
            inner = T.PRINTABLE_WIDTH - 16
            safe_link = (link or "").replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
            badge_html = (f'<a href="{safe_link}" color="#FFFFFF"><u><b>{org}</b></u></a>'
                          if link else f"<b>{org}</b>")
            badge = Table(
                [[Paragraph(badge_html,
                             _PS("fmi_badge", fontName=_FONT_CJK, fontSize=8.2,
                                 leading=10, textColor=T.WHITE))]],
                colWidths=[inner - 140])
            badge.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), T.CORAL),
                ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            hdr = Table([[badge, Paragraph(en(f"🕒 {when}"), card_meta)],
                          [Paragraph(en(f"<b>{focus}</b>"), card_title), ""]],
                         colWidths=[inner - 140, 140])
            hdr.setStyle(TableStyle([
                ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#FDE7E1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("SPAN", (0, 1), (1, 1)),
                ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, 0), 0), ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
                ("TOPPADDING", (0, 1), (-1, 1), 2),
            ]))
            mi_card = Table([[hdr], [Paragraph(en(summary), card_body)]],
                             colWidths=[T.PRINTABLE_WIDTH])
            mi_card.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FDE7E1")),
                ("BOX", (0, 0), (-1, -1), 0.5, T.BORDER),
                ("LINEBEFORE", (0, 0), (0, -1), 3, T.CORAL),
                ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))
            story.append(mi_card)
            story.append(Spacer(1, 3))

        story.append(Spacer(1, 4))
        story.append(Paragraph(en(f"<i>📡 {min(len(market_intel), 5)} 則即時金融新聞（近 3 日）</i>"),
                                _PS("fmi_note", fontName=_FONT_CJK, fontSize=7.5,
                                    leading=10, textColor=T.TEXT_MUTED, alignment=2)))
        story.append(PageBreak())

    # ======================= P2 — Signal Summary + KPI =====================
    # Standard page header like every other page (the old dark-navy rating
    # banner was a P1-era leftover — the only page without a title row).
    story.extend(make_title_row("今日市場總覽與訊號",
        "量化評級・關鍵指標・五大市場監控｜資料：TWSE・Yahoo Finance・美國財政部",
        date_str, T.NAVY, s, eyebrow_text="Financial Intelligence"))

    # Rating hero card — same visual family as the verdict banners:
    # signal-color left bar on the light tint, rating text colored by light.
    _light = "buy" if score >= 65 else ("hold" if score >= 45 else "sell")
    _rfg, _rbg = _VERDICT_STYLE[_light]
    _rfg_hex = "#" + _rfg.hexval()[2:]
    rating_stripped = rating.split(" ", 1)[1] if " " in rating else rating
    hero_rows = [
        [Paragraph(en("<b>【本日全球資產綜合評級】</b>"),
                   ParagraphStyle_local("RHead", 10.5, T.INK)),
         Paragraph(en(f'<font color="{_rfg_hex}"><b>{rating_stripped}'
                      f"　Signal Score {score}/100</b></font>"),
                   ParagraphStyle_local("RBody", 10.5, _rfg, align=2))],
    ]
    t_rating = Table(hero_rows, colWidths=[200, T.PRINTABLE_WIDTH - 200])
    t_rating.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), _rbg),
        ('BOX', (0, 0), (-1, -1), 0.5, T.BORDER),
        ('LINEBEFORE', (0, 0), (0, -1), 4, _rfg),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t_rating)

    # Decision summary as its own body card (was crammed into the banner).
    summary_card = Table([[Paragraph(en(
        f"<b>核心決策摘要：</b>台股融資餘額 {twm/10000:.1f} 萬張，美股 VIX {vix}，"
        f"美債 10Y-2Y 利差 {'+' if spread >= 0 else ''}{spread}%。"
        "量化模型綜合評估當前資產配置之風險報酬比。"),
        ParagraphStyle_local("RDesc", 9, T.TEXT_BODY, leading=13))]],
        colWidths=[T.PRINTABLE_WIDTH])
    summary_card.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), T.BG_CARD),
        ('BOX', (0, 0), (-1, -1), 0.5, T.BORDER),
        ('PADDING', (0, 0), (-1, -1), 7),
    ]))
    story.append(summary_card)
    story.append(Spacer(1, 8))

    story.append(Paragraph(en("關鍵進出場數據指標高亮 (Key Decision Metrics)"), s["h1"]))

    def kpi_card(title, value_html, foot):
        card = [
            [Paragraph(en(f"<b>{title}</b>"), s["card_title"])],
            [Paragraph(en(value_html, bold=True), s["body"])],
            [Paragraph(en(foot), s["body"])],
        ]
        return card

    cards = [
        (COLOR_TW_STOCK, kpi_card(
            "全市場融資餘額（TWSE 即時）",
            f"<font color='#EF6F53' size=13><b>{twm/10000:.1f} 萬張</b></font> <font color='#2E8B4F'><b>(低於門檻 900 萬張)</b></font>",
            f"融券餘額: {tws/10000:.1f} 萬張 | 來源: MI_MARGN 加總<br/>數值每日即時重抓，門檻可日後校準。")),
        (COLOR_US_STOCK, kpi_card(
            "外資台指期淨未平倉",
            f"<font color='#0E7C86' size=13><b>{oi:,} 口</b></font> <font color='#2E8B4F'><b>(空單大幅回補)</b></font>",
            "警戒線: -30,000 口<br/>空單單週回補 8,000 口，顯示期貨避險賣壓衰竭。")),
        (COLOR_BOND, kpi_card(
            "美股 VIX &amp; 恐懼貪婪指數",
            f"<font color='#E8A33D' size=13><b>VIX {vix} / F&amp;G {fg}</b></font> <font color='#2E8B4F'><b>(極度恐慌)</b></font>",
            "極度恐慌區間 (F&amp;G &lt; 25)，歷史數據顯示分批進場勝率 &gt; 82%。")),
        (COLOR_FOREX, kpi_card(
            "美債 10Y-2Y 殖利率利差",
            f"<font color='#6B8F71' size=13><b>{'+' if spread >= 0 else ''}{spread}%</b></font> <font color='#B9791C'><b>(倒掛結束)</b></font>",
            f"10 年期 {t10}% / 2 年期 {t2}%<br/>曲線陡峭化，市場預期 Fed 年底前啟動降息。")),
    ]
    grid = [[Table(cards[0][1], colWidths=[260]), Table(cards[1][1], colWidths=[260])],
            [Table(cards[2][1], colWidths=[260]), Table(cards[3][1], colWidths=[260])]]
    for i, (accent, _) in enumerate(cards):
        row, col = divmod(i, 2)
        grid[row][col].setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), T.BG_CARD),
            ('BOX', (0, 0), (-1, -1), 1, accent),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
    t_grid = Table(grid, colWidths=[270, 270])
    t_grid.setStyle(TableStyle([('PADDING', (0, 0), (-1, -1), 3), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    story.append(t_grid)
    story.append(Spacer(1, 8))

    story.append(Paragraph(en("五大投資市場即時狀態監控表"), s["h1"]))
    monitor = [
        [Paragraph(en("<b>市場類別</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>識別色</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>當前指標/點位</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>風險等級</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>進出場訊號燈號</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>短線趨勢說明</b>", color="#FFFFFF"), s["th"])],
        [Paragraph(en("1. 台股市場"), s["body"]), Paragraph(en("活力橘紅", color="#FFFFFF"), s["th"]),
         Paragraph(en(f"融資餘額 {twm/10000:.1f} 萬張"), s["body"]), Paragraph(en("中等偏低"), s["body"]),
         Paragraph(en("🟢 分批進場"), s["body"]), Paragraph(en("融資清洗完畢，台積電先進封裝支撐強健"), s["body"])],
        [Paragraph(en("2. 美股市場"), s["body"]), Paragraph(en("科技青", color="#FFFFFF"), s["th"]),
         Paragraph(en(f"S&P 500: 5,420 (VIX {vix})"), s["body"]), Paragraph(en("中等"), s["body"]),
         Paragraph(en("🟢 分批進場"), s["body"]), Paragraph(en("恐慌指數攀升至買點，科技巨頭區間築底"), s["body"])],
        [Paragraph(en("3. 全球債券"), s["body"]), Paragraph(en("暖琥珀", color="#FFFFFF"), s["th"]),
         Paragraph(en(f"美債 10Y: {t10}% (利差 {'+' if spread >= 0 else ''}{spread}%)"), s["body"]), Paragraph(en("低"), s["body"]),
         Paragraph(en("🟢 鎖利加碼"), s["body"]), Paragraph(en("倒掛結束，鎖定降息前高殖利率票息"), s["body"])],
        [Paragraph(en("4. 外匯與美元"), s["body"]), Paragraph(en("抹茶綠", color="#FFFFFF"), s["th"]),
         Paragraph(en(f"DXY: {dxy} / TWD: {twd}"), s["body"]), Paragraph(en("中等"), s["body"]),
         Paragraph(en("🟡 觀望升值"), s["body"]), Paragraph(en("美元高位震盪，亞幣匯率止跌回升"), s["body"])],
        [Paragraph(en("5. 商品與加密"), s["body"]), Paragraph(en("墨藍黑", color="#FFFFFF"), s["th"]),
         Paragraph(en(f"黃金 ${gold:,} / BTC ${btc:,}"), s["body"]), Paragraph(en("偏高"), s["body"]),
         Paragraph(en("🟡 觀望布局"), s["body"]), Paragraph(en("黃金避險高位震盪，BTC 槓桿清理完畢"), s["body"])],
    ]
    t_mon = Table(monitor, colWidths=[75, 50, 125, 55, 75, 167])
    t_mon.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), T.NAVY),
        ('FONTNAME', (0, 0), (-1, -1), s["body"].fontName),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, T.BORDER),
        ('BACKGROUND', (1, 1), (1, 1), COLOR_TW_STOCK),
        ('BACKGROUND', (1, 2), (1, 2), COLOR_US_STOCK),
        ('BACKGROUND', (1, 3), (1, 3), COLOR_BOND),
        ('BACKGROUND', (1, 4), (1, 4), COLOR_FOREX),
        ('BACKGROUND', (1, 5), (1, 5), COLOR_CRYPTO),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t_mon)

    # 核心總體經濟數據（方案 C：自債匯頁移入——P2 是「今日決策總覽」，
    # 最新總經數值與評級/監控同屬決策輸入；歷史走勢圖全部在 P7 儀表板）
    story.append(Spacer(1, 8))
    story.append(Paragraph(en("<b>【核心總體經濟數據檢視】(Macro Indicators — Live)</b>"), s["h1"]))
    md = data.get("macro") or {}
    cpi_r = _yoy_series(md.get("cpi_hist"))
    core_r = _yoy_series(md.get("core_cpi_hist"))
    cpi_y = cpi_r[0][-1] if cpi_r else None
    core_y = core_r[0][-1] if core_r else None
    un = md.get("unemployment") or {}
    un_v = un.get("value")

    def _infl(v):
        return ("🟢 通膨降溫（低於 2.5%）" if v < 2.5 else
                "🟡 溫和（2.5%–3%）" if v < 3.0 else "🔴 偏高（高於 3%）")

    macro = [
        [Paragraph(en("<b>指標項目</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>最新公布值</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>參考基準</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>期間</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>總結評價</b>", color="#FFFFFF"), s["th"])],
    ]
    if cpi_y is not None:
        macro.append([Paragraph(en("美國 CPI 年增率"), s["body"]),
                      Paragraph(en(f"{cpi_y}%", bold=True), s["body"]),
                      Paragraph(en("Fed 目標 2%"), s["body"]),
                      Paragraph(en(f"{un.get('period_name', '')}"), s["body"]),
                      Paragraph(en(_infl(cpi_y)), s["body"])])
    if core_y is not None:
        macro.append([Paragraph(en("美國 Core CPI 年增率"), s["body"]),
                      Paragraph(en(f"{core_y}%", bold=True), s["body"]),
                      Paragraph(en("Fed 目標 2%"), s["body"]),
                      Paragraph(en(f"{un.get('period_name', '')}"), s["body"]),
                      Paragraph(en(_infl(core_y)), s["body"])])
    if un_v:
        un_f = float(un_v)
        un_j = ("🟢 勞動偏緊" if un_f < 4.0 else
                "🟢 溫和均衡（4%–4.5%）" if un_f <= 4.5 else "🟡 走弱留意")
        macro.append([Paragraph(en("美國失業率"), s["body"]),
                      Paragraph(en(f"{un_v}%", bold=True), s["body"]),
                      Paragraph(en("充分就業 4%–4.5%"), s["body"]),
                      Paragraph(en(f"{un.get('period_name', '')}"), s["body"]),
                      Paragraph(en(un_j), s["body"])])
    nfp_data = md.get("nfp") or {}
    nfp_v = nfp_data.get("value")
    if nfp_v:
        try:
            nfp_f = float(nfp_v)
            nfp_j = ("🟢 就業強勁" if nfp_f > 200 else
                     "🟡 溫和（100–200K）" if nfp_f > 100 else
                     "🔴 走弱（<100K）")
            macro.append([Paragraph(en("非農就業新增"), s["body"]),
                          Paragraph(en(f"{nfp_f:+.0f}K", bold=True), s["body"]),
                          Paragraph(en("健康水準 150–250K"), s["body"]),
                          Paragraph(en(f"{nfp_data.get('period_name', '')}"), s["body"]),
                          Paragraph(en(nfp_j), s["body"])])
        except ValueError:
            pass
    macro.append([Paragraph(en("美債 10Y 殖利率"), s["body"]),
                  Paragraph(en(f"{t10}%", bold=True), s["body"]),
                  Paragraph(en("2Y 殖利率 " + f"{t2}%"), s["body"]),
                  Paragraph(en("當日"), s["body"]),
                  Paragraph(en("🟢 曲線正常化（未倒掛）" if spread >= 0 else "🔴 曲線倒掛"), s["body"])])
    if len(macro) > 1:
        t_macro = Table(macro, colWidths=[110, 70, 95, 65, 207])
        t_macro.setStyle(_detail_style(T.NAVY, T.BORDER, s))
        story.append(t_macro)

    # ======================= PAGE 2 — TW & US ==============================
    story.append(PageBreak())
    story.extend(make_title_row("台股與美股籌碼/技術面深度分析",
        "資料：TWSE MI_MARGN・Yahoo Finance｜籌碼數據截至前一交易日",
        date_str, COLOR_TW_STOCK, s, eyebrow_text="Financial Intelligence"))
    verdicts = _market_verdicts(data)

    story.append(Paragraph(en("<b>【台股市場專題】活力橘紅 —— 融資/融券餘額與籌碼分析</b>"), s["h1"]))
    tw_rows = _detail_table(
        ["關鍵指標", "當前數據", "歷史警戒/臨界值", "數據判讀與進出場建議"],
        [
            ["全市場融資餘額", f"{twm/10000:.1f} 萬張", "門檻 900 萬張（可校準）", "🟢 低於門檻，槓桿未過熱，洗盤接近尾聲，具反彈動能"],
            ["全市場融券餘額", f"{tws/10000:.1f} 萬張", "歷史區間 15–40 萬張", "🟢 融券水位中性，無軋空亦無悲觀過度"],
            ["外資現貨買賣超", "+125 億", "單日 > +100 億為轉多", "🟢 外資連續 3 日現貨轉買，資金回流權值股"],
            ["投信現貨買賣超", "+42 億", "持續買超支撐", "🟢 投信連續 15 日買超，內資法人底氣充足"],
            ["外資台指期未平倉", f"{oi:,} 口", "警戒線 -30,000 口", "🟢 空單較上週高點回補 8,000 口，避險賣壓大幅減輕"],
            ["大盤 MA20/60 乖離", "-2.8% / -4.1%", "負乖離 > -5% 為短線超賣", "🟢 短線正處於超賣區，具備急彈技術面條件"],
        ],
        header_bg=COLOR_TW_STOCK, grid_color=colors.HexColor('#FDE7E1'), styles=s,
    )
    story.append(tw_rows)
    story.append(Spacer(1, 10))

    story.append(Paragraph(en("<b>【美股市場專題】科技青 —— 恐慌指數與市場廣度</b>"), s["h1"]))
    us_rows = _detail_table(
        ["美股指數/指標", "當前數據", "歷史警戒/臨界值", "數據判讀與進出場建議"],
        [
            ["S&P 500 指數", "5,420 點", "季線 MA60 (5,400 點)", "🟢 於季線關卡展現強勁支撐，回測不破"],
            ["Nasdaq 指數", "16,950 點", "半年線 MA120 (16,800 點)", "🟢 科技股震盪築底，AI 龍頭自由現金流穩健"],
            ["費城半導體 (SOX)", "4,880 點", "年線 MA200 (4,750 點)", "🟡 受到出口限制與擴產 Capex 震盪，宜分批佈局"],
            ["VIX 恐慌指數", f"{vix}", "恐慌區 > 25 / 極度恐慌 > 35", "🟢 攀升至恐慌區，顯示情緒極度悲觀，通常為中長線買點"],
            ["Fear & Greed Index", f"{fg} (Extreme Fear)", "恐慌區 < 25", "🟢 進入極度恐慌區，符合巴菲特「別人恐慌我貪婪」條件"],
            ["MA200 成分股占比", "42.5%", "超賣區 < 30% / 超買區 > 80%", "🟡 市場廣度中性偏低，資金集中於七大巨頭 (Magnificent 7)"],
        ],
        header_bg=COLOR_US_STOCK, grid_color=colors.HexColor('#E3F3F4'), styles=s,
    )
    story.append(us_rows)
    # 本頁交易提示(置於頁尾,閱讀完內文後收束結論)
    story.append(Spacer(1, 16))
    story.extend(_verdict_banner([verdicts["tw"], verdicts["us"]], s))

    # ======================= PAGE 3 — Bonds / Forex =========================
    story.append(PageBreak())
    story.extend(make_title_row("債券與外匯市場深度分析",
        "資料：美國財政部・Yahoo Finance｜殖利率每日、利差計算（TTL 快取）",
        date_str, COLOR_BOND, s, eyebrow_text="Financial Intelligence"))

    story.append(Paragraph(en("<b>【全球債券專題】暖琥珀 —— 利率與殖利率曲線</b>"), s["h1"]))
    story.append(_detail_table(
        ["債券指標", "當前數據", "上月數據", "趨勢判讀與進出場建議"],
        [
            ["美債 10 年期殖利率", f"{t10}%", "4.15%", "🟢 殖利率顯著回落，長天期公債價格上漲，鎖定高票息"],
            ["美債 2 年期殖利率", f"{t2}%", "4.30%", "🟢 短端利率反映 Fed 年底前降息 2 碼之預期"],
            ["10Y-2Y 殖利率利差", f"{'+' if spread >= 0 else ''}{spread}%", "-0.15%", "🟢 殖利率倒掛結束並陡峭化，有利於金融機構利差改善"],
            ["美國高收益債信用利差", "340 bps", "320 bps", "🟡 信用利差微幅擴大但仍低於歷史均值 (450 bps)，無違約危機"],
        ],
        header_bg=COLOR_BOND, grid_color=colors.HexColor('#FCF0DC'), styles=s,
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph(en("<b>【外匯與美元專題】抹茶綠 —— 匯率與資金流動性</b>"), s["h1"]))
    story.append(_detail_table(
        ["外匯指標", "當前數據", "關鍵水位", "資金流向與影響判讀"],
        [
            ["美元指數 (DXY)", f"{dxy}", "阻力: 104.5 / 支撐: 101.0", "🟢 美元自高點走弱，減輕新興市場資金外流壓力"],
            ["美元/新台幣 (USD/TWD)", f"{twd}", "阻力: 32.50 / 支撐: 31.80", "🟢 台幣升值預期升溫，有利外資回流台股現貨"],
            ["美元/日圓 (USD/JPY)", "145.2", "警戒: 155.0 (套利平倉)", "🟡 日圓套利交易平倉風險趨緩，金融市場流動性恢復"],
        ],
        header_bg=COLOR_FOREX, grid_color=colors.HexColor('#E8F0E9'), styles=s,
    ))
    story.append(Spacer(1, 8))

    # 利差與動能計算表（方案 C：自總經儀表板移入——利差屬債券主題，
    # 與殖利率表同頁；儀表板 P7 專注歷史走勢圖）
    ycd = (data.get("macro") or {}).get("yield_curve") or {}
    curve = ycd.get("curve") or {}
    ten10y = (data.get("macro") or {}).get("us10y_hist") or []
    if curve and len(ten10y) >= 20:
        def _cv(t):
            return curve.get(t)
        rows = [[Paragraph(en("<b>計算指標</b>", color="#FFFFFF"), s["th"]),
                 Paragraph(en("<b>最新值</b>", color="#FFFFFF"), s["th"]),
                 Paragraph(en("<b>參考判準</b>", color="#FFFFFF"), s["th"]),
                 Paragraph(en("<b>判讀</b>", color="#FFFFFF"), s["th"])]]

        def _spread_row(name, lo, hi, ref, judge):
            a, b = _cv(lo), _cv(hi)
            if a is None or b is None:
                return
            v = round(b - a, 2)
            rows.append([Paragraph(en(name), s["body"]),
                         Paragraph(en(f"{v:+.2f}%", bold=True), s["body"]),
                         Paragraph(en(ref), s["body"]),
                         Paragraph(en(judge(v)), s["body"])])
        _spread_row("2Y–10Y 利差", "2Y", "10Y", "0% = 曲線正常",
                    lambda v: "🟢 正常化" if v > 0 else "🔴 倒掛")
        _spread_row("3M–10Y 利差", "3M", "10Y", "聯準會觀察重點",
                    lambda v: "🟢 正斜率" if v > 0 else "🟡 仍倒掛")
        _spread_row("5Y–30Y 利差", "5Y", "30Y", "長端期限貼水",
                    lambda v: "🟢 正常" if v > 0 else "🟡 貼水反轉")
        m_ago = ten10y[max(0, len(ten10y) - 22)]
        chg = round(ten10y[-1]["v"] - m_ago["v"], 2)
        rows.append([Paragraph(en("10Y 月變化"), s["body"]),
                     Paragraph(en(f"{chg:+.2f}%", bold=True), s["body"]),
                     Paragraph(en(f"vs {m_ago['date']}"), s["body"]),
                     Paragraph(en("🟢 降息預期升溫" if chg < -0.1 else ("🟡 溫和波動" if chg < 0.25 else "🔴 明顯上行")), s["body"])])
        t_spread = Table(rows, colWidths=[110, 80, 130, 227])
        t_spread.setStyle(_detail_style(T.NAVY, T.BORDER, s))
        story.append(Paragraph(en("<b>利差與動能計算表</b>"), s["h1"]))
        story.append(t_spread)
    # 本頁交易提示(置於頁尾)
    story.append(Spacer(1, 16))
    story.extend(_verdict_banner([verdicts["bond"], verdicts["forex"]], s))

    # ======================= PAGE 4 — Commodities / Crypto ==================
    story.append(PageBreak())
    story.extend(make_title_row("大宗商品與數位資產",
        "資料：Yahoo Finance｜商品與數位資產報價即時",
        date_str, COLOR_CRYPTO, s, eyebrow_text="Financial Intelligence"))

    story.append(Paragraph(en("<b>【大宗商品與數位資產】墨藍黑</b>"), s["h1"]))
    story.append(_detail_table(
        ["資產標的", "當前價格", "關鍵支撐/壓力", "鏈上/市場籌碼與觀點分析"],
        [
            ["黃金 (Gold)", f"${gold:,} / oz", "支撐: $2,400 / 壓力: $2,500", "🟢 央行持續購金與避險需求支撐，高位高姿態震盪"],
            ["紐約原油 (WTI)", "$76.5 / bbl", "支撐: $72.0 / 壓力: $82.0", "🟢 供需大致平衡，未出現引發二次通膨之暴漲風險"],
            ["比特幣 (BTC)", f"${btc:,}", "支撐: $55,000 / 壓力: $64,000", "🟢 永續合約資費歸零、多頭高槓桿清理完畢，呈現健康築底"],
        ],
        header_bg=COLOR_CRYPTO, grid_color=colors.HexColor('#EEF0F4'), styles=s,
    ))
    # 本頁交易提示(置於頁尾)
    story.append(Spacer(1, 16))
    story.extend(_verdict_banner([verdicts["cmdty"], verdicts["crypto"]], s))

    # ======================= PAGE 5 — Allocation / Entry / Exit =============
    story.append(PageBreak())
    story.extend(make_title_row("資產配置與進退場標的",
        "動態配置矩陣 ＋ 進場/退場精選清單｜綜合前述指標・非投資建議",
        date_str, T.SIGNAL_BUY, s, eyebrow_text="Financial Intelligence"))

    # 配置矩陣（方案 C：自商品頁移入——配置與標的同屬決策輸出，
    # 「情報→總覽→分市場→配置決策」的漏斗在此收束）
    story.append(Paragraph(en("<b>【當前動態資產配置建議矩陣】(Dynamic Allocation Matrix)</b>"), s["h1"]))
    alloc = [
        [Paragraph(en("<b>資產類別</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>建議配置比例</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>與標準配置對比</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>配置戰略與調整理由</b>", color="#FFFFFF"), s["th"])],
        [Paragraph(en("股票部位 (Equities)"), s["body"]), Paragraph(en("50%", bold=True), s["body"]),
         Paragraph(en("⬆️ +5% (偏多)"), s["body"]), Paragraph(en("台股融資洗盤完畢 + 美股 VIX 恐慌區，逢低分批佈局優質市值型標的"), s["body"])],
        [Paragraph(en("債券部位 (Bonds)"), s["body"]), Paragraph(en("30%", bold=True), s["body"]),
         Paragraph(en("⬆️ +5% (鎖利)"), s["body"]), Paragraph(en("倒掛結束，配置中長天期美國公債與投資級公司債，鎖定降息票息"), s["body"])],
        [Paragraph(en("現金與流動性 (Cash)"), s["body"]), Paragraph(en("15%", bold=True), s["body"]),
         Paragraph(en("⬇️ -10% (彈性)"), s["body"]), Paragraph(en("保留 15% 流動性，作為極端震盪或急跌時之二度加碼彈性預備金"), s["body"])],
        [Paragraph(en("黃金與替代資產"), s["body"]), Paragraph(en("5%", bold=True), s["body"]),
         Paragraph(en("➡️ 持平"), s["body"]), Paragraph(en("保持 5% 黃金/數位資產部位，作為地緣政治風險與貨幣貶值之對沖"), s["body"])],
    ]
    t_alloc = Table(alloc, colWidths=T.COLS_DETAIL)
    t_alloc.setStyle(_detail_style(T.NAVY, T.BORDER, s))
    story.append(t_alloc)
    story.append(Spacer(1, 10))

    story.append(Paragraph(en("<b>🟢 適合進場 / 分批加碼投資標的 (Recommended Entry Targets)</b>"), s["h1"]))
    story.append(_detail_table(
        ["投資領域", "標的名稱 / 代碼", "建議進場策略", "核心選股/選債量化理由"],
        [
            ["台股市場", "市值型 / 半導體 ETF<br/>(如 0050, 0052)", "分批逢低建立核心部位", f"全市場融資餘額 {twm/10000:.1f} 萬張、低於門檻，槓桿未過熱；先進封裝與 CoWoS 產能滿載，評價具吸引力。"],
            ["台股市場", "AI 伺服器水冷與散熱龍頭", "拉回重心支撐線加碼", "AI 伺服器單機功耗暴增，營收月增率持強，法人與投信連續 15 日買超護盤。"],
            ["美股市場", "標普 500 / 納指 ETF<br/>(如 VOO, QQQ)", "分 3 批定期定額扣款", f"VIX 升至 {vix} + F&amp;G 降至 {fg} 極度恐慌區，歷史回測分批進場勝率 > 82%。"],
            ["美股市場", "雲端 Hyperscaler &amp; AI 巨頭", "分批進場", "科技巨頭 2026 年 Capex 資本支出持續上修，自由現金流非常強健。"],
            ["全球債券", "20年期以上美國公債 ETF<br/>(如 TLT, 00679B)", "單筆搭配定期定額", f"10Y-2Y 倒掛結束，鎖定 {t10}%~{t10 + 0.15:.2f}% 高殖利率，降息啟動享資本利得。"],
            ["數位資產", "比特幣現貨 ETF / BTC", "分批佈局", "永續合約資費歸零、交易所槓桿多單清理完畢，鏈上算力持續創新高。"],
        ],
        header_bg=T.SIGNAL_BUY, grid_color=colors.HexColor('#E8F0E9'), styles=s,
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph(en("<b>🔴 需要注意退場 / 減碼避險投資標的 (Warning &amp; Exit Targets)</b>"), s["h1"]))
    story.append(_detail_table(
        ["投資領域", "標的類別 / 警示特徵", "建議退場/避險策略", "風險警示理由與量化數據"],
        [
            ["台股市場", "高融資比率之純題材中小型股", "反彈即時分批減碼", "大盤融資斷頭潮尚未全數結束，高融資率小型股面臨追繳與多殺多流動性風險。"],
            ["台股市場", "成熟製程與消費性電子弱勢股", "尋求停損或轉換標的", "終端消費需求復甦步調低於預期，毛利率持續受成熟製程價格戰壓抑。"],
            ["美股市場", "高債務與零獲利高估值科技股", "分批逢高出清離場", "高利率維持更久 (Higher for Longer) 壓抑無獔利公司估值，融資利息負擔過高。"],
            ["外匯與商品", "高槓桿槓桿型 ETF<br/>(如 2X/3X 槓桿商品)", "即時停損減碼離場", "市場波動率 VIX 大幅跳升，高波動期間槓桿 ETF 損耗風險極高，不宜長期持有。"],
        ],
        header_bg=T.SIGNAL_SELL, grid_color=colors.HexColor('#FDE7E1'), styles=s,
    ))
    # 本頁交易提示(置於頁尾——全報告的收束結論)
    story.append(Spacer(1, 16))
    story.extend(_verdict_banner([verdicts["overall"]], s))

    # ======================= PAGE 6 — Macro Dashboard =========================
    # 方案 C：四張總經走勢圖集中於此（NFP 自 P2 移入；利差計算表移至債券頁）。
    # 圖高 118/108 讓四圖 + 標題維持在同一頁。
    story.append(PageBreak())
    story.extend(make_title_row(
        "總體經濟儀表板（Macro Dashboard）",
        "殖利率曲線 × 10Y 走勢 × 通膨趨勢 × 非農就業 — 資料：美國財政部 / BLS（TTL 快取：月頻 7 天、殖利率 1 天）",
        date_str, T.SAGE, s, eyebrow_text="Financial Intelligence"))
    md = data.get("macro") or {}
    ycd = md.get("yield_curve") or {}
    curve = ycd.get("curve") or {}
    have_any = False
    if curve:
        have_any = True
        story.append(Paragraph(en(f"<b>美債殖利率曲線（{ycd.get('date', '')}）</b>"), s["h1"]))
        story.append(_line_chart(list(curve.keys()), [list(curve.values())], height=118,
                                 y_unit="%", y_fmt="{:.2f}", x_unit="天期"))
        story.append(Spacer(1, 5))
    ten10y = md.get("us10y_hist") or []
    if len(ten10y) >= 20:
        have_any = True
        step = max(1, len(ten10y) // 8)
        labels = [p["date"][:5] if i % step == 0 else ""
                  for i, p in enumerate(ten10y)]
        vals = [p["v"] for p in ten10y]
        first, last = ten10y[0], ten10y[-1]
        story.append(Paragraph(
            en(f"<b>美債 10Y 殖利率走勢（{first['date']} → {last['date']}，年內 {len(ten10y)} 個交易日）</b>"),
            s["h1"]))
        story.append(_line_chart(labels, [vals], height=118,
                                 y_unit="%", y_fmt="{:.2f}", x_unit="月份"))
        story.append(Spacer(1, 5))
    cpi_r2 = _yoy_series(md.get("cpi_hist"))
    core_r2 = _yoy_series(md.get("core_cpi_hist"))
    if cpi_r2 or core_r2:
        have_any = True
        series = [r[0] for r in (cpi_r2, core_r2) if r]
        labels = (cpi_r2 or core_r2)[1]
        story.append(Paragraph(en("<b>通膨趨勢 — CPI / Core CPI 年增率（青線 = CPI，琥珀線 = Core CPI）</b>"), s["h1"]))
        story.append(_line_chart(labels, series, height=118,
                                 y_unit="%", y_fmt="{:.1f}", x_unit="月份"))
        story.append(Spacer(1, 5))
    nfp_chart = _nfp_monthly_changes(md.get("nfp_hist"))
    if nfp_chart:
        have_any = True
        nfp_diffs, nfp_labels = nfp_chart
        step = max(1, len(nfp_labels) // 8)
        nfp_labels = [l if i % step == 0 else "" for i, l in enumerate(nfp_labels)]
        story.append(Paragraph(en("<b>非農就業月增人數（千人/月）— 就業動能指標</b>"), s["h1"]))
        story.append(_line_chart(nfp_labels, [nfp_diffs], height=108,
                                 y_unit="千人", y_fmt="{:+.0f}", x_unit="月份"))
    if not have_any:
        story.append(Paragraph(en("（總經資料來源暫時無法取得，快亦為空——本頁略過圖表）"), s["body"]))

    doc = new_doc(filename, title="Financial Intelligence 每日投資趨勢報告",
                 keywords="financial intelligence, TWSE, VIX, treasury, NFP, CPI, commodities, crypto, daily, quant, signal")
    doc.build(story, onFirstPage=footer_factory(DISCLAIMER, _PAGE_TOTAL),
              onLaterPages=footer_factory(DISCLAIMER, _PAGE_TOTAL))
    print("PDF build complete:", filename)
    return filename


# ---- local style + table helpers ------------------------------------------
from reportlab.lib.styles import ParagraphStyle


def ParagraphStyle_local(name, size, color, leading=None, align=0):
    from core.fonts import FONT_CJK
    return ParagraphStyle(name, fontName=FONT_CJK, fontSize=size,
                          leading=leading or size + 3, textColor=color, alignment=align)


def _detail_style(header_bg, grid_color, styles):
    return TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), header_bg),
        ('FONTNAME', (0, 0), (-1, -1), styles["body"].fontName),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, grid_color),
        ('BACKGROUND', (0, 1), (-1, -1), T.BG_CARD),
        ('PADDING', (0, 0), (-1, -1), 5),
    ])


def _detail_table(headers, rows, header_bg, grid_color, styles):
    head = [Paragraph(en(f"<b>{h}</b>", color="#FFFFFF"), styles["th"]) for h in headers]
    data = [head]
    for r in rows:
        data.append([
            Paragraph(en(r[0]), styles["body"]),
            Paragraph(en(r[1], bold=True), styles["body"]),
            Paragraph(en(r[2]), styles["body"]),
            Paragraph(en(r[3]), styles["body"]),
        ])
    t = Table(data, colWidths=T.COLS_DETAIL)
    t.setStyle(_detail_style(header_bg, grid_color, styles))
    return t


if __name__ == "__main__":
    out = os.path.join(_REPO_ROOT, "output", "Financial_Intelligence_每日投資趨勢報告.pdf")
    generate_daily_pdf(out, data={}, date_str="2026-08-11")
