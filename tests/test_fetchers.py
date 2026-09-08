"""Unit tests for the data fetchers (keyless sources).

These hit the network; if a source is unreachable the fetcher returns None,
which the tests treat as a soft-skip rather than a failure (CI/offline).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data import fetchers


def _at_least_one(values):
    """Pass if any value is not None (network ok); else xfail the test."""
    import pytest
    if all(v is None for v in values):
        pytest.skip("all sources unreachable in this environment")


def test_yahoo_quote_shape():
    # Not ^VIX: the snapshot test below already fetches it, and hitting the
    # same symbol twice per run doubled our throttle exposure.
    q = fetchers.fetch_yahoo_quote("BTC-USD")
    if q is None:
        import pytest; pytest.skip("Yahoo unreachable")
    assert isinstance(q, float) and 0 < q < 1_000_000


def test_treasury_yields_shape():
    t = fetchers.fetch_treasury_yields()
    if t is None:
        import pytest; pytest.skip("Treasury CSV unreachable")
    assert "10y" in t and "2y" in t
    assert isinstance(t["10y"], float) and t["10y"] > 0


def test_fear_greed_range():
    fg = fetchers.fetch_fear_greed()
    if fg is None:
        import pytest; pytest.skip("F&G API unreachable")
    assert isinstance(fg, int) and 0 <= fg <= 100


def test_bls_shape():
    rec = fetchers.fetch_bls_series("CUUR0000SA0L1E")
    if rec is None:
        import pytest; pytest.skip("BLS unreachable")
    assert rec["value"] and rec["year"]


def test_market_snapshot_or_skip():
    """Partial snapshots are legitimate: Yahoo throttles individual symbols
    (2026-09-04 — ^VIX alone failed a scheduled run while 7 resolved), and a
    missing key must surface as 數據待補 in the report, not a CI failure.
    14 symbols registered since 2026-09-08 → soft gate at ≥9/14."""
    snap = fetchers.fetch_market_snapshot()
    if not snap or len(snap) < 9:
        import pytest
        pytest.skip(f"Yahoo snapshot mostly unreachable ({len(snap or {})}/14)")
    assert set(snap) <= set(fetchers._YAHOO_SYMBOLS)
    assert all(isinstance(v, float) for v in snap.values())


def test_treasury_yields_prev_month_row():
    """The prev-month row must be the NEWEST row ≥28 days old (the first
    naive loop kept overwriting and ended on the oldest CSV row)."""
    tyc = fetchers.fetch_treasury_yields()
    if not tyc or "_prev_date" not in tyc:
        import pytest
        pytest.skip("Treasury CSV unreachable")
    assert tyc["2y_prev"] is not None and tyc["10y_prev"] is not None
    assert not tyc["_prev_date"].startswith("01/")


def test_fred_series_latest_and_prev():
    rec = fetchers.fetch_fred_series("BAMLH0A0HYM2")
    if rec is None:
        import pytest
        pytest.skip("FRED unreachable")
    assert 0 < rec["value"] < 25          # OAS in percentage points
    assert rec["prev_date"] < rec["date"]


def test_yahoo_quote_falls_back_to_mirror_host(monkeypatch):
    """A query1 failure (or 200-with-error-body) must reach the query2 mirror."""
    ok = {"chart": {"result": [{"meta": {"regularMarketPrice": 14.32}}]}}
    err_body = {"chart": {"result": None, "error": {"code": "Not Found"}}}
    seen = []

    def fake_get(url):
        seen.append(url)
        return err_body if "query1" in url else ok

    monkeypatch.setattr(fetchers, "_get_json", fake_get)
    assert fetchers.fetch_yahoo_quote("^VIX") == 14.32
    assert any("query1" in u for u in seen) and any("query2" in u for u in seen)


def test_yahoo_quote_all_hosts_down_returns_none(monkeypatch):
    monkeypatch.setattr(fetchers, "_get_json", lambda url: None)
    monkeypatch.setattr("time.sleep", lambda s: None)
    assert fetchers.fetch_yahoo_quote("^VIX") is None


def test_fetchers_return_none_on_bad_input():
    """Garbage in -> None out (never raises)."""
    assert fetchers.fetch_yahoo_quote("TOTALLY_BOGUS_$$$") is None
    assert fetchers.fetch_json("https://example.invalid/url") is None


# ---- RSS published stamp (2026-09-08 ①修復：發布時間必須帶進語料) ------------
def test_feed_items_carries_published():
    """feedparser entries expose published (RSS) / updated (Atom); the dict
    must carry it through — the corpus had 0/1483 items with published, so
    selection and card display both fell back to our fetched_at stamp."""
    import pytest
    feedparser = pytest.importorskip("feedparser")
    xml = """<?xml version="1.0"?>
    <rss version="2.0"><channel><title>t</title>
      <item><title>One</title><link>http://x/1</link>
        <description>d1</description><pubDate>Mon, 07 Sep 2026 09:00:00 GMT</pubDate></item>
      <item><title>Two</title><link>http://x/2</link>
        <description>d2</description></item>
    </channel></rss>"""
    items = fetchers._feed_items(feedparser.parse(xml), limit=4)
    assert items[0]["published"].startswith("Mon, 07 Sep 2026")
    assert items[1]["published"] == ""          # no pubDate → empty, not crash
    assert items[0]["title"] == "One"
