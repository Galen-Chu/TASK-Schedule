#!/usr/bin/env python3
"""Daily divination engines for the Spiritual report (keyless, deterministic).

Built on two authoritative libraries:
  * ``lunar_python``  — 干支 (Gan-Zhi)、農曆、節氣（八字、紫微流日基底）
  * ``pyswisseph``    — 行星黃道位置（人類圖流日閘門、梅花易數起卦隨機性）

Each engine returns a ``{"spotlight": ..., "system_data_summary": ...}`` pair so
the Spiritual scheduler can overlay them onto the matching ``SYSTEMS_CONFIG``
entry. When a library is missing, every function returns ``None`` and the
caller keeps the static sample.
"""
import datetime
import logging

log = logging.getLogger("divination")

_HAS_LUNAR = True
try:
    from lunar_python import Solar
except ImportError:
    _HAS_LUNAR = False
    log.info("lunar_python 未安裝，八字/紫微將退回 sample。")

try:
    from core.data import astro as _astro
except Exception:  # noqa: BLE001
    _astro = None


# ---- helpers ---------------------------------------------------------------
def _solar_from(date_str):
    try:
        y, m, d = (int(x) for x in str(date_str).split("-"))
        return Solar.fromYmd(y, m, d)
    except Exception:  # noqa: BLE001
        return None


# ---- 八字干支 (Bazi) --------------------------------------------------------
_TEN_GODS = {"比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印"}
_WUXING = {"甲乙": "木", "丙丁": "火", "戊己": "土", "庚辛": "金", "壬癸": "水"}


def _wuxing(gan):
    for pair, el in _WUXING.items():
        if gan in pair:
            return el
    return "?"


def bazi_transit(date_str):
    """Daily Bazi (Gan-Zhi) reading via lunar_python. Returns dict or None."""
    s = _solar_from(date_str)
    if s is None:
        return None
    l = s.getLunar()
    day_gz = l.getDayInGanZhi()        # e.g. "戊午"
    day_gan = l.getDayGan()            # e.g. "戊"
    day_zhi = l.getDayZhi()
    year_gz = l.getYearInGanZhi()
    month_gz = l.getMonthInGanZhi()
    wu = _wuxing(day_gan)
    # crude element-flow reading: day stem element + day branch element
    branch_wu = {"子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
                 "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水"}
    zhi_wu = branch_wu.get(day_zhi, "?")
    flow = "相生" if (wu in "木火土金水" and _generates(wu, zhi_wu)) else "平和"

    spotlight = f"📍 {day_gz} 流日 (日干{day_gan}{wu} / 日支{day_zhi}{zhi_wu}，{flow})"
    summary = (f"當日干支：{day_gz} | 年柱：{year_gz} | 月柱：{month_gz} | "
               f"日干{day_gan}({wu}) | 五行動能：{wu}{zhi_wu}{flow}")
    return {"spotlight": spotlight, "system_data_summary": summary}


def _generates(a, b):
    gen = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
    return gen.get(a) == b


# ---- 紫微斗數 (Ziwei) ------------------------------------------------------
_ZW_BRANCH_PALACE = {
    "子": "命宮", "丑": "兄弟", "寅": "夫妻", "卯": "子女", "辰": "財帛", "巳": "疾厄",
    "午": "遷移", "未": "交友", "申": "官祿", "酉": "田宅", "戌": "福德", "亥": "父母",
}


def ziwei_transit(date_str):
    """Daily Ziwei Doushu reading (流日命宮 + 四化). Returns dict or None.

    Uses the day branch to place the 流日命宮, and a fixed day-index rotation
    for the four transformations (四化) so the reading is stable per day yet
    varies day-to-day.
    """
    s = _solar_from(date_str)
    if s is None:
        return None
    l = s.getLunar()
    day_zhi = l.getDayZhi()
    palace = _ZW_BRANCH_PALACE.get(day_zhi, "命宮")
    # Four Transformations (化祿/化權/化科/化忌) rotate by day stem index.
    stems = "甲乙丙丁戊己庚辛壬癸"
    idx = stems.find(l.getDayGan())
    # Simplified, deterministic rotation across 10 stems.
    rotations = [
        ("廉貞化祿", "破軍化權", "武曲化科", "太陽化忌"),
        ("天機化祿", "天梁化權", "紫微化科", "太陰化忌"),
        ("天同化祿", "天機化權", "文昌化科", "廉貞化忌"),
        ("太陰化祿", "太陽化權", "武曲化科", "天同化忌"),
        ("貪狼化祿", "太陰化權", "右弼化科", "天機化忌"),
    ]
    luck, power, sci, taboo = rotations[idx % len(rotations)]
    spotlight = f"📍 流日命宮在{day_zhi}宮 ({palace}) / 流日{luck} / {taboo}入命提醒審慎"
    summary = (f"流日命宮：{day_zhi}宮({palace}) | 流日四化：{luck}、{power}、{sci}、{taboo}")
    return {"spotlight": spotlight, "system_data_summary": summary}


# ---- 人類圖 (Human Design) —— I Ching gate map ----------------------------
# 64 gates ordered around the zodiac (Mandala). Each spans 5.625°.
# Index = floor(longitude / 5.625) mod 64. Map below gives (gate, line) themes.
_HD_GATES = [
    "自我表達", "方向", "秩序", "滋養", "等待", "摩擦", "軍隊", "貢獻",
    "專注", "行為", "和平", "警覺", "傾聽", "極限", "謙遜", "技能",
    "意見", "修正", "需要", "當下", "獵人", "優雅", "分裂", "品味",
    "重生", "累積", "滋養", "玩樂", "毅力", "情感", "影響", "持久",
    "隱退", "隱密", "力量", "判斷", "友誼", "戰士", "阻礙", "解放",
    "收縮", "增加", "突破", "決定", "活力", "決心", "深度", "井",
    "革命", "宇宙", "驟變", "驚嚇", "靜止", "漸進", "豐盛", "細節",
    "溫柔", "直覺", "混亂", "限制", "真理", "謬誤", "完成", "創造",
]


def human_design_transit(date_str):
    """Human Design daily Sun gate via Swiss Ephemeris. Returns dict or None.

    The Sun's ecliptic longitude maps to one of 64 gates (each 5.625°); the
    line (1-6) is the sub-division. This is a real, daily-shifting gate.
    """
    if _astro is None:
        return None
    t = _astro.compute_transits(date_str)
    if not t or t.get("sun_lon") is None:
        return None
    lon = t["sun_lon"]
    gate_idx = int(lon // 5.625) % 64
    gate_num = gate_idx + 1
    line = int(((lon % 5.625) / 5.625) * 6) + 1
    theme = _HD_GATES[gate_idx]
    spotlight = f"📍 流日太陽進入 {gate_num} 號閘門 (動爻 {line}.{line}，主題：{theme})"
    summary = (f"流日太陽閘門：{gate_num}（{theme}）| 當日動爻：{line} | "
               f"太陽黃經：{lon:.1f}°")
    return {"spotlight": spotlight, "system_data_summary": summary}


# ---- 梅花易數 (I Ching / Mei Hua) -----------------------------------------
_TRIGRAMS = ["乾", "兌", "離", "震", "巽", "坎", "艮", "坤"]  # 0-7 by value
_HEX_NAMES = {
    "111111": "乾為天", "011111": "澤天夬", "101111": "火天大有", "001111": "雷天大壯",
    "110111": "風天小畜", "100111": "水天需", "010111": "山天大畜", "000111": "地天泰",
    "111011": "天澤履", "011011": "兌為澤", "101011": "火澤睽", "001011": "雷澤歸妹",
    "110011": "風澤中孚", "100011": "水澤節", "010011": "山澤損", "000011": "地澤臨",
    "111101": "天火同人", "011101": "澤火革", "101101": "離為火", "001101": "雷火豐",
    "110101": "風火家人", "100101": "水火既濟", "010101": "山火賁", "000101": "地火明夷",
    "111001": "天雷無妄", "011001": "澤雷隨", "101001": "火雷噬嗑", "001001": "震為雷",
    "110001": "風雷益", "100001": "水雷屯", "010001": "山雷頤", "000001": "地雷復",
    "111110": "天風姤", "011110": "澤風大過", "101110": "火風鼎", "001110": "雷風恒",
    "110110": "巽為風", "100110": "水風井", "010110": "山風蠱", "000110": "地風升",
    "111100": "天水訟", "011100": "澤水困", "101100": "火水未濟", "001100": "雷水解",
    "110100": "風水渙", "100100": "坎為水", "010100": "山水蒙", "000100": "地水師",
    "111010": "天山遯", "011010": "澤山咸", "101010": "火山旅", "001010": "雷山小過",
    "110010": "風山漸", "100010": "水山蹇", "010010": "艮為山", "000010": "地山謙",
    "111000": "天地否", "011000": "澤地萃", "101000": "火地晉", "001000": "雷地豫",
    "110000": "風地觀", "100000": "水地比", "010000": "山地剝", "000000": "坤為地",
}


def _upper_from(date_str):
    """Upper trigram from solar longitude (Mei Hua: time → trigram)."""
    if _astro is None:
        return 0
    t = _astro.compute_transits(date_str)
    lon = (t or {}).get("sun_lon", 0) or 0
    return int(lon // 45) % 8


def _lower_from(date_str):
    """Lower trigram from day-of-year parity (stable, deterministic)."""
    try:
        y, m, d = (int(x) for x in str(date_str).split("-"))
        doy = datetime.date(y, m, d).timetuple().tm_yday
        return (doy + int(str(doy)[-1])) % 8
    except Exception:  # noqa: BLE001
        return 0


def iching_transit(date_str):
    """Daily I-Ching hexagram (Mei Hua). Returns dict or None.

    Upper trigram from the Sun's longitude band, lower from the day index;
    a changing line from the sub-position within the band. Purely
    deterministic so a given day always yields the same hexagram.
    """
    u = _upper_from(date_str)
    low = _lower_from(date_str)
    # build binary string upper(3)+lower(3), yang=1 yin=0 using trigram bit patterns
    tri_bits = ["111", "110", "101", "100", "011", "010", "001", "000"]  # by _TRIGRAMS index
    upper_bits = tri_bits[u]
    lower_bits = tri_bits[low]
    glyph = upper_bits + lower_bits
    name = _HEX_NAMES.get(glyph, "未知卦")
    # changing line (1-6) from longitude fraction
    if _astro is not None:
        lon = (_astro.compute_transits(date_str) or {}).get("sun_lon", 0) or 0
        moving = int((lon % 30) / 5) + 1
    else:
        moving = 1
    spotlight = f"📍 當日得《{name}》卦，動爻在 {moving}（梅花易數起卦）"
    summary = (f"主卦：{name}（上{_TRIGRAMS[u]}下{_TRIGRAMS[low]}）| 動爻：{moving} | "
               f"體用：{_TRIGRAMS[u]}與{_TRIGRAMS[low]}")
    return {"spotlight": spotlight, "system_data_summary": summary}


# ---- aggregate -------------------------------------------------------------
def all_transits(date_str):
    """Return {system_id: {spotlight, system_data_summary}} for all 5 systems.

    Western astrology comes from core.data.astro; the other four from here.
    Entries that fail to compute are simply omitted (caller keeps sample).
    """
    out = {}
    if _astro is not None:
        t = _astro.compute_transits(date_str)
        sp = _astro.astrology_spotlight(t) if t else None
        if sp:
            out["SYS_AST"] = {"spotlight": sp[0], "system_data_summary": sp[1]}
    for sid, fn in [("SYS_HD", human_design_transit),
                    ("SYS_ZW", ziwei_transit),
                    ("SYS_BAZI", bazi_transit),
                    ("SYS_ICHING", iching_transit)]:
        r = fn(date_str)
        if r:
            out[sid] = r
    return out
