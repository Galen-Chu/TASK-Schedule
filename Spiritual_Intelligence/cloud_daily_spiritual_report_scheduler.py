#!/usr/bin/env python3
"""Spiritual Intelligence — daily report scheduler.

Triggered daily at **06:30 Asia/Taipei** (``30 6 * * *``). Built on
:class:`core.scheduler_base.BaseReportScheduler`.

All five occult systems are now computed live each day (Swiss Ephemeris for
Western astrology + Human Design gates; lunar_python for Bazi/Ziwei; Mei Hua
for I-Ching) via :mod:`core.data.divination`. Any system that fails to compute
keeps its static sample entry. Personal data (name, email, Drive folder) is
read from config / environment — never committed in source.
"""
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from core.scheduler_base import BaseReportScheduler
from core.data import divination
from core.dispatch.drive_uploader import upload_to_drive
from core.dispatch.gmail_dispatcher import send_digest


class SpiritualReportScheduler(BaseReportScheduler):
    report_id = "spiritual"
    report_title = "Spiritual Intelligence 每日覺察運勢報告"
    default_cron = "30 6 * * *"             # 06:30 Asia/Taipei
    page_count = 7

    # ---- config (no PII in source) ----------------------------------------
    def _profile(self):
        """Load birth/natal profile from config, with a sanitized fallback."""
        path = self.config.get("birth_profile_path") or os.path.join(
            _REPO_ROOT, "config", "birth-profile.yaml"
        )
        if os.path.isfile(path):
            try:
                import yaml
                with open(path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("birth-profile.yaml 載入失敗 (%s)；使用預設值。", exc)
        return {
            "user": {"name": "(本命設定檔未提供)", "timezone": "Asia/Taipei"},
            "location": "臺北市",
        }

    # ---- stages -----------------------------------------------------------
    def sample_data(self):
        from Spiritual_Intelligence.systems_data import spotlight_map
        return {"transit": spotlight_map()}

    def fetch_data(self):
        """Compute live readings for all five occult systems.

        Returns a dict whose ``systems`` field maps system_id -> spotlight/
        summary strings, or None if nothing could be computed (full sample
        fallback).
        """
        transits = divination.all_transits(self.date_str)
        if not transits:
            return None
        return {"_source": "divination", "systems": transits}

    def render_pdf(self, data):
        import copy
        from Spiritual_Intelligence.pdf_generator import generate_pdf_report
        from Spiritual_Intelligence.systems_data import SYSTEMS_CONFIG

        profile = self._profile()
        location = profile.get("location") or "臺北市"

        # Overlay today's computed spotlight/summary onto whichever systems
        # resolved; the rest keep their static sample entry.
        systems = SYSTEMS_CONFIG
        overlay = (data or {}).get("systems") or {}
        if overlay:
            systems = copy.deepcopy(SYSTEMS_CONFIG)
            for cfg in systems:
                hit = overlay.get(cfg["id"])
                if hit:
                    cfg["spotlight"] = hit["spotlight"]
                    cfg["system_data_summary"] = hit["system_data_summary"]

        pdf_path = os.path.join(self.output_dir, f"{self.date_str}_Spiritual_Intelligence_每日覺察運勢報告.pdf")
        generate_pdf_report(pdf_path, date_str=self.date_str, location=location, systems=systems)
        return pdf_path

    def render_obsidian(self, data):
        from Spiritual_Intelligence.obsidian_writer import ObsidianVaultWriter
        vault = os.path.join(self.output_dir, "obsidian_vault")
        writer = ObsidianVaultWriter(vault_path=vault)
        return writer.execute_writeback(self.date_str)

    def dispatch(self, pdf_path, data, note_path=None):
        link = upload_to_drive(pdf_path, folder_id=self.config.get("drive_folder_id"), subfolder=self.report_id)
        profile = self._profile()
        email = self.config.get("notify_email") or profile.get("user", {}).get("email")
        if email:
            send_digest(
                email,
                f"Spiritual Intelligence 每日覺察運勢報告 ({self.date_str})",
                f"今日報告已產出：{os.path.basename(pdf_path)}" + (f"\nDrive: {link}" if link else ""),
                attachments=[pdf_path],
            )


def run_daily_pipeline(date_str=None, output_dir=None):
    """Convenience entry point (preserves the original public API)."""
    return SpiritualReportScheduler(date_str=date_str, output_dir=output_dir).run()


if __name__ == "__main__":
    run_daily_pipeline()
