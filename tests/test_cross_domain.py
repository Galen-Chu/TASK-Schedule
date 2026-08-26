"""Unit tests: cross-domain briefing (G) — parser, fallback, rendering."""
import re

from core.cross_domain import parse_what_why_sowhat, signal_lines, trend_lines, daily_briefing


# ---- parser ---------------------------------------------------------------
def test_parse_plain():
    out = parse_what_why_sowhat("WHAT: a\nWHY: b\nSO_WHAT: c")
    assert out == {"what": "a", "why": "b", "so_what": "c"}


def test_parse_markdown_decorated_and_space_variant():
    txt = ("**WHAT:** 台股融資餘額回升、VIX 回落\n"
           "`WHY:` 恐貪指數自極端恐慌區反彈，與 AI 語料聲量上升互相印證\n"
           "> SO WHAT: 分批佈局台積電供應鏈")
    out = parse_what_why_sowhat(txt)
    assert out and "台股融資" in out["what"] and "語料聲量" in out["why"]
    assert "台積電" in out["so_what"]


def test_parse_caps_140_chars():
    out = parse_what_why_sowhat("WHAT: " + "長" * 200)
    assert len(out["what"]) == 141 and out["what"].endswith("…")


def test_parse_garbage_returns_none():
    assert parse_what_why_sowhat("no structure here") is None
    assert parse_what_why_sowhat("") is None
    assert parse_what_why_sowhat(None) is None


# ---- prompt-input compression ---------------------------------------------
def test_signal_lines_includes_core_fields():
    fin = {"signal_score": 72, "signal_rating": "🟢 偏多", "vix": 15.2,
           "fear_and_greed": 61, "treasury_10y": 3.9, "spread_10y2y": 0.15,
           "dxy": 101.2, "gold": 2500, "btc": 60000,
           "macro": {"nfp": {"value": "110", "year": "2026", "period_name": "July"}}}
    joined = "\n".join(signal_lines(fin))
    assert "72/100" in joined and "VIX" in joined and "15.20" in joined
    assert "非農就業" in joined and "110" in joined


def test_trend_lines_arrows_and_keywords():
    trends = {
        "domains": {"it_ai": {"this_week": 30, "last_week": 12, "change_pct": 150.0},
                    "geopolitics": {"this_week": 5, "last_week": 10, "change_pct": -50.0}},
        "keywords": [("tariff", 6, 200.0), ("minor word", 1, 300.0)],
    }
    lines = trend_lines(trends)
    joined = "\n".join(lines)
    assert "AI/半導體聲量週比 ↑150%" in joined
    assert "地緣政治聲量週比 ↓50%" in joined
    assert "「tariff」本週 6 則" in joined
    assert "minor word" not in joined  # below the 3-hit floor


# ---- LLM fallback + happy path --------------------------------------------
def test_briefing_none_without_key(monkeypatch):
    from core import llm
    monkeypatch.setattr(llm, "is_available", lambda: False)
    assert daily_briefing({"vix": 15}, {"domains": {}, "keywords": []}) is None


def test_briefing_happy_path(monkeypatch):
    from core import llm, cross_domain
    monkeypatch.setattr(llm, "is_available", lambda: True)

    captured = {}

    def fake_generate(prompt, max_tokens=600):
        captured["prompt"] = prompt
        return ("WHAT: 恐貪指數 61 與 AI 聲量週比 +150% 同步升溫\n"
                "WHY: 量化風險偏好回升與半導體新聞熱度互相印證\n"
                "SO_WHAT: 可分批佈局台股科技 ETF")

    monkeypatch.setattr(llm, "generate", fake_generate)
    fin = {"signal_score": 72, "signal_rating": "🟢 偏多", "vix": 15.2,
           "fear_and_greed": 61}
    trends = {"domains": {"it_ai": {"this_week": 30, "last_week": 12, "change_pct": 150.0}},
              "keywords": []}
    out = daily_briefing(fin, trends, headlines=[{"title": "TSMC beats"}])
    assert out["what"].startswith("恐貪指數") and "台股科技" in out["so_what"]
    # the prompt must carry both signal streams plus the headline
    assert "61" in captured["prompt"] and "AI/半導體" in captured["prompt"]
    assert "TSMC" in captured["prompt"]


def test_briefing_unparsable_reply_returns_none(monkeypatch):
    from core import llm
    monkeypatch.setattr(llm, "is_available", lambda: True)
    monkeypatch.setattr(llm, "generate", lambda p, max_tokens=600: "答非所問")
    assert daily_briefing({}, {}) is None


# ---- PDF: card renders, page count stays 7 --------------------------------
def test_financial_pdf_with_briefing_stays_7_pages(tmp_path):
    from Financial_Intelligence.pdf_generator import generate_daily_pdf
    data = {
        "cross_domain_briefing": {
            "what": "VIX 15.2、恐貪指數 61：風險偏好回暖，與 AI 語料聲量週比 +150% 同步。",
            "why": "量化訊號與新聞趨勢互相印證——半導體新聞熱度領先評價面修復。",
            "so_what": "台股科技 ETF 可分批布局；留意週五非農數據對利率路徑的定價。",
        },
        "market_intel": [
            {"title": f"Market headline number {i}", "summary": "summary " * 8,
             "source": "https://finance.yahoo.com/news/rss.xml", "link": "https://x.org",
             "published": "", "fetched_at": "2026-08-26T07:00:00+08:00"}
            for i in range(5)
        ],
    }
    out = str(tmp_path / "f.pdf")
    generate_daily_pdf(out, data=data, date_str="2026-08-26")
    raw = open(out, "rb").read()
    pages = len(re.findall(rb"/Type\s*/Page[^s]", raw))
    assert pages == 7, f"briefing card overflowed: {pages} pages"
