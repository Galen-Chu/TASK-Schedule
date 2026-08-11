"""Spark Schedule — shared core for all daily reports.

Modules:
  design_tokens  master palette, typography scale, A4 grid (single source of truth)
  fonts          portable TrueType font discovery + registration
  pdf_engine     shared ReportLab helpers (dual-font en(), styles, header, footer)
  scheduler_base BaseReportScheduler — stage-based orchestrator with fallback
  obsidian_writer generic markdown note writer
  data.fetchers  best-effort keyless data fetchers (TWSE, RSS)
  dispatch.*     Google Drive / Gmail stubs with clean interfaces
"""
__version__ = "2.0.0"
