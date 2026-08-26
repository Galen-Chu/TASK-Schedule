"""Central design tokens — single source of truth for the master palette,
typography scale and the A4 grid shared by every report.

The palette follows the **Daily Report Typography Guide Spec**: a warm,
editorial five-colour brand system (Ink / Teal / Amber / Coral / Sage) on warm
paper, with tint→shade ramps and dedicated status colours. Every report draws
its shared chrome (titles, rules, footers, card fills, borders, signals) from
the MASTER tokens here; report-specific section colours are defined locally
but are derived from the brand ramps (see ``RAMP_*`` / ``ACCENT``) so the
family stays consistent when switching between reports.

The stable aliases (NAVY / GOLD / BG_CARD / …) keep their names so existing
``T.*`` references across generators auto-pick up the new system; only their
values change.
"""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4

# ---- A4 grid ---------------------------------------------------------------
PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 24                                  # left/right margin (pt)
PRINTABLE_WIDTH = PAGE_WIDTH - 2 * MARGIN    # 547.27 pt
MARGIN_TOP = 28
MARGIN_BOTTOM = 42

# Standard 4-column detail-table grids. Both sum to PRINTABLE_WIDTH (547).
COLS_DETAIL = [65, 125, 100, 257]            # label / value / threshold / analysis
COLS_THINKTANK = [80, 110, 100, 257]         # org / focus / time / analysis

# ---- Brand colours (Typography Guide Spec) ---------------------------------
INK   = colors.HexColor("#1C2333")   # 墨藍黑 — primary text / headings
TEAL  = colors.HexColor("#0E7C86")   # 科技青 — primary accent
AMBER = colors.HexColor("#E8A33D")   # 暖琥珀
CORAL = colors.HexColor("#EF6F53")   # 活力橘紅
SAGE  = colors.HexColor("#6B8F71")   # 抹茶綠
PLUM  = colors.HexColor("#7A4B6B")   # 紫 (Guide pairing, for Spiritual 紫微)
PAPER = colors.HexColor("#FAF9F6")   # warm off-white background

# ---- Stable master aliases (names kept; values from the Guide) --------------
NAVY       = INK                            # primary heading / header chrome
GOLD       = TEAL                           # accent rule / divider emphasis
BG_CARD    = PAPER                          # card background (warm paper)
BORDER     = colors.HexColor("#E5E1D8")     # warm card border
RULE       = colors.HexColor("#D8D3C7")     # warm footer / divider rule
TEXT_BODY  = INK                            # primary body text
TEXT_SUB   = colors.HexColor("#4B5566")     # subtitle text
TEXT_MUTED = colors.HexColor("#9CA3AF")     # date / footer / metadata text
WHITE      = colors.white

# ---- Brand ramps (tint → shade) for section palettes -----------------------
# Index 0 = lightest bg tint, 2 = base, 4 = darkest (text).
RAMP_TEAL  = ["#E3F3F4", "#8FCAD0", "#0E7C86", "#0A5A62", "#063B40"]
RAMP_AMBER = ["#FCF0DC", "#F3CC8B", "#E8A33D", "#B97A22", "#5C4A22"]
RAMP_CORAL = ["#FDE7E1", "#F6AD9B", "#EF6F53", "#C24B32", "#832F1E"]
RAMP_SAGE  = ["#E8F0E9", "#B7CCB9", "#6B8F71", "#47654B", "#2C3F2E"]
RAMP_INK   = ["#EEF0F4", "#C7CDD9", "#1C2333", "#4B5566", "#1C2333"]
RAMP_PLUM  = ["#F1E9EE", "#A07A92", "#7A4B6B", "#5C3850", "#321F2C"]
RAMP_INDIGO = ["#E8EAF6", "#9FA8DA", "#3F51B5", "#303F9F", "#1A237E"]  # aerospace
RAMP_BRONZE = ["#F5EDE3", "#D4B896", "#A0845C", "#7A6344", "#554230"]  # I Ching — grounding earth
RAMP_WINE   = ["#F5E6E8", "#C4909E", "#8B4049", "#6B2D35", "#4A1E24"]  # Tarot — mystical wine

# Shared accent rotation — the five brand hues at the same lightness. Reports
# draw section colours from here so category colours read as siblings, not strangers.
ACCENT = [TEAL, AMBER, CORAL, SAGE, INK]

# ---- Signal / decision lights (Guide status colours) -----------------------
SIGNAL_BUY  = colors.HexColor("#2E8B4F")    # 達標 / 進場
SIGNAL_HOLD = colors.HexColor("#B9791C")    # 留意 / 觀望
SIGNAL_SELL = colors.HexColor("#D64545")    # 落後 / 減碼
# Status background tints
SIGNAL_BUY_TINT  = colors.HexColor("#EAF5EE")
SIGNAL_HOLD_TINT = colors.HexColor("#FBF3E4")
SIGNAL_SELL_TINT = colors.HexColor("#FBEAEA")
