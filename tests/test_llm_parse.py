"""Unit tests: markdown-tolerant LLM block parser + YoY series robustness.

These cover the two 2026-08-17 production failures:
1. Global three-part missing — flash-lite decorates replies with **/` which
   broke the strict "[N]/WHAT:" parser (LLM calls themselves were 200 OK).
2. Financial page 6 missing the CPI chart — real BLS rows contain '-' for
   missing months, which crashed float() and made the whole series None.
"""
from core.llm import parse_topic_blocks
from Financial_Intelligence.pdf_generator import _yoy_series


def test_parse_plain():
    txt = "[1]\nWHAT: a\nWHY: b\nSO_WHAT: c\n[2]\nWHAT: d\nWHY: e\nSO_WHAT: f"
    out = parse_topic_blocks(txt, 2)
    assert out[0]["what"] == "a" and out[1]["so_what"] == "f"


def test_parse_markdown_bold_and_code():
    txt = ("**[1]**\n**WHAT:** 台積電 *2nm* 擴產\n**WHY:** AI 需求\n**SO_WHAT:** 設備鏈受惠\n\n"
           "`[2]`\nWHAT: d\nWHY: e\nSO_WHAT: f")
    out = parse_topic_blocks(txt, 2)
    assert out and out[0] and "台積電" in out[0]["what"]
    assert out[1]["why"] == "e"


def test_parse_so_what_space_variant():
    out = parse_topic_blocks("[1]\nWHAT: a\nWHY: b\nSO WHAT: c", 1)
    assert out[0]["so_what"] == "c"


def test_parse_numbered_header():
    txt = "1.\nWHAT: a\nWHY: b\nSO_WHAT: c\n2. \nWHAT: d\nWHY: e\nSO_WHAT: f"
    out = parse_topic_blocks(txt, 2)
    assert out[1]["what"] == "d"


def test_parse_garbage_returns_none():
    assert parse_topic_blocks("no structure here", 3) is None


def test_yoy_skips_missing_dash_values():
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
              "Oct", "Nov", "Dec"]
    hist, idx = [], 0
    for y in (2025, 2026):
        for m in months:
            v = "-" if (y == 2025 and m == "Oct") else str(round(318.0 + idx * 0.9, 1))
            hist.append({"year": str(y), "period_name": m, "value": v})
            idx += 1
    out = _yoy_series(hist)
    assert out is not None
    vals, labels = out
    assert len(vals) >= 6
    assert labels[-1].startswith("26/")


def test_yoy_all_bad_returns_none():
    assert _yoy_series([{"year": "2026", "period_name": "Aug", "value": "-"}]) is None
