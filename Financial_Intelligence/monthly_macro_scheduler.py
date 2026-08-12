#!/usr/bin/env python3
"""Financial Intelligence — Monthly Macro Digest scheduler.

Distinct cadence from the daily Financial report:
  * daily  (``30 7 * * *``) — market quotes + signal score (intraday/priced)
  * monthly (``0 9 2 * *``) — structural macro indicators (CPI/NFP/PCE/yields)

Runs on the 2nd of each month at 09:00 Asia/Taipei so the previous month's
batch of macro releases (CPI ~mid-month, NFP ~1st, PCE ~end) are mostly in.
Keyless: pulls BLS (CPI/Core CPI/unemployment/NFP) + U.S. Treasury yield curve.
"""
import os
import sys
import datetime

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from core.scheduler_base import BaseReportScheduler
from core.data.fetchers import fetch_macro_snapshot, fetch_treasury_yields
from core.dispatch.drive_uploader import upload_to_drive


class MonthlyMacroScheduler(BaseReportScheduler):
    report_id = "macro"
    report_title = "Financial Intelligence Monthly Macro Digest"
    default_cron = "0 9 2 * *"             # 2nd of month, 09:00 Asia/Taipei
    page_count = 1

    def sample_data(self):
        """Static fallback used only if every live source fails."""
        return {
            "cpi_headline": {"value": "3.0", "year": "2026", "period_name": "June"},
            "cpi_core": {"value": "3.2", "year": "2026", "period_name": "June"},
            "unemployment": {"value": "4.1", "year": "2026", "period_name": "July"},
            "nfp": {"value": "165", "year": "2026", "period_name": "July"},
        }

    def fetch_data(self):
        """Pull BLS macro bundle + Treasury yield curve (all keyless)."""
        sources = []
        data = {}
        macro = fetch_macro_snapshot()
        if macro:
            data.update(macro)
            sources.append("BLS")
        tyc = fetch_treasury_yields()
        if tyc:
            data["treasury"] = {k: v for k, v in tyc.items() if not k.startswith("_")}
            sources.append("Treasury")
        if not sources:
            return None
        data["_source"] = "+".join(sources)
        return data

    def _period_label(self):
        """Previous-month label, e.g. '2026-07 月度總經'."""
        try:
            d = datetime.date.fromisoformat(self.date_str)
            prev = (d.replace(day=1) - datetime.timedelta(days=1))
            return f"{prev.strftime('%Y-%m')} 月度總經（前月公佈值）"
        except (ValueError, TypeError):
            return f"{self.date_str[:7]} 月度總經"

    def render_pdf(self, data):
        from Financial_Intelligence.macro_pdf_generator import build_macro_pdf
        pdf_path = os.path.join(self.output_dir, f"{self.date_str[:7]}_Financial_Intelligence_Monthly_Macro_Digest.pdf")
        build_macro_pdf(pdf_path, data=data, date_str=self.date_str, period_label=self._period_label())
        return pdf_path

    def render_obsidian(self, data):
        from core.obsidian_writer import write_note
        vault = os.path.join(self.output_dir, "obsidian_vault")
        cpi = (data or {}).get("cpi_headline", {})
        body = (
            f"# Monthly Macro Digest ({self._period_label()})\n\n"
            f"- **CPI（頭條）**: {cpi}\n"
            f"- **資料來源**: {data.get('_source','—')}\n"
            f"\n*Monthly cadence — 與每日投資趨勢報告區隔。*\n"
        )
        return write_note(vault, f"{self.date_str[:7]}_Monthly_Macro_Digest.md", body)

    def dispatch(self, pdf_path, data, note_path=None):
        upload_to_drive(pdf_path, folder_id=self.config.get("drive_folder_id"))


def run_monthly_macro_pipeline(date_str=None, output_dir=None):
    """Convenience entry point."""
    return MonthlyMacroScheduler(date_str=date_str, output_dir=output_dir).run()


if __name__ == "__main__":
    run_monthly_macro_pipeline()
