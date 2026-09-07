"""Regression tests for the 2026-09-07 CI failure.

An Electrek RSS summary (WordPress full HTML) was truncated mid-tag at
ingest; the unterminated ``<a class="more-link"…`` fragment survived
tag-stripping, ``en()`` glued it into a Latin ``<font>`` wrapper, and
ReportLab's paragraph parser rejected the malformed markup — killing the
whole report build (test_report_produces_pdf[global]). These tests pin
every layer of the fix: shared sanitizer, ingest-time cleaning, backlog
self-heal, and ``en()`` escaping of stray brackets.
"""
import json

import pytest

from core.text_clean import strip_html

# Faithful shape of the corpus entry that crashed CI (Electrek 2026-09-01,
# stored summary truncated mid-attribute at the 500-char ingest cut).
POISONED = (
    '<div class="feat-image"><img src="https://electrek.co/x.jpg?quality=82'
    '&#038;strip=all&#038;w=1600" /></div>'
    '<p class="wp-block-paragraph">The Ford Fathom will go on sale in early '
    '2027, starting at $28,350. Ford revealed new footage of the electric '
    'pickup.</p>\n\n<a class="more-link" href="https://electrek.co/2026/09/01/ford-sha'
)


# ---- core.text_clean.strip_html ---------------------------------------------

def test_strip_html_removes_truncated_tag_tail():
    out = strip_html(POISONED)
    assert "<" not in out and ">" not in out
    assert out.startswith("The Ford Fathom will go on sale")
    assert out.endswith("electric pickup.")


def test_strip_html_unescapes_entities():
    assert strip_html("A &amp; B &#8212; C") == "A & B — C"


def test_strip_html_keeps_comparison_bracket():
    # '<' NOT followed by a tag-like char stays text (en() escapes it later);
    # only tag-shaped tails ('<a…', '</p…') are dropped.
    assert strip_html("獲利 < 預期") == "獲利 < 預期"
    assert strip_html("5 <3 5000") == "5 <3 5000"
    assert strip_html("x </div tail") == "x"


def test_strip_html_drops_bare_trailing_bracket():
    # A 500-char cut can land right after '<', before the tag name.
    assert strip_html("makes the PV5 seem tiny. more…<") == \
        "makes the PV5 seem tiny. more…"


# ---- core.pdf_engine.en — last line of defense -------------------------------

def test_en_escapes_stray_brackets_no_crash():
    try:
        from core import fonts
        fonts.ensure_fonts()
    except RuntimeError as exc:
        pytest.skip(f"no CJK font available: {exc}")
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph
    from core.fonts import FONT_CJK
    from core.pdf_engine import en

    # The exact fragment that crashed paraparser, without any prior stripping.
    body = strip_html(POISONED, unescape=False)[:200] + '<a class="more-link'
    styled = en(body)
    assert "&lt;" in styled
    st = ParagraphStyle("t", fontName=FONT_CJK, fontSize=8)
    Paragraph(styled, st)  # must not raise


# ---- ingest: store.add sanitizes before truncating ---------------------------

def test_store_add_sanitizes_before_truncation(tmp_path):
    from core.retrieval.store import CorpusStore

    store = CorpusStore(str(tmp_path / "corpus.jsonl"))
    # <a href="…pad…"> spans the 500-char cut: a raw [:500] would slice it.
    long_html = '<p>Alpha beta gamma.</p>' + '<a href="https://x/' + "z" * 600 + '">'
    store.add([{"title": "t", "link": "https://x/1", "summary": long_html,
                "source": "s"}])
    rec = store.all()[0]
    assert "<" not in rec["summary"]
    assert len(rec["summary"]) <= 500
    assert "Alpha beta gamma." in rec["summary"]


def test_store_sanitize_heals_backlog(tmp_path):
    from core.retrieval.store import CorpusStore

    store = CorpusStore(str(tmp_path / "corpus.jsonl"))
    rec = {"id": "abc123", "title": "T", "link": "https://x/1",
           "summary": POISONED, "source": "s", "domain_tag": "hardware",
           "fetched_at": "2026-09-02T08:19:33+08:00", "emb": [0.1, 0.2]}
    with open(store.path, "w", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    assert store.sanitize_summaries() == 1
    healed = store.all()[0]
    assert healed["id"] == "abc123"            # dedup key untouched
    assert "<" not in healed["summary"]
    assert "emb" not in healed                  # stale vector dropped for re-embed
    assert store.sanitize_summaries() == 0      # idempotent


# ---- end-to-end: the card that crashed CI builds cleanly ----------------------

def test_global_rss_card_with_poisoned_summary():
    try:
        from core import fonts
        fonts.ensure_fonts()
    except RuntimeError as exc:
        pytest.skip(f"no CJK font available: {exc}")
    from Global_Intelligence.pdf_generator import _rss_card

    ramp = ["#f7e9e3", "#e8cfc3", "#b5715c", "#7a4634"]
    item = {"title": "Ford shares a closer look at the $30,000 Fathom EV pickup",
            "summary": POISONED, "source": "https://electrek.co/feed/",
            "link": "https://electrek.co/2026/09/01/ford-fathom/",
            "published": "Mon, 01 Sep 2026 10:00:00 +0000"}
    card = _rss_card(item, ramp, None, gwt=None, compact=True)
    assert card is not None  # built without ValueError
