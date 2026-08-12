"""Unit tests for the divination engines (keyless, deterministic per day)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.data import divination, astro

DATE = "2026-08-12"  # fixed date so assertions are stable


def test_bazi_transit_has_ganzi():
    r = divination.bazi_transit(DATE)
    if r is None:
        pytest.skip("lunar_python not installed")
    assert "流日" in r["spotlight"]
    assert "干支" in r["system_data_summary"]


def test_ziwei_transit_has_palace():
    r = divination.ziwei_transit(DATE)
    if r is None:
        pytest.skip("lunar_python not installed")
    assert "命宮" in r["spotlight"]
    assert "四化" in r["system_data_summary"]


def test_human_design_gate_number():
    r = divination.human_design_transit(DATE)
    if r is None:
        pytest.skip("pyswisseph not installed")
    assert "閘門" in r["spotlight"]
    # gate number 1-64 should appear
    import re
    m = re.search(r"(\d+)\s*號閘門", r["spotlight"])
    assert m and 1 <= int(m.group(1)) <= 64


def test_iching_hexagram_name():
    r = divination.iching_transit(DATE)
    if r is None:
        pytest.skip("astro/divination unavailable")
    assert "卦" in r["spotlight"]
    assert "動爻" in r["spotlight"]


def test_all_transits_keys():
    out = divination.all_transits(DATE)
    if not out:
        pytest.skip("no divination engines available")
    # whichever systems resolved must carry the two required fields
    for sid, payload in out.items():
        assert "spotlight" in payload and "system_data_summary" in payload


def test_divination_deterministic_same_day():
    """Same date -> identical output (no randomness)."""
    a = divination.all_transits(DATE)
    b = divination.all_transits(DATE)
    assert a == b


def test_astro_compute_transits_shape():
    t = astro.compute_transits(DATE)
    if t is None:
        pytest.skip("pyswisseph not installed")
    assert 0 <= t["sun_lon"] <= 360
    assert t["sun_mercury_orb"] is None or 0 <= t["sun_mercury_orb"] <= 180
