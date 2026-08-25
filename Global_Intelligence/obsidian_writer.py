#!/usr/bin/env python3
"""Global Intelligence — Obsidian markdown writer.

Delegates file I/O to :mod:`core.obsidian_writer`; content is the daily
6-domain dynamic digest (5 topic cards per domain pulled live from the
retrieval corpus), overlaid with a live RSS快訊 section.
"""
import os
import re
import sys
from html import unescape as _html_unescape
from urllib.parse import urlparse as _urlparse

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from core.obsidian_writer import write_note

_TAG_RE = re.compile(r"<[^>]+>")

def _strip_html(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", _html_unescape(_TAG_RE.sub(" ", text))).strip()


def _domain_name(tag):
    return {
        "geopolitics": "地緣政治與國際關係",
        "macro": "巨觀經濟與金融市場",
        "it_ai": "資訊科技與人工智慧",
        "biotech": "生物科技與健康醫療",
        "hardware": "硬體工程、自動化與能源轉型",
        "aerospace": "航空太空產業趨勢",
    }.get(tag, tag)


def _live_feed_block(rss_items, date_str):
    """Render the live RSS快訊 section, or an offline note if no items."""
    items = rss_items or []
    if not items:
        return (
            f"\n## 即時快訊 (Live RSS, {date_str})\n"
            f"> 本日即時來源未取得（離線/CI 或 feedparser 未安裝）。\n"
        )
    lines = [f"\n## 即時快訊 (Live RSS, {date_str}) — 共 {len(items)} 則", ""]
    for e in items:
        title = _strip_html(e.get("title") or "").strip()
        if not title:
            continue
        lines.append(f"- {title}")
    return "\n".join(lines) + "\n"


def build_note_content(date_str, rss_items=None, retrieval=None):
    live = _live_feed_block(rss_items, date_str)
    retrieval = retrieval or {}

    # Build per-domain dynamic sections
    domain_sections = []
    for i, (tag, _) in enumerate([
        ("geopolitics", ""), ("macro", ""), ("it_ai", ""),
        ("biotech", ""), ("hardware", ""), ("aerospace", ""),
    ], start=1):
        zh = _domain_name(tag)
        items = retrieval.get(tag, [])
        if items:
            lines = [f"\n## {i}. {zh}", ""]
            for it in items[:5]:
                src = _urlparse(it.get("source", "")).netloc.replace("www.", "").split(".")[0].upper()
                title = _strip_html(it.get("title", ""))[:100]
                link = it.get("link", "")
                if link:
                    lines.append(f"- **[{src}]** [{title}]({link})")
                else:
                    lines.append(f"- **[{src}]** {title}")
            domain_sections.append("\n".join(lines))
        else:
            domain_sections.append(f"\n## {i}. {zh}\n> 本領域今日無即時項目（語料累積中）。")

    domains_md = "\n".join(domain_sections)

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
  - aerospace
---

# Global Intelligence 每日產業局勢報告 ({date_str})

> [!abstract] 每日 6 大領域即時情報速讀（5 卡/領域，動態檢索）
> 來源：BBC / AlJazeera / UN / CNBC / Economist / TechCrunch / TechNews / iThome / ScienceDaily / IEEE / Electrek / NASA / SpaceNews / Ars Technica / Aviation Week / Reuters
{live}
{domains_md}

*Generated automatically by Global Intelligence System on {date_str}*
"""


def write_global_obsidian_note(date_str=None, output_dir=None, data=None):
    """Write the daily Global markdown note. Returns the file path."""
    data = data or {}
    date_str = date_str or data.get("date") or "2026-08-25"
    output_dir = output_dir or os.path.join(_REPO_ROOT, "output", "obsidian_vault")
    filename = f"{date_str}_Global_Intelligence_每日產業局勢.md"
    return write_note(
        output_dir, filename,
        build_note_content(date_str, data.get("rss_items"), data.get("retrieval")),
    )


if __name__ == "__main__":
    print("Obsidian note created:", write_global_obsidian_note("2026-08-25"))
