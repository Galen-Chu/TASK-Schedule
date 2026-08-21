"""Tests for the Phase-2 semantic layer (core.retrieval.embed).

All embedding API calls are faked with deterministic vectors — these verify
the math and the graceful degradation, no network or key needed.
"""
import math

from core.retrieval import embed
from core.retrieval.store import CorpusStore


def _unit(theta):
    """Deterministic unit vector at angle theta in the first two dims."""
    return [math.cos(theta), math.sin(theta)] + [0.0] * 254


def test_cosine_math():
    assert abs(embed.cosine(_unit(0), _unit(0)) - 1.0) < 1e-9
    assert abs(embed.cosine(_unit(0), _unit(math.pi / 2))) < 1e-9
    assert embed.cosine(_unit(0), [0] * 256) == 0.0


def test_backfill_attaches_and_classifies(tmp_path, monkeypatch):
    store = CorpusStore(str(tmp_path / "c.jsonl"))
    store.add([
        {"title": "Funding bill passes parliament", "link": "1", "summary": "",
         "domain_tag": "", "source": "x"},                       # untagged
        {"title": "已有分類不應被覆寫", "link": "2", "summary": "通膨 利率",
         "domain_tag": "macro", "source": "x"},                   # already tagged
    ])
    monkeypatch.setattr(embed, "is_available", lambda: True)
    # fake embeddings: item1 -> near the geopolitics anchor, item2 -> orthogonal
    anchors = {"geopolitics": _unit(0), "macro": _unit(1.0), "it_ai": _unit(2.0),
               "biotech": _unit(3.0), "hardware": _unit(4.0)}

    def fake_embed(texts, task_type="RETRIEVAL_DOCUMENT"):
        return [_unit(0.1) if "Funding" in t else _unit(1.5) for t in texts]

    monkeypatch.setattr(embed, "embed_texts", fake_embed)
    monkeypatch.setattr(embed, "_anchor_vectors", lambda: anchors)
    embed.backfill(store)
    recs = {r["link"]: r for r in store.all()}
    assert recs["1"]["emb"], "vector attached"
    assert recs["1"]["domain_tag"] == "geopolitics", "semantic classify via anchor"
    assert recs["2"]["domain_tag"] == "macro", "existing tag untouched"


def test_backfill_disabled_is_noop(tmp_path, monkeypatch):
    store = CorpusStore(str(tmp_path / "c.jsonl"))
    store.add([{"title": "x", "link": "1", "summary": "", "source": "s"}])
    monkeypatch.setattr(embed, "is_available", lambda: False)
    embed.backfill(store)
    assert not store.all()[0].get("emb")


def test_hybrid_retrieve_semantic_beats_lexical(tmp_path, monkeypatch):
    """A CJK query with zero token overlap must still surface the English item
    whose (fake) vector aligns — the whole point of semantic retrieval."""
    store = CorpusStore(str(tmp_path / "c.jsonl"))
    store.add([
        {"title": "TSMC 2nm capacity expansion", "link": "sem", "summary": "",
         "domain_tag": "it_ai", "source": "s",
         "emb": [round(x, 4) for x in _unit(0)]},
        {"title": "unrelated cooking recipe", "link": "lex", "summary": "",
         "domain_tag": "it_ai", "source": "s",
         "emb": [round(x, 4) for x in _unit(2.5)]},
    ])
    monkeypatch.setattr(embed, "is_available", lambda: True)
    monkeypatch.setattr(embed, "embed_query", lambda q: _unit(0.05))
    from core.retrieval.retrieve import retrieve as retrieve_fn
    out = retrieve_fn(store, query="半導體 晶圓 擴產", domain="it_ai", k=2)
    assert out and out[0]["link"] == "sem"


def test_budget_exhaustion_returns_none(monkeypatch):
    from core import llm
    monkeypatch.setattr(embed, "is_available", lambda: True)
    monkeypatch.setattr(llm, "_allow_call", lambda tick=False: False)
    assert embed.embed_texts(["hello"]) is None
