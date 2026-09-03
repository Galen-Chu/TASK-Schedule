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
    "111110": "天風姤", "011110": "澤風大過", "101110": "火風鼎", "001110": "雷風恆",
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


# ---- 易經六爻 (Liu Yao / Six Lines divination) ------------------------------
_LIUYAO_LINES = {
    "初九": ("陽", "潛龍勿用，蓄勢待發"), "初六": ("陰", "陰凝於下，慎始為宜"),
    "九二": ("陽", "見龍在田，利見大人"), "六二": ("陰", "直方大，不習無不利"),
    "九三": ("陽", "君子終日乾乾，夕惕若厲"), "六三": ("陰", "含章可貞，或從王事"),
    "九四": ("陽", "或躍在淵，進無咎也"), "六四": ("陰", "括囊，無咎無譽"),
    "九五": ("陽", "飛龍在天，利見大人"), "六五": ("陰", "黃裳元吉，居中得正"),
    "上九": ("陽", "亢龍有悔，盈不可久"), "上六": ("陰", "龍戰於野，其道窮也"),
}

def liuyao_transit(date_str):
    """易經六爻：以日干支起卦，得六爻卦象。Returns dict or None."""
    if not _HAS_LUNAR:
        return None
    try:
        solar = _solar_from(date_str)
        lunar = solar.getLunar()
        day_gan = lunar.getDayGan()   # 日干
        day_zhi = lunar.getDayZhi()   # 日支
        gan_num = "甲乙丙丁戊己庚辛壬癸".index(day_gan) + 1  # 1-10
        zhi_num = "子丑寅卯辰巳午未申酉戌亥".index(day_zhi) + 1  # 1-12
        # 六爻由日干支數值決定：干定上卦、支定下卦、干支和定動爻
        upper_num = (gan_num % 8) or 8  # 1-8 對應八卦
        lower_num = (zhi_num % 8) or 8
        moving_num = ((gan_num + zhi_num) % 6) or 6  # 1-6 動爻
        # 八卦編號：1乾2兌3離4震5巽6坎7艮8坤
        bagua = {1:"乾",2:"兌",3:"離",4:"震",5:"巽",6:"坎",7:"艮",8:"坤"}
        upper = bagua[upper_num]
        lower = bagua[lower_num]
        hex_name = f"{upper}上{lower}下"
        yao_names = ["初", "二", "三", "四", "五", "上"]
        lines = []
        for i in range(6):
            yin_yang = "六" if (lower_num + i) % 2 == 0 else "九"
            if i < 3:  # 下卦
                trigram = lower
            else:      # 上卦
                trigram = upper
            yao_label = f"{yao_names[i]}{yin_yang}"
            meaning = _LIUYAO_LINES.get(yao_label, ("—", "—"))[1]
            is_moving = (i + 1) == moving_num
            lines.append(f"{yao_label}（{trigram}卦{'·動爻' if is_moving else ''}）：{meaning}")
        spotlight = f"📍 日干支 {day_gan}{day_zhi} 起卦，得「{hex_name}」，動爻在第 {moving_num} 爻"
        summary = f"主卦：{hex_name}（上{upper}下{lower}）| 動爻：第{moving_num}爻 | 日干支：{day_gan}{day_zhi}"
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
    ly = liuyao_transit(date_str)
    if ly:
        out["SYS_LIUYAO"] = ly
    to = tarot_transit(date_str)
    if to:
        out["SYS_TAROT"] = to
    for sid, fn in [("SYS_HD", human_design_transit),
                    ("SYS_ZW", ziwei_transit),
                    ("SYS_BAZI", bazi_transit),
                    ("SYS_ICHING", iching_transit)]:
        r = fn(date_str)
        if r:
            out[sid] = r
    return out
