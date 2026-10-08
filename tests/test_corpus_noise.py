"""Dividend-declaration noise filter + backlog prune + finance feed swap.

2026-10-08 audit: Seeking Alpha market_currents boilerplate ("Kish Bancorp
declares $0.44 dividend") dominated the unclassified bucket (22% of corpus)
and diluted market_intel selection; finance.yahoo.com/news/rss.xml had been
silently 404 for 13 days. These pin the fixes.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.retrieval.ingest import ingest_items, is_noise
from core.retrieval.store import CorpusStore


def test_is_noise_targets_declarations_only():
    assert is_noise("Kish Bancorp declares $0.44 dividend")
    assert is_noise("XAI Madison Equity Premium Income Fund declares $0.06 dividend")
    assert is_noise("Foo Corp declares 0.85 distribution")
    # Real dividend-policy news must survive (no "declares $N" phrasing)
    assert not is_noise("Fed signals slower rate cuts as dividend yields climb")
    assert not is_noise("台積電法說會：AI 需求強勁，資本支出上修")
    assert not is_noise("")


class _MemStore:
    def __init__(self):
        self.rows = []

    def add(self, rows):
        self.rows.extend(rows)
        return len(rows)


def test_ingest_items_drops_declaration_noise():
    store = _MemStore()
    items = [
        {"title": "Kish Bancorp declares $0.44 dividend", "link": "a"},
        {"title": "Elmer Bancorp declares $0.20 dividend", "link": "b"},
        {"title": "Fed signals slower rate cuts", "link": "c"},
    ]
    n = ingest_items(store, items, source="test")
    assert n == 1
    assert store.rows[0]["title"].startswith("Fed")


def test_prune_noise_cleans_backlog(tmp_path):
    p = tmp_path / "corpus.jsonl"
    rows = [
        {"title": "Kish Bancorp declares $0.44 dividend"},
        {"title": "Elmer Bancorp declares $0.20 dividend"},
        {"title": "real news stays"},
    ]
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    store = CorpusStore(str(p))
    assert store.prune_noise() == 2
    assert [it["title"] for it in store.all()] == ["real news stays"]


def test_financial_feeds_dead_yahoo_swapped_for_nyt():
    from Financial_Intelligence.cloud_daily_financial_report_scheduler import (
        FINANCIAL_FEEDS,
    )
    assert not any("finance.yahoo.com" in u for u in FINANCIAL_FEEDS)
    assert any("nytimes.com" in u for u in FINANCIAL_FEEDS)
