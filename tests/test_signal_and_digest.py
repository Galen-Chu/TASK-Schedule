"""Graded signal score + Global rules-digest fallback (2026-11-10 redesign).

Monthly review feedback: the score sat pinned at exactly 50 for 38 straight
days (binary bands + spread(+10) cancelling OI(-10) daily; F&G/DXY/P&C/
breadth not inputs at all), and llm_digest produced 0/32 days (Gemini quota
depleted — account-side). These pin the new behaviour.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Financial_Intelligence.pdf_generator import calculate_signal_score
from Global_Intelligence.obsidian_writer import build_digest as glob_digest
from Global_Intelligence.obsidian_writer import build_rules_digest

# The actual 2026-09-30 production inputs (from the Library digest archive)
# — old model scored this exactly 50 for the 38th consecutive day.
D0930 = {
    "vix": 16.04, "dxy": 101.34, "spread_10y2y": 0.37, "fear_and_greed": 71,
    "tw_margin_balance": 9_302_602, "futures_net_oi": -79_101,
    "pc_ratio_oi": 82.25, "tw_advance": 588, "tw_decline": 387,
}


def test_historical_day_scores_not_pinned():
    assert calculate_signal_score(D0930) == 59  # 50+3+0+5+3-8+1+1+4


def test_graded_bands_move_with_inputs():
    # F&G 24 (extreme fear, +7) vs 71 (greed, +0) — same everything else
    fear = dict(D0930, fear_and_greed=24)
    greed = dict(D0930, fear_and_greed=71)
    assert calculate_signal_score(fear) - calculate_signal_score(greed) == 7


def test_spread_oi_cancellation_broken():
    # Old model: spread>0 (+10) and OI<-30k (-10) cancelled to 0 every day.
    only = {"spread_10y2y": 0.4, "futures_net_oi": -79_101}
    assert calculate_signal_score(only) == 47  # 50 +5 -8, no longer pinned


def test_vix_bands_monotonic():
    scores = [calculate_signal_score({"vix": v}) for v in (31, 26, 16, 13, 11)]
    assert scores == sorted(scores, reverse=True) and len(set(scores)) == 5


def test_missing_new_inputs_contribute_nothing():
    base = calculate_signal_score({"vix": 16})
    assert calculate_signal_score({"vix": 16, "fear_and_greed": None,
                                   "dxy": None, "pc_ratio_oi": None,
                                   "tw_advance": None, "tw_decline": None}) == base


# ---- Global rules digest ---------------------------------------------------

_TRENDS = {
    "domains": {"it_ai": {"this_week": 30, "last_week": 20, "change_pct": 50.0},
                "macro": {"this_week": 10, "last_week": 20, "change_pct": -50.0}},
    "keywords": [["ai chips", 5], ["tsmc", 3]],
}
_ITEMS = [{"title": "<b>TSMC</b> lifts capex guidance", "link":
           "https://www.bloomberg.com/x"}]


def test_rules_digest_composed_from_pipeline_facts():
    fb = build_rules_digest(_ITEMS, _TRENDS)
    assert fb["source"] == "rules"
    assert "資訊科技" in fb["given"] and "+50%" in fb["given"]
    assert "TSMC lifts capex guidance" in fb["when"] and "BLOOMBERG" in fb["when"]
    assert "ai chips" in fb["then"] and "熱詞" in fb["then"]
    for v in fb.values():
        assert len(v) <= 62


def test_rules_digest_empty_when_nothing_to_say():
    assert build_rules_digest([], {}) is None
    # trends-only still yields GIVEN/THEN
    fb = build_rules_digest([], _TRENDS)
    assert fb and fb["when"] == ""


def test_global_digest_carries_fallback_alongside_null_llm_digest():
    d = glob_digest("2026-11-10", {"digest_fallback": {"given": "g", "when": "w",
                                                       "then": "t", "source": "rules"}})
    assert d["llm_digest"] is None          # machine signal preserved
    assert d["digest_fallback"]["source"] == "rules"
