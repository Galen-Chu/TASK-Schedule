"""Unified retrieval layer (core/retrieval/).

A shared, report-agnostic ingest → dedup → rank → retrieve pipeline. The
Global report is the first consumer; the layer is designed so Financial /
Spiritual can consume it later (the "統一檢索層" from the project roadmap).

Phase 1: keyword/BM25 retrieval over a JSONL corpus committed to the repo so
it accumulates across ephemeral CI runs. The ``CorpusStore`` method interface
(add / all / compact) is the contract — a Phase 2 remote backend (GCP) can
replace the JSONL persistence without changing callers.
"""
from core.retrieval.store import CorpusStore, item_id
from core.retrieval.ingest import ingest_items, normalize, classify_domain
from core.retrieval.retrieve import retrieve, tokenize

__all__ = [
    "CorpusStore", "item_id",
    "ingest_items", "normalize", "classify_domain",
    "retrieve", "tokenize",
]
