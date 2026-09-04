#!/usr/bin/env python3
"""Financial Intelligence — Obsidian markdown writer.

Builds the daily Markdown note (frontmatter + body) from the market ``data``
dict and delegates file I/O to :mod:`core.obsidian_writer` so path handling is
shared with the other reports.
"""
import os
import sys
import datetime

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from core.obsidian_writer import write_note


def _g(data, key, default):
    return (data or {}).get(key, default)


def _briefing_md(data):
    """(G) Cross-domain briefing callout; empty string when unavailable."""
    b = (data or {}).get("cross_domain_briefing")
    if not b:
        return ""
    rows = [("WHAT 市場全貌", b.get("what", "")),
            ("WHY 訊號×趨勢", b.get("why", "")),
            ("SO WHAT 投資啟示", b.get("so_what", ""))]
    body = "\n".join(f"> **{lab}**：{txt}" for lab, txt in rows if txt)
    return f"\n> [!tip] 🧭 今日情報摘要（跨域關聯）\n{body}\n\n"


def build_note_content(data, date_str):
    twm = _g(data, "tw_margin_balance", None)
    vix = _g(data, "vix", None)
    spread = _g(data, "spread_10y2y", None)
    dxy = _g(data, "dxy", None)
    score = _g(data, "signal_score", 72)
    rating = _g(data, "signal_rating", "🟢 偏多進場 / 尋找超跌加碼點")
    # Verdict inputs arrive as None when their live fetch failed — frontmatter
    # keeps a YAML null and the body shows 待補 instead of the stale sample.
    twm_d = f"{twm/10000:.1f} 萬張" if twm is not None else "待補"
    vix_d = f"{vix}" if vix is not None else "待補"
    spread_d = (f"{'+' if spread >= 0 else ''}{spread}%" if spread is not None else "待補")
    dxy_d = f"{dxy}" if dxy is not None else "待補"
    us_note = ("恐慌指數攀升至買點，科技巨頭區間築底" if vix is not None
               else "VIX 未取得，情緒訊號待補")
    return f"""---
title: "Financial Intelligence 每日投資趨勢 ({date_str})"
date: {date_str}
type: daily-report
tags:
  - finance
  - market-trends
  - quant-indicators
  - asset-allocation
tw_margin_balance_lots: {twm if twm is not None else 'null'}
vix: {vix if vix is not None else 'null'}
signal_rating: "{rating}"
---

# Financial Intelligence 每日投資趨勢與市場指標 ({date_str})

> [!abstract] 核心決策與資產評級
> **本日綜合評級**：`{rating}` (Signal Score: {score}/100)
>
> 台股全市場融資餘額 **{twm_d}**（TWSE MI_MARGN 即時加總），美股 VIX **{vix_d}**。量化模型綜合評估多數市場進入中長線高勝率分批佈局點。
{_briefing_md(data)}
---

---

## 📊 五大市場核心數據監控

| 市場類別 | 當前關鍵指標 | 風險評級 | 進出場訊號 | 短線趨勢與籌碼觀察 |
| :--- | :--- | :--- | :--- | :--- |
| **1. 台股市場** | 融資餘額 {twm_d} | 中等偏低 | 🟢 分批進場 | 融資洗盤完畢，台積電先進封裝支撐強 |
| **2. 美股市場** | VIX {vix_d} | 中等 | 🟢 分批進場 | {us_note} |
| **3. 全球債券** | 10Y {_g(data, "treasury_10y", 3.85)}% (利差 {spread_d}) | 低 | 🟢 鎖利加碼 | 倒掛結束，鎖定降息前高殖利率票息 |
| **4. 外匯與美元** | DXY {dxy_d} / TWD {_g(data, "usdtwd", 32.15)} | 中等 | 🟡 觀望升值 | 美元高位震盪，亞幣匯率止跌回升 |
| **5. 商品與加密** | 黃金 ${_g(data, "gold", 2450):,} / BTC ${_g(data, "btc", 58500):,} | 偏高 | 🟡 觀望布局 | 黃金避險高位震盪，BTC 槓桿清理完畢 |

---

## 🟢 適合進場 / 分批加碼標的清單

1. **台股市場**：市值型 / 半導體 ETF (如 `0050`, `0052`)
2. **美股市場**：標普 500 / 納指 ETF (如 `VOO`, `QQQ`)
3. **全球債券**：20 年期以上美國公債 ETF (如 `TLT`, `00679B`)

## 🔴 需要注意退場 / 減碼避險標的清單

1. **台股市場**：高融資比率之純題材中小型股
2. **美股市場**：高債務與零獲利高估值科技股

---

*Generated automatically by Financial Intelligence System on {date_str}*
"""


def write_obsidian_note(data, output_dir=None):
    """Write the daily Financial markdown note. Returns the file path."""
    data = data or {}
    date_str = data.get("date") or datetime.date.today().strftime("%Y-%m-%d")
    output_dir = output_dir or os.path.join(_REPO_ROOT, "output", "obsidian_vault")
    filename = f"{date_str}_Financial_Intelligence_每日投資趨勢.md"
    content = build_note_content(data, date_str)
    return write_note(output_dir, filename, content)


if __name__ == "__main__":
    path = write_obsidian_note({"date": "2026-08-11", "vix": 28.4, "tw_margin_balance": 8969841})
    print("Obsidian note created:", path)
