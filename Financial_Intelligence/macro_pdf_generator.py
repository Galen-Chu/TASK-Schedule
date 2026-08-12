#!/usr/bin/env python3
"""Financial Intelligence — Monthly Macro Digest PDF generator.

Distinct from the daily report: this is a slower, monthly/quarterly cadence
view of structural macro indicators (CPI, Core PCE proxy, unemployment, NFP,
yield curve, PMI) sourced from keyless BLS + Treasury feeds. Layout is a
single-page indicator scorecard.
"""
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from reportlab.lib import colors
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from core import design_tokens as T
from core.pdf_engine import en, standard_styles, make_title_row, footer_factory, new_doc

DISCLAIMER = "Monthly Macro Digest — 月度總經指標快照，僅供研究參考，不構成投資建議。"


def _g(d, k, default="—"):
    return (d or {}).get(k, default)


def build_macro_pdf(filename, data=None, date_str=None, period_label=None):
    """Build the monthly Macro Digest PDF. Returns ``filename``."""
    data = data or {}
    date_str = date_str or data.get("date") or "2026-08"
    s = standard_styles()
    story = []

    label = period_label or f"{date_str[:7]} 月度總經快照"
    story.extend(make_title_row(
        "Financial Intelligence — Monthly Macro Digest",
        f"{label}（與每日投資趨勢報告區隔；月頻公佈指標）",
        date_str, T.GOLD, s,
    ))

    story.append(Paragraph(en("<b>【當月總經體檢】核心指標計分卡 (Monthly Macro Scorecard)</b>"), s["h1"]))

    cpi = _g(data, "cpi_headline")
    cpi_core = _g(data, "cpi_core")
    unemp = _g(data, "unemployment")
    nfp = _g(data, "nfp")
    tyc = data.get("treasury") or {}

    def val(rec, suffix=""):
        if rec is None:
            return "—"
        if isinstance(rec, dict):
            return f"{rec.get('value','—')}{suffix}  ({rec.get('period_name','')} {rec.get('year','')})"
        return f"{rec}{suffix}"

    rows = [
        [Paragraph(en("<b>指標</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>最新值</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>趨勢判讀</b>", color="#FFFFFF"), s["th"])],
        [Paragraph(en("CPI（頭條通膨）"), s["body"]),
         Paragraph(en(val(cpi), bold=True), s["body"]),
         Paragraph(en("Fed 2% 目標的頭條觀察值；持續降溫有利降息路徑。"), s["body"])],
        [Paragraph(en("Core CPI（核心通膨）"), s["body"]),
         Paragraph(en(val(cpi_core), bold=True), s["body"]),
         Paragraph(en("扣除食品能源；Fed 更看重的黏性指標。"), s["body"])],
        [Paragraph(en("失業率 (Unemployment)"), s["body"]),
         Paragraph(en(val(unemp, "%"), bold=True), s["body"]),
         Paragraph(en("升破 4.2% 觸發薩姆規則 (Sahm Rule) 衰退警訊。"), s["body"])],
        [Paragraph(en("非農就業 (NFP)"), s["body"]),
         Paragraph(en(val(nfp, " 千"), bold=True), s["body"]),
         Paragraph(en("月增 < 10 萬顯示勞動市場降溫；軟著陸關鍵。"), s["body"])],
        [Paragraph(en("殖利率曲線 (2Y / 10Y / 利差)"), s["body"]),
         Paragraph(en(f"2Y {tyc.get('2y','—')}% / 10Y {tyc.get('10y','—')}% / 利差 {tyc.get('spread_10y2y','—')}%", bold=True), s["body"]),
         Paragraph(en("利差回正為經濟正常化訊號；倒掛已久後回正常伴隨降息。"), s["body"])],
    ]
    t = Table(rows, colWidths=[140, 180, T.PRINTABLE_WIDTH - 320])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), T.NAVY),
        ('FONTNAME', (0, 0), (-1, -1), s["body"].fontName),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, T.BORDER),
        ('BACKGROUND', (0, 1), (-1, -1), T.BG_CARD),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story += [t, Spacer(1, 12)]

    source = data.get("_source", "—")
    story.append(Paragraph(en(f"<i>資料來源：{source}（keyless BLS + U.S. Treasury）。指標為月/季頻公佈，故採月度排程。</i>"), s["body"]))

    doc = new_doc(filename, title="Financial Intelligence Monthly Macro Digest")
    doc.build(story, onFirstPage=footer_factory(DISCLAIMER),
              onLaterPages=footer_factory(DISCLAIMER))
    print("Macro PDF build complete:", filename)
    return filename


if __name__ == "__main__":
    out = os.path.join(_REPO_ROOT, "output", "Financial_Intelligence_Monthly_Macro_Digest.pdf")
    build_macro_pdf(out, date_str="2026-08")
