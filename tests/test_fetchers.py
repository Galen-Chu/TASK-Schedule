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
    q = fetchers.fetch_yahoo_quote("^VIX")
    if q is None:
        import pytest; pytest.skip("Yahoo unreachable")
    assert isinstance(q, float) and 0 < q < 1000


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
    snap = fetchers.fetch_market_snapshot()
    if snap is None:
        import pytest; pytest.skip("Yahoo market snapshot unreachable")
    assert "vix" in snap


def test_fetchers_return_none_on_bad_input():
    """Garbage in -> None out (never raises)."""
    assert fetchers.fetch_yahoo_quote("TOTALLY_BOGUS_$$$") is None
    assert fetchers.fetch_json("https://example.invalid/url") is None
