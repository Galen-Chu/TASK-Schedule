"""Normalize + domain-classify fetched items before they enter the store."""
import logging

log = logging.getLogger("retrieval.ingest")

# Domain → trigger keywords (Traditional Chinese + English). Used to tag each
# item so per-domain retrieval can filter without a query.
_DOMAIN_KEYWORDS = {
    "geopolitics": ["地緣", "外交", "軍事", "國防", "兩岸", "台海", "關稅", "制裁",
                    "北約", "印太", "戰", "geopolitics", "diplomacy", "tariff",
                    "sanction", "nato", "war"],
    "macro": ["通膨", "通脹", "利率", "央行", "降息", "殖利率", "就業", "非農",
              "景氣", "cpi", "pce", "gdp", "fed", "ecb", "macro", "inflation",
              "yield"],
    "it_ai": ["ai", "半導體", "晶片", "晶圓", "台積電", "tsmc", "nvidia", "伺服器",
              "算力", "gpu", "封裝", "cowos", "llm", "agent", "semiconductor", "chip"],
    "biotech": ["生技", "生醫", "醫藥", "新藥", "臨床", "疫苗", "基因", "adc",
                "fda", "biotech", "drug", "clinical", "pharma"],
    "hardware": ["硬體", "能源", "電池", "核能", "smr", "電動車", "儲能", "電網",
                 "機器人", "hardware", "energy", "battery", "robot", "solar", "grid"],
}

DOMAIN_KEYWORDS = _DOMAIN_KEYWORDS  # re-export for callers (e.g. queries)


def classify_domain(title, summary):
    """Return the best-matching domain tag, or "" if no keyword hits."""
    low = ((title or "") + " " + (summary or "")).lower()
    best, best_score = "", 0
    for dom, kws in _DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in kws if kw in low)
        if score > best_score:
            best, best_score = dom, score
    return best


def normalize(raw, source="", domain_hint=""):
    """Map a fetched item ({title,link,summary,...}) to a store record."""
    title = raw.get("title", "")
    return {
        "title": title,
        "link": raw.get("link", ""),
        "summary": raw.get("summary", ""),
        "source": source or raw.get("source", ""),
        "domain_tag": domain_hint or classify_domain(title, raw.get("summary", "")),
        "published": raw.get("published", ""),
    }


def ingest_items(store, items, source="", domain_hint=""):
    """Normalize + add a batch of items. Returns the number newly stored."""
    norm = [normalize(it, source=source, domain_hint=domain_hint) for it in items]
    return store.add(norm)
