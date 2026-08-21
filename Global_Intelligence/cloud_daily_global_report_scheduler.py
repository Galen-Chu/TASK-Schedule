#!/usr/bin/env python3
"""Global Intelligence — daily report scheduler.

Triggered daily at **06:30 Asia/Taipei** (``30 6 * * *``). Built on
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
from core.retrieval import CorpusStore, ingest_items, retrieve
from core.retrieval.ingest import DOMAIN_KEYWORDS

# Default public, keyless RSS feeds — breadth across the five domains
# (international + Taiwan). All verified reachable 2026-08-20. Override via
# config global.rss_feeds. Parsed with feedparser (optional); any feed that
# fails is skipped and the report still builds.
SAMPLE_FEEDS = [
    # 地緣政治 / 國際
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://news.un.org/feed/subscribe/en/news/all/rss.xml",
    # 巨觀經濟 / 金融
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
    "https://www.economist.com/latest/rss.xml",
    # 資訊科技 / AI（國際 + 台灣）
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://technews.tw/feed/",
    "https://www.ithome.com.tw/rss",
    # 生技 / 醫療
    "https://www.sciencedaily.com/rss/health_medicine.xml",
    # 硬體 / 半導體 / 能源
    "https://spectrum.ieee.org/feeds/topic/semiconductors.rss",
    "https://electrek.co/feed/",
]

# Persistent retrieval corpus — committed to the repo so it accumulates across
# ephemeral CI runs. Swap to a remote backend (GCP) in a later phase.
CORPUS_PATH = os.path.join(_REPO_ROOT, "data", "retrieval", "global_corpus.jsonl")


class GlobalReportScheduler(BaseReportScheduler):
    report_id = "global"
    report_title = "Global Intelligence 每日產業局勢報告"
    default_cron = "30 6 * * *"             # 06:30 Asia/Taipei
    page_count = 5

    def sample_data(self):
        return {"editorial": True}

    def _store(self):
        """The persistent retrieval corpus (None if unavailable)."""
        try:
            return CorpusStore(CORPUS_PATH)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("corpus store unavailable (%s)", exc)
            return None

    def fetch_data(self):
        """Best-effort RSS pull. Ingests items into the persistent retrieval
        corpus so it accumulates across runs. Returns the sample if nothing is
        reachable."""
        items = []
        store = self._store()
        for url in self.config.get("rss_feeds", SAMPLE_FEEDS):
            feed_items = fetch_rss_items(url, limit=4)
            items.extend(feed_items)
            if store is not None and feed_items:
                ingest_items(store, feed_items, source=url)
        if store is not None:
            store.compact(keep_days=30)
        if not items:
            return None
        return {"editorial": True, "rss_items": items[:6]}

    def synthesize(self, data):
        """Gemini digest of today's RSS (when keyed), then pull recent real
        items per domain from the retrieval corpus to supplement the editorial
        content. Retrieval works even if today's fetch failed, because the
        corpus persists across runs."""
        items = (data or {}).get("rss_items") or []
        if items:
            from core import llm
            if llm.is_available():
                digest = llm.summarize_news_what_why_sowhat(items, domain_label="全球產業情報")
                if digest:
                    data["llm_digest"] = digest
                    data["_source"] = (data.get("_source") or "") + "+Gemini"
        store = self._store()
        if store is not None:
            data.setdefault("retrieval", {})
            for dom, kws in DOMAIN_KEYWORDS.items():
                got = retrieve(store, query=" ".join(kws[:6]), domain=dom, k=2, days=7)
                if got:
                    data["retrieval"][dom] = got
        return data

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
        upload_to_drive(pdf_path, folder_id=self.config.get("drive_folder_id"), subfolder=self.report_id)


def run_global_daily_pipeline(date_str=None, output_dir=None):
    """Convenience entry point (preserves the original public API)."""
    return GlobalReportScheduler(date_str=date_str, output_dir=output_dir).run()


if __name__ == "__main__":
    run_global_daily_pipeline()
