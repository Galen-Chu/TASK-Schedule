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
_WUXING = {"甲乙": "木", "丙丁": "火", "戊己": "土", "庚辛": "金", "壬癸": "水"}


def _wuxing(gan):
    for pair, el in _WUXING.items():
        if gan in pair:
            return el
    return "?"


_GAN_ELEM = "木火土金水"          # 甲乙木 丙丁火 戊己土 庚辛金 壬癸水
_ELEM_GEN = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
_ELEM_CTRL = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}


def _generates(a, b):
    return _ELEM_GEN.get(a) == b


def ten_god(day_master, other):
    """十神：日主 vs 他干（五行×陰陽標準表）。八字分析的核心對照系統。"""
    elem = lambda g: _GAN_ELEM["甲乙丙丁戊己庚辛壬癸".find(g) // 2]
    polar = lambda g: "甲乙丙丁戊己庚辛壬癸".find(g) % 2     # 0 陽 1 陰
    me, ot, same_pol = elem(day_master), elem(other), polar(day_master) == polar(other)
    if me == ot:
        return "比肩" if same_pol else "劫財"
    if _ELEM_GEN.get(me) == ot:                    # 我生
        return "食神" if same_pol else "傷官"
    if _ELEM_GEN.get(ot) == me:                    # 生我
        return "偏印" if same_pol else "正印"
    if _ELEM_CTRL.get(me) == ot:                   # 我剋
        return "偏財" if same_pol else "正財"
    if _ELEM_CTRL.get(ot) == me:                   # 剋我
        return "七殺" if same_pol else "正官"
    return "?"


def bazi_transit(date_str, day_master=None):
    """Daily Bazi (Gan-Zhi) reading via lunar_python. Returns dict or None.

    ``day_master``（本命日主，如示範本命「丙」）傳入時，流日干支以十神對照
    呈現——十神是四柱八字最核心的對照系統，流日通用觀點即以「流日干 vs
    日主」的十神定調當日課題。無日主時退回純五行生剋說明。
    """
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
    branch_wu = {"子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
                 "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水"}
    zhi_wu = branch_wu.get(day_zhi, "?")
    flow = "相生" if (wu in _GAN_ELEM and _generates(wu, zhi_wu)) else "平和"
    tg = ten_god(day_master, day_gan) if day_master else None
    tg_note = (f"，流日干對日主{day_master}為【{tg}】" if tg else "")

    spotlight = f"📍 {day_gz} 流日 (日干{day_gan}{wu} / 日支{day_zhi}{zhi_wu}，{flow}){tg_note}"
    summary = (f"當日干支：{day_gz} | 年柱：{year_gz} | 月柱：{month_gz} | "
               f"日干{day_gan}({wu}) | 五行動能：{wu}{zhi_wu}{flow}"
               + (f" | 十神（vs 日主{day_master}）：{tg}" if tg else ""))
    return {"spotlight": spotlight, "system_data_summary": summary}


# ---- 紫微斗數 (Ziwei) ------------------------------------------------------
# 正統十天干四化表（中州派通行版）。2026-09-08 前為 5 列輪播的簡化表，
# 丁幹起即錯、己~癸全數錯位。
_ZW_SI_HUA = {
    "甲": ("廉貞化祿", "破軍化權", "武曲化科", "太陽化忌"),
    "乙": ("天機化祿", "天梁化權", "紫微化科", "太陰化忌"),
    "丙": ("天同化祿", "天機化權", "文昌化科", "廉貞化忌"),
    "丁": ("太陰化祿", "天同化權", "天機化科", "巨門化忌"),
    "戊": ("貪狼化祿", "太陰化權", "右弼化科", "天機化忌"),
    "己": ("武曲化祿", "貪狼化權", "天梁化科", "文曲化忌"),
    "庚": ("太陽化祿", "武曲化權", "太陰化科", "天同化忌"),
    "辛": ("巨門化祿", "太陽化權", "文曲化科", "文昌化忌"),
    "壬": ("天梁化祿", "紫微化權", "左輔化科", "武曲化忌"),
    "癸": ("破軍化祿", "巨門化權", "太陰化科", "貪狼化忌"),
}

# 十二宮依命宮逆行排列（兄弟在命宮逆行第一支）
_BRANCHES = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
_PALACES = ["命宮", "兄弟", "夫妻", "子女", "財帛", "疾厄", "遷移", "交友", "官祿", "田宅", "福德", "父母"]


def zw_palace_for(day_zhi, natal_cmd_branch=None):
    """流日地支落在本命哪一宮。無本命資料時退化為固定 12 宮起命宮於子。"""
    base = _BRANCHES.index(natal_cmd_branch) if natal_cmd_branch in _BRANCHES else 0
    pal_idx = (base - _BRANCHES.index(day_zhi)) % 12
    return _PALACES[pal_idx]


def ziwei_transit(date_str, natal_cmd_branch=None):
    """Daily Ziwei Doushu reading（流日命宮＋日干四化）.

    流日命宮＝日支所在宮；有本命命宮時以本命盤十二宮對照（zw_palace_for），
    無則以子起命宮的固定版面呈現。四化為正統日干四化。
    """
    s = _solar_from(date_str)
    if s is None:
        return None
    l = s.getLunar()
    day_zhi = l.getDayZhi()
    day_gan = l.getDayGan()
    palace = zw_palace_for(day_zhi, natal_cmd_branch)
    luck, power, sci, taboo = _ZW_SI_HUA.get(day_gan, ("", "", "", ""))
    where = f"{day_zhi}宮（本命{palace}）" if natal_cmd_branch else f"{day_zhi}宮（{palace}）"
    spotlight = f"📍 流日命宮在{where} / 流日{luck} / {taboo}提醒審慎"
    summary = (f"流日命宮：{where} | 流日四化（{day_gan}干）：{luck}、{power}、{sci}、{taboo}")
    return {"spotlight": spotlight, "system_data_summary": summary,
            "day_branch": day_zhi, "day_gan": day_gan}


# ---- 人類圖 (Human Design) —— Rave Mandala ---------------------------------
# 真實曼陀羅：閘 41 起於寶瓶 2°（黃經 302°），每閘 5°37'30"（=5.625°），
# 順黃經依序排列（Barney+flow / Gates-and-Zodiac-Placements 對照表驗證，
# 2026-09-08）。閘門 N 對應易經第 N 卦（King Wen），卦名即中文名依據。
_HD_MANDALA = [
    41, 19, 13, 49, 30, 55, 37, 63, 22, 36, 25, 17, 21, 51, 42, 3,
    27, 24, 2, 23, 8, 20, 16, 35, 45, 12, 15, 52, 39, 53, 62, 56,
    31, 33, 7, 4, 29, 59, 40, 64, 47, 6, 46, 18, 48, 57, 32, 50,
    28, 44, 1, 43, 14, 34, 9, 5, 26, 11, 10, 58, 38, 54, 61, 60,
]
_HD_START_LON = 302.0      # 2° Aquarius

# 閘門 → 卦名（King Wen，閘 N = 第 N 卦）＋主題詞（HD 命名脈絡）
_GATE_INFO = {
    1: ("乾為天", "創造表達"), 2: ("坤為地", "方向包容"), 3: ("水雷屯", "開創秩序"),
    4: ("山水蒙", "公式啟蒙"), 5: ("水天需", "等待時機"), 6: ("天水訟", "衝突調解"),
    7: ("地水師", "領導統御"), 8: ("水地比", "貢獻凝聚"), 9: ("風天小畜", "專注聚焦"),
    10: ("天澤履", "自處行為"), 11: ("地天泰", "理想平衡"), 12: ("天地否", "靜止緘默"),
    13: ("天火同人", "聆聽見證"), 14: ("火天大有", "掌握資源"), 15: ("地山謙", "謙遜"),
    16: ("雷地豫", "熱情豫樂"), 17: ("澤雷隨", "順勢跟隨"), 18: ("山風蠱", "修正除弊"),
    19: ("地澤臨", "需求感知"), 20: ("風地觀", "觀察當下"), 21: ("火雷噬嗑", "決斷"),
    22: ("山火賁", "裝飾賁美"), 23: ("山地剝", "剝落放手"), 24: ("地雷復", "復始更新"),
    25: ("天雷無妄", "無妄天真"), 26: ("山天大畜", "蓄積大能"), 27: ("山雷頤", "頤養滋養"),
    28: ("澤風大過", "承重過載"), 29: ("坎為水", "險難習坎"), 30: ("離為火", "光明依附"),
    31: ("澤山咸", "感應"), 32: ("雷風恆", "恆常持續"), 33: ("天山遯", "退避遯世"),
    34: ("雷天大壯", "威力大壯"), 35: ("火地晉", "晉升前進"), 36: ("地火明夷", "晦明養晦"),
    37: ("風火家人", "家人內治"), 38: ("火澤睽", "睽異分歧"), 39: ("水山蹇", "蹇難知止"),
    40: ("雷水解", "解脫赦免"), 41: ("山澤損", "損減收縮"), 42: ("風雷益", "增益豐盛"),
    43: ("澤天夬", "決斷清除"), 44: ("天風姤", "姤遇微交"), 45: ("澤地萃", "萃聚"),
    46: ("地風升", "升進"), 47: ("澤水困", "困窘自處"), 48: ("水風井", "井源不竭"),
    49: ("澤火革", "革變"), 50: ("火風鼎", "鼎新養賢"), 51: ("震為雷", "震動驚蟄"),
    52: ("艮為山", "艮止安定"), 53: ("風山漸", "漸進"), 54: ("雷澤歸妹", "歸妹終始"),
    55: ("雷火豐", "豐盛"), 56: ("火山旅", "旅居歷練"), 57: ("巽為風", "巽順滲透"),
    58: ("兌為澤", "兌悅"), 59: ("風水渙", "渙散離聚"), 60: ("水澤節", "節制守分"),
    61: ("風澤中孚", "中孚誠信"), 62: ("雷山小過", "小過細行"), 63: ("水火既濟", "既濟完成"),
    64: ("火水未濟", "未濟轉化"),
}


def hd_gate_line(lon):
    """黃經 → (閘門號, 線1-6)。真實曼陀羅順序（閘 41 起於寶瓶 2°）。"""
    if lon is None:
        return None, None
    idx = int(((lon - _HD_START_LON) % 360) // 5.625)
    gate = _HD_MANDALA[idx]
    frac = ((lon - _HD_START_LON) % 360) - idx * 5.625
    line = int(frac / 5.625 * 6) + 1
    return gate, min(6, max(1, line))


def human_design_transit(date_str):
    """Human Design daily Sun gate via Swiss Ephemeris. Returns dict or None.

    黃經為真值（pyswisseph）；閘門/線由真實曼陀羅表決定（閘 N = 易經 N 卦）。
    """
    if _astro is None:
        return None
    t = _astro.compute_transits(date_str)
    if not t or t.get("sun_lon") is None:
        return None
    lon = t["sun_lon"]
    gate, line = hd_gate_line(lon)
    hex_name, theme = _GATE_INFO.get(gate, ("未知", "未知"))
    spotlight = f"📍 流日太陽進入閘門 {gate}.{line}《{hex_name}》（{theme}）"
    summary = (f"流日太陽閘門：{gate}（{hex_name}·{theme}）| 線：{line} | "
               f"太陽黃經：{lon:.1f}°")
    return {"spotlight": spotlight, "system_data_summary": summary}


# ---- 梅花易數 (I Ching / Mei Hua) -----------------------------------------
_TRIGRAMS = ["乾", "兌", "離", "震", "巽", "坎", "艮", "坤"]  # index = 先天卦數-1
_TRI_BITS = ["111", "110", "101", "100", "011", "010", "001", "000"]
_HEX_NAMES = {
    "111111": "乾為天", "011111": "澤天夬", "101111": "火天大有", "001111": "雷天大壯",
    "110111": "風天小畜", "100111": "水天需", "010111": "山天大畜", "000111": "地天泰",
    "111011": "天澤履", "011011": "兌為澤", "101011": "火澤睽", "001011": "雷澤歸妹",
    "110011": "風澤中孚", "100011": "水澤節", "010011": "山澤損", "000011": "地澤臨",
    "111101": "天火同人", "011101": "澤火革", "101101": "離為火", "001101": "雷火豐",
    "110101": "風火家人", "100101": "水火既濟", "010101": "山火賁", "000101": "地火明夷",
    "111001": "天雷無妄", "011001": "澤雷隨", "101001": "火雷噬嗑", "001001": "震為雷",
    "110001": "風雷益", "100001": "水雷屯", "010001": "山雷頤", "000001": "地雷復",
    "111110": "天風姤", "011110": "澤風大過", "101110": "火風鼎", "001110": "雷風恆",
    "110110": "巽為風", "100110": "水風井", "010110": "山風蠱", "000110": "地風升",
    "111100": "天水訟", "011100": "澤水困", "101100": "火水未濟", "001100": "雷水解",
    "110100": "風水渙", "100100": "坎為水", "010100": "山水蒙", "000100": "地水師",
    "111010": "天山遯", "011010": "澤山咸", "101010": "火山旅", "001010": "雷山小過",
    "110010": "風山漸", "100010": "水山蹇", "010010": "艮為山", "000010": "地山謙",
    "111000": "天地否", "011000": "澤地萃", "101000": "火地晉", "001000": "雷地豫",
    "110000": "風地觀", "100000": "水地比", "010000": "山地剝", "000000": "坤為地",
}


# (上卦, 下卦) -> 卦名——結構化 King Wen 八八方陣（與 _GATE_INFO 閘門卦名
# 全數交叉一致）。舊的位元串鍵 _HEX_NAMES 與上下卦組成本來就對不上（卦名
# 與宣稱的上下卦互相矛盾），2026-09-08 改為顯式表，不再經位元轉換。
_HEX_BY_PAIR = {
    ("乾", "乾"): "乾為天", ("乾", "兌"): "天澤履", ("乾", "離"): "天火同人",
    ("乾", "震"): "天雷無妄", ("乾", "巽"): "天風姤", ("乾", "坎"): "天水訟",
    ("乾", "艮"): "天山遯", ("乾", "坤"): "天地否",
    ("兌", "乾"): "澤天夬", ("兌", "兌"): "兌為澤", ("兌", "離"): "澤火革",
    ("兌", "震"): "澤雷隨", ("兌", "巽"): "澤風大過", ("兌", "坎"): "澤水困",
    ("兌", "艮"): "澤山咸", ("兌", "坤"): "澤地萃",
    ("離", "乾"): "火天大有", ("離", "兌"): "火澤睽", ("離", "離"): "離為火",
    ("離", "震"): "火雷噬嗑", ("離", "巽"): "火風鼎", ("離", "坎"): "火水未濟",
    ("離", "艮"): "火山旅", ("離", "坤"): "火地晉",
    ("震", "乾"): "雷天大壯", ("震", "兌"): "雷澤歸妹", ("震", "離"): "雷火豐",
    ("震", "震"): "震為雷", ("震", "巽"): "雷風恆", ("震", "坎"): "雷水解",
    ("震", "艮"): "雷山小過", ("震", "坤"): "雷地豫",
    ("巽", "乾"): "風天小畜", ("巽", "兌"): "風澤中孚", ("巽", "離"): "風火家人",
    ("巽", "震"): "風雷益", ("巽", "巽"): "巽為風", ("巽", "坎"): "風水渙",
    ("巽", "艮"): "風山漸", ("巽", "坤"): "風地觀",
    ("坎", "乾"): "水天需", ("坎", "兌"): "水澤節", ("坎", "離"): "水火既濟",
    ("坎", "震"): "水雷屯", ("坎", "巽"): "水風井", ("坎", "坎"): "坎為水",
    ("坎", "艮"): "水山蹇", ("坎", "坤"): "水地比",
    ("艮", "乾"): "山天大畜", ("艮", "兌"): "山澤損", ("艮", "離"): "山火賁",
    ("艮", "震"): "山雷頤", ("艮", "巽"): "山風蠱", ("艮", "坎"): "山水蒙",
    ("艮", "艮"): "艮為山", ("艮", "坤"): "山地剝",
    ("坤", "乾"): "地天泰", ("坤", "兌"): "地澤臨", ("坤", "離"): "地火明夷",
    ("坤", "震"): "地雷復", ("坤", "巽"): "地風升", ("坤", "坎"): "地水師",
    ("坤", "艮"): "地山謙", ("坤", "坤"): "坤為地",
}


def _hex_name_from_trigrams(upper_num, lower_num):
    """卦名＝（上卦, 下卦）查表；輸入為先天卦數 1-8（乾兌離震巽坎艮坤）。"""
    return _HEX_BY_PAIR.get((_TRIGRAMS[upper_num - 1], _TRIGRAMS[lower_num - 1]),
                            "未知卦")


def mei_hua_cast(year_zhi_idx, lunar_month, lunar_day, hour_zhi_idx):
    """正統梅花易數「年月日時起卦」：農曆年支數＋月＋日 除 8 餘為上卦，
    加時支數除 8 餘為下卦，總和除 6 餘為動爻（餘 0 取 8/6）。"""
    u = (year_zhi_idx + lunar_month + lunar_day) % 8 or 8
    low = (year_zhi_idx + lunar_month + lunar_day + hour_zhi_idx) % 8 or 8
    moving = (year_zhi_idx + lunar_month + lunar_day + hour_zhi_idx) % 6 or 6
    return u, low, moving


def iching_transit(date_str):
    """Daily I-Ching hexagram — 正統梅花易數年月日時起卦（農曆）。"""
    s = _solar_from(date_str)
    if s is None:
        return None
    l = s.getLunar()
    year_zhi_idx = _BRANCHES.index(l.getYearZhi()) + 1
    hour_zhi_idx = _BRANCHES.index(l.getTimeZhi()) + 1
    u, low, moving = mei_hua_cast(year_zhi_idx, l.getMonth(), l.getDay(), hour_zhi_idx)
    name = _hex_name_from_trigrams(u, low)
    spotlight = f"📍 當日得《{name}》卦，動爻在 {moving}（梅花易數・年月日時起卦）"
    summary = (f"主卦：{name}（上{_TRIGRAMS[u-1]}下{_TRIGRAMS[low-1]}）| 動爻：{moving} | "
               f"起卦：{l.getMonth()}月{l.getDay()}日{hour_zhi_idx}時")
    return {"spotlight": spotlight, "system_data_summary": summary}


# ---- 易經六爻 (Liu Yao / Six Lines divination) ------------------------------
# 爻位通用釋義（初/二/三/四/五/上 × 陰陽質性）。2026-09-08 前直接借用乾/坤
# 二卦的爻辭（潛龍勿用、亢龍有悔…）套用到任何卦——方法論錯置，已改為
# 不指涉特定卦的爻位通則。
_LIUYAO_POS = {
    0: ("潛藏待時，醞釀先行", "靜觀其變，慎始為宜"),
    1: ("嶄露頭角，穩健推進", "含蓄持中，借力使力"),
    2: ("勤奮警惕，調整節奏", "含章不顯，等待時機"),
    3: ("躍升前夕，進退有據", "謹言慎行，整備資源"),
    4: ("當權主導，利見大人", "柔中得正，以和為貴"),
    5: ("盈滿思退，防範過亢", "陰極思變，靜待轉機"),
}

def liuyao_transit(date_str):
    """易經六爻：以日干支起卦（干定上卦、支定下卦、干支和定動爻）。"""
    if not _HAS_LUNAR:
        return None
    try:
        solar = _solar_from(date_str)
        lunar = solar.getLunar()
        day_gan = lunar.getDayGan()   # 日干
        day_zhi = lunar.getDayZhi()   # 日支
        gan_num = "甲乙丙丁戊己庚辛壬癸".index(day_gan) + 1  # 1-10
        zhi_num = _BRANCHES.index(day_zhi) + 1               # 1-12
        upper_num = (gan_num % 8) or 8
        lower_num = (zhi_num % 8) or 8
        moving_num = ((gan_num + zhi_num) % 6) or 6
        upper, lower = _TRIGRAMS[upper_num - 1], _TRIGRAMS[lower_num - 1]
        hex_name = _hex_name_from_trigrams(upper_num, lower_num)
        yao_names = ["初", "二", "三", "四", "五", "上"]
        lines = []
        for i in range(6):
            yang = ((lower_num if i < 3 else upper_num) + i) % 2 == 1
            polarity = "陽" if yang else "陰"
            label = "九" if yang else "六"
            meaning = _LIUYAO_POS[i][0 if yang else 1]
            is_moving = (i + 1) == moving_num
            lines.append(f"{yao_names[i]}{label}（{polarity}爻{'·動爻' if is_moving else ''}）：{meaning}")
        spotlight = f"📍 日干支 {day_gan}{day_zhi} 起卦，得《{hex_name}》，動爻在第 {moving_num} 爻"
        summary = (f"主卦：{hex_name}（上{upper}下{lower}）| 動爻：第{moving_num}爻 | "
                   f"日干支：{day_gan}{day_zhi}")
        return {"spotlight": spotlight, "system_data_summary": summary,
                "lines": lines, "moving_line": moving_num}
    except Exception as exc:
        log.warning("liuyao failed: %s", exc)
        return None


# ---- 塔羅牌 (Tarot daily draw) ----------------------------------------------
_TAROT_MAJOR = [
    ("0 愚者", ["新開始", "冒險", "自由", "純真"], "踏出舒適圈，以初學者心態迎接未知。信任直覺的引導。"),
    ("I 魔術師", ["創造", "意志", "專注", "資源"], "你擁有實現目標的所有工具。集中意志力，付諸行動。"),
    ("II 女祭司", ["直覺", "智慧", "內在", "寧靜"], "答案在內心而非外在。靜心傾聽，信任潛意識的訊息。"),
    ("III 皇后", ["豐盛", "創造力", "母性", "感官"], "滋養自己與他人。享受當下的美好，創造力正處於高峰。"),
    ("IV 皇帝", ["秩序", "權威", "穩定", "結構"], "以紀律和邏輯建立秩序。今天適合規劃與組織。"),
    ("V 教皇", ["傳統", "學習", "指引", "信念"], "向導師或傳統智慧學習。遵循已驗證的方法論。"),
    ("VI 戀人", ["選擇", "和諧", "關係", "價值觀"], "面對重要的價值選擇。以心為指引，做出真實的決定。"),
    ("VII 戰車", ["決心", "勝利", "意志", "掌控"], "以堅定意志駕馭方向。專注目標，克服障礙。"),
    ("VIII 力量", ["內在力量", "勇氣", "耐心", "慈悲"], "以柔克剛。真正的力量來自耐心與慈悲，而非強迫。"),
    ("IX 隱者", ["內省", "智慧", "孤獨", "指引"], "暫時退隱充電。在獨處中找到答案。"),
    ("X 命運之輪", ["轉變", "週期", "機會", "命運"], "局勢正在轉動。順應變化，把握時機。"),
    ("XI 正義", ["公正", "平衡", "因果", "責任"], "因果法則運作中。為選擇負責，追求公平。"),
    ("XII 吊人", ["犧牲", "換位", "等待", "放下"], "暫停行動，從不同角度看事情。放下執著。"),
    ("XIII 死神", ["結束", "轉化", "重生", "釋放"], "舊的結束是新的開始。釋放不再服務你的事物。"),
    ("XIV 節制", ["平衡", "融合", "療癒", "耐心"], "在極端之間找到中道。調和衝突，融合資源。"),
    ("XV 惡魔", ["束縛", "慾望", "依賴", "解放"], "看見束縛自己的模式。覺察即是解脫的第一步。"),
    ("XVI 高塔", ["突變", "崩塌", "覺醒", "真相"], "既有結構突然瓦解。擁抱真相，從廢墟中重建。"),
    ("XVII 星星", ["希望", "療癒", "信念", "靈感"], "風暴後的寧靜。保持信念，靈感正在流入。"),
    ("XVIII 月亮", ["幻象", "潛意識", "不安", "直覺"], "並非所有如表面所見。信任直覺，穿越迷霧。"),
    ("XIX 太陽", ["成功", "喜悅", "活力", "明確"], "光明與溫暖的日子。自信地表達，成功自然到來。"),
    ("XX 審判", ["覺醒", "重生", "召喚", "整合"], "聆聽內在召喚。整合過去經驗，迎接蛻變。"),
    ("XXI 世界", ["完成", "整合", "成就", "圓滿"], "週期完成。慶祝成就，準備展開新篇章。"),
]

def tarot_transit(date_str):
    """塔羅牌：以日期為種子，決定性地抽取三張牌（過去/現在/未來）。
    Returns dict or None."""
    import hashlib
    try:
        h = hashlib.sha256(date_str.encode("utf-8")).hexdigest()
        # 三張牌：從 22 張大牌中選取，由 hash 決定
        nums = []
        for i in range(3):
            idx = int(h[i*4:i*4+4], 16) % 22
            nums.append(idx)
        # 確保三張不重複（若重複則偏移）
        seen = set()
        for i, n in enumerate(nums):
            while n in seen:
                n = (n + 1) % 22
            nums[i] = n
            seen.add(n)
        cards = []
        positions = ["過去／根源", "現在／課題", "未來／指引"]
        for i, (idx, pos) in enumerate(zip(nums, positions)):
            name, keywords, interp = _TAROT_MAJOR[idx]
            # 正逆位由 hash 決定
            reversed_ = bool(int(h[12 + i], 16) % 2)
            orient = "逆位" if reversed_ else "正位"
            # 逆位時調整解讀
            rev_hint = {"正位": "", "逆位": "（能量內化或受阻，需向內在探索）"}
            cards.append(f"{pos}：{name}（{orient}）— {interp}{rev_hint[orient]}")
        spotlight = f"📍 今日牌陣：{cards[0].split('：')[1][:20]} → {cards[1].split('：')[1][:20]} → {cards[2].split('：')[1][:20]}"
        summary = " | ".join(c.split("—")[0].strip() for c in cards)
        return {"spotlight": spotlight, "system_data_summary": summary, "cards": cards}
    except Exception as exc:
        log.warning("tarot failed: %s", exc)
        return None


# ---- 轉換點偵測 (transition points) -----------------------------------------
def _dstr(date_str, delta):
    import datetime as _dt
    d = _dt.date.fromisoformat(str(date_str)) + _dt.timedelta(days=delta)
    return d.isoformat()


def _sign_of(lon):
    if lon is None:
        return None
    from core.data.astro import _SIGNS_ZH as _SIGNS
    return _SIGNS[int(lon // 30) % 12]


def transitions(date_str):
    """跨日轉換點偵測：比較 date±1 的各系統狀態。回傳中文提示 list（空=無）。

    涵蓋有連續天文/曆法意義者：行星換座（太陽/月亮/水星）、人類圖換閘、
    八字換月柱（節氣交換）。紫微流日四化逐日輪替、梅花/六爻/塔羅為逐日
    起卦（無跨日連續性概念），不在此列。
    """
    out = []
    try:
        if _astro is not None and _astro._HAS_SWISSEPH:
            today = _astro.compute_transits(date_str) or {}
            prev = _astro.compute_transits(_dstr(date_str, -1)) or {}
            nxt = _astro.compute_transits(_dstr(date_str, 1)) or {}
            for label, lon_key in (("太陽", "sun_lon"), ("月亮", "moon_lon"),
                                   ("水星", "mercury_lon")):
                t_s, p_s, n_s = (_sign_of(today.get(lon_key)), _sign_of(prev.get(lon_key)),
                                 _sign_of(nxt.get(lon_key)))
                if t_s and p_s and t_s != p_s:
                    out.append(f"⚡ 今日轉換：{label}由{p_s}座進入{t_s}座")
                elif t_s and n_s and t_s != n_s:
                    out.append(f"⚡ 明日轉換（預告）：{label}將由{t_s}座進入{n_s}座")
            t_g, _ = hd_gate_line(today.get("sun_lon"))
            p_g, _ = hd_gate_line(prev.get("sun_lon"))
            n_g, _ = hd_gate_line(nxt.get("sun_lon"))
            if t_g and p_g and t_g != p_g:
                hex_name, theme = _GATE_INFO.get(t_g, ("", ""))
                out.append(f"⚡ 今日轉換：人類圖太陽換入 {t_g} 號閘門《{hex_name}》（{theme}）")
            elif t_g and n_g and t_g != n_g:
                hex_name, theme = _GATE_INFO.get(n_g, ("", ""))
                out.append(f"⚡ 明日轉換（預告）：人類圖太陽將換入 {n_g} 號閘門《{hex_name}》（{theme}）")
        if _HAS_LUNAR:
            s = _solar_from(date_str)
            sp = _solar_from(_dstr(date_str, -1))
            if s is not None and sp is not None:
                m_now = s.getLunar().getMonthInGanZhi()
                m_prev = sp.getLunar().getMonthInGanZhi()
                if m_now != m_prev:
                    try:
                        jq = s.getLunar().getPrevJieQi()
                        jieqi = jq.getName() if hasattr(jq, "getName") else str(jq)
                    except Exception:  # noqa: BLE001
                        jieqi = "節氣"
                    out.append(f"⚡ 今日轉換：交{jieqi}，月柱由{m_prev}轉{m_now}")
    except Exception as exc:  # noqa: BLE001 — 轉換偵測不得影響報告產出
        log.warning("transitions failed: %s", exc)
    return out


# ---- 當日關鍵詞（motto 選擇器素材） ----------------------------------------
def motto_keywords(date_str, day_master=None):
    """每系統一句「當日關鍵詞」——全部取自各系統的當日 live 計算（與 spotlight
    同源：pyswisseph 黃經 / lunar_python 干支農曆 / 日期 hash 塔羅），資料流
    單一可追溯，不引入外部資料。回傳 {system_id: keyword}。
    """
    out = {}
    try:
        if _astro is not None:
            t = _astro.compute_transits(date_str)
            if t:
                out["SYS_AST"] = f"日行{t['sun_sign_zh']}·月行{t['moon_sign_zh']}"
                gate, line = hd_gate_line(t.get("sun_lon"))
                if gate:
                    hex_name, theme = _GATE_INFO.get(gate, ("", ""))
                    out["SYS_HD"] = f"閘{gate}.{line}《{hex_name}》·{theme}"
        if _HAS_LUNAR:
            s = _solar_from(date_str)
            if s is not None:
                l = s.getLunar()
                day_gz = l.getDayInGanZhi()
                wu = _wuxing(l.getDayGan())
                tg = ten_god(day_master, l.getDayGan()) if day_master else None
                out["SYS_BAZI"] = (f"{day_gz}流日·{tg}日" if tg else f"{day_gz}流日·日干{wu}")
                palace = zw_palace_for(l.getDayZhi())
                luck, _, _, _ = _ZW_SI_HUA.get(l.getDayGan(), ("", "", "", ""))
                out["SYS_ZW"] = f"流日命宮{palace}·{luck}"
                u, low, moving = mei_hua_cast(
                    _BRANCHES.index(l.getYearZhi()) + 1, l.getMonth(), l.getDay(),
                    _BRANCHES.index(l.getTimeZhi()) + 1)
                out["SYS_ICHING"] = f"《{_hex_name_from_trigrams(u, low)}》動{moving}爻"
                gan_num = "甲乙丙丁戊己庚辛壬癸".index(l.getDayGan()) + 1
                zhi_num = _BRANCHES.index(l.getDayZhi()) + 1
                un, ln = (gan_num % 8) or 8, (zhi_num % 8) or 8
                out["SYS_LIUYAO"] = (f"《{_hex_name_from_trigrams(un, ln)}》"
                                     f"第{(gan_num + zhi_num) % 6 or 6}爻動")
        to = tarot_transit(date_str)
        if to and to.get("cards"):
            now_card = to["cards"][1].split("：", 1)[-1].split("（")[0].strip()
            out["SYS_TAROT"] = f"現在牌·{now_card}"
    except Exception as exc:  # noqa: BLE001
        log.warning("motto keywords failed: %s", exc)
    return out


# ---- aggregate -------------------------------------------------------------
def all_transits(date_str, natal_cmd_branch=None, day_master=None):
    """Return {system_id: {spotlight, system_data_summary}} for all systems.

    Western astrology comes from core.data.astro; the others from here.
    ``natal_cmd_branch``（本命紫微命宮地支）傳入時，流日命宮以本命十二宮
    對照呈現。Entries that fail to compute are simply omitted (caller keeps
    sample).
    """
    out = {}
    if _astro is not None:
        t = _astro.compute_transits(date_str)
        sp = _astro.astrology_spotlight(t) if t else None
        if sp:
            out["SYS_AST"] = {"spotlight": sp[0], "system_data_summary": sp[1]}
    ly = liuyao_transit(date_str)
    if ly:
        out["SYS_LIUYAO"] = ly
    to = tarot_transit(date_str)
    if to:
        out["SYS_TAROT"] = to
    bz = bazi_transit(date_str, day_master)
    if bz:
        out["SYS_BAZI"] = bz
    for sid, fn in [("SYS_HD", human_design_transit),
                    ("SYS_ICHING", iching_transit)]:
        r = fn(date_str)
        if r:
            out[sid] = r
    zw = ziwei_transit(date_str, natal_cmd_branch)
    if zw:
        out["SYS_ZW"] = zw
    return out
