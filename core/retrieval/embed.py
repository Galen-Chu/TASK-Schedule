"""Embedding layer for the unified retrieval (Phase 2, semantic retrieval).

Uses the Gemini embedding API with the SAME key/SDK as the LLM layer:
- small output dimensionality (256) and BATCHED calls — a whole day's new
  items embed in ~1 request, so the shared daily call budget stays tiny;
- vectors live inline in the corpus JSONL (``emb`` field);
- ``backfill()`` runs each pipeline pass: attaches vectors to any stored
  records missing one and SEMANTICALLY CLASSIFIES untagged items against
  bilingual domain anchors (fixes the ~30% "unclassified" tail);
- everything degrades gracefully: no key / SDK / API failure / budget spent
  -> functions return None and retrieval falls back to keyword BM25. Set
  EMBED_ENABLED=0 to disable outright.
"""
import logging
import math
import os

log = logging.getLogger("retrieval.embed")

_DIM = 256
_MODELS = ["text-embedding-004", "gemini-embedding-001"]
_ENABLED = os.environ.get("EMBED_ENABLED", "1") != "0"
_model = None            # resolved on first successful call
_query_cache = {}        # query text -> vector (per process)

# Bilingual domain anchors — semantic classification targets for items the
# keyword classifier can't place (mostly English headlines).
_DOMAIN_ANCHORS = {
    "geopolitics": "地緣政治 國際關係 戰爭 外交 制裁 選舉 election war diplomacy sanctions geopolitics conflict",
    "macro": "總體經濟 金融市場 通膨 利率 央行 經濟成長 股市 inflation interest rates central bank economy markets GDP",
    "it_ai": "資訊科技 人工智慧 半導體 晶片 軟體 雲端 AI semiconductor chips software cloud computing GPU",
    "biotech": "生物科技 醫療健康 藥物 疫苗 基因 臨床 biotech health medicine drug clinical trial vaccine",
    "hardware": "硬體工程 能源 電池 電動車 電網 製造 hardware energy battery electric vehicle manufacturing grid",
}


def is_available():
    """True when embeddings can be attempted (key present + not disabled)."""
    if not _ENABLED:
        return False
    from core import llm
    return bool(llm._AVAILABLE)


def cosine(a, b):
    try:
        num = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        return num / (na * nb) if na and nb else 0.0
    except (TypeError, ValueError):
        return 0.0


def embed_texts(texts, task_type="RETRIEVAL_DOCUMENT"):
    """Embed a batch of texts in ONE API call. Returns list of vectors or None.

    Counts one call against the shared daily Gemini budget (llm._allow_call);
    on budget exhaustion returns None so callers degrade gracefully.
    """
    if not texts or not is_available():
        return None
    from core import llm
    if not llm._allow_call(tick=True):
        log.info("embedding skipped: daily budget reached")
        return None
    from google.genai import types as _gtypes
    global _model
    models = [_model] if _model else list(_MODELS)
    for model in models:
        try:
            resp = llm._CLIENT.models.embed_content(
                model=model, contents=list(texts),
                config=_gtypes.EmbedContentConfig(
                    output_dimensionality=_DIM, task_type=task_type))
            vectors = [list(e.values) for e in resp.embeddings]
            if _model != model:
                _model = model
                log.info("embedding model: %s (%dd, %d texts)", model, _DIM, len(vectors))
            return vectors
        except Exception as exc:  # noqa: BLE001 — try next candidate model
            log.info("embed model %s failed (%s); trying next", model, exc)
            continue
    return None


def embed_query(text):
    """Cached single-text embedding for retrieval queries."""
    if text in _query_cache:
        return _query_cache[text]
    vecs = embed_texts([text], task_type="RETRIEVAL_QUERY")
    if not vecs:
        return None
    _query_cache[text] = vecs[0]
    return vecs[0]


def _anchor_vectors():
    """Batch-embed the five domain anchors (one call, cached per process)."""
    if not hasattr(_anchor_vectors, "_cache"):
        keys = list(_DOMAIN_ANCHORS)
        vecs = embed_texts([_DOMAIN_ANCHORS[k] for k in keys])
        _anchor_vectors._cache = (dict(zip(keys, vecs)) if vecs else {})
    return _anchor_vectors._cache


def _nearest(vec, anchors):
    best, best_s = None, -1.0
    for tag, avec in anchors.items():
        s = cosine(vec, avec)
        if s > best_s:
            best, best_s = tag, s
    return best, best_s


def backfill(store):
    """Attach vectors to records missing one; semantic-classify untagged items.

    Must never raise into the pipeline — all failures are logged and skipped.
    """
    try:
        if not is_available():
            return
        recs = store.all()
        todo = [r for r in recs if not r.get("emb")]
        if todo:
            texts = [((r.get("title", "") or "") + " " +
                      (r.get("summary", "") or "")[:300])[:2000] for r in todo]
            vecs = embed_texts(texts)
            if vecs:
                for r, v in zip(todo, vecs):
                    r["emb"] = [round(x, 4) for x in v]
                log.info("embeddings: attached %d/%d missing", len(vecs), len(todo))
        anchors = _anchor_vectors()
        if anchors:
            tagged = 0
            for r in recs:
                if not r.get("domain_tag") and r.get("emb"):
                    tag, score = _nearest(r["emb"], anchors)
                    if tag and score >= 0.32:
                        r["domain_tag"] = tag
                        tagged += 1
            if tagged:
                log.info("embeddings: semantic-classified %d untagged items", tagged)
        if todo or (anchors and recs):
            store.save_all(recs)
    except Exception as exc:  # noqa: BLE001 — pipeline must never break here
        log.warning("embedding backfill failed (%s); BM25 only this run.", exc)
