#!/usr/bin/env python3
"""Global Intelligence — Obsidian markdown writer.

Delegates file I/O to :mod:`core.obsidian_writer`; content is the daily
5-domain think-tank digest (editorial sample, overlaid with RSS items when a
feed fetcher is wired).
"""
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from core.obsidian_writer import write_note


def build_note_content(date_str):
    return f"""---
title: "Global Intelligence 每日產業局勢報告 ({date_str})"
date: {date_str}
type: global-intelligence
tags:
  - geopolitics
  - macroeconomy
  - ai-semiconductors
  - biotech
  - energy-transition
---

# Global Intelligence 每日產業局勢報告 ({date_str})

> [!abstract] 每日 5 大領域智庫焦點速讀
> 涵蓋 CSIS, ECB, FDA, DOE, 台積電, 工研院, 中經院與台經院之最新研究與產業焦點。

## 1. 地緣政治與國際關係
- **CSIS**：中��關係重組與東北亞安全新格局研討會。
- **The Conference Board**：美國關稅新規常態化加速友岸外包 (Friendshoring)。

## 2. 巨觀經濟與金融市場
- **歐洲央行 (ECB)**：最新經濟通報警告通膨受能源影響，Higher for Longer 為常態。
- **Mohamed El-Erian**：成熟與新興市場貨幣政策出現顯著分化。

## 3. 資訊科技與人工智慧
- **台積電 (TSMC)**：算力爆發帶動 640 億美元資本支出，加速 2nm 與 CoWoS 擴產。
- **NVIDIA & TSMC**：將 AI 自動化檢測演算法深度植入晶圓廠良率控制。

## 4. 生物科技與健康醫療
- **U.S. FDA**：正式推動 Pilot Plan 試點加速計畫，簡化關鍵新藥行政審查。
- **Eli Lilly**：胰臟癌新藥 Olomorasib 正式獲得 FDA 突破性療法認證。

## 5. 硬體工程、自動化與能源轉型
- **U.S. DOE**：宣布 8 月 SMR 小型模組化核反應爐創新園區競逐名單。
- **固態電池高峰會**：聚焦人形機器人高能量密度與高放電倍率需求。

*Generated automatically by Global Intelligence System on {date_str}*
"""


def write_global_obsidian_note(date_str=None, output_dir=None, data=None):
    """Write the daily Global markdown note. Returns the file path."""
    date_str = date_str or (data or {}).get("date") or "2026-08-11"
    output_dir = output_dir or os.path.join(_REPO_ROOT, "output", "obsidian_vault")
    filename = f"{date_str}_Global_Intelligence_每日產業局勢.md"
    return write_note(output_dir, filename, build_note_content(date_str))


if __name__ == "__main__":
    print("Obsidian note created:", write_global_obsidian_note("2026-08-11"))
