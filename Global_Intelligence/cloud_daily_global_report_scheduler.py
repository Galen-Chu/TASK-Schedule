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
from core.retrieval.retrieve import domain_trends, trending_keywords
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
    # 航空太空與量子科技
    "https://www.nasa.gov/news-release/feed/",
    "https://spacenews.com/feed/",
    "https://arstechnica.com/space/feed/",
    "https://aviationweek.com/rss-feeds?rss=air-transport",
    "https://www.reuters.com/technology/space/rss",
    # 量子科技
    "https://thequantuminsider.com/feed/",
    "https://physicsworld.com/feed/",
]

# Persistent retrieval corpus — committed to the repo so it accumulates across
# ephemeral CI runs. Swap to a remote backend (GCP) in a later phase.
CORPUS_PATH = os.path.join(_REPO_ROOT, "data", "retrieval", "global_corpus.jsonl")


class GlobalReportScheduler(BaseReportScheduler):
    report_id = "global"
    report_title = "Global Intelligence 每日產業局勢報告"
    default_cron = "30 6 * * *"             # 06:30 Asia/Taipei
    page_count = 7

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
        """Best-effort RSS pull (parallel). Ingests items into the persistent
        retrieval corpus so it accumulates across runs. Returns the sample if
        nothing is reachable."""
        items = []
        store = self._store()

        # Purge items from removed/deprecated sources (immediate cleanup,
        # instead of waiting for 30-day retention).
        if store is not None:
            store.purge_source("reddit.com")

        # Parallel RSS fetching (16 feeds × ~2s sequential = ~32s → ~5s parallel)
        import concurrent.futures as _cf
        feed_urls = self.config.get("rss_feeds", SAMPLE_FEEDS)
        with _cf.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(
                lambda url: (url, fetch_rss_items(url, limit=4)),
                feed_urls
            ))

        for url, feed_items in results:
            items.extend(feed_items)
            if store is not None and feed_items:
                ingest_items(store, feed_items, source=url)

        if store is not None:
            store.compact(keep_days=30)
            store.dedup_cross_source()
            # Phase 2: attach embeddings + semantic domain tags (no-op without
            # GEMINI_API_KEY; never raises into the pipeline).
            from core.retrieval.embed import backfill as embed_backfill
            embed_backfill(store)
        if not items:
            return None
        return {"editorial": True, "rss_items": items[:6]}

    def synthesize(self, data):
        """Gemini digest of today's RSS (when keyed), then pull recent real
        items per domain from the retrieval corpus — these become the **primary
        dynamic topic cards** (5 per page). Editorial content is fallback."""
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
                got = retrieve(store, query=" ".join(kws[:8]), domain=dom, k=6, days=7)
                if got:
                    data["retrieval"][dom] = got
            # Trend comparison (G): week-over-week domain heat + trending keywords
            data["trends"] = {
                "domains": domain_trends(store),
                "keywords": trending_keywords(store),
            }
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
