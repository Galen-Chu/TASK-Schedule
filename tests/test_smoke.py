"""Smoke tests: every report scheduler produces a multi-page PDF.

These build real PDFs into a temp output dir. They require the CJK font to
resolve (the CI workflow and Dockerfile install it). Page counts:
financial = 6 (macro dashboard merged as page 6), global/spiritual = 5, macro = 1.
"""
import os
import re
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import fonts  # noqa: F401  (ensures import path works)

EXPECTED_PAGES = {
    "financial": 7,
    "global": 6,
    "spiritual": 5,
    "macro": 1,
}
REPORT_MODULES = {
    "financial": ("Financial_Intelligence.cloud_daily_financial_report_scheduler", "FinancialReportScheduler"),
    "global": ("Global_Intelligence.cloud_daily_global_report_scheduler", "GlobalReportScheduler"),
    "spiritual": ("Spiritual_Intelligence.cloud_daily_spiritual_report_scheduler", "SpiritualReportScheduler"),
    "macro": ("Financial_Intelligence.monthly_macro_scheduler", "MonthlyMacroScheduler"),
}


def _page_count(pdf_path):
    raw = open(pdf_path, "rb").read()
    return len(re.findall(rb"/Type\s*/Page[^s]", raw))


@pytest.fixture(scope="module")
def tmp_output():
    d = tempfile.mkdtemp(prefix="spark_test_")
    yield d


@pytest.mark.parametrize("report_id", list(REPORT_MODULES))
def test_report_produces_pdf(report_id, tmp_output):
    # Skip cleanly if the CJK font isn't available in this environment.
    try:
        fonts.ensure_fonts()
    except RuntimeError as exc:
        pytest.skip(f"no CJK font available: {exc}")

    import importlib
    mod_name, cls_name = REPORT_MODULES[report_id]
    cls = getattr(importlib.import_module(mod_name), cls_name)
    scheduler = cls(output_dir=tmp_output, date_str="2026-08-12")
    pdf = scheduler.run()
    assert os.path.isfile(pdf), f"{report_id} did not produce a PDF"
    assert os.path.getsize(pdf) > 1000, f"{report_id} PDF is suspiciously small"
    pages = _page_count(pdf)
    assert pages == EXPECTED_PAGES[report_id], (
        f"{report_id} expected {EXPECTED_PAGES[report_id]} pages, got {pages}")
