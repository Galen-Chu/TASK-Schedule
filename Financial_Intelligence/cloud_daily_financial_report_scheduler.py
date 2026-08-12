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
from core.data.fetchers import (
    fetch_twse_margin, fetch_market_snapshot, fetch_treasury_yields, fetch_fear_greed,
)
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
        """Best-effort real data, layered onto the sample baseline.

        All sources are keyless now: Yahoo Finance (VIX/DXY/Gold/BTC/WTI),
        U.S. Treasury yield-curve CSV (2Y/10Y/spread), Fear & Greed index,
        and TWSE margin maintenance ratio. Each layer only overwrites the
        fields it actually resolved; if nothing resolves the method returns
        None and the base class falls back to the full sample.
        """
        sources = []
        data = self.sample_data()

        # 1) Yahoo Finance headline quotes (keyless)
        snap = fetch_market_snapshot()
        if snap:
            keymap = {"vix": "vix", "dxy": "dxy", "gold": "gold", "btc": "btc", "wti": "wti"}
            for k, dk in keymap.items():
                if k in snap:
                    data[dk] = snap[k]
            sources.append("Yahoo")

        # 2) U.S. Treasury daily yield curve — 2Y / 10Y / spread (keyless)
        tyc = fetch_treasury_yields()
        if tyc:
            if "10y" in tyc:
                data["treasury_10y"] = tyc["10y"]
            if "2y" in tyc:
                data["treasury_2y"] = tyc["2y"]
            if "spread_10y2y" in tyc:
                data["spread_10y2y"] = tyc["spread_10y2y"]
            sources.append("Treasury")

        # 3) Fear & Greed index (keyless) — replaces the old VIX heuristic
        fg = fetch_fear_greed()
        if fg is not None:
            data["fear_and_greed"] = fg
            sources.append("F&G")

        # 4) TWSE margin maintenance ratio (keyless)
        twse = fetch_twse_margin(self.date_str)
        if twse:
            try:
                rows = twse["raw"].get("data", [])
                if rows:
                    ratio = float(str(rows[0][-1]).replace(",", "").strip())
                    if 100 < ratio < 300:
                        data["margin_maintenance_ratio"] = round(ratio, 2)
                        sources.append("TWSE")
            except (ValueError, TypeError, IndexError, KeyError):
                self.logger.info("TWSE 回傳解析失敗，沿用 sample 維持率。")

        if not sources:
            return None  # triggers full sample fallback in base class
        data["_source"] = "+".join(sources)
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
        upload_to_drive(pdf_path, folder_id=self.config.get("drive_folder_id"), subfolder=self.report_id)


def run_daily_pipeline(date_str=None, output_dir=None):
    """Convenience entry point (preserves the original public API)."""
    return FinancialReportScheduler(date_str=date_str, output_dir=output_dir).run()


if __name__ == "__main__":
    run_daily_pipeline()
