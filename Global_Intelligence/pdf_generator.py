#!/usr/bin/env python3
"""Global Intelligence — PDF report generator (5-page A4).

Each page is one domain rendered as a stack of **topic cards** (2
international + 2 domestic think tanks), per the Design Spec: a source badge,
two-row metadata, a bold focus title, and a What/Why/So-What body. When a
Gemini key is configured each topic's editorial analysis is distilled into the
three-part structure; otherwise the raw analysis paragraph is shown.

Built on the shared core (:mod:`core.pdf_engine`, :mod:`core.design_tokens`).
Domain colours come from the Typography-Guide brand ramps, so every domain
reads as part of the same family.
"""
import os
import sys

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

# Editorial source homepages — used for the clickable source badge on each card.
_ORG_URLS = {
    "CSIS": "https://www.csis.org",
    "The Conference Board": "https://www.conference-board.org",
    "國防院 (INDSR)": "https://www.indsr.org.tw",
    "中經院 (CIER)": "https://www.cier.edu.tw",
    "歐洲央行 (ECB)": "https://www.ecb.europa.eu",
    "Mohamed El-Erian": "https://www.project-syndicate.org",
    "台經院 (TIER)": "https://www.tier.org.tw",
    "中央銀行 (CBC)": "https://www.cbc.gov.tw",
    "TSMC / Motley Fool": "https://www.fool.com",
    "NVIDIA / Design&Reuse": "https://www.designreuse.com",
    "工研院 (ITRI ISTI)": "https://www.itri.org.tw",
    "資策會 (MIC)": "https://mic.iii.org.tw",
    "U.S. FDA / Endpoints": "https://endpts.com",
    "Eli Lilly / PR Newswire": "https://www.prnewswire.com",
    "國衛院 (NHRI)": "https://www.nhri.org.tw",
    "生技中心 (DCB)": "https://www.dcb.org.tw",
    "U.S. DOE / NCSL": "https://www.energy.gov",
    "Cambridge EnerTech": "https://www.informaconnect.com",
    "國研院 (NARLabs)": "https://www.narlabs.org.tw",
    "工研院綠能所 (GEL)": "https://www.itri.org.tw",
}

# ---- Editorial content: (domain_tag, domain_zh, domain_en, category, ramp, rows)
# domain_tag links each page to the retrieval layer's classify_domain tags.
# ramp = [tint, light, base, dark, darkest]; base is the domain accent.
# rows = [org, focus, time, analysis]
PAGES = [
    ("geopolitics", "地緣政治與國際關係", "Geopolitics & International Relations", "Category 01", T.RAMP_INK, [
        ["CSIS", "中朝關係重組研討會", "2026-08-10 09:00 EDT", "CSIS 舉辦專題研討會剖析東北亞安全新格局。大國博弈加劇，供應鏈韌性建置與友岸外包 (Friendshoring) 需求提升。"],
        ["The Conference Board", "近岸與友岸外包加速", "2026-08-06 18:00 EST", "美國關稅政策新規常態化，製造業供應鏈加速向東南亞與拉美近岸轉移，合規門檻提高。"],
        ["國防院 (INDSR)", "印太安全與供應鏈保全", "2026-08-08 10:00 TST", "評估紅海航道干擾與台海安全，建議企業提高安全存貨水準以因應物流延遲。"],
        ["中經院 (CIER)", "地緣政治對台商投資影響", "2026-08-07 15:30 TST", "分析關稅合規與地緣風險，建議跨國企業建立多區域備援供應鏈。"],
    ]),
    ("macro", "巨觀經濟與金融市場", "Macroeconomics & Financial Markets", "Category 02", T.RAMP_AMBER, [
        ["歐洲央行 (ECB)", "最新貨幣通報與通膨警告", "2026-08-06 10:00 CEST", "ECB 指出歐元區頭條通膨雖受控制，但能源波動仍存。主要央行延後大幅降息，高利率 Higher for Longer 成為常態。"],
        ["Mohamed El-Erian", "全球央行政策分化分析", "2026-08-09 21:00 EST", "成熟與新興市場經濟復甦步調不一，資本跨國流動敏感度提升，投資人應增加防禦性資產配置。"],
        ["台經院 (TIER)", "台灣宏觀經濟與出口展望", "2026-08-08 11:00 TST", "受惠 AI 與伺服器拉貨強勁，出口動能維持高檔，景氣黃紅燈展現內外需強勁韌性。"],
        ["中央銀行 (CBC)", "貨幣政策與流動性分析", "2026-08-07 16:30 TST", "維持適度緊縮貨幣立場，密切監控不動產信用風險與通膨預期。"],
    ]),
    ("it_ai", "資訊科技與人工智慧", "IT, AI & Semiconductors", "Category 03", T.RAMP_TEAL, [
        ["TSMC / Motley Fool", "超預期算力帶動 640 億 Capex", "2026-08-09 08:30 EST", "台積電擴大 640 億美元資本支出，加速 2nm 與 CoWoS 先進封裝擴產，鞏固台灣半導體戰略龍頭地位。"],
        ["NVIDIA / Design&Reuse", "AI 演算法深入晶圓廠良率控制", "2026-08-08 11:00 EST", "NVIDIA 與台積電合作將 AI 檢測演算法導入晶圓廠，進行複雜奈米晶圓缺陷檢測，大幅提升生產良率。"],
        ["工研院 (ITRI ISTI)", "3D Chiplet 與 HBM4 封裝趨勢", "2026-08-08 14:00 TST", "單晶片微縮極限顯現，晶片競賽轉向 3D 堆疊、HBM 高頻寬記憶體與系統級封裝 (SiP)。"],
        ["資策會 (MIC)", "AI Agent 商業落地與 ROI 評估", "2026-08-07 10:30 TST", "企業 AI 應用從 PoC 概念驗證轉向算力投資回報率 (ROI) 驗證，軟體自動化代理需求爆發。"],
    ]),
    ("biotech", "生物科技與健康醫療", "Biotech & Healthcare", "Category 04", T.RAMP_SAGE, [
        ["U.S. FDA / Endpoints", "Pilot Plan 試點加速計畫推動", "2026-08-07 06:38 EST", "FDA 正式啟動試點加速計畫，開放最多 10 個核心臨床專案簡化行政審查，縮短新藥上市週期 15%~20%。"],
        ["Eli Lilly / PR Newswire", "Olomorasib 獲突破性療法認證", "2026-08-03 09:00 EST", "禮來 KRAS G12C 突變晚期胰臟癌新藥獲得 FDA 突破性療法認證 (Breakthrough Designation)，帶動生醫價值重估。"],
        ["國衛院 (NHRI)", "抗體藥物複合體 (ADC) 研發", "2026-08-08 10:00 TST", "精準腫瘤學標靶藥物突破，國內生技團隊於 ADC 鏈結技術與 Biomarkers 生物標記取得專利進展。"],
        ["生技中心 (DCB)", "CDMO 委託開發製造量能", "2026-08-07 14:30 TST", "推動核酸藥物與細胞治療 CDMO 產線國際認證，打造台灣成為亞洲生技製造樞紐。"],
    ]),
    ("hardware", "硬體工程、自動化與能源轉型", "Hardware, Automation & Energy", "Category 05", T.RAMP_CORAL, [
        ["U.S. DOE / NCSL", "8 月 SMR 核能創新園區名單", "2026-08-08 12:00 EST", "美國能源部啟動核能生命週期園區計畫，加速小型模組化反應爐 (SMR) 商業化，滿足 AI 數據中心零碳電力。"],
        ["Cambridge EnerTech", "固態電池與人形機器人應用", "2026-08-09 09:00 EST", "固態電池高峰會聚焦人形機器人高能量密度與高放電倍率需求，次世代電池決定自動化商業落地進程。"],
        ["國研院 (NARLabs)", "工業 4.0 智慧感測與自動化", "2026-08-08 11:30 TST", "研發次世代高精度物理量感測器，強化國產自動化設備在極端環境下之穩定度。"],
        ["工研院綠能所 (GEL)", "智慧電網與長時儲能 (LDES)", "2026-08-07 16:00 TST", "數據中心高算力倒逼區域電網升級，推動 AI 智慧電池管理系統 (AI-BMS) 與地熱能供電合約。"],
    ]),
]


def _topic_card(org, focus, when, body_flowables, ramp, styles, url=None):
    """One think-tank topic as a card: linked source badge + metadata, focus title, body."""
    base = colors.HexColor(ramp[2])    # domain accent
    tint = colors.HexColor(ramp[0])    # light card fill
    dark = colors.HexColor(ramp[3])    # emphasis

    meta_st = ParagraphStyle("gmeta", fontName=FONT_CJK, fontSize=7.8, leading=10,
                             textColor=T.TEXT_MUTED, alignment=2)
    title_st = ParagraphStyle("gtitle", fontName=FONT_CJK, fontSize=9.8, leading=13,
                              textColor=dark, spaceBefore=2, spaceAfter=3)
    body_st = ParagraphStyle("gbody", fontName=FONT_CJK, fontSize=8.3, leading=11.8,
                             textColor=T.TEXT_BODY)

    # Header row: linked org badge (accent fill, white) + publish time (right-aligned)
    org_html = (f'<a href="{url}" color="#FFFFFF"><u><b>{org}</b></u></a>'
                if url else f"<b>{org}</b>")
    badge = Table(
        [[Paragraph(en(org_html, color="#FFFFFF"),
                    ParagraphStyle("gbadge", fontName=FONT_CJK, fontSize=8.2,
                                   leading=10, textColor=T.WHITE))]],
        colWidths=[T.PRINTABLE_WIDTH - 150],
    )
    badge.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), base),
        ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    header = Table([[badge, Paragraph(en(f"🕒 {when}"), meta_st)],
                    [Paragraph(en(f"<b>{focus}</b>"), title_st), ""]],
                   colWidths=[T.PRINTABLE_WIDTH - 150, 150])
    header.setStyle(TableStyle([
        ('BACKGROUND', (1, 0), (1, 0), tint),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('SPAN', (0, 1), (1, 1)),
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 0), ('BOTTOMPADDING', (0, 0), (-1, 0), 2),
        ('TOPPADDING', (0, 1), (-1, 1), 2),
    ]))

    # Wrap header + body in an outer card with tint fill + accent left stripe.
    rows = [[header]] + [[Paragraph(en(b), body_st)] for b in body_flowables]
    card = Table(rows, colWidths=[T.PRINTABLE_WIDTH])
    card.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), tint),
        ('BOX', (0, 0), (-1, -1), 0.5, T.BORDER),
        ('LINEBEFORE', (0, 0), (0, -1), 3, base),
        ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
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
    """Build the 5-page Global PDF. Returns ``filename``."""
    date_str = date_str or (data or {}).get("date") or "2026-08-11"
    s = standard_styles()
    story = []
    title = "Global Intelligence 每日產業局勢報告"
    use_llm = llm.is_available()

    # Optional report-level AI digest card (from RSS, when a key is set)
    digest = (data or {}).get("llm_digest")
    if digest:
        story.extend(make_title_row(title, "AI 智庫摘要 (Gemini 即時萃取)", date_str, T.GOLD, s))
        digest_rows = [
            [Paragraph(en("<b>WHAT（事實概要）</b>", color="#FFFFFF"), s["th"]),
             Paragraph(en(digest.get("what", ""), bold=True), s["body"])],
            [Paragraph(en("<b>WHY（脈絡影響）</b>", color="#FFFFFF"), s["th"]),
             Paragraph(en(digest.get("why", "")), s["body"])],
            [Paragraph(en("<b>SO WHAT（台灣啟示）</b>", color="#FFFFFF"), s["th"]),
             Paragraph(en(digest.get("so_what", "")), s["body"])],
        ]
        t_ai = Table(digest_rows, colWidths=[110, T.PRINTABLE_WIDTH - 110])
        t_ai.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), T.NAVY),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, T.BORDER),
            ('BACKGROUND', (1, 0), (1, -1), T.BG_CARD),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story += [t_ai, Spacer(1, 10)]

    for idx, (domain_tag, domain_zh, domain_en, category, ramp, rows) in enumerate(PAGES):
        if idx > 0 or digest:
            story.append(PageBreak())
        page_title = title if idx == 0 else f"{category}：{domain_zh}"
        subtitle = domain_en if idx == 0 else f"{category} · {domain_en}"
        base = colors.HexColor(ramp[2])
        story.extend(make_title_row(page_title, subtitle, date_str, base, s))

        # Domain label band
        band = Table(
            [[Paragraph(en(f"<b>{category}</b> 　{domain_zh}　·　{domain_en}"),
                        ParagraphStyle("gband", fontName=FONT_CJK, fontSize=9, leading=12,
                                       textColor=T.WHITE))]],
            colWidths=[T.PRINTABLE_WIDTH],
        )
        band.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), base),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story += [band, Spacer(1, 8)]

        domain_label = domain_zh
        # One batched Gemini call per page (not per topic) to respect free-tier limits
        page_tp = (llm.summarize_topics_what_why_sowhat(
            [(o, f, a) for (o, f, _w, a) in rows], domain_label=domain_label)
            if use_llm else None)
        for i, (org, focus, when, analysis) in enumerate(rows):
            tp = page_tp[i] if page_tp else None
            body = _three_part_paras(tp) if tp else [analysis]
            story.append(_topic_card(org, focus, when, body, ramp, s,
                                     url=_ORG_URLS.get(org)))
            story.append(Spacer(1, 7))

        # Supplement: live items from the retrieval layer (persistent corpus)
        live = (data or {}).get("retrieval", {}).get(domain_tag, [])
        if live:
            from urllib.parse import urlparse as _up
            story.append(Spacer(1, 6))
            story.append(Paragraph(en("<b>🔍 即時檢索補充 (Live Retrieval · 近 7 日累積)</b>"), s["h1"]))
            base = colors.HexColor(ramp[2])
            rows = [[Paragraph(en("<b>日期</b>", color="#FFFFFF"), s["th"]),
                     Paragraph(en("<b>來源</b>", color="#FFFFFF"), s["th"]),
                     Paragraph(en("<b>標題</b>", color="#FFFFFF"), s["th"])]]
            for it in live:
                day = (it.get("fetched_at") or "")[5:10] or "—"
                src = _up(it.get("source", "")).netloc or "RSS"
                title = it.get("title", "")
                link = it.get("link", "")
                txt = (f'<a href="{link}" color="#0E7C86"><u>{title}</u></a>'
                       if link else title)
                rows.append([Paragraph(en(day), s["body"]),
                             Paragraph(en(src), s["body"]),
                             Paragraph(en(txt), s["body"])])
            t_live = Table(rows, colWidths=[42, 150, T.PRINTABLE_WIDTH - 192])
            t_live.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), base),
                ('GRID', (0, 0), (-1, -1), 0.4, T.BORDER),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BACKGROUND', (0, 1), (-1, -1), T.BG_CARD),
                ('PADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(t_live)

    doc = new_doc(filename, title=title)
    doc.build(story, onFirstPage=footer_factory(DISCLAIMER),
              onLaterPages=footer_factory(DISCLAIMER))
    print("PDF build complete:", filename)
    return filename


if __name__ == "__main__":
    out = os.path.join(_REPO_ROOT, "output", "Global_Intelligence_每日產業局勢報告.pdf")
    build_global_pdf(out, date_str="2026-08-11")
