#!/usr/bin/env python3
"""Real astrology transit calculations via Swiss Ephemeris (``pyswisseph``).

Keyless and offline once the package is installed (uses bundled ephemeris
data for the modern range). Used by the Spiritual report to compute the
*current* ecliptic longitudes of the Sun, Moon and Mercury, derive their
zodiac signs, and detect a Sun-Mercury conjunction (orb < 3°).

If ``pyswisseph`` is not installed, every function degrades gracefully to
``None`` so the caller can fall back to the static ``systems_data`` sample.
"""
import datetime
import logging

log = logging.getLogger("astro")

_SIGNS_EN = ["ARI", "TAU", "GEM", "CAN", "LEO", "VIR", "LIB", "SCO", "SAG", "CAP", "AQU", "PIS"]
_SIGNS_ZH = ["白羊", "金牛", "双子", "巨蟹", "狮子", "处女", "天秤", "天蝎", "射手", "摩羯", "水瓶", "双鱼"]

_HAS_SWISSEPH = True
try:
    import swisseph as swe
    swe.set_ephe_path()  # bundled ephemeris
except ImportError:
    _HAS_SWISSEPH = False
    log.info("pyswisseph 未安裝，astro 計算將退回 sample。")


def _jd(date_str, hour_utc=4.0):
    # noon Asia/Taipei (UTC+8) = 04:00 UTC on the same calendar day as the
    # Taipei date_str. A fixed noon instant keeps the chart reproducible
    # regardless of exactly when the daily schedule fires.
    try:
        y, m, d = (int(x) for x in str(date_str).split("-"))
        return swe.julday(y, m, d, hour_utc)
    except Exception:  # noqa: BLE001
        return None


def _planet_lon(jd, planet):
    try:
        return swe.calc_ut(jd, planet)[0][0]
    except Exception:  # noqa: BLE001
        return None


def compute_transits(date_str):
    """Return a transit snapshot dict, or ``None`` if swisseph is unavailable.

    Fields: sun_sign_zh, moon_sign_zh, sun_lon, moon_lon, mercury_lon,
    sun_mercury_orb (None when Mercury longitude missing).
    """
    if not _HAS_SWISSEPH:
        return None
    jd = _jd(date_str)
    if jd is None:
        return None
    sun = _planet_lon(jd, swe.SUN)
    moon = _planet_lon(jd, swe.MOON)
    mercury = _planet_lon(jd, swe.MERCURY)
    if sun is None or moon is None:
        return None

    def sign_zh(lon):
        return _SIGNS_ZH[int(lon // 30) % 12]

    orb = None
    if mercury is not None:
        orb = abs(((sun - mercury + 180) % 360) - 180)

    return {
        "sun_sign_zh": sign_zh(sun),
        "moon_sign_zh": sign_zh(moon),
        "sun_lon": round(sun, 2),
        "moon_lon": round(moon, 2),
        "mercury_lon": None if mercury is None else round(mercury, 2),
        "sun_mercury_orb": None if orb is None else round(orb, 2),
    }


def astrology_spotlight(transits):
    """Build the SYS_AST spotlight + summary strings from a transit snapshot.

    Returns ``(spotlight, system_data_summary)`` or ``None`` if transits is None.
    """
    if not transits:
        return None
    sun = transits["sun_sign_zh"]
    moon = transits["moon_sign_zh"]
    orb = transits["sun_mercury_orb"]
    conj = ""
    if orb is not None and orb < 3.0:
        conj = f" / 太陽合相水星 (Orb {orb:.1f}°)"
    spotlight = f"📍 當日天象：太陽在{sun} / 月亮在{moon}{conj}"
    summary = f"太陽：{sun} | 月亮：{moon} | 上升：獅子座(預設) | 日水相位 Orb: {orb if orb is not None else 'N/A'}°"
    return spotlight, summary
