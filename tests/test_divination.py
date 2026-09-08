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
    # 新格式「閘門 N.M」（閘 N = 易經 N 卦，線 1-6）
    import re
    m = re.search(r"閘門 (\d+)\.(\d)", r["spotlight"])
    assert m and 1 <= int(m.group(1)) <= 64 and 1 <= int(m.group(2)) <= 6


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


# ---- 2026-09-08：真實曼陀羅、正統起卦、四化表、轉換點、關鍵詞 ---------------
def test_hd_mandala_real_boundaries():
    """真實曼陀羅：0° 牡羊 = 閘 25、寶瓶 2° = 閘 41 起點、每閘 5.625°。"""
    from core.data.divination import hd_gate_line
    assert hd_gate_line(0.0) == (25, 2)      # 閘25起於雙魚28°15'，0°牡羊已入第2線
    assert hd_gate_line(302.0) == (41, 1)
    assert hd_gate_line(301.99) == (60, 6)          # 閘 41 前一格的盡頭
    g, l = hd_gate_line(302.0 + 5.625 * 3)
    assert g == 49


def test_hd_mandala_covers_all_gates_once():
    from core.data.divination import _HD_MANDALA
    assert sorted(_HD_MANDALA) == list(range(1, 65))


def test_galen_demo_natal_profile_is_5_1():
    """示範本命交叉驗證：真實曼陀羅下 Galen（1995-04-15 12:52 澎湖）回推
    人生角色 = 5/1，與本人自述一致。"""
    pytest.importorskip("swisseph")
    from core.data.natal import natal_hd
    n = natal_hd()
    if n is None:
        pytest.skip("swisseph engine unavailable")
    assert n["profile"] == "5/1"
    assert n["pers_gate"] == 42 and n["design_gate"] == 60


def test_galen_bazi_pillars_and_lunar():
    pytest.importorskip("lunar_python")
    from core.data.natal import natal_bazi
    b = natal_bazi()
    if b is None:
        pytest.skip("lunar engine unavailable")
    assert b["pillars"].startswith("乙亥 庚辰 丙子 甲午")
    assert "三月十六" in b["lunar"] and "午" in b["lunar"]


def test_ziwei_real_si_hua_table():
    from core.data.divination import _ZW_SI_HUA
    assert _ZW_SI_HUA["乙"] == ("天機化祿", "天梁化權", "紫微化科", "太陰化忌")
    assert _ZW_SI_HUA["丁"] == ("太陰化祿", "天同化權", "天機化科", "巨門化忌")
    assert len(_ZW_SI_HUA) == 10


def test_mei_hua_year_month_day_hour_cast():
    """年月日時起卦：公式 (年支+月+日)%8 上卦、(+時)%8 下卦、總和%6 動爻。"""
    from core.data.divination import mei_hua_cast, _hex_name_from_trigrams
    u, low, moving = mei_hua_cast(12, 3, 16, 7)     # 亥年3月16日午時
    assert 1 <= u <= 8 and 1 <= low <= 8 and 1 <= moving <= 6
    assert _hex_name_from_trigrams(1, 1) == "乾為天"
    assert _hex_name_from_trigrams(7, 6) == "山水蒙"  # 上艮下坎
    assert _hex_name_from_trigrams(6, 1) == "水天需"


def test_transitions_detect_known_ingress():
    """2026-09-23 太陽由處女進入天秤（秋分）——轉換偵測必須命中。"""
    pytest.importorskip("swisseph")
    from core.data.divination import transitions
    hits = transitions("2026-09-23")
    assert any("太陽" in h and "天秤座" in h for h in hits)


def test_motto_keywords_cover_seven_systems():
    from core.data.divination import motto_keywords
    kw = motto_keywords("2026-09-08")
    assert set(kw) >= {"SYS_AST", "SYS_HD", "SYS_BAZI", "SYS_ZW",
                       "SYS_ICHING", "SYS_LIUYAO", "SYS_TAROT"}
    assert all(v for v in kw.values())


def test_natal_section_none_safe():
    from core.data.natal import build_natal_section
    ns = build_natal_section("2026-09-08")
    assert isinstance(ns, dict) and ns
    for v in ns.values():
        assert set(v) == {"params", "compare"}
