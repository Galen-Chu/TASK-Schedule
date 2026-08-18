"""Shared ReportLab building blocks, built on :mod:`core.design_tokens` and
:mod:`core.fonts`:

  * :func:`en` — dual-font (Latin/CJK) + XML-safe text helper
  * :func:`standard_styles` — the common paragraph-style set
  * :func:`make_title_row` — the two-column header + accent rule
  * :func:`footer_factory` — builds a per-report footer callback
  * :func:`new_doc` — ``SimpleDocTemplate`` with the standard A4 frame
"""
import re
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, HRFlowable
from reportlab.lib.styles import ParagraphStyle

from core.fonts import FONT_CJK, FONT_EN, FONT_EN_BOLD, ensure_fonts
from core import design_tokens as T

_TAG_RE = r'(</?(?:b|i|br|font|a|u)\b[^>]*>)'
_LATIN_RUN_RE = r'([A-Za-z0-9%.,+\-\$/:_&><]+(?:\s+[A-Za-z0-9%.,+\-\$/:_&><]+)*)'


def en(text, bold=False, color=None):
    """Wrap Latin/digit runs in the Latin font and XML-escape ``& < >``.

    Existing ``<b>``/``<i>``/``<br>``/``<font>`` tags are preserved. The result
    is safe to embed inside a ReportLab ``<para>``.
    """
    ensure_fonts()
    font = FONT_EN_BOLD if bold else FONT_EN
    color_attr = f' color="{color}"' if color else ''

    wrapped = []
    for tok in re.split(_TAG_RE, str(text), flags=re.IGNORECASE):
        if re.match(_TAG_RE, tok, flags=re.IGNORECASE):
            wrapped.append(tok)
        else:
            wrapped.append(re.sub(
                _LATIN_RUN_RE,
                rf'<font fontName="{font}"{color_attr}>\g<1></font>',
                tok,
            ))
    intermediate = ''.join(wrapped)

    out = []
    for tok in re.split(_TAG_RE, intermediate, flags=re.IGNORECASE):
        if re.match(_TAG_RE, tok, flags=re.IGNORECASE):
            out.append(tok)
        else:
            out.append(tok.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))
    return ''.join(out)


def standard_styles():
    """Return the shared paragraph-style dictionary."""
    ensure_fonts()
    return {
        "title": ParagraphStyle("title", fontName=FONT_CJK, fontSize=16, leading=20, textColor=T.NAVY),
        "date": ParagraphStyle("date", fontName=FONT_CJK, fontSize=9.5, leading=14, textColor=T.TEXT_MUTED, alignment=2),
        "subtitle": ParagraphStyle("subtitle", fontName=FONT_CJK, fontSize=10, leading=14, textColor=T.TEXT_SUB, spaceBefore=3, spaceAfter=6),
        "h1": ParagraphStyle("h1", fontName=FONT_CJK, fontSize=12, leading=16, textColor=T.NAVY, spaceBefore=8, spaceAfter=5),
        "body": ParagraphStyle("body", fontName=FONT_CJK, fontSize=8.5, leading=12.5, textColor=T.TEXT_BODY),
        "th": ParagraphStyle("th", fontName=FONT_CJK, fontSize=8.5, leading=12.5, textColor=T.WHITE, alignment=1),
        "card_title": ParagraphStyle("card_title", fontName=FONT_CJK, fontSize=10.5, leading=13.5, textColor=T.NAVY, spaceAfter=4),
        "footer": ParagraphStyle("footer", fontName=FONT_CJK, fontSize=8, leading=10, textColor=T.TEXT_MUTED),
    }


def make_title_row(title_text, subtitle_text=None, date_str="", accent_color=None,
                   styles=None, eyebrow_text=None):
    """Unified page header shared by every report and every page.

    Anatomy (identical across reports):
      eyebrow   — report series name, small muted caps (first page of sections)
      title     — section/page title (16pt navy); publish date + weekday right
                  (11pt, accent colour — part of the title band, not tiny footer text)
      subtitle  — ONE muted context line (data sources / scope). Must add
                  information, not restate the body content below.
      divider   — full-width 1.5pt accent rule, same spacing everywhere.
    """
    styles = styles or standard_styles()
    accent = accent_color or T.GOLD
    eyebrow_st = ParagraphStyle("eyebrow", fontName=FONT_CJK, fontSize=8,
                                leading=10, textColor=T.TEXT_MUTED)
    date_st = ParagraphStyle("dateband", fontName=FONT_CJK, fontSize=11,
                             leading=13, textColor=accent, alignment=2)
    label = str(date_str)
    try:
        import datetime as _dt
        d = _dt.date.fromisoformat(label[:10])
        label = f"{label[:10]}（{'一二三四五六日'[d.weekday()]}）"
    except ValueError:
        pass
    rows = []
    if eyebrow_text:
        rows.append([Paragraph(en(eyebrow_text), eyebrow_st), ""])
    rows.append([Paragraph(en(title_text), styles["title"]),
                 Paragraph(en(label), date_st)])
    header = Table(rows, colWidths=[350, T.PRINTABLE_WIDTH - 350])
    header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('PADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elems = [header]
    if subtitle_text:
        elems.append(Paragraph(en(subtitle_text), styles["subtitle"]))
    elems.append(HRFlowable(width="100%", thickness=1.5, color=accent, spaceAfter=8))
    return elems


def footer_factory(disclaimer, total_pages=None):
    """Return a ReportLab footer callback with this report's disclaimer.

    If ``total_pages`` is None, the footer prints only the current page number
    (avoids the old "Page X of 5" lying when content overflows).
    """
    def make_footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(T.RULE)
        canvas.setLineWidth(0.5)
        canvas.line(T.MARGIN, 32, T.PAGE_WIDTH - T.MARGIN, 32)
        canvas.setFillColor(T.TEXT_MUTED)
        canvas.setFont(FONT_CJK, 8)
        canvas.drawString(T.MARGIN, 18, disclaimer)
        label = f"Page {doc.page}" + (f" of {total_pages}" if total_pages else "")
        canvas.drawRightString(T.PAGE_WIDTH - T.MARGIN, 18, label)
        canvas.restoreState()
    return make_footer


def new_doc(filename, top_margin=None, bottom_margin=None, title="Spark Report"):
    """SimpleDocTemplate with the standard A4 frame + margins."""
    ensure_fonts()
    return SimpleDocTemplate(
        filename,
        pagesize=A4,
        leftMargin=T.MARGIN,
        rightMargin=T.MARGIN,
        topMargin=T.MARGIN_TOP if top_margin is None else top_margin,
        bottomMargin=T.MARGIN_BOTTOM if bottom_margin is None else bottom_margin,
        title=title,
    )
