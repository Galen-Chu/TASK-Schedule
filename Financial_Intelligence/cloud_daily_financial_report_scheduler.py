#!/usr/bin/env python3
"""Financial Intelligence — daily report scheduler.

Triggered daily at **06:30 Asia/Taipei** (``30 6 * * *``). Built on
:class:`core.scheduler_base.BaseReportScheduler`:

  fetch_data    -> TWSE open API (best-effort, keyless) + overlay onto sample
  synthesize    -> compute the quantitative signal score + rating
  render_pdf    -> Financial_Intelligence/pdf_generator.generate_daily_pdf
  render_obsidian -> Financial_Intelligence/obsidian_writer.write_obsidian_note
  dispatch      -> core.dispatch.drive_uploader (no-op until creds configured)
"""
import datetime
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
from core.retrieval import CorpusStore, ingest_items, retrieve

# Financial news RSS feeds — ingested into the same retrieval corpus as Global,
# but tagged with "financial" domain keywords via the classify_domain logic.
FINANCIAL_FEEDS = [
    "https://finance.yahoo.com/news/rss.xml",
    "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",  # CNBC Top News
    "https://www.ft.com/rss/home",
    "https://seekingalpha.com/market_currents.xml",
]

CORPUS_PATH = os.path.join(_REPO_ROOT, "data", "retrieval", "global_corpus.jsonl")

# Imported lazily inside methods so the module imports cleanly even before
# reportlab/fonts are available (e.g. during `--help`).


class FinancialReportScheduler(BaseReportScheduler):
    report_id = "financial"
    report_title = "Financial Intelligence 每日投資趨勢報告"
    default_cron = "30 7 * * *"          # 07:30 Asia/Taipei
    page_count = 7

    def sample_data(self):
        """Bundled offline dataset (used when the live source is unavailable)."""
        return {
            "signal_score": 72,
            "signal_rating": "🟢 偏多進場 / 尋找超跌加碼點",
            "tw_margin_balance": 8970000,
            "tw_short_balance": 214000,
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
            "macro": {
                "yield_curve": {
                    "date": "08/13/2026",
                    "curve": {"1M": 3.79, "3M": 3.81, "6M": 3.84, "1Y": 3.92,
                              "2Y": 4.15, "3Y": 4.24, "5Y": 4.35, "7Y": 4.48,
                              "10Y": 4.63, "20Y": 4.90, "30Y": 4.82},
                },
                "us10y_hist": [
                    {"date": (datetime.date(2026, 1, 2) + datetime.timedelta(weeks=i)).strftime("%m/%d/%Y"),
                     "v": round(4.62 - 0.010 * i + (0.05 if i % 7 == 0 else 0), 2)}
                    for i in range(30)
                ],
                "cpi_hist": [{"year": y, "period_name": m,
                              "value": str(round(318.0 + 1.05 * i, 1))}
                             for i, (y, m) in enumerate(zip(
                                 (["2024"] * 4 + ["2025"] * 12 + ["2026"] * 12)[:25],
                                 (["Sep", "Oct", "Nov", "Dec"] +
                                  ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"] * 2)[:25]))],
                "core_cpi_hist": [{"year": y, "period_name": m,
                                   "value": str(round(322.0 + 0.75 * i, 1))}
                                  for i, (y, m) in enumerate(zip(
                                      (["2024"] * 4 + ["2025"] * 12 + ["2026"] * 12)[:25],
                                      (["Sep", "Oct", "Nov", "Dec"] +
                                       ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"] * 2)[:25]))],
                "unemployment": {"value": "4.2", "year": "2026", "period_name": "July"},
            },
        }

    def fetch_data(self):
        """Best-effort real data, layered onto the sample baseline.

        All sources are keyless: Yahoo Finance, Treasury, Fear & Greed, TWSE.
        Also ingests financial news RSS into the retrieval corpus for the
        Market Intelligence page (dynamic cards).
        """
        sources = []
        data = self.sample_data()

        # 0) Financial news RSS → retrieval corpus (for Market Intelligence page)
        try:
            from core.data.fetchers import fetch_rss_items
            store = CorpusStore(CORPUS_PATH)
            import concurrent.futures as _cf
            with _cf.ThreadPoolExecutor(max_workers=4) as pool:
                feeds = list(pool.map(
                    lambda url: (url, fetch_rss_items(url, limit=4)),
                    FINANCIAL_FEEDS
                ))
            for url, items in feeds:
                if items:
                    ingest_items(store, items, source=url)
            store.compact(keep_days=30)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("financial RSS ingest failed: %s", exc)

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

        # 4) TWSE market-wide margin / short balances (keyless, MI_MARGN sum)
        twse = fetch_twse_margin(self.date_str)
        if twse and twse.get("total_margin_balance"):
            data["tw_margin_balance"] = twse["total_margin_balance"]
            if twse.get("total_short_balance"):
                data["tw_short_balance"] = twse["total_short_balance"]
            sources.append("TWSE")

        # 5) Slow macro series behind a TTL cache (BLS monthly / Treasury daily);
        #    the cache file is committed back by CI so it persists across runs.
        from core.data.macro_cache import cached
        from core.data.fetchers import (fetch_treasury_curve, fetch_treasury_10y_series,
                                        fetch_bls_history, _BLS_SERIES)
        macro = {}
        curve = cached("yield_curve", 1, fetch_treasury_curve)
        if curve:
            macro["yield_curve"] = curve
        us10 = cached("us10y_hist", 1, fetch_treasury_10y_series)
        if us10:
            macro["us10y_hist"] = us10
        cpi = cached("cpi_hist", 7,
                     lambda: fetch_bls_history(_BLS_SERIES["cpi_headline"], 25))
        if cpi:
            macro["cpi_hist"] = cpi
        core_cpi = cached("core_cpi_hist", 7,
                          lambda: fetch_bls_history(_BLS_SERIES["cpi_core"], 25))
        if core_cpi:
            macro["core_cpi_hist"] = core_cpi
        unemp = cached("unemployment", 7,
                       lambda: fetch_bls_history(_BLS_SERIES["unemployment"], 1))
        if unemp:
            macro["unemployment"] = unemp[0]
        nfp = cached("nfp", 7,
                     lambda: fetch_bls_history(_BLS_SERIES["nfp"], 1))
        if nfp:
            macro["nfp"] = nfp[0]
        nfp_hist = cached("nfp_hist", 7,
                          lambda: fetch_bls_history(_BLS_SERIES["nfp"], 25))
        if nfp_hist:
            macro["nfp_hist"] = nfp_hist
        if macro:
            data["macro"] = macro
            sources.append("Macro")

        if not sources:
            return None  # triggers full sample fallback in base class
        data["_source"] = "+".join(sources)
        return data

    def synthesize(self, data):
        from Financial_Intelligence.pdf_generator import calculate_signal_score, rating_from_score
        if "signal_score" not in data:
            data["signal_score"] = calculate_signal_score(data)
        data["signal_rating"] = rating_from_score(data["signal_score"])

        # Pull financial news for the Market Intelligence page
        # Phase 3 H2: also query geopolitics domain for cross-domain context
        # (e.g. Middle East tension → oil price impact)
        try:
            store = CorpusStore(CORPUS_PATH)
            # Macro domain: core financial news
            items = retrieve(store, query="market stocks bonds federal reserve "
                              "inflation earnings economy finance",
                              domain="macro", k=3, days=3)
            # Geopolitics domain: events that drive markets
            geo = retrieve(store, query="tariff war sanctions oil energy "
                             "trade conflict supply chain",
                             domain="geopolitics", k=2, days=3)
            if geo:
                items = (items or []) + geo
            if items:
                data["market_intel"] = items[:5]

            # (G) Cross-domain briefing: fuse this report's quantitative
            # signals with the shared corpus' week-over-week trends into one
            # analyst lead card (needs GEMINI_API_KEY; skipped otherwise).
            from core.retrieval.retrieve import domain_trends, trending_keywords
            from core.cross_domain import daily_briefing
            trends = {"domains": domain_trends(store),
                      "keywords": trending_keywords(store)}
            data["trends"] = trends
            briefing = daily_briefing(data, trends, headlines=(items or [])[:3])
            if briefing:
                data["cross_domain_briefing"] = briefing
                data["_source"] = (data.get("_source") or "") + "+Gemini"
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("market intel retrieval failed: %s", exc)

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
