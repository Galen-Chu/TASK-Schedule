#!/usr/bin/env python3
"""Global Intelligence — PDF report generator (6-page A4, dynamic cards).

Each page is one domain rendered as a stack of **dynamic topic cards**
pulled live from the retrieval corpus (5 per page = the primary content).
Editorial fallback cards are shown only when the corpus has insufficient
items for a domain. The 6th domain (aerospace) covers aviation & space.

When a Gemini key is configured each topic's editorial analysis is distilled
into a What/Why/So-What structure; otherwise the RSS summary is shown.

Built on the shared core (:mod:`core.pdf_engine`, :mod:`core.design_tokens`).
Domain colours come from the Typography-Guide brand ramps.
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

# ---- Domain definitions (tag, zh, en, category, ramp, editorial_fallback) ----
# Editorial fallbacks are used ONLY when the retrieval corpus has < 5 items
# for a domain. They mirror the original PAGES data but serve as backup.
DOMAINS = [
    ("geopolitics", "地緣政治與國際關係", "Geopolitics & International Relations", "Category 01", T.RAMP_INK),
    ("macro", "巨觀經濟與金融市場", "Macroeconomics & Financial Markets", "Category 02", T.RAMP_AMBER),
    ("it_ai", "資訊科技與人工智慧", "IT, AI & Semiconductors", "Category 03", T.RAMP_TEAL),
    ("biotech", "生物科技與健康醫療", "Biotech & Healthcare", "Category 04", T.RAMP_SAGE),
    ("hardware", "硬體工程、自動化與能源轉型", "Hardware, Automation & Energy", "Category 05", T.RAMP_CORAL),
    ("aerospace", "航空太空與量子科技", "Aerospace & Quantum Technology", "Category 06", T.RAMP_INDIGO),
]

# Editorial fallback content (org, focus, time, analysis) — used when the
# retrieval corpus is empty or has fewer than 5 items for a domain.
EDITORIAL_FALLBACK = {
    "geopolitics": [
        ["CSIS", "中朝關係重組研討會", "2026-08-10 09:00 EDT", "CSIS 舉辦專題研討會剖析東北亞安全新格局。"],
        ["The Conference Board", "近岸與友岸外包加速", "2026-08-06 18:00 EST", "美國關稅政策新規常態化，製造業供應鏈加速向東南亞與拉美近岸轉移。"],
        ["國防院 (INDSR)", "印太安全與供應鏈保全", "2026-08-08 10:00 TST", "評估紅海航道干擾與台海安全，建議企業提高安全存貨水準。"],
        ["中經院 (CIER)", "地緣政治對台商投資影響", "2026-08-07 15:30 TST", "分析關稅合規與地緣風險，建議跨國企業建立多區域備援供應鏈。"],
    ],
    "macro": [
        ["歐洲央行 (ECB)", "最新貨幣通報與通膨警告", "2026-08-06 10:00 CEST", "ECB 指出歐元區頭條通膨雖受控制，但能源波動仍存。"],
        ["Mohamed El-Erian", "全球央行政策分化分析", "2026-08-09 21:00 EST", "成熟與新興市場經濟復甦步調不一，資本跨國流動敏感度提升。"],
        ["台經院 (TIER)", "台灣宏觀經濟與出口展望", "2026-08-08 11:00 TST", "受惠 AI 與伺服器拉貨強勁，出口動能維持高檔。"],
        ["中央銀行 (CBC)", "貨幣政策與流動性分析", "2026-08-07 16:30 TST", "維持適度緊縮貨幣立場，密切監控不動產信用風險。"],
    ],
    "it_ai": [
        ["TSMC / Motley Fool", "超預期算力帶動 640 億 Capex", "2026-08-09 08:30 EST", "台積電擴大 640 億美元資本支出，加速 2nm 與 CoWoS 先進封裝擴產。"],
        ["NVIDIA / Design&Reuse", "AI 演算法深入晶圓廠良率控制", "2026-08-08 11:00 EST", "NVIDIA 與台積電合作將 AI 檢測演算法導入晶圓廠。"],
        ["工研院 (ITRI ISTI)", "3D Chiplet 與 HBM4 封裝趨勢", "2026-08-08 14:00 TST", "單晶片微縮極限顯現，晶片競賽轉向 3D 堆疊與 SiP。"],
        ["資策會 (MIC)", "AI Agent 商業落地與 ROI 評估", "2026-08-07 10:30 TST", "企業 AI 應用從 PoC 轉向 ROI 驗證，軟體自動化代理需求爆發。"],
    ],
    "biotech": [
        ["U.S. FDA / Endpoints", "Pilot Plan 試點加速計畫推動", "2026-08-07 06:38 EST", "FDA 啟動試點加速計畫，縮短新藥上市週期 15%~20%。"],
        ["Eli Lilly / PR Newswire", "Olomorasib 獲突破性療法認證", "2026-08-03 09:00 EST", "禮來 KRAS G12C 新藥獲 FDA 突破性療法認證。"],
        ["國衛院 (NHRI)", "抗體藥物複合體 (ADC) 研發", "2026-08-08 10:00 TST", "精準腫瘤學標靶藥物突破，國內生技團隊取得專利進展。"],
        ["生技中心 (DCB)", "CDMO 委託開發製造量能", "2026-08-07 14:30 TST", "推動核酸藥物與細胞治療 CDMO 產線國際認證。"],
    ],
    "hardware": [
        ["U.S. DOE / NCSL", "8 月 SMR 核能創新園區名單", "2026-08-08 12:00 EST", "美國能源部啟動核能生命週期園區計畫，加速 SMR 商業化。"],
        ["Cambridge EnerTech", "固態電池與人形機器人應用", "2026-08-09 09:00 EST", "固態電池高峰會聚焦人形機器人高能量密度需求。"],
        ["國研院 (NARLabs)", "工業 4.0 智慧感測與自動化", "2026-08-08 11:30 TST", "研發次世代高精度物理量感測器。"],
        ["工研院綠能所 (GEL)", "智慧電網與長時儲能 (LDES)", "2026-08-07 16:00 TST", "數據中心高算力倒逼區域電網升級。"],
    ],
    "aerospace": [
        ["NASA", "Artemis II 月球任務進展", "2026-08-20 10:00 EST", "NASA 載人繞月任務持續推進，SLS 火箭與 Orion 太空船整合測試。"],
        ["SpaceNews", "Starship 第五次試飛與商業發射", "2026-08-22 08:00 EST", "SpaceX Starship 筷子夾火箭回收成功，商業發射成本大幅下降。"],
        ["IBM Quantum", "量子錯誤修正里程碑", "2026-08-21 14:00 EST", "IBM 發表 1,000+ qubit 量子處理器，錯誤修正碼實用化進程加速。"],
        ["The Quantum Insider", "後量子密碼學標準化", "2026-08-19 11:00 EST", "NIST 後量子密碼學標準正式定案，金融與國防體系啟動遷移時程。"],
        ["Ars Technica", "量子網際網路原型", "2026-08-18 14:00 EST", "量子糾纏分發距離突破 1,000 公里，量子通訊基礎設施邁向實用。"],
        ["Aviation Week", "電動航空與 eVTOL 變局", "2026-08-21 09:00 EST", "電動垂直起降飛機認證進度加速，2030 年城市空中交通市場可期。"],
    ],
}


_TAG_RE = re.compile(r"<[^>]+>")

# Domain → clean source name (for the card badge). Falls back to extracting
# the second-level domain (e.g., feeds.bbci.co.uk → BBC, search.cnbc.com → CNBC).
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
    "www.reddit.com": "REDDIT",
}

def _source_display(url_or_domain):
    """Map a source URL/domain to a clean organization name."""
    try:
        netloc = _urlparse(url_or_domain).netloc if "://" in url_or_domain else url_or_domain
    except Exception:
        netloc = url_or_domain
    netloc = (netloc or "").lower().strip()
    if netloc in _SOURCE_NAMES:
        return _SOURCE_NAMES[netloc]
    # Fallback: extract the recognizable part (skip subdomains like www./feeds./search.)
    parts = netloc.replace("www.", "").split(".")
    # Take the first non-generic part (skip feeds, search, news, www)
    generic = {"feeds", "search", "news", "www", "rss", "feed"}
    for p in parts:
        if p not in generic and len(p) > 2:
            return p.upper()
    return (parts[0] if parts else "RSS").upper()


def _strip_html(text):
    """Remove HTML tags + unescape entities from RSS summaries (ReportLab-safe)."""
    if not text:
        return ""
    cleaned = _TAG_RE.sub(" ", text)
    cleaned = _html_unescape(cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _format_rss_time(item):
    """Format the article's PUBLISHED date (not when we fetched it)."""
    # Try published (from RSS feed, article's actual date)
    pub = item.get("published", "")
    if pub:
        # RFC 2822 format: "Mon, 25 Aug 2026 08:00:00 GMT"
        try:
            from email.utils import parsedate_to_datetime as _pdt
            dt = _pdt(pub)
            return dt.astimezone(_TZ).strftime("%m-%d %H:%M")
        except Exception:
            pass
        # ISO format
        try:
            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            return dt.astimezone(_TZ).strftime("%m-%d %H:%M")
        except Exception:
            pass
    # Fallback to fetched_at (when our pipeline ran)
    fa = item.get("fetched_at", "")
    try:
        dt = datetime.fromisoformat(fa)
        return dt.astimezone(_TZ).strftime("%m-%d %H:%M")
    except (ValueError, TypeError):
        return (pub or "—")[:16]


def _rss_card(item, ramp, styles, three_part=None):
    """Render a retrieval item as a topic card (dynamic content).

    ``three_part``: optional {what, why, so_what} dict from Gemini. When present,
    renders the three-part analysis instead of the raw RSS summary.
    """
    org_display = _source_display(item.get("source", ""))
    focus = _strip_html(item.get("title", ""))[:80]
    when = _format_rss_time(item)
    summary = _strip_html(item.get("summary", ""))[:200] or focus
    link = item.get("link", "")

    body = _three_part_paras(three_part) if three_part else [summary]
    return _topic_card(org_display, focus, when, body, ramp, styles, url=link)


def _topic_card(org, focus, when, body_flowables, ramp, styles, url=None):
    """One topic as a card: linked source badge + metadata, focus title, body."""
    base = colors.HexColor(ramp[2])
    tint = colors.HexColor(ramp[0])
    dark = colors.HexColor(ramp[3])

    meta_st = ParagraphStyle("gmeta", fontName=FONT_CJK, fontSize=7.8, leading=10,
                             textColor=T.TEXT_MUTED, alignment=2)
    title_st = ParagraphStyle("gtitle", fontName=FONT_CJK, fontSize=9.2, leading=12.0,
                              textColor=dark, spaceBefore=1, spaceAfter=1)
    body_st = ParagraphStyle("gbody", fontName=FONT_CJK, fontSize=8.0, leading=10.0,
                             textColor=T.TEXT_BODY)

    inner = T.PRINTABLE_WIDTH - 16
    org_html = (f'<a href="{url}" color="#FFFFFF"><u><b>{org}</b></u></a>'
                if url else f"<b>{org}</b>")
    badge = Table(
        [[Paragraph(en(org_html, color="#FFFFFF"),
                    ParagraphStyle("gbadge", fontName=FONT_CJK, fontSize=8.2,
                                   leading=10, textColor=T.WHITE))]],
        colWidths=[inner - 140],
    )
    badge.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), base),
        ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    header = Table([[badge, Paragraph(en(f"🕒 {when}"), meta_st)],
                    [Paragraph(en(f"<b>{focus}</b>"), title_st), ""]],
                   colWidths=[inner - 140, 140])
    header.setStyle(TableStyle([
        ('BACKGROUND', (1, 0), (1, 0), tint),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('SPAN', (0, 1), (1, 1)),
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 0), ('BOTTOMPADDING', (0, 0), (-1, 0), 2),
        ('TOPPADDING', (0, 1), (-1, 1), 2),
    ]))

    rows = [[header]] + [[Paragraph(en(b), body_st)] for b in body_flowables]
    card = Table(rows, colWidths=[T.PRINTABLE_WIDTH])
    card.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), tint),
        ('BOX', (0, 0), (-1, -1), 0.5, T.BORDER),
        ('LINEBEFORE', (0, 0), (0, -1), 3, base),
        ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    return card


def _three_part_paras(tp):
    """Format a {what,why,so_what} dict as three labeled paragraphs."""
    return [
        f"<b><font color='#0E7C86'>What</font>（事實概要）</b> {tp['what']}",
        f"<b><font color='#0E7C86'>Why</font>（脈絡影響）</b> {tp['why']}",
        f"<b><font color='#0E7C86'>So What</font>（台灣啟示）</b> {tp['so_what']}",
    ]


def build_global_pdf(filename, data=None, date_str=None):
    """Build the 6-page Global PDF with dynamic topic cards."""
    date_str = date_str or (data or {}).get("date") or "2026-08-25"
    s = standard_styles()
    story = []
    title = "Global Intelligence 每日產業局勢報告"
    EYEBROW = "Global Intelligence"
    use_llm = llm.is_available()
    retrieval_data = (data or {}).get("retrieval", {})

    # Optional report-level AI digest card (from RSS, when a key is set).
    digest = (data or {}).get("llm_digest")
    if digest:
        digest_st = ParagraphStyle("gdigest", fontName=FONT_CJK, fontSize=8.0,
                                   leading=10.4, textColor=T.TEXT_BODY)
        story.extend(make_title_row(
            "每日產業局勢報告",
            "AI 智庫摘要（Gemini）＋ 六大領域即時情報速讀",
            date_str, T.GOLD, s, eyebrow_text=EYEBROW))
        story.append(Paragraph(en("<b>AI 智庫摘要（Gemini 即時萃取）</b>"), s["h1"]))
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

    for idx, (domain_tag, domain_zh, domain_en, category, ramp) in enumerate(DOMAINS):
        if idx > 0:
            story.append(PageBreak())
        base = colors.HexColor(ramp[2])
        if idx == 0 and digest:
            story.append(Paragraph(en(f"<b>{category}　{domain_zh}</b>　·　{domain_en}"),
                                   ParagraphStyle("gsecmark", fontName=FONT_CJK, fontSize=9,
                                                  leading=12, textColor=base,
                                                  spaceBefore=4, spaceAfter=4)))
        else:
            story.extend(make_title_row(
                f"{category}　{domain_zh}", domain_en, date_str, base, s,
                eyebrow_text=EYEBROW))

        # Pull live items from retrieval (primary content)
        live_items = retrieval_data.get(domain_tag, [])

        # LLM three-part analysis for dynamic cards (one batched call per page)
        dynamic_tp = None
        if use_llm and live_items:
            topics_for_llm = [
                (_source_display(it.get("source", "")),
                 _strip_html(it.get("title", ""))[:60],
                 _strip_html(it.get("summary", ""))[:200])
                for it in live_items[:5]
            ]
            dynamic_tp = llm.summarize_topics_what_why_sowhat(
                topics_for_llm, domain_label=domain_zh)

        # Build 5 cards: dynamic first, editorial fallback fills the gap
        cards_shown = 0
        for i, item in enumerate(live_items[:5]):
            tp = dynamic_tp[i] if dynamic_tp and i < len(dynamic_tp) else None
            story.append(_rss_card(item, ramp, s, three_part=tp))
            story.append(Spacer(1, 3))
            cards_shown += 1

        # Fill remaining slots with editorial fallback (+ LLM if available)
        if cards_shown < 5:
            fallback = EDITORIAL_FALLBACK.get(domain_tag, [])
            fallback_rows = fallback[:5 - cards_shown]
            fallback_tp = None
            if use_llm and fallback_rows:
                fallback_tp = llm.summarize_topics_what_why_sowhat(
                    [(o, f, a) for (o, f, _w, a) in fallback_rows],
                    domain_label=domain_zh)
            for j, (org, focus, when, analysis) in enumerate(fallback_rows):
                tp = fallback_tp[j] if fallback_tp and j < len(fallback_tp) else None
                body = _three_part_paras(tp) if tp else [analysis]
                story.append(_topic_card(org, focus, when, body, ramp, s))
                story.append(Spacer(1, 3))
                cards_shown += 1

        # Source indicator: dynamic vs editorial
        if live_items:
            n_live = min(len(live_items), 5)
            source_note = f"📡 {n_live} 則即時 RSS" + (f" + {5 - n_live} 則編輯精選" if n_live < 5 else "")
        else:
            source_note = "📚 編輯精選（語料庫累積中）"
        story.append(Spacer(1, 4))
        story.append(Paragraph(en(f"<i>{source_note}</i>"),
                               ParagraphStyle("gsrcnote", fontName=FONT_CJK, fontSize=7.5,
                                              leading=10, textColor=T.TEXT_MUTED,
                                              alignment=2)))

    doc = new_doc(filename, title=title)
    doc.build(story, onFirstPage=footer_factory(DISCLAIMER),
              onLaterPages=footer_factory(DISCLAIMER))
    print("PDF build complete:", filename)
    return filename


if __name__ == "__main__":
    out = os.path.join(_REPO_ROOT, "output", "Global_Intelligence_每日產業局勢報告.pdf")
    build_global_pdf(out, date_str="2026-08-25")
