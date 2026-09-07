"""Shared text sanitizing for RSS-sourced content.

WordPress feeds (Electrek, SpaceNews, …) deliver summaries as full HTML.
``CorpusStore.add`` truncates to 500 chars, which can cut a tag mid-attribute
(``<a class="more-link" href=…``) — an unterminated fragment that survives
``<[^>]+>`` stripping and, once ``en()`` glues it into a Latin ``<font>``
wrapper, crashes ReportLab's paragraph parser (2026-09-07 CI failure).

``strip_html`` is the one canonical cleaner, import-safe from any layer
(no reportlab/fonts deps — ingest must not pull the PDF stack).
"""
import html
import re

_TAG_RE = re.compile(r"<[^>]+>")
# A tag cut off before its '>' — the tail of a truncated summary. The cut can
# land before the tag name too, leaving a bare trailing '<' ('more…<'). Only
# tag-shaped tails are dropped; '< 5,000' keeps its '<', which en() escapes.
_TAIL_TAG_RE = re.compile(r"<(?:[a-zA-Z/!][^>]*)?\s*$")


def strip_html(text, unescape=True):
    """Strip complete tags and a trailing truncated tag; collapse whitespace.

    With ``unescape`` (default) HTML entities decode to plain characters —
    the corpus stores plain text and ``en()`` re-escapes ``&`` when rendering.
    """
    if not text:
        return ""
    out = _TAG_RE.sub(" ", text)
    out = _TAIL_TAG_RE.sub("", out)
    if unescape:
        out = html.unescape(out)
    return re.sub(r"\s+", " ", out).strip()
