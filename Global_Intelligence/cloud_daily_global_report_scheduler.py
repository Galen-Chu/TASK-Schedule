#!/usr/bin/env python3
"""Global Intelligence — daily report scheduler.

Triggered daily at **07:00 Asia/Taipei** (``0 7 * * *``). Built on
:class:`core.scheduler_base.BaseReportScheduler`. This fixes the original
``from generate_global_pdf import build_global_pdf`` ModuleNotFoundError (the
module was always named ``pdf_generator``).
"""
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from core.scheduler_base import BaseReportScheduler
from core.data.fetchers import fetch_rss_items
from core.dispatch.drive_uploader import upload_to_drive

# A few public, keyless RSS feeds to demonstrate the live-source path. Parsed
# with feedparser (optional); on any failure the scheduler falls back to the
# editorial sample content baked into the PDF generator.
SAMPLE_FEEDS = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.reddit.com/r/worldnews/.rss",
]


class GlobalReportScheduler(BaseReportScheduler):
    report_id = "global"
    report_title = "Global Intelligence 每日產業局勢報告"
    default_cron = "0 7 * * *"             # 07:00 Asia/Taipei
    page_count = 5

    def sample_data(self):
        return {"editorial": True}

    def fetch_data(self):
        """Best-effort RSS pull. Returns the sample if nothing is reachable."""
        items = []
        for url in self.config.get("rss_feeds", SAMPLE_FEEDS):
            items.extend(fetch_rss_items(url, limit=3))
        if not items:
            return None
        return {"editorial": True, "rss_items": items[:6]}

    def render_pdf(self, data):
        from Global_Intelligence.pdf_generator import build_global_pdf
        pdf_path = os.path.join(self.output_dir, f"{self.date_str}_Global_Intelligence_每日產業局勢報告.pdf")
        build_global_pdf(pdf_path, data=data, date_str=self.date_str)
        return pdf_path

    def render_obsidian(self, data):
        from Global_Intelligence.obsidian_writer import write_global_obsidian_note
        vault = os.path.join(self.output_dir, "obsidian_vault")
        return write_global_obsidian_note(self.date_str, output_dir=vault, data=data)

    def dispatch(self, pdf_path, data, note_path=None):
        upload_to_drive(pdf_path, folder_id=self.config.get("drive_folder_id"))


def run_global_daily_pipeline(date_str=None, output_dir=None):
    """Convenience entry point (preserves the original public API)."""
    return GlobalReportScheduler(date_str=date_str, output_dir=output_dir).run()


if __name__ == "__main__":
    run_global_daily_pipeline()
