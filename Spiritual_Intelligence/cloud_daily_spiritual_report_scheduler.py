#!/usr/bin/env python3
"""Spiritual Intelligence — daily report scheduler.

Triggered daily at **06:30 Asia/Taipei** (``30 6 * * *``). Built on
:class:`core.scheduler_base.BaseReportScheduler`.

No real ephemeris engine is wired yet, so :meth:`fetch_data` falls back to the
static :mod:`Spiritual_Intelligence.systems_data` sample (the calculation
engines described in the spec are future work). Personal data (name, email,
Drive folder) is read from config / environment — never committed in source.
"""
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from core.scheduler_base import BaseReportScheduler
from core.data import astro
from core.dispatch.drive_uploader import upload_to_drive
from core.dispatch.gmail_dispatcher import send_digest


class SpiritualReportScheduler(BaseReportScheduler):
    report_id = "spiritual"
    report_title = "Spiritual Intelligence 每日覺察運勢報告"
    default_cron = "30 6 * * *"             # 06:30 Asia/Taipei
    page_count = 5

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
        """Compute real Western-astrology transits via Swiss Ephemeris.

        Returns a dict with the resolved systems (a deep copy of the sample
        with the SYS_AST spotlight/summary overwritten by today's actual
        Sun/Moon/Mercury positions), or None to keep the static sample.
        """
        transits = astro.compute_transits(self.date_str)
        if not transits:
            return None
        return {"_source": "SwissEphemeris", "transits": transits}

    def render_pdf(self, data):
        import copy
        from Spiritual_Intelligence.pdf_generator import generate_pdf_report
        from Spiritual_Intelligence.systems_data import SYSTEMS_CONFIG
        from core.data.astro import astrology_spotlight

        profile = self._profile()
        location = profile.get("location") or "臺北市"

        # If we computed real transits, overlay them onto the Astrology system
        # so the PDF shows today's actual Sun/Moon/Mercury instead of the sample.
        systems = SYSTEMS_CONFIG
        transits = (data or {}).get("transits")
        spot = astrology_spotlight(transits) if transits else None
        if spot:
            spotlight_text, summary_text = spot
            systems = copy.deepcopy(SYSTEMS_CONFIG)
            for cfg in systems:
                if cfg["id"] == "SYS_AST":
                    cfg["spotlight"] = spotlight_text
                    cfg["system_data_summary"] = summary_text

        pdf_path = os.path.join(self.output_dir, f"{self.date_str}_Spiritual_Intelligence_每日覺察運勢報告.pdf")
        generate_pdf_report(pdf_path, date_str=self.date_str, location=location, systems=systems)
        return pdf_path

    def render_obsidian(self, data):
        from Spiritual_Intelligence.obsidian_writer import ObsidianVaultWriter
        vault = os.path.join(self.output_dir, "obsidian_vault")
        writer = ObsidianVaultWriter(vault_path=vault)
        return writer.execute_writeback(self.date_str)

    def dispatch(self, pdf_path, data, note_path=None):
        link = upload_to_drive(pdf_path, folder_id=self.config.get("drive_folder_id"))
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
