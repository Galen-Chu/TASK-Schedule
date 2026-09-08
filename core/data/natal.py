# -*- coding: utf-8 -*-
"""示範本命（Galen）——各術數系統的出生參數轉換與流日對照。

出生資料：西元 1995-04-15 12:52（午時）・臺灣澎湖（馬公 23.57N 119.59E）。
此為刻意內建於報告的「示範本命」（用戶指定），非機密個資；個人化資料
未來仍走 config/birth-profile.yaml（gitignored）。

轉換鏈（各系統自取所需）：
  * 八字/紫微/梅花/六爻 —— lunar_python：農曆生日、四柱、時辰、起卦
  * 西洋占星/人類圖    —— pyswisseph：本命行星黃經、上升、設計太陽
      （人類圖 Design = 個性太陽黃經 −88°，即受孕期太陽；人生角色 =
        個性太陽線/設計太陽線——真實曼陀羅下 Galen 回推得 5/1，與
        自述一致，作為映射正確性的交叉驗證）
  * 塔羅 —— 原型系統無本命盤，以出生日期 hash 得「出生牌陣」供參考

每個函式都 None/部分安全：任何引擎失敗只少該系統的對照，不影響報告。
"""
import logging

log = logging.getLogger("natal")

# ---- 出生資料（示範本命） ----------------------------------------------------
BIRTH_DATE = (1995, 4, 15)          # 西元生日（Asia/Taipei 日曆日）
BIRTH_HOUR_UTC = 4 + 52 / 60        # 12:52 台北 = 04:52 UT
BIRTH_PLACE = "臺灣澎湖"
BIRTH_LAT, BIRTH_LON = 23.5654, 119.5863   # 馬公

_ZHIS = "子丑寅卯辰巳午未申酉戌亥"
_TRI_ELEMENT = {"乾": "金", "兌": "金", "離": "火", "震": "木",
                "巽": "木", "坎": "水", "艮": "土", "坤": "土"}
_ELE_GEN = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
_ELE_CTRL = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
_TRI_ELEMENT = {"乾": "金", "兌": "金", "離": "火", "震": "木",
                "巽": "木", "坎": "水", "艮": "土", "坤": "土"}


def _lunar():
    from lunar_python import Solar
    # 必須帶時辰：fromYmd 預設 0 時會把時柱算成子時（12:52 應為午時）
    return Solar.fromYmdHms(BIRTH_DATE[0], BIRTH_DATE[1], BIRTH_DATE[2],
                            int(BIRTH_HOUR_UTC + 8), 52, 0).getLunar()


def _jd():
    import swisseph as swe
    y, m, d = BIRTH_DATE
    return swe.julday(y, m, d, BIRTH_HOUR_UTC)


def _lon_at(jd, planet):
    import swisseph as swe
    return swe.calc_ut(jd, planet)[0][0]


# ---- 十神（八字）——實作移至 divination（流日層亦需使用） -------------
from core.data.divination import ten_god  # noqa: F401  (re-export)


# ---- 各系統本命參數 -----------------------------------------------------------
def natal_bazi():
    try:
        l = _lunar()
        return {
            "pillars": (f"{l.getYearInGanZhi()} {l.getMonthInGanZhi()} "
                        f"{l.getDayInGanZhi()} {l.getTimeInGanZhi()}"),
            "lunar": (f"{l.getYearInGanZhi()}年{l.getMonthInChinese()}月"
                      f"{l.getDayInChinese()}日{l.getTimeZhi()}時"),
            "day_master": l.getDayGan(),
        }
    except Exception as exc:  # noqa: BLE001
        log.info("natal bazi failed: %s", exc)
        return None


# ---- 紫微安星（iztro 安星訣；規則互相交叉驗證過，見測試） -------------------
_WU_HU = {"甲": "丙", "己": "丙", "乙": "戊", "庚": "戊", "丙": "庚",
          "辛": "庚", "丁": "壬", "壬": "壬", "戊": "甲", "癸": "甲"}  # 五虎遁（年起寅干）
_JV_STEM_NUM = {"甲": 1, "乙": 1, "丙": 2, "丁": 2, "戊": 3, "己": 3,
                "庚": 4, "辛": 4, "壬": 5, "癸": 5}
_JV_BRANCH_NUM = {"子": 1, "午": 1, "丑": 1, "未": 1,
                  "寅": 2, "申": 2, "卯": 2, "酉": 2,
                  "辰": 3, "戌": 3, "巳": 3, "亥": 3}
_JU_ELEM = {1: ("木", 3), 2: ("金", 4), 3: ("水", 2), 4: ("火", 6), 5: ("土", 5)}
_ZIWEI_PALACES = ["命宮", "兄弟", "夫妻", "子女", "財帛", "疾厄",
                  "遷移", "交友", "官祿", "田宅", "福德", "父母"]   # 命宮起逆行


def wu_xing_jv(gan, zhi):
    """五行局（算術法：干數+支數，>5 減 5；1木3 2金4 3水2 4火6 5土5）。
    與六十甲子納音法等價（甲子→金四局等已交叉驗證）。"""
    n = _JV_STEM_NUM[gan] + _JV_BRANCH_NUM[zhi]
    if n > 5:
        n -= 5
    elem, jv = _JU_ELEM[n]
    return f"{elem}{jv}局", jv


def an_zi_wei(day, jv):
    """安紫微星（iztro 訣）：日÷局得商餘；整除→寅起順數商宮；不整除→借數
    （局-餘）後商+1 為基準宮，借數奇退偶進。回傳地支 index（子0..亥11）。"""
    q, r = divmod(day, jv)
    if r == 0:
        return (2 + (q - 1)) % 12
    borrow = jv - r
    base = (2 + q) % 12            # 商+1 宮（寅起數，寅=2）
    return (base - borrow) % 12 if borrow % 2 == 1 else (base + borrow) % 12


def ziwei_chart(gan_zhi_day=None):
    """十四主星全盤。回傳 {"palaces": {宮名: {"branch", "stars"}},
    "ziwei_branch", "tianfu_branch", "cmd_stars", ...}。閏月依 lunar_python
    月序直接入式（閏月視同該月，學派簡化，已註明）。"""
    try:
        l = _lunar()
        month, hour_idx = l.getMonth(), _ZHIS.find(l.getTimeZhi())
        cmd_idx = (2 + (month - 1) - hour_idx) % 12
        body_idx = (2 + (month - 1) + hour_idx) % 12
        # 命宮干（五虎遁：年干定寅干，順數至命宮支）
        yin_gan_idx = "甲乙丙丁戊己庚辛壬癸".index(_WU_HU[l.getYearGan()])
        cmd_gan = "甲乙丙丁戊己庚辛壬癸"[(yin_gan_idx + (cmd_idx - 2)) % 10]
        ju_name, jv = wu_xing_jv(cmd_gan, _ZHIS[cmd_idx])
        zw_idx = an_zi_wei(l.getDay(), jv)
        tf_idx = (4 - zw_idx) % 12                        # 天府＝寅申軸鏡像
        stars = {}
        for name, off in (("紫微", 0), ("天機", -1), ("太陽", -3),
                          ("武曲", -4), ("天同", -5), ("廉貞", -8)):
            stars.setdefault((zw_idx + off) % 12, []).append(name)
        for name, off in (("天府", 0), ("太陰", 1), ("貪狼", 2), ("巨門", 3),
                          ("天相", 4), ("天梁", 5), ("七殺", 6), ("破軍", 10)):
            stars.setdefault((tf_idx + off) % 12, []).append(name)
        palaces = {}
        for i, pname in enumerate(_ZIWEI_PALACES):
            br = (cmd_idx - i) % 12
            palaces[pname] = {"branch": _ZHIS[br],
                              "stars": stars.get(br, []),
                              "is_body": br == body_idx}
        return {"ju": ju_name, "cmd_branch": _ZHIS[cmd_idx],
                "cmd_gan_zhi": f"{cmd_gan}{_ZHIS[cmd_idx]}",
                "body_branch": _ZHIS[body_idx],
                "ziwei_branch": _ZHIS[zw_idx], "tianfu_branch": _ZHIS[tf_idx],
                "cmd_stars": palaces["命宮"]["stars"], "palaces": palaces}
    except Exception as exc:  # noqa: BLE001
        log.info("ziwei chart failed: %s", exc)
        return None


def natal_ziwei():
    """本命紫微：命宮/身宮、五行局、十四主星全盤、年干四化。"""
    try:
        l = _lunar()
        chart = ziwei_chart()
        if chart is None:
            return None
        from core.data.divination import _ZW_SI_HUA
        luck, power, sci, taboo = _ZW_SI_HUA.get(l.getYearGan(), ("",) * 4)
        out = dict(chart)
        out["year_gan"] = l.getYearGan()
        out["si_hua"] = f"{luck}、{power}、{sci}、{taboo}"
        return out
    except Exception as exc:  # noqa: BLE001
        log.info("natal ziwei failed: %s", exc)
        return None


def natal_astro():
    try:
        import swisseph as swe
        jd = _jd()
        out = {}
        for key, planet, zh in (("sun", swe.SUN, "太陽"), ("moon", swe.MOON, "月亮"),
                                ("mercury", swe.MERCURY, "水星"), ("venus", swe.VENUS, "金星"),
                                ("mars", swe.MARS, "火星"), ("jupiter", swe.JUPITER, "木星"),
                                ("saturn", swe.SATURN, "土星")):
            lon = _lon_at(jd, planet)
            out[key] = round(lon, 2)
        cusps, ascmc = swe.houses(jd, BIRTH_LAT, BIRTH_LON, b"P")
        out["asc"] = round(ascmc[0], 2)
        return out
    except Exception as exc:  # noqa: BLE001
        log.info("natal astro failed: %s", exc)
        return None


def _sign_zh(lon):
    signs = ["白羊", "金牛", "雙子", "巨蟹", "獅子", "處女",
             "天秤", "天蠍", "射手", "摩羯", "水瓶", "雙魚"]
    return signs[int(lon // 30) % 12]


def natal_hd():
    """個性/設計太陽閘門與線 → 人生角色（真實曼陀羅）。"""
    try:
        import swisseph as swe
        from core.data.divination import hd_gate_line, _GATE_INFO
        jd = _jd()
        pers_lon = _lon_at(jd, swe.SUN)
        target = (pers_lon - 88.0) % 360          # Design 太陽 = 個性太陽 −88°
        # 從 jd-95 起逐日找穿越 target 的位置，再二分求精（誤差 << 一線 0.94°）
        lo, hi = jd - 95, jd - 80
        def _diff(j):
            return ((_lon_at(j, swe.SUN) - target + 180) % 360) - 180
        d_lo = _diff(lo)
        j = lo
        while j < hi:
            k = j + 0.5
            if _diff(k) * d_lo <= 0 or abs(_diff(k)) < 0.2:
                lo, hi = j, k
                break
            j, d_lo = k, _diff(k)
        for _ in range(18):
            mid = (lo + hi) / 2
            if _diff(lo) * _diff(mid) <= 0:
                hi = mid
            else:
                lo = mid
        design_lon = _lon_at((lo + hi) / 2, swe.SUN)
        p_gate, p_line = hd_gate_line(pers_lon)
        d_gate, d_line = hd_gate_line(design_lon)
        p_hex = _GATE_INFO.get(p_gate, ("",))[0]
        d_hex = _GATE_INFO.get(d_gate, ("",))[0]
        return {"pers_gate": p_gate, "pers_line": p_line, "pers_hex": p_hex,
                "design_gate": d_gate, "design_line": d_line, "design_hex": d_hex,
                "profile": f"{p_line}/{d_line}"}
    except Exception as exc:  # noqa: BLE001
        log.info("natal hd failed: %s", exc)
        return None


def natal_tarot():
    try:
        from core.data.divination import tarot_transit
        return tarot_transit(f"{BIRTH_DATE[0]}-{BIRTH_DATE[1]:02d}-{BIRTH_DATE[2]:02d}")
    except Exception as exc:  # noqa: BLE001
        log.info("natal tarot failed: %s", exc)
        return None


# ---- 流日 × 本命對照（每系統 1–3 行，供 PDF 個人本命對照卡） -------------------
_ASPECTS = ((0, "合相"), (60, "六合"), (90, "四分"), (120, "三分"), (180, "對沖"))


def build_natal_section(date_str):
    """{system_id: {"params": str, "compare": str}}——全部 None-safe。"""
    out = {}

    b = natal_bazi()
    if b:
        out["SYS_BAZI"] = {
            "params": f"本命四柱 {b['pillars']}・{b['lunar']}・日主{b['day_master']}",
            "compare": "",
        }


    z = natal_ziwei()
    if z:
        cmd_stars = "+".join(z["cmd_stars"]) if z["cmd_stars"] else "無主星・借對宮"
        # 全盤一行摘要：宮 支 主星，只列有星的宮（不用括號）
        full = "・".join(
            f"{pn}{pv['branch']} {'+'.join(pv['stars'])}"
            for pn, pv in z["palaces"].items() if pv["stars"])
        body_note = "・身宮同命宮" if z["body_branch"] == z["cmd_branch"] else ""
        out["SYS_ZW"] = {
            "params": (f"本命 {z['ju']}・命宮{z['cmd_gan_zhi']}〔{cmd_stars}〕"
                       f"・身宮{z['body_branch']}・{z['year_gan']}干四化 {z['si_hua']}"),
            "compare": f"全盤 {full}{body_note}",
        }

    a = natal_astro()
    if a:
        out["SYS_AST"] = {
            "params": (f"本命 太陽{_sign_zh(a['sun'])}{a['sun'] % 30:.1f}°"
                       f"・月亮{_sign_zh(a['moon'])}・上升{_sign_zh(a['asc'])}"),
            "compare": "",
        }

    h = natal_hd()
    if h:
        out["SYS_HD"] = {
            "params": (f"本命 個性太陽閘{h['pers_gate']}.{h['pers_line']}《{h['pers_hex']}》"
                       f"／設計太陽閘{h['design_gate']}.{h['design_line']}《{h['design_hex']}》"
                       f"→ 人生角色 {h['profile']}"),
            "compare": "",
        }

    # —— 需要當日流日的對照 ——
    try:
        from core.data import astro as _astro
        from core.data import divination as _div
        today = _astro.compute_transits(date_str) if _astro else None

        if today and a:
            hits = []
            natal_pts = [("本命太陽", a["sun"]), ("本命月亮", a["moon"]),
                         ("本命水星", a["mercury"]), ("本命金星", a["venus"]),
                         ("本命火星", a["mars"]), ("本命木星", a["jupiter"]),
                         ("本命土星", a["saturn"]), ("本命上升", a["asc"])]
            for t_key, t_zh in (("sun_lon", "流日太陽"), ("moon_lon", "流日月亮"),
                                ("mercury_lon", "流日水星")):
                t_lon = today.get(t_key)
                if t_lon is None:
                    continue
                for n_name, n_lon in natal_pts:
                    sep = abs(((t_lon - n_lon + 180) % 360) - 180)
                    for angle, name in _ASPECTS:
                        orb = abs(sep - angle)
                        if orb <= 2.5:
                            hits.append((orb, f"{t_zh}{name}{n_name}（orb {orb:.1f}°）"))
            hits.sort()
            if hits:
                out["SYS_AST"]["compare"] = "今日相位 " + "、".join(h[1] for h in hits[:2])

        if h and today:
            t_gate, _ = _div.hd_gate_line(today.get("sun_lon"))
            if t_gate:
                natal_gates = {h["pers_gate"], h["design_gate"]}
                if t_gate in natal_gates:
                    out["SYS_HD"]["compare"] = f"今日流日閘 {t_gate} 直接引動本命太陽閘・共鳴日"
                else:
                    out["SYS_HD"]["compare"] = (f"今日流日閘 {t_gate}"
                                            f"・未直觸本命太陽閘 {h['pers_gate']}/{h['design_gate']}")

        if z:
            try:
                from core.data.divination import ziwei_transit
                zw_today = ziwei_transit(date_str, natal_cmd_branch=z["cmd_branch"])
                if zw_today:
                    spot = zw_today["spotlight"].replace("📍 ", "")
                    # 流日命宮落宮提示 + 落宮的本命主星
                    palace_stars = ""
                    for pn, pv in z["palaces"].items():
                        if pv["branch"] == zw_today.get("day_branch", "") and pv["stars"]:
                            palace_stars = f"・宮主星 {'+'.join(pv['stars'])}"
                            break
                    out["SYS_ZW"]["compare"] += f"｜流日對照 {spot}{palace_stars}"
            except Exception as exc:  # noqa: BLE001
                log.info("zw natal compare failed: %s", exc)

        if b:
            try:
                from lunar_python import Solar as _S
                y, m, d = (int(x) for x in str(date_str).split("-"))
                l2 = _S.fromYmd(y, m, d).getLunar()
                tg = ten_god(b["day_master"], l2.getDayGan())
                out["SYS_BAZI"]["compare"] = f"流日對照 今日{l2.getDayInGanZhi()}・日主見{tg}"
            except Exception as exc:  # noqa: BLE001
                log.info("bazi natal compare failed: %s", exc)

        # 時間卦系統：出生日卦作為「本命卦」參考
        birth_iso = f"{BIRTH_DATE[0]}-{BIRTH_DATE[1]:02d}-{BIRTH_DATE[2]:02d}"
        # 出生卦需帶出生時辰（iching_transit 只收日期、時辰會退回子時）
        try:
            lb = _lunar()
            u_b, low_b, mv_b = _div.mei_hua_cast(
                _ZHIS.find(lb.getYearZhi()) + 1, lb.getMonth(), lb.getDay(),
                _ZHIS.find(lb.getTimeZhi()) + 1)
            ich = {"system_data_summary": (
                f"主卦：{_div._hex_name_from_trigrams(u_b, low_b)}"
                f"（上{_div._TRIGRAMS[u_b-1]}下{_div._TRIGRAMS[low_b-1]}）| 動爻：{mv_b}")}
        except Exception:  # noqa: BLE001
            ich = _div.iching_transit(birth_iso)
        if ich:
            today_ich = _div.iching_transit(date_str)
            t_up = today_ich["system_data_summary"].split("上")[1][0] if today_ich else ""
            n_up = ich["system_data_summary"].split("上")[1][0]
            rel = ("相生" if (_ELE_GEN.get(_TRI_ELEMENT.get(n_up, "")) == _TRI_ELEMENT.get(t_up, "")
                              or _ELE_GEN.get(_TRI_ELEMENT.get(t_up, "")) == _TRI_ELEMENT.get(n_up, ""))
                   else "相剋" if (_ELE_CTRL.get(_TRI_ELEMENT.get(n_up, "")) == _TRI_ELEMENT.get(t_up, "")
                                   or _ELE_CTRL.get(_TRI_ELEMENT.get(t_up, "")) == _TRI_ELEMENT.get(n_up, ""))
                   else "比和")
            out["SYS_ICHING"] = {
                "params": f"出生日起卦・本命卦參考｜{ich['system_data_summary']}",
                "compare": (f"今日卦與本命卦體用{rel}" if today_ich else ""),
            }
        ly = _div.liuyao_transit(birth_iso)
        if ly:
            out["SYS_LIUYAO"] = {
                "params": f"出生日干支起卦｜{ly['system_data_summary']}",
                "compare": "六爻為時卦系統，出生卦僅作背景參考",
            }
        tt = natal_tarot()
        if tt:
            names = []
            for c in tt.get("cards", [])[:3]:
                head = c.split("—")[0]                     # 「位置 牌名・方位」
                name = head.split("・")[0].split("／", 1)[-1].strip()
                names.append(name + ("・逆" if "逆位" in c else "・正"))
            out["SYS_TAROT"] = {
                "params": "出生日牌陣・參考 " + "／".join(names),
                "compare": "塔羅為原型占卜系統，無本命盤；以當日牌陣為主",
            }
    except Exception as exc:  # noqa: BLE001
        log.warning("natal compare failed: %s", exc)

    return out


if __name__ == "__main__":
    import os
    import sys
    import json
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    print(json.dumps(build_natal_section("2026-09-08"), ensure_ascii=False, indent=1))
