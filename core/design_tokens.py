"""Central design tokens — single source of truth for the master palette,
typography scale and the A4 grid shared by every report.

Each report imports the MASTER tokens (NAVY / GOLD / slate grays) and the
SIGNAL lights from here, then defines its own *section* palette
(per-market / per-domain / per-system colours) locally. Section colours are
intentionally report-specific; the master identity is what stays consistent.
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

# ---- Master brand palette (shared) -----------------------------------------
NAVY = colors.HexColor("#0F172A")            # Master Header Navy
GOLD = colors.HexColor("#C5A059")            # Master Accent Gold
BG_CARD = colors.HexColor("#F8FAFC")         # card background (slate light)
BORDER = colors.HexColor("#E2E8F0")          # card border
RULE = colors.HexColor("#CBD5E1")            # footer / divider rule
TEXT_BODY = colors.HexColor("#1E293B")       # primary body text
TEXT_SUB = colors.HexColor("#475569")        # subtitle text
TEXT_MUTED = colors.HexColor("#64748B")      # date / footer text
WHITE = colors.white

# ---- Signal / decision lights (shared) -------------------------------------
SIGNAL_BUY = colors.HexColor("#16A34A")      # 進場 / 加碼
SIGNAL_HOLD = colors.HexColor("#CA8A04")     # 觀望 / 持股
SIGNAL_SELL = colors.HexColor("#DC2626")     # 減碼 / 避險
