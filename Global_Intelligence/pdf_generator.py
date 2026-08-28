#!/usr/bin/env python3
"""Global Intelligence — PDF report generator (7-page A4, dynamic cards).

P1: Trend overview (domain heat table + bar chart + trending keywords + AI digest)
P2-P7: One domain per page, 6 dynamic topic cards each.

Cards pull live from the retrieval corpus; editorial fallback fills gaps.
"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from html import unescape as _html_unescape
from urllib.parse import urlparse as _urlparse

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak

from core import design_tokens as T
from core import llm
from core.pdf_engine import en, standard_styles, make_title_row, footer_factory, new_doc
from core.fonts import FONT_CJK

DISCLAIMER = "本報告由 Global Intelligence 自動化情報系統產生，涵蓋全球與國內權威智庫報告速讀。"

_TZ = timezone(timedelta(hours=8))
_TAG_RE = re.compile(r"<[^>]+>")

DOMAINS = [
    ("geopolitics", "地緣政治與國際關係", "Geopolitics & International Relations", "Category 01", T.RAMP_INK),
    ("macro", "巨觀經濟與金融市場", "Macroeconomics & Financial Markets", "Category 02", T.RAMP_AMBER),
    ("it_ai", "資訊科技與人工智慧", "IT, AI & Semiconductors", "Category 03", T.RAMP_TEAL),
    ("biotech", "生物科技與健康醫療", "Biotech & Healthcare", "Category 04", T.RAMP_SAGE),
    ("hardware", "硬體工程、自動化與能源轉型", "Hardware, Automation & Energy", "Category 05", T.RAMP_CORAL),
    ("aerospace", "航空太空與量子科技", "Aerospace & Quantum Technology", "Category 06", T.RAMP_INDIGO),
]

_SOURCE_NAMES = {
    "feeds.bbci.co.uk": "BBC",
    "search.cnbc.com": "CNBC",
    "www.aljazeera.com": "ALJAZEERA",
    "news.un.org": "UN NEWS",
    "techcrunch.com": "TECHCRUNCH",
    "technews.tw": "TECHNEWS",
    "www.ithome.com.tw": "ITHOME",
    "www.sciencedaily.com": "SCIENCEDAILY",
    "www.economist.com": "ECONOMIST",
    "spectrum.ieee.org": "IEEE SPECTRUM",
    "electrek.co": "ELECTREK",
    "www.nasa.gov": "NASA",
    "spacenews.com": "SPACENEWS",
    "arstechnica.com": "ARS TECHNICA",
    "aviationweek.com": "AVIATION WEEK",
    "www.reuters.com": "REUTERS",
    "thequantuminsider.com": "QUANTUM INSIDER",
    "physicsworld.com": "PHYSICS WORLD",
    "www.reddit.com": "REDDIT",
    "finance.yahoo.com": "YAHOO FINANCE",
    "feeds.content.dowjones.io": "MARKETWATCH",
    "www.ft.com": "FINANCIAL TIMES",
    "seekingalpha.com": "SEEKING ALPHA",
    "www.cnbc.com": "CNBC",
}

EDITORIAL_FALLBACK = {
    "geopolitics": [
        ["CSIS", "中朝關係重組研討會", "2026-08-10 09:00 EDT", "CSIS 舉辦專題研討會剖析東北亞安全新格局。"],
        ["The Conference Board", "近岸與友岸外包加速", "2026-08-06 18:00 EST", "美國關稅政策新規常態化，製造業供應鏈加速轉移。"],
        ["國防院 (INDSR)", "印太安全與供應鏈保全", "2026-08-08 10:00 TST", "評估紅海航道干擾與台海安全。"],
        ["中經院 (CIER)", "地緣政治對台商投資影響", "2026-08-07 15:30 TST", "分析關稅合規與地緣風險。"],
    ],
    "macro": [
        ["歐洲央行 (ECB)", "最新貨幣通報與通膨警告", "2026-08-06 10:00 CEST", "ECB 指出歐元區通膨雖受控制，但能源波動仍存。"],
        ["Mohamed El-Erian", "全球央行政策分化分析", "2026-08-09 21:00 EST", "成熟與新興市場復甦步調不一。"],
        ["台經院 (TIER)", "台灣宏觀經濟與出口展望", "2026-08-08 11:00 TST", "受惠 AI 拉貨強勁，出口動能維持高檔。"],
        ["中央銀行 (CBC)", "貨幣政策與流動性分析", "2026-08-07 16:30 TST", "維持適度緊縮貨幣立場。"],
    ],
    "it_ai": [
        ["TSMC / Motley Fool", "超預期算力帶動 640 億 Capex", "2026-08-09 08:30 EST", "台積電擴大 640 億美元資本支出。"],
        ["NVIDIA / Design&Reuse", "AI 演算法深入晶圓廠", "2026-08-08 11:00 EST", "NVIDIA 與台積電合作 AI 檢測。"],
        ["工研院 (ITRI ISTI)", "3D Chiplet 與 HBM4 封裝", "2026-08-08 14:00 TST", "晶片競賽轉向 3D 堆疊與 SiP。"],
        ["資策會 (MIC)", "AI Agent 商業落地", "2026-08-07 10:30 TST", "企業 AI 從 PoC 轉向 ROI 驗證。"],
    ],
    "biotech": [
        ["U.S. FDA / Endpoints", "Pilot Plan 試點加速", "2026-08-07 06:38 EST", "FDA 啟動試點加速計畫。"],
        ["Eli Lilly / PR Newswire", "Olomorasib 獲認證", "2026-08-03 09:00 EST", "禮來 KRAS G12C 新藥獲 FDA 認證。"],
        ["國衛院 (NHRI)", "ADC 研發進展", "2026-08-08 10:00 TST", "精準腫瘤學標靶藥物突破。"],
        ["生技中心 (DCB)", "CDMO 量能", "2026-08-07 14:30 TST", "推動核酸藥物 CDMO 國際認證。"],
    ],
    "hardware": [
        ["U.S. DOE / NCSL", "SMR 核能創新園區", "2026-08-08 12:00 EST", "美國能源部啟動 SMR 商業化。"],
        ["Cambridge EnerTech", "固態電池與機器人", "2026-08-09 09:00 EST", "固態電池聚焦高能量密度。"],
        ["國研院 (NARLabs)", "工業 4.0 智慧感測", "2026-08-08 11:30 TST", "研發次世代感測器。"],
        ["工研院綠能所 (GEL)", "智慧電網與 LDES", "2026-08-07 16:00 TST", "數據中心倒逼電網升級。"],
    ],
    "aerospace": [
        ["NASA", "Artemis II 月球任務", "2026-08-20 10:00 EST", "NASA 載人繞月任務持續推進。"],
        ["SpaceNews", "Starship 第五次試飛", "2026-08-22 08:00 EST", "SpaceX Starship 回收成功。"],
        ["IBM Quantum", "量子錯誤修正里程碑", "2026-08-21 14:00 EST", "IBM 發表 1,000+ qubit 處理器。"],
        ["The Quantum Insider", "後量子密碼學標準化", "2026-08-19 11:00 EST", "NIST 後量子密碼學標準定案。"],
        ["Ars Technica", "量子網際網路原型", "2026-08-18 14:00 EST", "量子糾纏分發距離突破。"],
        ["Aviation Week", "電動航空 eVTOL 變局", "2026-08-21 09:00 EST", "電動垂直起降認證加速。"],
    ],
}


def _strip_html(text):
    """Remove HTML tags. Entities stay escaped for ReportLab Paragraph safety."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", text)).strip()


def _source_display(url_or_domain):
    try:
        netloc = _urlparse(url_or_domain).netloc if "://" in url_or_domain else url_or_domain
    except Exception:
        netloc = url_or_domain
    netloc = (netloc or "").lower().strip()
    if netloc in _SOURCE_NAMES:
        return _SOURCE_NAMES[netloc]
    parts = netloc.replace("www.", "").split(".")
    generic = {"feeds", "search", "news", "www", "rss", "feed"}
    for p in parts:
        if p not in generic and len(p) > 2:
            return p.upper()
    return (parts[0] if parts else "RSS").upper()


def _fmt_time(item):
    pub = item.get("published", "")
    if pub:
        try:
            from email.utils import parsedate_to_datetime as _pdt
            dt = _pdt(pub)
            return dt.astimezone(_TZ).strftime("%m-%d %H:%M")
        except Exception:
            pass
        try:
            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            return dt.astimezone(_TZ).strftime("%m-%d %H:%M")
        except Exception:
            pass
    fa = item.get("fetched_at", "")
    try:
        dt = datetime.fromisoformat(fa)
        return dt.astimezone(_TZ).strftime("%m-%d %H:%M")
    except (ValueError, TypeError):
        return (pub or "—")[:16]


def _topic_card(org, focus, when, body_flowables, ramp, styles, url=None, compact=False):
    """Topic card with optional compact mode (6/page)."""
    base = colors.HexColor(ramp[2])
    tint = colors.HexColor(ramp[0])
    dark = colors.HexColor(ramp[3])

    body_size = 7.8 if compact else 8.0
    body_lead = 9.6 if compact else 10.0
    pad_v = 1.5 if compact else 2

    meta_st = ParagraphStyle("gmeta", fontName=FONT_CJK, fontSize=7.5,
                             leading=9, textColor=T.TEXT_MUTED, alignment=2)
    title_st = ParagraphStyle("gtitle", fontName=FONT_CJK, fontSize=9.0,
                              leading=11.5, textColor=dark, spaceBefore=1, spaceAfter=1)
    body_st = ParagraphStyle("gbody", fontName=FONT_CJK, fontSize=body_size,
                             leading=body_lead, textColor=T.TEXT_BODY)

    inner = T.PRINTABLE_WIDTH - 12  # compact: 6pt padding each side
    safe_url = (url or "").replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;") if url else ""
    org_html = (f'<a href="{safe_url}" color="#FFFFFF"><u><b>{org}</b></u></a>'
                if url else f"<b>{org}</b>")
    badge = Table(
        [[Paragraph(org_html,
                    ParagraphStyle("gbadge", fontName=FONT_CJK, fontSize=7.8,
                                   leading=9, textColor=T.WHITE))]],
        colWidths=[inner - 130],
    )
    badge.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), base),
        ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    header = Table([[badge, Paragraph(en(f"🕒 {when}"), meta_st)],
                    [Paragraph(en(f"<b>{focus}</b>"), title_st), ""]],
                   colWidths=[inner - 130, 130])
    header.setStyle(TableStyle([
        ('BACKGROUND', (1, 0), (1, 0), tint),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('SPAN', (0, 1), (1, 1)),
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, 0), 0), ('BOTTOMPADDING', (0, 0), (-1, 0), 1),
        ('TOPPADDING', (0, 1), (-1, 1), 1),
    ]))

    rows = [[header]] + [[Paragraph(en(b), body_st)] for b in body_flowables]
    card = Table(rows, colWidths=[T.PRINTABLE_WIDTH])
    card.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), tint),
        ('BOX', (0, 0), (-1, -1), 0.5, T.BORDER),
        ('LINEBEFORE', (0, 0), (0, -1), 3, base),
        ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), pad_v), ('BOTTOMPADDING', (0, 0), (-1, -1), pad_v),
    ]))
    return card


def _rss_card(item, ramp, styles, three_part=None, compact=False):
    """Dynamic RSS card."""
    org_display = _source_display(item.get("source", ""))
    focus = _strip_html(item.get("title", ""))[:80]
    when = _fmt_time(item)
    summary = _strip_html(item.get("summary", ""))[:200] or focus
    link = item.get("link", "")
    body = [_strip_html(three_part["what"])[:110]] if three_part else [summary]
    return _topic_card(org_display, focus, when, body, ramp, styles, url=link, compact=compact)


def _bar_chart(data, ramp_map, styles, max_val=None):
    """Horizontal bar chart showing domain article counts."""
    if not data:
        return None
    max_val = max_val or max(v for v in data.values()) or 1
    bar_st = ParagraphStyle("gbar", fontName=FONT_CJK, fontSize=7.5,
                             leading=9, textColor=T.TEXT_BODY)
    rows = []
    for dom_tag, count in sorted(data.items(), key=lambda x: x[1], reverse=True):
        dom_names = {d[0]: d[1] for d in DOMAINS}
        zh = dom_names.get(dom_tag, dom_tag)
        pct = int(count / max_val * 100) if max_val else 0
        ramp = ramp_map.get(dom_tag, T.RAMP_INK)
        bar_color = ramp[2]
        bar_bg = ramp[0]
        rows.append([
            Paragraph(en(zh[:10]), bar_st),
            Table(
                [[Table([[""]], colWidths=[max(1, int(pct * 3.5))],
                        rowHeights=[12],
                        style=TableStyle([('BACKGROUND', (0,0),(-1,-1), colors.HexColor(bar_color))])
                        )]],
                colWidths=[350], rowHeights=[14],
                style=TableStyle([('BACKGROUND', (0,0),(-1,-1), colors.HexColor(bar_bg)),
                                  ('LEFTPADDING', (0,0),(-1,-1), 0),
                                  ('RIGHTPADDING', (0,0),(-1,-1), 0),
                                  ('TOPPADDING', (0,0),(-1,-1), 0),
                                  ('BOTTOMPADDING', (0,0),(-1,-1), 0)])
            ),
            Paragraph(en(f"<b>{count}</b>"), bar_st),
        ])
    t = Table(rows, colWidths=[100, 360, 60])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2), ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))
    return t


def build_global_pdf(filename, data=None, date_str=None):
    """Build the 7-page Global PDF: P1 trend overview + P2-P7 domain cards."""
    date_str = date_str or (data or {}).get("date") or "2026-08-26"
    s = standard_styles()
    story = []
    title = "Global Intelligence 每日產業局勢報告"
    EYEBROW = "Global Intelligence"
    use_llm = llm.is_available()
    retrieval_data = (data or {}).get("retrieval", {})
    trends = (data or {}).get("trends") or {}

    # ============ P1: Trend Overview ============
    story.extend(make_title_row(
        "六大領域情報速讀＋趨勢比較",
        "AI 智庫摘要 ＋ 領域熱度 ＋ 發燒關鍵字 — 即時 RSS 語料庫（本週 vs 上週）",
        date_str, T.GOLD, s, eyebrow_text=EYEBROW))

    # AI digest (if LLM key available)
    digest = (data or {}).get("llm_digest")
    if digest:
        digest_st = ParagraphStyle("gdigest", fontName=FONT_CJK, fontSize=8.0,
                                   leading=10.4, textColor=T.TEXT_BODY)
        story.append(Paragraph(en("<b>🤖 AI 智庫摘要（Gemini 即時萃取）</b>"), s["h1"]))
        digest_rows = [
            [Paragraph(en("<b>WHAT（事實概要）</b>", color="#FFFFFF"), s["th"]),
             Paragraph(en(digest.get("what", ""), bold=True), digest_st)],
            [Paragraph(en("<b>WHY（脈絡影響）</b>", color="#FFFFFF"), s["th"]),
             Paragraph(en(digest.get("why", "")), digest_st)],
            [Paragraph(en("<b>SO WHAT（台灣啟示）</b>", color="#FFFFFF"), s["th"]),
             Paragraph(en(digest.get("so_what", "")), digest_st)],
        ]
        t_ai = Table(digest_rows, colWidths=[110, T.PRINTABLE_WIDTH - 110])
        t_ai.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), T.NAVY),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, T.BORDER),
            ('BACKGROUND', (1, 0), (1, -1), T.BG_CARD),
            ('PADDING', (0, 0), (-1, -1), 4),
        ]))
        story += [t_ai, Spacer(1, 8)]
    elif use_llm:
        # Gemini is keyed but no digest came back — RSS empty, the API call
        # failed, or the reply didn't parse. Show the degradation instead of
        # letting the three-part brief vanish silently (it did exactly that on
        # 2026-08-28 while CI stayed green).
        had_rss = bool((data or {}).get("rss_items"))
        reason = ("今日 RSS 未取得，無素材可摘要" if not had_rss
                  else "Gemini 未回應或回覆格式未解析")
        miss_st = ParagraphStyle("gdigestmiss", fontName=FONT_CJK, fontSize=7.5,
                                 leading=10, textColor=T.TEXT_MUTED)
        story.append(Paragraph(en("<b>🤖 AI 智庫摘要（Gemini 即時萃取）</b>"), s["h1"]))
        story.append(Paragraph(en(
            f"本次未生成（{reason}）——三段式論述暫缺，請參閱下方各領域卡片；"
            "下次排程將自動重試。"), miss_st))
        story.append(Spacer(1, 8))

    # Trend table with (單位) labels
    if trends.get("domains"):
        trend_st = ParagraphStyle("gtrend", fontName=FONT_CJK, fontSize=7.8,
                                  leading=10, textColor=T.TEXT_BODY)
        trend_hdr = ParagraphStyle("gtrendh", fontName=FONT_CJK, fontSize=8.0,
                                   leading=10, textColor=T.WHITE)

        story.append(Paragraph(en("<b>📈 領域熱度（本週 vs 上週，單位：則）</b>"), s["h1"]))
        dom_names = {d[0]: d[1] for d in DOMAINS}
        dom_rows = [[
            Paragraph(en("<b>領域</b>", color="#FFFFFF"), trend_hdr),
            Paragraph(en("<b>本週（則）</b>", color="#FFFFFF"), trend_hdr),
            Paragraph(en("<b>上週（則）</b>", color="#FFFFFF"), trend_hdr),
            Paragraph(en("<b>變化</b>", color="#FFFFFF"), trend_hdr),
        ]]
        for dom_tag, info in trends["domains"].items():
            zh = dom_names.get(dom_tag, dom_tag)
            tw, lw = info["this_week"], info["last_week"]
            pct = info.get("change_pct")
            if pct is None or lw < 3:
                pct_str = "🆕 新增" if tw > 0 else "—"
                color = T.TEXT_MUTED
            else:
                arrow = "↑" if pct > 0 else ("↓" if pct < 0 else "→")
                capped = min(abs(pct), 500)
                pct_str = f"{arrow} {capped:.0f}%" + ("+" if abs(pct) > 500 else "")
                color = "#2E8B4F" if pct > 0 else ("#D64545" if pct < 0 else T.TEXT_MUTED)
            dom_rows.append([
                Paragraph(en(zh), trend_st),
                Paragraph(en(f"<b>{tw}</b>"), trend_st),
                Paragraph(en(str(lw)), trend_st),
                Paragraph(en(f'<font color="{color}"><b>{pct_str}</b></font>'), trend_st),
            ])
        t_trend = Table(dom_rows, colWidths=[200, 80, 80, 187])
        t_trend.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), T.NAVY),
            ('GRID', (0, 0), (-1, -1), 0.4, T.BORDER),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 1), (-1, -1), T.BG_CARD),
            ('PADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(t_trend)
        story.append(Spacer(1, 8))

        # Bar chart: domain distribution
        story.append(Paragraph(en("<b>📊 資料檢索分布（本週文章數）</b>"), s["h1"]))
        ramp_map = {d[0]: d[4] for d in DOMAINS}
        this_week_counts = {dt: info["this_week"] for dt, info in trends["domains"].items()}
        bar = _bar_chart(this_week_counts, ramp_map, s)
        if bar:
            story.append(bar)
        story.append(Spacer(1, 6))

        # Trending keywords — two-column list (emoji glyphs like 🔥/📈 render
        # as .notdef boxes in the bundled CJK fonts, so use colored ▲/● text
        # markers instead).
        kw_list = trends.get("keywords") or []
        if kw_list:
            kw_style = ParagraphStyle("gkw", fontName=FONT_CJK, fontSize=8.2,
                                      leading=11.5, textColor=T.TEXT_BODY)
            kw_cells = []
            for k in kw_list[:8]:
                hot = k.get("change", 0) >= 8
                mark_color = "#EF6F53" if hot else "#0E7C86"
                mark = "▲" if hot else "●"
                kw_cells.append(
                    f'<font color="{mark_color}"><b>{mark}</b></font> '
                    f"<b>{k['keyword']}</b>　本週 {k.get('this_week', '?')} 則"
                    f'（<font color="{mark_color}">+{k.get("change", 0)}</font>）')
            half = (len(kw_cells) + 1) // 2
            rows = [[Paragraph(en(kw_cells[i]), kw_style),
                     Paragraph(en(kw_cells[i + half]), kw_style) if i + half < len(kw_cells) else ""]
                    for i in range(half)]
            kw_table = Table(rows, colWidths=[T.PRINTABLE_WIDTH / 2] * 2)
            kw_table.setStyle(TableStyle([
                ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, T.RULE),
            ]))
            story.append(Paragraph(en("<b>發燒關鍵字（本週 vs 上週）</b>"), s["h1"]))
            story.append(kw_table)

    # ============ P2-P7: Domain pages (6 compact cards each) ============
    for idx, (domain_tag, domain_zh, domain_en, category, ramp) in enumerate(DOMAINS):
        story.append(PageBreak())
        base = colors.HexColor(ramp[2])
        story.extend(make_title_row(
            f"{category}　{domain_zh}", domain_en, date_str, base, s,
            eyebrow_text=EYEBROW))

        live_items = retrieval_data.get(domain_tag, [])

        # LLM three-part (one batched call per page)
        dynamic_tp = None
        if use_llm and live_items:
            topics_for_llm = [
                (_source_display(it.get("source", "")),
                 _strip_html(it.get("title", ""))[:60],
                 _strip_html(it.get("summary", ""))[:200])
                for it in live_items[:6]
            ]
            dynamic_tp = llm.summarize_topics_what_why_sowhat(
                topics_for_llm, domain_label=domain_zh)

        cards_shown = 0
        for i, item in enumerate(live_items[:6]):
            tp = dynamic_tp[i] if dynamic_tp and i < len(dynamic_tp) else None
            story.append(_rss_card(item, ramp, s, three_part=tp, compact=True))
            story.append(Spacer(1, 2))
            cards_shown += 1

        if cards_shown < 6:
            fallback = EDITORIAL_FALLBACK.get(domain_tag, [])
            for org, focus, when, analysis in fallback[:6 - cards_shown]:
                story.append(_topic_card(org, focus, when, [analysis], ramp, s, compact=True))
                story.append(Spacer(1, 2))
                cards_shown += 1

        n_live = min(len(live_items), 6)
        src_note = (f"📡 {n_live} 則即時 RSS" +
                    (f" + {6 - n_live} 則編輯精選" if n_live < 6 else "")) if live_items else "📚 編輯精選"
        story.append(Spacer(1, 3))
        story.append(Paragraph(en(f"<i>{src_note}</i>"),
                               ParagraphStyle("gsrcnote", fontName=FONT_CJK, fontSize=7.5,
                                              leading=10, textColor=T.TEXT_MUTED,
                                              alignment=2)))

    doc = new_doc(filename, title=title,
                 keywords="global intelligence, geopolitics, macro, AI, biotech, hardware, aerospace, quantum, daily report, RSS, retrieval")
    doc.build(story, onFirstPage=footer_factory(DISCLAIMER, 7),
              onLaterPages=footer_factory(DISCLAIMER, 7))
    print("PDF build complete:", filename)
    return filename


if __name__ == "__main__":
    out = os.path.join(_REPO_ROOT, "output", "Global_Intelligence_每日產業局勢報告.pdf")
    build_global_pdf(out, date_str="2026-08-26")
