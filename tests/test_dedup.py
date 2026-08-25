"""Cross-source dedup tests: similar stories from different feeds → keep highest authority."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.retrieval.store import CorpusStore


def _seed(path, records):
    """Write records directly to the corpus file (bypasses ingestion dedup)."""
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return CorpusStore(str(path))


def _item(id, title, link, source, domain="geopolitics", summary="A news summary of the story"):
    return {"id": id, "title": title, "link": link, "summary": summary,
            "source": source, "domain_tag": domain, "fetched_at": "2026-08-25T10:00:00+08:00"}


class TestDedupCrossSource:
    def test_same_story_different_sources_keeps_bbc(self, tmp_path):
        """BBC and Reddit both report the same story with slightly different headlines."""
        p = tmp_path / "c.jsonl"
        store = _seed(p, [
            _item("a1", "Trump announces sweeping new tariff policy on Chinese goods",
                  "https://bbc.co.uk/x", "https://feeds.bbci.co.uk/news/world/rss.xml"),
            _item("a2", "Trump announces new tariff policy on Chinese goods",
                  "https://reddit.com/y", "https://www.reddit.com/r/worldnews"),
        ])
        removed = store.dedup_cross_source()
        assert removed == 1
        remaining = store.all()
        assert len(remaining) == 1
        assert "bbc" in remaining[0]["source"]

    def test_different_stories_not_deduped(self, tmp_path):
        """Completely different headlines → both survive."""
        p = tmp_path / "c.jsonl"
        store = _seed(p, [
            _item("b1", "Fed cuts interest rates by 50 basis points",
                  "https://bbc.co.uk/a", "https://feeds.bbci.co.uk/news/world/rss.xml", domain="macro"),
            _item("b2", "Nvidia stock surges on earnings beat",
                  "https://cnbc.com/b", "https://search.cnbc.com/x", domain="it_ai"),
        ])
        removed = store.dedup_cross_source()
        assert removed == 0
        assert len(store.all()) == 2

    def test_cross_domain_not_deduped(self, tmp_path):
        """Same headline but different domain tags → both survive."""
        p = tmp_path / "c.jsonl"
        store = _seed(p, [
            _item("c1", "AI chip manufacturing breakthrough announced",
                  "https://a.com/1", "https://techcrunch.com/feed/", domain="it_ai"),
            _item("c2", "AI chip manufacturing breakthrough announced",
                  "https://b.com/2", "https://electrek.co/feed/", domain="hardware"),
        ])
        removed = store.dedup_cross_source()
        assert removed == 0

    def test_higher_authority_replaces_lower(self, tmp_path):
        """When a higher-authority source's version exists, lower one is removed."""
        p = tmp_path / "c.jsonl"
        store = _seed(p, [
            _item("d1", "Major trade deal signed by US and European Union",
                  "https://reddit.com/r", "https://www.reddit.com/r/worldnews"),
            _item("d2", "Major trade agreement signed by US and European Union",
                  "https://bbc.co.uk/b", "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ])
        removed = store.dedup_cross_source()
        assert removed == 1
        remaining = store.all()
        assert "bbc" in remaining[0]["source"]

    def test_no_duplicates_no_change(self, tmp_path):
        """All unique items → dedup is a no-op."""
        p = tmp_path / "c.jsonl"
        store = _seed(p, [
            _item("e1", " unique headline about topic one ", "https://a.com/1", "https://a.com/feed"),
            _item("e2", "completely different story about sports", "https://b.com/2", "https://b.com/feed"),
            _item("e3", "another unrelated technology news item", "https://c.com/3", "https://c.com/feed"),
        ])
        removed = store.dedup_cross_source()
        assert removed == 0
        assert len(store.all()) == 3
