"""Tests for the unified retrieval layer (core.retrieval).

All tests use a temp JSONL store — no network, no Gemini key.
"""
from datetime import datetime, timedelta, timezone

from core.retrieval import (
    CorpusStore, classify_domain, ingest_items, item_id, retrieve, tokenize,
)

_TZ = timezone(timedelta(hours=8))


def _iso(days_ago):
    return (datetime.now(_TZ) - timedelta(days=days_ago)).isoformat(timespec="seconds")


# ---- tokenize --------------------------------------------------------------
def test_tokenize_mixes_ascii_and_cjk_bigrams():
    toks = tokenize("Taiwan 半導體 surge")
    assert "taiwan" in toks and "surge" in toks
    assert "半導" in toks            # CJK bigram


# ---- classify --------------------------------------------------------------
def test_classify_domain_hits():
    assert classify_domain("台積電擴大 2nm 與 CoWoS 封裝", "") == "it_ai"
    assert classify_domain("ECB 殖利率與通膨路徑", "") == "macro"
    assert classify_domain("FDA 核准新藥臨床試驗", "") == "biotech"


def test_classify_domain_empty_when_no_keyword():
    assert classify_domain("一則與任何領域無關的天氣短訊", "") == ""


def test_classify_domain_english_titles():
    """The expanded source list is mostly English — keywords must classify
    English headlines, and short ASCII keywords must respect word boundaries
    ('ai' must NOT match inside 'said')."""
    assert classify_domain("U.S. government debt passes $40 trillion", "") == "macro"
    assert classify_domain("Nvidia unveils new AI chip for data centers", "") == "it_ai"
    assert classify_domain("Coffee drinkers have less fat, study finds", "") == "biotech"
    assert classify_domain("Solid-state battery breakthrough for EV makers", "") == "hardware"
    assert classify_domain("Ceasefire talks collapse as border conflict widens", "") == "geopolitics"


def test_classify_domain_word_boundary_no_false_positive():
    # 'ai' inside 'said'/'maintain' must not classify as it_ai
    assert classify_domain("He said the weather was nice and calm", "") == ""


# ---- item_id ---------------------------------------------------------------
def test_item_id_stable_and_case_insensitive_title():
    assert item_id("A", "b") == item_id("a", "b")
    assert item_id("a", "b") != item_id("a", "c")


# ---- store dedup -----------------------------------------------------------
def test_store_exact_dedup(tmp_path):
    store = CorpusStore(str(tmp_path / "c.jsonl"))
    items = [{"title": "台積電Capex", "link": "http://x/1", "summary": "s"}]
    assert store.add(items) == 1
    assert store.add(items) == 0           # same id → skipped
    assert len(store.all()) == 1


def test_store_near_dup_title(tmp_path):
    store = CorpusStore(str(tmp_path / "c.jsonl"))
    store.add([{"title": "台積電擴大資本支出", "link": "http://x/1", "summary": ""}])
    n = store.add([{"title": "台積電擴大資本支出再加速", "link": "http://x/2", "summary": ""}])
    assert n == 0                          # near-duplicate title → skipped


# ---- ingest ----------------------------------------------------------------
def test_ingest_classifies_and_tags_source(tmp_path):
    store = CorpusStore(str(tmp_path / "c.jsonl"))
    n = ingest_items(store, [{"title": "Fed 降息與通膨", "link": "http://x", "summary": ""}],
                     source="bbc")
    assert n == 1
    rec = store.all()[0]
    assert rec["domain_tag"] == "macro"
    assert rec["source"] == "bbc"


# ---- retrieve --------------------------------------------------------------
def test_retrieve_domain_filtered_and_keyword_ranked(tmp_path):
    store = CorpusStore(str(tmp_path / "c.jsonl"))
    ingest_items(store, [
        {"title": "台積電 CoWoS 封裝產能滿載", "link": "1", "summary": "半導體 AI 算力"},
        {"title": "Fed 利率決策與通膨路徑", "link": "2", "summary": "殖利率 macro"},
    ])
    it = retrieve(store, query="半導體 晶片", domain="it_ai", k=3)
    assert len(it) == 1 and "台積電" in it[0]["title"]
    mac = retrieve(store, query="利率 通膨", domain="macro", k=3)
    assert len(mac) == 1 and "Fed" in mac[0]["title"]


def test_retrieve_keyword_only_requires_match(tmp_path):
    store = CorpusStore(str(tmp_path / "c.jsonl"))
    ingest_items(store, [{"title": "台積電 AI 封裝", "link": "1", "summary": "半導體"}])
    hit = retrieve(store, query="台積電", k=3)            # no domain → BM25 must match
    assert hit and "台積電" in hit[0]["title"]
    miss = retrieve(store, query="zzz unrelated", k=3)   # no overlap → []
    assert miss == []


def test_retrieve_recency_window(tmp_path):
    store = CorpusStore(str(tmp_path / "c.jsonl"))
    store.add([{"title": "台積電舊聞", "link": "1", "summary": "半導體",
                "domain_tag": "it_ai", "fetched_at": _iso(20)}])
    assert retrieve(store, query="台積電", domain="it_ai", days=7) == []


# ---- compact ---------------------------------------------------------------
def test_compact_drops_old(tmp_path):
    store = CorpusStore(str(tmp_path / "c.jsonl"))
    store.add([{"title": "台積電新聞", "link": "1", "summary": "半導體",
                "domain_tag": "it_ai", "fetched_at": _iso(40)}])
    assert len(store.all()) == 1
    assert store.compact(keep_days=30) == 1
    assert len(store.all()) == 0
