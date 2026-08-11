#!/usr/bin/env python3
"""Spiritual Intelligence — Obsidian vault writer.

Phase-2 write-back: a full detail note in ``Awareness/Daily-Transit/`` plus a
section merged into the daily note, with a wikilink between them. Content is
derived from :mod:`Spiritual_Intelligence.systems_data` so it always matches
the PDF. Paths are portable (no hardcoded ``/working_dir``).
"""
import os
import sys
import logging
from datetime import datetime

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from core.obsidian_writer import write_note
from Spiritual_Intelligence.systems_data import SYSTEMS_CONFIG

logger = logging.getLogger("ObsidianWriter")

_SECTION_TITLES = {
    "SYS_HD": ("一、 人類圖流日 (Human Design Transit)", "Human Design Transit"),
    "SYS_AST": ("二、 西洋占星流日 (Western Astrology)", "Western Astrology"),
    "SYS_ZW": ("三、 紫微斗數流日 (Ziwei Doushu)", "Ziwei Doushu"),
    "SYS_BAZI": ("四、 八字干支流日 (Bazi)", "Bazi & Four Pillars"),
    "SYS_ICHING": ("五、 梅花易數當日起卦 (I Ching)", "I Ching & Mei Hua"),
}


def _detail_content(date_str):
    parts = [
        "---",
        f"created: {date_str}",
        "tags:",
        "  - awareness/transit",
        "  - spiritual-intelligence",
        "  - daily-report",
        "status: generated",
        "---",
        "",
        f"# Spiritual Intelligence 每日覺察詳細報告 ({date_str})",
        "",
    ]
    for cfg in SYSTEMS_CONFIG:
        zh_title, _en = _SECTION_TITLES.get(cfg["id"], (cfg["title"], cfg["title"]))
        parts.append(f"## {zh_title}")
        parts.append(f"> **宇宙點名：** {cfg['spotlight']}")
        parts.append(f"- **關鍵參數：** {cfg['system_data_summary']}")
        parts.append(f"- **覺察觀察 (What)：** {cfg['what']}")
        parts.append("")
    return "\n".join(parts)


def _summary_text():
    return "  /  ".join(cfg["spotlight"].replace("📍 ", "") for cfg in SYSTEMS_CONFIG)


class ObsidianVaultWriter:
    """Writes the detail note + merges a section into the daily note."""

    def __init__(self, vault_path=None):
        self.vault_path = vault_path or os.path.join(_REPO_ROOT, "output", "obsidian_vault")
        self.daily_folder = os.path.join(self.vault_path, "Daily")
        self.awareness_folder = os.path.join(self.vault_path, "Awareness", "Daily-Transit")
        os.makedirs(self.daily_folder, exist_ok=True)
        os.makedirs(self.awareness_folder, exist_ok=True)

    def write_awareness_detail_note(self, date_str, system_data=None):
        """Create Awareness/Daily-Transit/YYYY-MM-DD.md. Returns the path."""
        detail_path = os.path.join(self.awareness_folder, f"{date_str}.md")
        write_note(self.awareness_folder, f"{date_str}.md", _detail_content(date_str))
        logger.info("Awareness detail note created at: %s", detail_path)
        return detail_path

    def merge_into_daily_note(self, date_str, summary_text, wikilink):
        """Append (or create) the awareness section in Daily/YYYY-MM-DD.md."""
        daily_path = os.path.join(self.daily_folder, f"{date_str}.md")
        section = (
            f"\n## 🔮 今日命理覺察 (Spiritual Intelligence)\n"
            f"> **覺察連結：** [[Awareness/Daily-Transit/{date_str}|{date_str} 覺察詳細報告]]\n\n"
            f"{summary_text}\n\n---\n"
        )
        if not os.path.exists(daily_path):
            initial = (
                "---\n"
                f"created: {date_str}\n"
                "tags:\n  - daily-note\n  - worklog\n"
                "pipeline_status: generated\n"
                "---\n\n"
                f"# Daily Note ({date_str})\n{section}"
            )
            with open(daily_path, "w", encoding="utf-8") as f:
                f.write(initial)
            logger.info("Created new Daily Note at %s", daily_path)
        else:
            with open(daily_path, "r", encoding="utf-8") as f:
                existing = f.read()
            if "## 🔮 今日命理覺察" not in existing:
                with open(daily_path, "a", encoding="utf-8") as f:
                    f.write("\n" + section)
                logger.info("Appended awareness section into %s", daily_path)
        return daily_path

    def execute_writeback(self, date_str, summary_text=None, system_data=None):
        """Run the full write-back flow. Returns the detail note path."""
        detail_path = self.write_awareness_detail_note(date_str, system_data)
        wikilink = f"[[Awareness/Daily-Transit/{date_str}|{date_str} 覺察詳細報告]]"
        self.merge_into_daily_note(date_str, summary_text or _summary_text(), wikilink)
        logger.info("Obsidian write-back completed for date: %s", date_str)
        return detail_path


if __name__ == "__main__":
    writer = ObsidianVaultWriter()
    writer.execute_writeback(datetime.now().strftime("%Y-%m-%d"))
