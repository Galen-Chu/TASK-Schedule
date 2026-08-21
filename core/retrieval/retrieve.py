"""Retrieval over the corpus: tokenize, BM25, recency + source weighting.

Backend-agnostic: takes a ``CorpusStore`` (anything with ``.all()``) and a
query string. Phase 1 uses BM25 over title+summary tokens; a Phase 2 embedding
scorer can replace ``_bm25_scores`` without touching callers.
"""
import logging
import math
import re
from datetime import datetime, timedelta, timezone

_TZ = timezone(timedelta(hours=8))  # Asia/Taipei

_ASCII_RE = re.compile(r"[a-z0-9]+")
_CJK_RE = re.compile(r"[一-鿿]+")


def tokenize(text):
    """ASCII words (lowercased) + CJK bigrams. The shared unit for dedup and BM25."""
    text = (text or "").lower()
    tokens = _ASCII_RE.findall(text)
    for run in _CJK_RE.findall(text):
        for i in range(len(run) - 1):
            tokens.append(run[i:i + 2])
    return tokens


def _parse_dt(s):
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _age_days(it, now):
    fa = _parse_dt(it.get("fetched_at", ""))
    if fa is None:
        return 0
    if fa.tzinfo is None:
        fa = fa.replace(tzinfo=_TZ)
    return max(0, (now - fa).days)


def _bm25_scores(query_tokens, doc_token_lists, k1=1.5, b=0.75):
    """BM25 relevance of each doc vs the query tokens."""
    n = len(doc_token_lists)
    if n == 0:
        return []
    df = {}
    for dtoks in doc_token_lists:
        for t in set(dtoks):
            df[t] = df.get(t, 0) + 1
    avgdl = (sum(len(d) for d in doc_token_lists) / n) or 1
    scores = []
    for dtoks in doc_token_lists:
        dl = len(dtoks) or 1
        tf = {}
        for t in dtoks:
            tf[t] = tf.get(t, 0) + 1
        s = 0.0
        for t in query_tokens:
            if t not in tf:
                continue
            idf = math.log((n - df.get(t, 0) + 0.5) / (df.get(t, 0) + 0.5) + 1)
            f = tf[t]
            s += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avgdl))
        scores.append(s)
    return scores


# Per-source authority multiplier (Phase 1: uniform). Overridable per call.
DEFAULT_SOURCE_WEIGHTS = {}


def retrieve(store, query, k=4, days=7, domain=None, now=None,
             source_weights=None):
    """Return up to ``k`` items relevant to ``query`` from ``store``.

    ``domain``: if set, restrict to items tagged with that domain AND keep all
    of them ranked by relevance×recency (so a domain page always has content
    once the corpus has any domain item). If None, only keyword-matched items
    are returned (BM25 > 0).
    """
    now = now or datetime.now(_TZ)
    weights = source_weights or DEFAULT_SOURCE_WEIGHTS
    cands = []
    for it in store.all():
        if domain and it.get("domain_tag") != domain:
            continue
        if _age_days(it, now) > days:
            continue
        cands.append(it)
    if not cands:
        return []
    qtoks = tokenize(query)
    dtoks = [tokenize(it.get("title", "") + " " + it.get("summary", "")) for it in cands]
    bm = _bm25_scores(qtoks, dtoks)
    # Semantic layer (Phase 2): embed the query once; items carrying vectors
    # get a hybrid score (cosine 55% + BM25 45%). No key / no vectors on
    # either side -> pure BM25, exactly the Phase-1 behaviour.
    qvec = None
    try:
        from core.retrieval import embed as _embed
        if _embed.is_available():
            qvec = _embed.embed_query(query)
    except Exception:  # noqa: BLE001
        qvec = None
    bmax = max(bm) or 1.0
    scored = []
    n_sem = 0
    for it, raw in zip(cands, bm):
        recency = math.exp(-_age_days(it, now) / 7.0)
        w = weights.get(it.get("source", ""), 1.0)
        if qvec and it.get("emb"):
            n_sem += 1
            cos = _embed.cosine(qvec, it["emb"])
            s = (0.45 * (raw / bmax) + 0.55 * cos) * recency * w
        else:
            s = raw * recency * w
        scored.append((s, it))
    if qvec:
        logging.getLogger("retrieval").info(
            "retrieve: semantic hybrid (query+item vectors) for %d/%d candidates", n_sem, len(cands))
    scored.sort(key=lambda x: x[0], reverse=True)
    if domain:
        return [it for _, it in scored[:k]]
    matched = [it for s, it in scored if s > 0]
    return matched[:k]
