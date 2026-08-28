"""Base orchestrator for every daily report.

The pipeline is split into overridable stages so each report only implements
the bits that are unique to it (sample data, PDF render, Obsidian render).
Real-time fetching is optional: if :meth:`fetch_data` is not implemented or
fails, the scheduler falls back to :meth:`sample_data` so a report is ALWAYS
produced — this is what lets the pipeline run end-to-end in CI without API
keys or network access.
"""
import os
import sys
import logging
import datetime

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


try:
    from zoneinfo import ZoneInfo
    _TAIPEI = ZoneInfo("Asia/Taipei")
except Exception:  # noqa: BLE001 — Py<3.9 or missing TZDB -> fixed +08:00
    _TAIPEI = datetime.timezone(datetime.timedelta(hours=8))


def today_str():
    """Today's date in Asia/Taipei (the report audience's timezone).

    The CI runner clock is UTC, so without rebasing, a 22:18 UTC schedule
    (= 06:18 next-day Taipei) would be stamped with the prior calendar day.
    """
    return datetime.datetime.now(_TAIPEI).date().strftime("%Y-%m-%d")


def default_output_dir():
    return os.environ.get("SPARK_OUTPUT_DIR", os.path.join(_REPO_ROOT, "output"))


class BaseReportScheduler:
    """Subclass and override :meth:`sample_data`, :meth:`render_pdf` and
    optionally :meth:`fetch_data` / :meth:`render_obsidian` / :meth:`dispatch`.
    """

    report_id = "base"
    report_title = "Base Report"
    default_cron = "0 6 * * *"        # override per report
    page_count = 5

    def __init__(self, config=None, output_dir=None, date_str=None):
        self.config = config or {}
        self.date_str = date_str or today_str()
        self.output_dir = output_dir or default_output_dir()
        os.makedirs(self.output_dir, exist_ok=True)
        self.logger = logging.getLogger(f"scheduler.{self.report_id}")
        if not logging.getLogger().handlers:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            )

    # ---- stages (override these) ------------------------------------------
    def sample_data(self):
        """Return the bundled sample/offline dataset. Override me."""
        return {}

    def fetch_data(self):
        """Override to hit real (ideally keyless) APIs.

        Return the data dict on success, or ``None`` to fall back to sample.
        Raising is also fine — it is caught and falls back to sample.
        """
        return None

    def synthesize(self, data):
        """Optional scoring / LLM enrichment. Default: passthrough."""
        return data

    def render_pdf(self, data):
        """Build the PDF. Must return the output path. Override me."""
        raise NotImplementedError

    def render_obsidian(self, data):
        """Optional Obsidian markdown write-back. Return path or None."""
        return None

    def dispatch(self, pdf_path, data, note_path=None):
        """Optional Drive upload / Gmail dispatch. Default: no-op."""

    # ---- orchestration ----------------------------------------------------
    def run(self):
        self.logger.info("================ START %s ================", self.report_id)
        real = None
        try:
            real = self.fetch_data()
            if real is None:
                self.logger.warning("即時資料來源未提供，使用 sample data（離線/CI 模式）。")
        except Exception as exc:  # noqa: BLE001 — intentional broad fallback
            self.logger.warning("fetch_data 失敗 (%s)；改用 sample data。", exc)

        data = real if real is not None else self.sample_data()
        data = dict(data) if isinstance(data, dict) else {"value": data}
        data.setdefault("date", self.date_str)
        self.date_str = data["date"]

        data = self.synthesize(data)

        pdf_path = self.render_pdf(data)
        self.logger.info("PDF 產出：%s", pdf_path)

        note_path = None
        try:
            note_path = self.render_obsidian(data)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Obsidian 寫入失敗：%s", exc)

        try:
            self.dispatch(pdf_path, data, note_path)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("分派 (Drive/Gmail) 失敗：%s", exc)

        self.logger.info("================ %s DONE ================", self.report_id)
        return pdf_path
