"""Unit tests: markdown-tolerant LLM block parser + YoY series robustness.

These cover the production failures:
1. Global three-part missing — flash-lite decorates replies with **/` which
   broke the strict "[N]/FIELD:" parser (2026-08-17), plus the 2026-08-28
   recurrence in the P1 digest parser. Vocabulary switched to
   GIVEN/WHEN/THEN on 2026-08-31.
2. The 2026-08-31 root cause: flash-lite's mandatory thinking tokens eat
   into max_output_tokens, so every capped call returned an EMPTY reply and
   no parser ever ran — fixed by pinning thinking + raising ceilings in
   core/llm.py (see its module docstring).
3. Financial page 6 missing the CPI chart — real BLS rows contain '-' for
   missing months, which crashed float() and made the whole series None.
"""
import pytest

from core import llm
from core.llm import parse_topic_blocks
from Financial_Intelligence.pdf_generator import _yoy_series


def test_parse_plain():
    txt = "[1]\nGIVEN: a\nWHEN: b\nTHEN: c\n[2]\nGIVEN: d\nWHEN: e\nTHEN: f"
    out = parse_topic_blocks(txt, 2)
    assert out[0]["given"] == "a" and out[1]["then"] == "f"


def test_parse_markdown_bold_and_code():
    txt = ("**[1]**\n**GIVEN:** 台積電 *2nm* 擴產\n**WHEN:** AI 需求\n**THEN:** 設備鏈受惠\n\n"
           "`[2]`\nGIVEN: d\nWHEN: e\nTHEN: f")
    out = parse_topic_blocks(txt, 2)
    assert out and out[0] and "台積電" in out[0]["given"]
    assert out[1]["when"] == "e"


def test_parse_fullwidth_colon():
    out = parse_topic_blocks("[1]\nGIVEN：台積電上修資本支出\nWHEN：AI 需求強勁\nTHEN：供應鏈受惠", 1)
    assert out[0]["given"] == "台積電上修資本支出" and out[0]["then"] == "供應鏈受惠"


def test_parse_numbered_header():
    txt = "1.\nGIVEN: a\nWHEN: b\nTHEN: c\n2. \nGIVEN: d\nWHEN: e\nTHEN: f"
    out = parse_topic_blocks(txt, 2)
    assert out[1]["given"] == "d"


def test_parse_partial_block_still_counts():
    # GIVEN alone is enough for a usable card row (WHEN/THEN render optional)
    out = parse_topic_blocks("[1]\nGIVEN: a", 1)
    assert out[0]["given"] == "a" and out[0]["when"] == ""


def test_parse_garbage_returns_none():
    assert parse_topic_blocks("no structure here", 3) is None


# ---- P1 digest parser (summarize_news_given_when_then) — the 08-28 recurrence
_ITEMS = [{"title": "台積電法說", "summary": "資本支出上修"}]


def _digest(monkeypatch, reply):
    monkeypatch.setattr(llm, "_AVAILABLE", True)
    monkeypatch.setattr(llm, "generate", lambda p, max_tokens=1600: reply)
    return llm.summarize_news_given_when_then(_ITEMS, domain_label="全球產業情報")


@pytest.mark.parametrize("reply", [
    "GIVEN: 美中科技戰延伸\nWHEN: 美國擴大出口管制\nTHEN: 台灣供應鏈轉單受惠",
    "**GIVEN:** 美中科技戰延伸\n**WHEN:** 美國擴大出口管制\n**THEN:** 台灣供應鏈轉單受惠",
    "1. GIVEN: 美中科技戰延伸\n2. WHEN: 美國擴大出口管制\n3. THEN: 台灣供應鏈轉單受惠",
    "GIVEN：美中科技戰延伸\nWHEN：美國擴大出口管制\nTHEN：台灣供應鏈轉單受惠",
    "GIVEN: 美中科技戰延伸\nWHEN: 美國擴大出口管制\nTHEN : 台灣供應鏈轉單受惠",
])
def test_digest_parse_tolerates_decoration(monkeypatch, reply):
    out = _digest(monkeypatch, reply)
    assert out and out["given"] == "美中科技戰延伸"
    assert out["when"] == "美國擴大出口管制" and out["then"] == "台灣供應鏈轉單受惠"


def test_digest_parse_garbage_returns_none(monkeypatch):
    assert _digest(monkeypatch, "以下是今日摘要：\n- 標題一") is None


def test_digest_truncates_to_60_chars(monkeypatch):
    out = _digest(monkeypatch, "GIVEN: " + "勢" * 200)
    assert out and len(out["given"]) == 61 and out["given"].endswith("…")


# ---- thinking-budget guardrails (2026-08-31 root cause) --------------------
# Flash-lite's thinking floor is 512 tokens and counts inside max_output_
# tokens; ceilings below floor+reply produced empty replies for weeks.

def test_gen_configs_pins_lite_thinking(monkeypatch):
    monkeypatch.setattr(llm, "_MODEL_NAME", "gemini-flash-lite-latest")
    cfgs = llm._gen_configs(1600, 0.4)
    assert len(cfgs) == 2
    assert cfgs[0].thinking_config.thinking_budget == 512
    assert cfgs[1].thinking_config is None


def test_gen_configs_plain_for_non_lite(monkeypatch):
    monkeypatch.setattr(llm, "_MODEL_NAME", "gemini-2.5-flash")
    assert len(llm._gen_configs(1600, 0.4)) == 1


def test_call_sites_leave_thinking_headroom():
    # 800 = 512 thinking floor + slack; every ceiling must clear it.
    src = open("core/llm.py", encoding="utf-8").read()
    assert "max_tokens=800 + 320 * len(topics)" in src
    src_cd = open("core/cross_domain.py", encoding="utf-8").read()
    assert "max_tokens=1600" in src_cd
    assert "max_tokens=420" not in src_cd


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


def test_global_with_maxlen_gwt_fits_and_labels_visible(tmp_path, monkeypatch):
    """Worst case: every topic card gets the 110-char capped G-W-T body.

    Guards the 08-17 overflow (pages blew past 7 once three-part parsing was
    fixed) — the layout must stay within the CI page assertion even with
    full-length LLM text on all eight cards (8/page since 09-03; measured
    worst case ends at y≈693, ~107pt above the margin). Also verifies (via
    pymupdf when installed locally) that the GIVEN/WHEN/THEN labels actually
    render, on P1's digest table and on every live domain card.
    """
    import re
    from core import llm
    from Global_Intelligence import pdf_generator as g
    monkeypatch.setattr(llm, "is_available", lambda: True)

    long_tp = {"given": "台積電擴大 2nm 與 CoWoS 先進封裝資本支出至 640 億美元，管理層於法人說明會"
                        "上修全年 capex 指引並重申 AI 需求結構性成長，外資法人普遍解讀為正面訊號並"
                        "調升目標價，反映先進製程供需持續吃緊。" * 2,
               "when": "全球雲端服務商持續上修 AI 伺服器採購，帶動先進製程與封裝產能吃緊，同時競爭"
                       "對手在成熟製程價格轉趨保守，有利台積電毛利率穩健，市場預期此輪擴產循環將"
                       "延續至少八個季度。" * 2,
               "then": "台灣半導體設備與散熱供應鏈將受惠於擴產循環，相關供應商營收動能可望延續至明"
                       "年，可留意上游材料與檢測設備廠的估值重評機會，並觀察 CoWoS 產能開放對象名"
                       "單釋出進度。" * 2}

    def fake(topics, domain_label=""):
        return [dict(long_tp) for _ in topics]
    monkeypatch.setattr(g.llm, "summarize_topics_given_when_then", fake)
    out = str(tmp_path / "g.pdf")
    data = {"editorial": True,
            "llm_digest": {"given": "勢" * 60, "when": "事" * 60, "then": "啟" * 60},
            "retrieval": {d[0]: [{"fetched_at": "2026-08-17T07:00:00+08:00",
                                  "source": "https://feeds.bbci.co.uk/news/world/rss.xml",
                                  "title": "TSMC expands 2nm capacity as AI demand surge continues into 2027",
                                  "link": "https://x.org"}] * 8
                          for d in g.DOMAINS}}
    g.build_global_pdf(out, data=data, date_str="2026-08-17")
    raw = open(out, "rb").read()
    pages = len(re.findall(rb"/Type\s*/Page[^s]", raw))
    # 7 pages (P1 trend + 6 domains), 8 cards/page with full G-W-T bodies.
    assert pages == 7, f"Global overflowed to {pages} pages with full G-W-T bodies"

    fitz = pytest.importorskip("pymupdf")   # local-only invariant; CI skips
    doc = fitz.open(out)
    p1 = doc[0].get_text()
    assert "GIVEN（前提態勢）" in p1 and "WHEN（關鍵事件）" in p1 and "THEN（台灣啟示）" in p1
    dom_text = doc[1].get_text()
    assert dom_text.count("GIVEN 前提") == 8     # 8 live cards on P2
    assert dom_text.count("THEN 影響") == 8
    assert "GIVEN" in dom_text and "WHEN 事件" in dom_text
