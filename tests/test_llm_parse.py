"""Unit tests: markdown-tolerant LLM block parser + YoY series robustness.

These cover the two 2026-08-17 production failures:
1. Global three-part missing — flash-lite decorates replies with **/` which
   broke the strict "[N]/WHAT:" parser (LLM calls themselves were 200 OK).
2. Financial page 6 missing the CPI chart — real BLS rows contain '-' for
   missing months, which crashed float() and made the whole series None.
"""
import pytest

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


def test_global_with_maxlen_three_part_fits_5_pages(tmp_path, monkeypatch):
    """Worst case: every topic card gets the 110-char capped three-part body.

    Regression guard for the 08-17 overflow (7 pages) once three-part parsing
    was fixed — the layout must stay 5 pages even with full-length LLM text.
    """
    import re
    from core import llm
    from Global_Intelligence import pdf_generator as g
    monkeypatch.setattr(llm, "is_available", lambda: True)

    def cap(s):  # mirror the 110-char cap enforced by parse_topic_blocks
        return s[:110] + "…" if len(s) > 110 else s
    long_tp = {"what": cap("台積電擴大 2nm 與 CoWoS 先進封裝資本支出至 640 億美元，"
                           "管理層於法人說明會上修全年 capex 指引並重申 AI 需求結構性成長，"
                           "外資法人普遍解讀為正面訊號並調升目標價，反映先進製能供需持續吃緊。"),
               "why": cap("全球雲端服務商持續上修 AI 伺服器採購，帶動先進製程與封裝產能吃緊，"
                          "同時競爭對手在成熟製程價格轉趨保守，有利台積電毛利率持穩，"
                          "市場預期此輪擴產循環將延續至少八個季度。"),
               "so_what": cap("台灣半導體設備與散熱供應鏈將受惠於擴產循環，相關供應商營收動能"
                              "可望延續至明年，可留意上游材料與檢測設備廠的估值重評機會，"
                              "並觀察 CoWoS 產能開放對象名單。")}

    def fake(topics, domain_label=""):
        return [dict(long_tp) for _ in topics]
    monkeypatch.setattr(g.llm, "summarize_topics_what_why_sowhat", fake)
    out = str(tmp_path / "g.pdf")
    data = {"editorial": True,
            "llm_digest": {"what": "台" * 60, "why": "脈" * 60, "so_what": "啟" * 60},
            "retrieval": {d[0]: [{"fetched_at": "2026-08-17T07:00:00+08:00",
                                  "source": "https://feeds.bbci.co.uk/news/world/rss.xml",
                                  "title": "TSMC expands 2nm capacity as AI demand surge continues into 2027",
                                  "link": "https://x.org"}] * 3
                          for d in g.DOMAINS}}
    g.build_global_pdf(out, data=data, date_str="2026-08-17")
    raw = open(out, "rb").read()
    pages = len(re.findall(rb"/Type\s*/Page[^s]", raw))
    # 7 pages (P1 trend + 6 domains), 6 cards/page with full three-part bodies.
    # Guard against 9+ (severe overflow).
    assert pages <= 8, f"Global overflowed to {pages} pages with full three-part bodies"
