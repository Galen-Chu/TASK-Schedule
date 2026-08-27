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
from core.retrieval import CorpusStore, ingest_items, retrieve

# Spiritual/wellness RSS — ingested into the shared corpus (Phase 3 H1)
SPIRITUAL_FEEDS = [
    "https://www.biddytarot.com/blog/feed/",
    "https://www.mindful.org/feed/",
    "https://www.elephantjournal.com/feed/",
    "https://astrostyle.com/feed/",
]
CORPUS_PATH = os.path.join(_REPO_ROOT, "data", "retrieval", "global_corpus.jsonl")


class SpiritualReportScheduler(BaseReportScheduler):
    report_id = "spiritual"
    report_title = "Spiritual Intelligence 每日覺察運勢報告"
    default_cron = "30 7 * * *"             # 07:30 Asia/Taipei
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
        """Compute live readings for all systems + ingest spiritual RSS (Phase 3 H1).

        Returns a dict whose ``systems`` field maps system_id -> spotlight/
        summary strings. Spiritual/wellness RSS items are ingested into the
        shared retrieval corpus. Returns None only if nothing computed AND
        no RSS items (full sample fallback).
        """
        # Phase 3 H1: ingest spiritual RSS into the shared corpus
        try:
            from core.data.fetchers import fetch_rss_items
            store = CorpusStore(CORPUS_PATH)
            for url in SPIRITUAL_FEEDS:
                items = fetch_rss_items(url, limit=4)
                if items:
                    ingest_items(store, items, source=url)
            store.compact(keep_days=30)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("spiritual RSS ingest failed: %s", exc)

        transits = divination.all_transits(self.date_str)
        if not transits:
            return None
        return {"_source": "divination", "systems": transits}

    def synthesize(self, data):
        """Phase 3 H1: retrieve spiritual domain items for the PDF news section."""
        try:
            store = CorpusStore(CORPUS_PATH)
            items = retrieve(store, query="spiritual meditation tarot astrology mindfulness wellness",
                              domain="spiritual", k=4, days=7)
            if items:
                data["spiritual_intel"] = items
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("spiritual retrieval failed: %s", exc)
        return data

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
        generate_pdf_report(pdf_path, date_str=self.date_str, location=location, systems=systems,
                           spiritual_intel=(data or {}).get("spiritual_intel"))
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
