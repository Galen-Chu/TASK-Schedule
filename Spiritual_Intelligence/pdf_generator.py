#!/usr/bin/env python3
"""Spiritual Intelligence — PDF report generator (5-page A4, one page per
occult system).

Refactored onto the shared core (font registration, ``en()`` helper, master
palette) and the single-source :mod:`Spiritual_Intelligence.systems_data`, so
the scheduler, PDF and Obsidian note can no longer disagree on a day's
reading. Keeps the original 8-card vertical layout per system.
"""
import os
import sys
import datetime
import locale

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from reportlab.lib import colors
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import ParagraphStyle

from core import design_tokens as T
from core.fonts import FONT_CJK, ensure_fonts
from core.pdf_engine import en, make_title_row, footer_factory, new_doc
from Spiritual_Intelligence.systems_data import SYSTEMS_CONFIG

_DEFAULT_LOCATION = "臺北市"
_WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]


def _date_label(date_str):
    """Convert YYYY-MM-DD -> '2026-08-11 (二)' for the header line."""
    try:
        d = datetime.date.fromisoformat(date_str)
        return f"{date_str} ({_WEEKDAYS[d.weekday()]})"
    except (ValueError, TypeError):
        return date_str


def _style(name, size, color, leading=None, wrap=True):
    return ParagraphStyle(
        name, fontName=FONT_CJK, fontSize=size,
        leading=leading or size + 3, textColor=color,
        wordWrap="CJK" if wrap else None,
    )


def create_system_page(cfg, page_num, page_total, date_str, location):
    """Build the 8-card story for one occult system."""
    ensure_fonts()

    motto_st   = _style("Motto", 9.5, cfg["color_text_dark"], 14.0)
    spot_st    = _style("Spotlight", 9.0, cfg["color_highlight"], 13.0)
    param_st   = _style("SysParam", 8.5, cfg["color_primary"], 12.5)
    heading_st = _style("Section", 10.0, cfg["color_primary"], 14.0)
    dim_h_st   = _style("DimH", 8.8, cfg["color_primary"], 12.0)
    dim_b_st   = _style("DimB", 8.2, cfg["color_text_dark"], 11.8)
    harmony_st = _style("Harmony", 8.5, cfg["color_text_dark"], 12.5)

    story = []

    # 1. Header — shared title row + accent rule in this system's primary color
    story += make_title_row(
        f"Spiritual Intelligence 每日覺察運勢報告 ── {cfg['title']}",
        subtitle_text=f"地點：{location}　|　副標題：{cfg['subtitle']}",
        date_str=_date_label(date_str),
        accent_color=cfg["color_primary"],
    )
    story.append(Spacer(1, 6))

    # 2. Motto card
    motto = Table([[Paragraph(en(f"<b>【意識定錨座右銘】</b> {cfg['motto']}"), motto_st)]], colWidths=[T.PRINTABLE_WIDTH])
    motto.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), cfg["color_bg"]),
        ('BOX', (0, 0), (-1, -1), 0.5, cfg["color_secondary"]),
        ('LINELEFT', (0, 0), (0, 0), 4, cfg["color_primary"]),
        ('PADDING', (0, 0), (-1, -1), 7),
    ]))
    story += [motto, Spacer(1, 8)]

    # 3. Spotlight card
    spotlight = Table([[Paragraph(en(f"<b>{cfg['spotlight']}</b>"), spot_st)]], colWidths=[T.PRINTABLE_WIDTH])
    spotlight.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#FFFDF5")),
        ('BOX', (0, 0), (-1, -1), 0.8, cfg["color_primary"]),
        ('LINELEFT', (0, 0), (0, -1), 4, cfg["color_highlight"]),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story += [spotlight, Spacer(1, 8)]

    # 4. System parameters card
    params = Table([[Paragraph(en(f"<b>【系統關鍵參數】</b> {cfg['system_data_summary']}"), param_st)]], colWidths=[T.PRINTABLE_WIDTH])
    params.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), cfg["color_bg"]),
        ('BOX', (0, 0), (-1, -1), 0.5, cfg["color_secondary"]),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story += [params, Spacer(1, 10)]

    # 5. Five dimensions cards
    story.append(Paragraph(en("<b>五大維度深度覺察 (5-Dimensional Analysis)</b>"), heading_st))
    for dim_title, dim_content in cfg["dimensions"]:
        card = Table(
            [[Paragraph(en(f"<b>{dim_title}</b>"), dim_h_st)],
             [Paragraph(en(dim_content), dim_b_st)]],
            colWidths=[T.PRINTABLE_WIDTH],
        )
        card.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#D8D8D8")),
            ('LINELEFT', (0, 0), (0, -1), 3, cfg["color_secondary"]),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        story += [card, Spacer(1, 5)]
    story.append(Spacer(1, 6))

    # 6. Three-step guidance card
    story.append(Paragraph(en("<b>三段式結構導引 (Structured Guidance: What / Why / So What)</b>"), heading_st))
    action_str = "<br/>".join(cfg["action"])
    guidance = Table(
        [[Paragraph(en(f"<b>📍 覺察觀察 (What)：</b> {cfg['what']}"), dim_b_st)],
         [Paragraph(en(f"<b>💡 轉化思維 (Why)：</b> {cfg['why']}"), dim_b_st)],
         [Paragraph(en(f"<b>🎯 定錨行動 (So What)：</b><br/>{action_str}"), dim_b_st)]],
        colWidths=[T.PRINTABLE_WIDTH],
    )
    guidance.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), cfg["color_bg"]),
        ('BOX', (0, 0), (-1, -1), 0.5, cfg["color_primary"]),
        ('LINELEFT', (0, 0), (0, -1), 3, cfg["color_highlight"]),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E2E2")),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story += [guidance, Spacer(1, 8)]

    # 7. Harmony & flow note
    harmony = Table([[Paragraph(en(f"<b>{cfg['harmony_note']}</b>"), harmony_st)]], colWidths=[T.PRINTABLE_WIDTH])
    harmony.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.6, cfg["color_primary"]),
        ('LINELEFT', (0, 0), (0, 0), 4, cfg["color_secondary"]),
        ('PADDING', (0, 0), (-1, -1), 7),
    ]))
    story += [harmony, Spacer(1, 12)]

    if page_num < page_total:
        story.append(PageBreak())
    return story


def generate_pdf_report(output_filename, date_str=None, location=None, systems=None):
    """Build the 5-page Spiritual PDF. Returns ``output_filename``."""
    ensure_fonts()
    date_str = date_str or datetime.date.today().strftime("%Y-%m-%d")
    location = location or _DEFAULT_LOCATION
    systems = systems or SYSTEMS_CONFIG
    page_total = len(systems)

    doc = new_doc(
        output_filename,
        title="Spiritual Intelligence 每日覺察運勢報告",
    )
    footer = footer_factory(
        "Spiritual Intelligence Pipeline 5 · Powered by Gemini Spark",
        total_pages=page_total,
    )
    story = []
    for idx, cfg in enumerate(systems, start=1):
        story.extend(create_system_page(cfg, idx, page_total, date_str, location))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"PDF successfully generated: {output_filename}")
    return output_filename


if __name__ == "__main__":
    out = os.path.join(_REPO_ROOT, "output", "Spiritual_Intelligence_每日覺察運勢報告.pdf")
    generate_pdf_report(out, date_str="2026-08-11")
