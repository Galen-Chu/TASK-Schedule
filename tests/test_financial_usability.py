"""Unit tests: chart axis helpers, NFP monthly changes, market verdict banners."""
import re

from Financial_Intelligence.pdf_generator import (
    _nice_ticks, _nfp_monthly_changes, _market_verdicts, _line_chart,
    generate_daily_pdf,
)

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ---- chart axis helpers ----------------------------------------------------
def test_nice_ticks_round_steps_cover_range():
    ticks = _nice_ticks(3.6, 4.9)
    assert ticks[0] <= 3.6 and ticks[-1] >= 4.9
    assert len(ticks) >= 4
    step = ticks[1] - ticks[0]
    assert all(abs((ticks[i + 1] - ticks[i]) - step) < 1e-9 for i in range(len(ticks) - 1))


def test_nice_ticks_negative_range():
    ticks = _nice_ticks(-320.0, 260.0)
    assert ticks[0] <= -320 and ticks[-1] >= 260
    assert any(t == 0 for t in ticks)


def test_line_chart_drawing_with_units():
    d = _line_chart(["A", "B", "C"], [[1.0, 2.5, 2.0]], height=100,
                    y_unit="%", x_unit="月份")
    assert d is not None and len(d.contents) >= 1


# ---- NFP monthly changes ----------------------------------------------------
def test_nfp_monthly_changes_from_newest_first_levels():
    # BLS newest-first; chronological levels rise 100K/month → diffs = +100
    hist = [{"value": str(101100 - i * 100), "year": "2026",
             "period_name": m} for i, m in enumerate(reversed(_MONTHS))]
    diffs, labels = _nfp_monthly_changes(hist)
    assert len(diffs) == 11 and all(d == 100 for d in diffs)
    assert labels[0].startswith("Feb") and labels[-1].startswith("Dec")


def test_nfp_skips_annual_and_bad_rows():
    base = [{"value": str(100000 + i * 100), "year": "2026", "period_name": m}
            for i, m in enumerate(_MONTHS[:7])]
    base.insert(0, {"value": "103000", "year": "2025", "period_name": "Annual"})  # M13
    base.insert(2, {"value": "-", "year": "2026", "period_name": "Mar"})  # missing
    diffs, labels = _nfp_monthly_changes(base)
    assert len(diffs) == 6                       # 7 clean months → 6 diffs
    assert all("Annual" not in l for l in labels)


def test_nfp_insufficient_history_returns_none():
    assert _nfp_monthly_changes([]) is None
    assert _nfp_monthly_changes([{"value": "1", "year": "2026",
                                  "period_name": "Jan"}]) is None


# ---- market verdicts --------------------------------------------------------
def test_market_verdicts_bullish_inputs():
    v = _market_verdicts({"tw_margin_balance": 8_500_000, "vix": 30,
                          "spread_10y2y": 0.3, "dxy": 100.5,
                          "fear_and_greed": 20, "futures_net_oi": -5000})
    assert v["tw"][1] == "buy" and "門檻" in v["tw"][3]
    assert v["us"][1] == "buy" and v["us"][2] == "恐慌區・中長線買點"
    assert v["bond"][1] == "buy" and v["forex"][1] == "buy"
    assert v["cmdty"][1] == "buy" and v["overall"][1] == "buy"


def test_market_verdicts_bearish_and_mid_inputs():
    v = _market_verdicts({"tw_margin_balance": 9_600_000, "vix": 12,
                          "spread_10y2y": -0.6, "dxy": 105.2,
                          "fear_and_greed": 50, "futures_net_oi": -40000})
    assert v["tw"][1] == "sell" and v["us"][1] == "hold"
    assert v["bond"][1] == "sell" and v["forex"][1] == "hold"
    assert v["cmdty"][1] == "hold" and v["crypto"][1] == "hold"
    assert v["overall"][1] == "hold" or v["overall"][1] == "sell"


def test_market_verdicts_missing_data_all_neutral():
    v = _market_verdicts({})
    for key in ("tw", "us", "bond", "forex", "cmdty", "crypto"):
        assert v[key][1] == "neutral", key
    # overall needs no market data (base score) — still a valid verdict
    assert v["overall"][1] in ("buy", "hold", "sell")


# ---- full PDF with banners + all charts stays 7 pages ----------------------
def _full_macro():
    def bls(levels):  # newest-first numeric BLS rows
        return [{"value": str(v), "year": y, "period_name": m}
                for v, y, m in levels]

    years = (["2025"] * 12 + ["2026"] * 12)[:24]
    periods = (_MONTHS + _MONTHS)[:24]
    cpi = bls(zip([round(310 + i * 0.8, 1) for i in range(24)][::-1], years, periods))
    core = bls(zip([round(315 + i * 0.5, 1) for i in range(24)][::-1], years, periods))
    nfp = bls(zip([158000 - i for i in range(13)],
                  ["2026"] * 13,
                  (["Annual"] + _MONTHS[::-1])[:13]))
    ten10y = [{"date": f"{(i % 12) + 1:02d}/15", "v": round(4.4 - i * 0.02, 2)}
              for i in range(25)]
    return {
        "yield_curve": {"date": "08/27/2026",
                        "curve": {"1M": 3.8, "3M": 3.85, "6M": 3.9, "1Y": 3.95,
                                  "2Y": 4.0, "3Y": 4.1, "5Y": 4.2, "7Y": 4.3,
                                  "10Y": 4.4, "20Y": 4.6, "30Y": 4.5}},
        "us10y_hist": ten10y,
        "cpi_hist": cpi, "core_cpi_hist": core, "nfp_hist": nfp,
        "unemployment": {"value": "4.2", "year": "2026", "period_name": "July"},
    }


def test_financial_pdf_full_charts_and_banners_stay_7_pages(tmp_path):
    data = {"tw_margin_balance": 8_894_000, "vix": 15.2, "fear_and_greed": 71,
            "spread_10y2y": 0.47, "dxy": 102.4, "treasury_10y": 3.9,
            "treasury_2y": 3.43, "macro": _full_macro(),
            "market_intel": [
                {"title": f"Market headline number {i}", "summary": "summary " * 8,
                 "source": "https://finance.yahoo.com/news/rss.xml", "link": "https://x.org",
                 "published": "", "fetched_at": "2026-08-27T07:00:00+08:00"}
                for i in range(5)
            ]}
    out = str(tmp_path / "f.pdf")
    generate_daily_pdf(out, data=data, date_str="2026-08-27")
    raw = open(out, "rb").read()
    pages = len(re.findall(rb"/Type\s*/Page[^s]", raw))
    assert pages == 7, f"banners/charts overflowed: {pages} pages"
