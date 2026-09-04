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
    missing key must surface as 數據待補 in the report, not a CI failure."""
    snap = fetchers.fetch_market_snapshot()
    if not snap or len(snap) < 5:
        import pytest
        pytest.skip(f"Yahoo snapshot mostly unreachable ({len(snap or {})}/8)")
    assert set(snap) <= set(fetchers._YAHOO_SYMBOLS)
    assert all(isinstance(v, float) for v in snap.values())


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
