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


# ---- 十神對照（2026-09-08 用戶建議：流日帶入十神解析） -----------------------
def test_ten_god_standard_table():
    """五行×陰陽十神標準表抽樣驗證（日主丙）。"""
    from core.data.divination import ten_god
    assert ten_god("丙", "丙") == "比肩"    # 同我同性
    assert ten_god("丙", "丁") == "劫財"    # 同我異性
    assert ten_god("丙", "乙") == "正印"    # 生我異性（乙木生丙火）
    assert ten_god("丙", "甲") == "偏印"    # 生我同性
    assert ten_god("丙", "戊") == "食神"    # 我生同性
    assert ten_god("丙", "己") == "傷官"    # 我生異性
    assert ten_god("丙", "庚") == "偏財"    # 我剋同性（丙火剋庚金）
    assert ten_god("丙", "辛") == "正財"    # 我剋異性
    assert ten_god("丙", "壬") == "七殺"    # 剋我同性（壬水剋丙火）
    assert ten_god("丙", "癸") == "正官"    # 剋我異性


def test_bazi_transit_ten_god_with_day_master():
    pytest.importorskip("lunar_python")
    from core.data.divination import bazi_transit
    r = bazi_transit("2026-09-08", day_master="丙")     # 乙酉日
    assert "正印" in r["spotlight"] and "十神" in r["system_data_summary"]
    plain = bazi_transit("2026-09-08")
    assert "十神" not in plain["system_data_summary"]


def test_motto_keyword_bazi_includes_ten_god():
    from core.data.divination import motto_keywords
    kw = motto_keywords("2026-09-08", day_master="丙")
    assert kw["SYS_BAZI"] == "乙酉流日·正印日"


# ---- 紫微全盤十四主星（2026-09-08 第二波） -----------------------------------
def test_wu_xing_jv_arithmetic_matches_nayin():
    """五行局算術法 vs 納音法等價（iztro 三例＋甲子）。"""
    from core.data.natal import wu_xing_jv
    assert wu_xing_jv("丙", "子")[1] == 2     # 水二局
    assert wu_xing_jv("辛", "未")[1] == 5     # 土五局
    assert wu_xing_jv("庚", "申")[1] == 3     # 木三局
    assert wu_xing_jv("甲", "子")[1] == 4     # 金四局（海中金）


def test_an_zi_wei_day1_and_classical_examples():
    """局一落宮口訣（水丑/木辰/金亥/土午/火酉）＋福山堂例題（27日木三局→戌）。"""
    from core.data.natal import an_zi_wei
    assert an_zi_wei(1, 2) == 1    # 水二局初一→丑
    assert an_zi_wei(1, 3) == 4    # 木三局初一→辰
    assert an_zi_wei(1, 4) == 11   # 金四局初一→亥
    assert an_zi_wei(1, 5) == 6    # 土五局初一→午
    assert an_zi_wei(1, 6) == 9    # 火六局初一→酉
    assert an_zi_wei(27, 3) == 10  # 木三局27日→戌
    assert an_zi_wei(13, 6) == 11  # 火六局13日→亥


def test_ziwei_chart_galen_structure():
    """Galen 盤：土五局、命宮丙戌〔巨門〕、紫微在酉（紫貪同宮）、武破同宮巳。"""
    from core.data.natal import ziwei_chart
    c = ziwei_chart()
    if c is None:
        pytest.skip("lunar engine unavailable")
    assert c["ju"] == "土5局" and c["cmd_gan_zhi"] == "丙戌"
    assert c["cmd_stars"] == ["巨門"]
    assert c["palaces"]["兄弟"]["stars"] == ["紫微", "貪狼"]
    assert c["palaces"]["疾厄"]["stars"] == ["武曲", "破軍"]
    assert c["palaces"]["田宅"]["stars"] == ["廉貞", "七殺"]
    # 十四主星全數入盤
    all_stars = [s for pv in c["palaces"].values() for s in pv["stars"]]
    assert len(all_stars) == 14 and len(set(all_stars)) == 14
    # 天府＝紫微寅申軸鏡像：mirror(idx)=(4-idx)%12 → 兩支和 mod 12 == 4（寅申同宮除外）
    zi = "子丑寅卯辰巳午未申酉戌亥"
    assert (zi.index(c["ziwei_branch"]) + zi.index(c["tianfu_branch"])) % 12 == 4 \
        or c["ziwei_branch"] == c["tianfu_branch"]


# ---- 本日經典（2026-09-08 第四波） -------------------------------------------
def test_daily_classic_fallback_shape():
    """確定性 fallback：非空、≤100 字、含干支、白話句。"""
    pytest.importorskip("lunar_python")
    from core.data.divination import daily_classic
    c = daily_classic("2026-09-08")
    assert c and len(c) <= 100
    assert not c.startswith("乙酉")      # 干支前綴已移除（2026-09-10）
    assert "。" in c                     # 白話句


def test_daily_classic_per_system_variants():
    """每系統一則：非空、≤100 字、七術間有差異、無干支前綴。"""
    import re
    pytest.importorskip("lunar_python")
    from core.data.divination import daily_classic
    sids = ["SYS_AST", "SYS_HD", "SYS_ZW", "SYS_BAZI",
            "SYS_ICHING", "SYS_LIUYAO", "SYS_TAROT"]
    got = {s: daily_classic("2026-09-08", s) for s in sids}
    for s, c in got.items():
        assert c and len(c) <= 100, s
        assert "。" in c, s
    vals = [v for v in got.values() if v]
    assert len(set(vals)) >= 2           # 紫微/八字/易經樣板必各自不同
    gz = re.compile(r"^[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]・")
    assert not any(gz.match(v) for v in vals)
    # 八字頁的干支自然融入句中（非前綴）
    assert "乙酉" in got["SYS_BAZI"]


def test_news_card_dates_iso(tmp_path):
    """Financial/Global 新聞卡日期統一 YYYY-MM-DD（無時間）。"""
    import re
    from Global_Intelligence.pdf_generator import _fmt_time
    it = {"published": "Mon, 07 Sep 2026 09:38:00 GMT", "fetched_at": ""}
    d = _fmt_time(it)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", d), d
    it2 = {"published": "", "fetched_at": "2026-09-08T07:00:00+08:00"}
    assert _fmt_time(it2) == "2026-09-08"
    # Financial 的 _ftime 在 generate_daily_pdf 內部——以實際渲染出的卡驗證
    fitz = pytest.importorskip("fitz")
    from Financial_Intelligence.pdf_generator import generate_daily_pdf
    data = {"tw_margin_balance": None, "vix": None, "fear_and_greed": None,
            "spread_10y2y": None, "dxy": None,
            "market_intel": [{
                "title": "ISO date check", "summary": "summary " * 10,
                "source": "https://finance.yahoo.com/news/rss.xml", "link": "https://x.org",
                "published": "Mon, 07 Sep 2026 09:38:00 GMT"}]}
    out = str(tmp_path / "iso.pdf")
    generate_daily_pdf(out, data=data, date_str="2026-09-08")
    doc = fitz.open(out)
    text = "".join(pg.get_text() for pg in doc)
    doc.close()
    assert "2026-09-07" in text and "09-07 09:38" not in text
