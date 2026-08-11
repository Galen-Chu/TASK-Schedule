#!/usr/bin/env python3
"""Financial Intelligence — daily report scheduler.

Triggered daily at **07:30 Asia/Taipei** (``30 7 * * *``). Built on
:class:`core.scheduler_base.BaseReportScheduler`:

  fetch_data    -> TWSE open API (best-effort, keyless) + overlay onto sample
  synthesize    -> compute the quantitative signal score + rating
  render_pdf    -> Financial_Intelligence/pdf_generator.generate_daily_pdf
  render_obsidian -> Financial_Intelligence/obsidian_writer.write_obsidian_note
  dispatch      -> core.dispatch.drive_uploader (no-op until creds configured)
"""
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from core.scheduler_base import BaseReportScheduler
from core.data.fetchers import fetch_twse_margin
from core.dispatch.drive_uploader import upload_to_drive

# Imported lazily inside methods so the module imports cleanly even before
# reportlab/fonts are available (e.g. during `--help`).


class FinancialReportScheduler(BaseReportScheduler):
    report_id = "financial"
    report_title = "Financial Intelligence 每日投資趨勢報告"
    default_cron = "30 7 * * *"          # 07:30 Asia/Taipei
    page_count = 5

    def sample_data(self):
        """Bundled offline dataset (used when the live source is unavailable)."""
        return {
            "signal_score": 72,
            "signal_rating": "🟢 偏多進場 / 尋找超跌加碼點",
            "margin_maintenance_ratio": 151.8,
            "futures_net_oi": -18500,
            "vix": 28.4,
            "fear_and_greed": 24,
            "treasury_10y": 3.85,
            "treasury_2y": 3.73,
            "spread_10y2y": 0.12,
            "dxy": 102.4,
            "usdtwd": 32.15,
            "gold": 2450,
            "btc": 58500,
        }

    def fetch_data(self):
        """Best-effort: pull TWSE margin data and overlay onto sample.

        Returns ``None`` (-> sample fallback) if the network call or parsing
        fails. FRED/Yahoo need API keys and are documented in the spec but not
        wired here yet.
        """
        twse = fetch_twse_margin(self.date_str)
        if not twse:
            return None
        data = self.sample_data()
        try:
            rows = twse["raw"].get("data", [])
            fields = twse["raw"].get("fields", [])
            # MI_MARGIN fields typically include 融資維持率(%) as the last col.
            if rows and fields:
                last = rows[0][-1]
                ratio = float(str(last).replace(",", "").strip())
                if 100 < ratio < 300:          # sanity range
                    data["margin_maintenance_ratio"] = round(ratio, 2)
        except (ValueError, TypeError, IndexError, KeyError):
            self.logger.info("TWSE 回傳解析失敗，沿用 sample 維持率。")
            return None
        data["_source"] = "TWSE+sample"
        return data

    def synthesize(self, data):
        from Financial_Intelligence.pdf_generator import calculate_signal_score, rating_from_score
        if "signal_score" not in data:
            data["signal_score"] = calculate_signal_score(data)
        data["signal_rating"] = rating_from_score(data["signal_score"])
        return data

    def render_pdf(self, data):
        from Financial_Intelligence.pdf_generator import generate_daily_pdf
        pdf_path = os.path.join(self.output_dir, f"{self.date_str}_Financial_Intelligence_每日投資趨勢報告.pdf")
        generate_daily_pdf(pdf_path, data=data, date_str=self.date_str)
        return pdf_path

    def render_obsidian(self, data):
        from Financial_Intelligence.obsidian_writer import write_obsidian_note
        vault = os.path.join(self.output_dir, "obsidian_vault")
        return write_obsidian_note(data, output_dir=vault)

    def dispatch(self, pdf_path, data, note_path=None):
        upload_to_drive(pdf_path, folder_id=self.config.get("drive_folder_id"))


def run_daily_pipeline(date_str=None, output_dir=None):
    """Convenience entry point (preserves the original public API)."""
    return FinancialReportScheduler(date_str=date_str, output_dir=output_dir).run()


if __name__ == "__main__":
    run_daily_pipeline()
