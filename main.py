#!/usr/bin/env python3
"""Spark Schedule — unified entry point.

Run one or all daily reports:

    python main.py                       # all reports, today
    python main.py financial             # just Financial
    python main.py spiritual global      # a subset
    python main.py all --date 2026-08-11 --output-dir ./out
    python main.py --list                # show reports + schedules
    python main.py --fonts               # show resolved fonts
    python main.py --stats               # show retrieval corpus health

Optional overrides come from ``config/spark.yaml`` (see
``config/spark.yaml.example``). No config file is required — every report has
sensible defaults and produces output offline (sample data).
"""
import argparse
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from Financial_Intelligence.cloud_daily_financial_report_scheduler import FinancialReportScheduler
from Financial_Intelligence.monthly_macro_scheduler import MonthlyMacroScheduler
from Global_Intelligence.cloud_daily_global_report_scheduler import GlobalReportScheduler
from Spiritual_Intelligence.cloud_daily_spiritual_report_scheduler import SpiritualReportScheduler

REPORTS = {
    "financial": FinancialReportScheduler,
    "global": GlobalReportScheduler,
    "spiritual": SpiritualReportScheduler,
    "macro": MonthlyMacroScheduler,           # monthly cadence, Financial-only
}


def load_config():
    """Load config/spark.yaml if present; returns a dict (possibly empty)."""
    path = os.path.join(_REPO_ROOT, "config", "spark.yaml")
    if not os.path.isfile(path):
        return {}
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] 無法載入 config/spark.yaml ({exc})；使用預設值。", file=sys.stderr)
        return {}


def _section_cfg(cfg, report_id):
    """Merge top-level config with the per-report section."""
    section = cfg.get(report_id, {}) or {}
    merged = dict(cfg)
    merged.update(section)
    # drop other report sections to avoid confusion
    for key in REPORTS:
        if key != report_id:
            merged.pop(key, None)
    return merged


def cmd_list():
    print(f"{'report':12s} {'cron (Asia/Taipei)':22s} title")
    print("-" * 70)
    for rid, cls in REPORTS.items():
        print(f"{rid:12s} {cls.default_cron:22s} {cls.report_title}")


def cmd_fonts():
    from core.fonts import fonts_status
    import json
    print(json.dumps(fonts_status(), ensure_ascii=False, indent=2))


def cmd_stats():
    """Display retrieval corpus health: per-feed activity + domain distribution."""
    import json
    from urllib.parse import urlparse as _up
    from collections import Counter
    from datetime import datetime, timedelta, timezone

    _TZ = timezone(timedelta(hours=8))
    _now = datetime.now(_TZ)
    _path = os.path.join(_REPO_ROOT, "data", "retrieval", "global_corpus.jsonl")
    items, bad_lines = [], 0
    if os.path.isfile(_path):
        with open(_path, encoding="utf-8") as f:
            for line in f:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    bad_lines += 1

    if not items:
        print("Corpus is empty (run `python main.py all` to ingest items)")
        return

    skipped = f" (+{bad_lines} unparseable lines)" if bad_lines else ""
    print(f"Corpus: {len(items)} items{skipped}")
    print()

    # Domain distribution
    dom = Counter(it.get("domain_tag", "") or "(unclassified)" for it in items)
    print("Domain distribution:")
    for d, n in dom.most_common():
        pct = n / len(items) * 100
        print(f"  {d:20s} {n:5d} ({pct:.0f}%)")

    unclass = dom.get("(unclassified)", 0)
    if unclass:
        print()
        print(f"Recent unclassified titles ({unclass} total — keyword candidates for ingest.py):")
        recent = sorted(items, key=lambda it: it.get("fetched_at", ""), reverse=True)
        for it in [it for it in recent if not (it.get("domain_tag") or "")][:5]:
            src = _up(it.get("source", "")).netloc.replace("www.", "")
            print(f"  · {it.get('title', '')[:70]}  [{src}]")

    print()

    # Per-feed stats
    feed_items = {}
    for it in items:
        src = _up(it.get("source", "")).netloc.replace("www.", "")
        if src not in feed_items:
            feed_items[src] = {"count": 0, "last": None}
        feed_items[src]["count"] += 1
        fa = it.get("fetched_at", "")
        if fa and (feed_items[src]["last"] is None or fa > feed_items[src]["last"]):
            feed_items[src]["last"] = fa

    print("Feed health (by domain):")
    for src, info in sorted(feed_items.items(), key=lambda x: -x[1]["count"]):
        days = "?"
        if info["last"]:
            try:
                dt = datetime.fromisoformat(info["last"])
                days = f"{(_now - dt).days}d ago"
            except ValueError:
                days = "?"
        status = "✅" if info["count"] >= 5 else ("⚠️" if info["count"] >= 2 else "❌")
        print(f"  {status} {src:40s} {info['count']:5d} items, last {days}")

    print()
    print("Tips:")
    print("  ❌ = feed has <2 items (may be dead)")
    print("  ⚠️ = feed has 2-4 items (sporadic)")
    print("  ✅ = healthy (5+ items)")
    print("  Run `python main.py all` to ingest fresh items.")


def cmd_reclassify():
    """Re-tag stored corpus items with the current keyword set."""
    from core.retrieval.store import CorpusStore
    from core.retrieval.ingest import DOMAIN_KEYWORDS

    store = CorpusStore(os.path.join(_REPO_ROOT, "data", "retrieval", "global_corpus.jsonl"))
    before = sum(1 for it in store.all() if it.get("domain_tag"))
    changed = store.reclassify()
    after = sum(1 for it in store.all() if it.get("domain_tag"))
    total = len(store.all())
    print(f"Re-tagged {changed} items; classified {before} → {after} of {total} "
          f"({(total - after) / total * 100:.0f}% unclassified)")
    print("Keywords live in core/retrieval/ingest.py —"
          f" {sum(len(k) for k in DOMAIN_KEYWORDS.values())} terms across "
          f"{len(DOMAIN_KEYWORDS)} domains.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Spark Schedule — 每日排程報告統一入口")
    parser.add_argument("reports", nargs="*", default=["all"],
                        help="要執行的報告：financial / global / spiritual / all（預設 all）")
    parser.add_argument("--date", help="報告日期 YYYY-MM-DD（預設今天）")
    parser.add_argument("--output-dir", help="輸出目錄（預設 ./output）")
    parser.add_argument("--list", action="store_true", help="列出報告與排程時間後退出")
    parser.add_argument("--fonts", action="store_true", help="顯示字型解析狀態後退出")
    parser.add_argument("--stats", action="store_true", help="顯示檢索語料庫健康度統計")
    parser.add_argument("--reclassify", action="store_true",
                        help="以目前關鍵字重新分類語料庫既有項目後退出")
    args = parser.parse_args(argv)

    if args.list:
        cmd_list(); return 0
    if args.fonts:
        cmd_fonts(); return 0
    if args.stats:
        cmd_stats(); return 0
    if args.reclassify:
        cmd_reclassify(); return 0

    # "all" = the three daily reports only. "macro" is a separate monthly
    # cadence — run it explicitly or via the monthly workflow job.
    DAILY = ["financial", "global", "spiritual"]
    chosen = DAILY if (not args.reports or "all" in args.reports) else args.reports
    unknown = [r for r in chosen if r not in REPORTS]
    if unknown:
        parser.error(f"未知的報告：{unknown}。可選：{list(REPORTS)}")

    cfg = load_config()
    output_dir = args.output_dir or cfg.get("output_dir")
    results = {}
    failed = []
    for rid in chosen:
        cls = REPORTS[rid]
        try:
            scheduler = cls(config=_section_cfg(cfg, rid), output_dir=output_dir, date_str=args.date)
            pdf = scheduler.run()
            results[rid] = pdf
        except Exception as exc:  # noqa: BLE001 — one report failing shouldn't kill the rest
            failed.append((rid, exc))
            print(f"[error] {rid} 失敗：{exc}", file=sys.stderr)

    print("\n========== summary ==========")
    for rid, pdf in results.items():
        print(f"  [OK]   {rid:10s} -> {pdf}")
    for rid, exc in failed:
        print(f"  [FAIL] {rid:10s} {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
