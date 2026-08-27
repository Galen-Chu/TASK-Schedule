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


# Per-source authority multiplier — authoritative sources rank higher in
# retrieval scoring. Domain-based (matches the `source` field, which is the
# RSS feed URL). Overridable per call via `source_weights` parameter.
_AUTHORITY = {
    # Tier 1: International authoritative (news agencies, institutions)
    "feeds.bbci.co.uk": 1.5,
    "news.un.org": 1.5,
    "www.economist.com": 1.4,
    "www.reuters.com": 1.4,
    "search.cnbc.com": 1.3,
    "www.aljazeera.com": 1.2,
    # Tier 2: Domain-specialist publications
    "www.nasa.gov": 1.4,
    "spacenews.com": 1.3,
    "arstechnica.com": 1.2,
    "aviationweek.com": 1.2,
    "spectrum.ieee.org": 1.2,
    "www.sciencedaily.com": 1.1,
    "electrek.co": 1.0,
    # Tier 3: Tech blogs / regional (good but less authoritative)
    "techcrunch.com": 0.9,
    "technews.tw": 0.9,
    "www.ithome.com.tw": 0.9,
    # Low authority: community aggregators
    "www.reddit.com": 0.3,
}
DEFAULT_SOURCE_WEIGHTS = _AUTHORITY

# Minimum content quality: skip link-only / empty items.
# Keep thresholds low so legitimate short titles/summaries in tests pass.
_MIN_SUMMARY_LEN = 5   # just filter out empty/near-empty
_MIN_TITLE_LEN = 3     # just filter out empty/near-empty


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
        # Quality filter: skip items with BOTH empty summary AND empty title
        summary_len = len((it.get("summary") or "").strip())
        title_len = len((it.get("title") or "").strip())
        if summary_len < _MIN_SUMMARY_LEN and title_len < _MIN_TITLE_LEN:
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
        # Domain-based weight: match the source URL against _AUTHORITY domains
        src = it.get("source", "")
        w = 1.0
        for dom, weight in weights.items():
            if dom in src:
                w = weight
                break
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


# ---- Trend analysis (weekly comparison) --------------------------------------

def domain_trends(store, now=None):
    """Per-domain article counts: this week vs last week.

    Returns dict: {domain: {"this_week": int, "last_week": int,
                             "change_pct": float or None}}
    Sorted by absolute change (most active movement first).
    """
    now = now or datetime.now(_TZ)
    this_week, last_week = {}, {}
    for it in store.all():
        dom = it.get("domain_tag", "") or "(未分類)"
        age = _age_days(it, now)
        if age <= 7:
            this_week[dom] = this_week.get(dom, 0) + 1
        elif age <= 14:
            last_week[dom] = last_week.get(dom, 0) + 1

    all_doms = set(this_week) | set(last_week)
    out = {}
    for dom in all_doms:
        tw = this_week.get(dom, 0)
        lw = last_week.get(dom, 0)
        if lw > 0:
            pct = round((tw - lw) / lw * 100, 1)
        elif tw > 0:
            pct = None  # new this week (no baseline)
        else:
            pct = None
        out[dom] = {"this_week": tw, "last_week": lw, "change_pct": pct}
    return dict(sorted(out.items(), key=lambda x: abs(x[1]["change_pct"] or 0), reverse=True))


# English stop words to exclude from trending keywords
_STOP_WORDS = frozenset({
    "the", "and", "for", "from", "with", "that", "this", "have", "has",
    "will", "was", "are", "were", "been", "being", "into", "over", "after",
    "than", "then", "them", "they", "their", "there", "these", "those",
    "what", "when", "where", "which", "while", "who", "whom", "why",
    "how", "all", "any", "both", "each", "few", "more", "most", "other",
    "some", "such", "not", "only", "own", "same", "too", "very", "just",
    "also", "but", "can", "did", "does", "doing", "had", "having", "his",
    "her", "hers", "him", "his", "its", "may", "might", "must", "shall",
    "should", "would", "could", "about", "against", "between", "through",
    "during", "before", "after", "above", "below", "off", "down", "out",
    "up", "in", "on", "at", "by", "to", "of", "or", "as", "is", "it",
    "an", "be", "do", "if", "no", "so", "we", "he", "she", "you", "i",
    "a", "new", "says", "said", "amid", "after", "first", "two", "one",
})

def trending_keywords(store, now=None, top_k=8):
    """Keywords that surge this week vs last week.

    Extracts bigrams/unigrams from titles, counts frequency per week,
    returns items with the biggest positive change (only if this week > 2 hits).
    English stop words are excluded.
    """
    now = now or datetime.now(_TZ)
    this_kw, last_kw = {}, {}
    for it in store.all():
        age = _age_days(it, now)
        tokens = set(tokenize(it.get("title", "")))
        target = this_kw if age <= 7 else (last_kw if age <= 14 else None)
        if target is None:
            continue
        for t in tokens:
            if len(t) >= 3 and t not in _STOP_WORDS and not t.isdigit():
                target[t] = target.get(t, 0) + 1

    trending = []
    for kw, tw_count in this_kw.items():
        if tw_count < 3:
            continue
        lw_count = last_kw.get(kw, 0)
        change = tw_count - lw_count
        if change > 0:
            trending.append({"keyword": kw, "this_week": tw_count,
                             "last_week": lw_count, "change": change})
    trending.sort(key=lambda x: x["change"], reverse=True)
    return trending[:top_k]
