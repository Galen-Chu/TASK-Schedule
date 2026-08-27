"""Portable TrueType font discovery + registration.

Resolution order for each font:
  1. ``SPARK_FONTS_DIR`` / ``FONTS_DIR`` environment variable
  2. ``<repo>/fonts/`` directory
  3. Common Linux system paths (matches ``apt-get install fonts-droid-fallback
     fonts-liberation`` on Debian/Ubuntu — what the GitHub Actions workflow uses)
  4. Common Windows system paths

A CJK font is REQUIRED (Traditional Chinese rendering). The Latin font is
optional: when missing, Latin runs fall back to the CJK font, so reports still
render. Call :func:`ensure_fonts` once before building any PDF (the helpers in
:mod:`core.pdf_engine` do this automatically).
"""
import os
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Logical font names used across all reports
FONT_CJK = "SparkCJK"
FONT_EN = "SparkLatin"
FONT_EN_BOLD = "SparkLatinBold"

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Filename candidates, in priority order, searched inside each font directory.
_CJK_FILES = [
    "NotoSansTC-Regular.ttf",
    "NotoSansTC-Regular.otf",
    "DroidSansFallbackFull.ttf",
    "DroidSansFallback.ttf",
]
_LATIN_FILES = ["LiberationSans-Regular.ttf", "Arial.ttf"]
_LATIN_BOLD_FILES = ["LiberationSans-Bold.ttf", "Arial-Bold.ttf"]

_LINUX_SYS = {
    "cjk": ["/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"],
    "latin": ["/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"],
    "latin_bold": ["/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"],
}
_WIN_SYS = {"cjk": [], "latin": [], "latin_bold": []}

_registered = False


def _resolve(candidates, sys_paths):
    """Return the first existing font path from env/repo/system, else None."""
    env = os.environ.get("SPARK_FONTS_DIR") or os.environ.get("FONTS_DIR")
    dirs = []
    if env:
        dirs.append(env)
    dirs.append(os.path.join(_REPO_ROOT, "fonts"))
    for d in dirs:
        for fname in candidates:
            p = os.path.join(d, fname)
            if os.path.isfile(p):
                return p
    for p in sys_paths:
        if os.path.isfile(p):
            return p
    return None


def ensure_fonts():
    """Register the CJK (+ optional Latin) fonts once. Idempotent."""
    global _registered
    if _registered:
        return

    cjk_path = _resolve(_CJK_FILES, _LINUX_SYS["cjk"] + _WIN_SYS["cjk"])
    if not cjk_path:
        raise RuntimeError(
            "找不到 CJK 字型。\n"
            "  • 在 Linux/CI 執行：sudo apt-get install -y fonts-droid-fallback\n"
            "  • 或下載開源字型到 fonts/：python scripts/fetch_fonts.py\n"
            "  • 或設定環境變數 SPARK_FONTS_DIR 指向字型目錄。"
        )
    pdfmetrics.registerFont(TTFont(FONT_CJK, cjk_path))

    # A real Bold face when available — otherwise <b> silently renders in the
    # same weight. With the variable-font default (Thin) that made small
    # white badge text near-invisible. Statics: scripts/fetch_fonts.py.
    bold_path = _resolve(["NotoSansTC-Bold.ttf"], [])
    if bold_path:
        from reportlab.pdfbase.pdfmetrics import registerFontFamily
        pdfmetrics.registerFont(TTFont(FONT_CJK + "/Bold", bold_path))
        registerFontFamily(FONT_CJK, normal=FONT_CJK, bold=FONT_CJK + "/Bold",
                           italic=FONT_CJK, boldItalic=FONT_CJK + "/Bold")

    latin_path = _resolve(_LATIN_FILES, _LINUX_SYS["latin"] + _WIN_SYS["latin"])
    latin_bold_path = _resolve(_LATIN_BOLD_FILES, _LINUX_SYS["latin_bold"] + _WIN_SYS["latin_bold"])
    # When a Latin font is missing, alias its logical name to the CJK file so
    # the dual-font en() helper degrades gracefully instead of crashing.
    pdfmetrics.registerFont(TTFont(FONT_EN, latin_path or cjk_path))
    pdfmetrics.registerFont(TTFont(FONT_EN_BOLD, latin_bold_path or latin_path or cjk_path))

    _registered = True


def fonts_status():
    """Return a human-readable summary of which fonts resolved (for README/debug)."""
    cjk = _resolve(_CJK_FILES, _LINUX_SYS["cjk"] + _WIN_SYS["cjk"])
    latin = _resolve(_LATIN_FILES, _LINUX_SYS["latin"] + _WIN_SYS["latin"])
    latin_bold = _resolve(_LATIN_BOLD_FILES, _LINUX_SYS["latin_bold"] + _WIN_SYS["latin_bold"])
    return {
        "cjk": cjk or "(missing)",
        "latin": latin or "(will fall back to CJK)",
        "latin_bold": latin_bold or "(will fall back to CJK)",
    }
