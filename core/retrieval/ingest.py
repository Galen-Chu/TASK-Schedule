"""Normalize + domain-classify fetched items before they enter the store."""
import logging

log = logging.getLogger("retrieval.ingest")

# Domain → trigger keywords (Traditional Chinese + English). Used to tag each
# item so per-domain retrieval can filter without a query.
_DOMAIN_KEYWORDS = {
    "geopolitics": [
        "地緣", "外交", "軍事", "國防", "兩岸", "台海", "關稅", "制裁", "北約",
        "印太", "戰爭", "選舉",
        "geopolitics", "diplomacy", "tariff", "sanction", "nato", "war",
        "ukraine", "gaza", "israel", "china", "taiwan", "military", "strike",
        "conflict", "border", "refugee", "summit", "election", "minister",
        "president", "parliament", "treaty",
    ],
    "macro": [
        "通膨", "通脹", "利率", "央行", "降息", "殖利率", "就業", "非農", "景氣",
        "cpi", "pce", "gdp", "fed", "ecb", "macro", "inflation", "yield",
        "economy", "economic", "recession", "market", "stocks", "bond",
        "treasury", "dollar", "jobs", "trade", "deficit", "debt", "rate cut",
        "interest rate",
    ],
    "it_ai": [
        "ai", "artificial intelligence", "半導體", "晶片", "晶圓", "台積電",
        "tsmc", "nvidia", "伺服器", "算力", "gpu", "封裝", "cowos", "llm",
        "agent", "semiconductor", "chip",
        "openai", "google", "microsoft", "apple", "cloud", "software",
        "cyber", "hack", "data center", "startup", "app", "iphone",
    ],
    "biotech": [
        "生技", "生醫", "醫藥", "新藥", "臨床", "疫苗", "基因", "adc", "fda",
        "biotech", "drug", "clinical", "pharma",
        "health", "medicine", "cancer", "vaccine", "gene", "disease",
        "study finds", "covid", "hospital", "brain", "obesity", "diabetes",
    ],
    "hardware": [
        "硬體", "能源", "電池", "核能", "smr", "電動車", "儲能", "電網", "機器人",
        "hardware", "energy", "battery", "robot", "solar", "grid",
        "ev", "electric vehicle", "charging", "nuclear", "power", "renewable",
        "manufacturing", "supply chain", "factory", "chip plant",
    ],
    "aerospace": [
        "航太", "太空", "航空", "衛星", "火箭", "太空梭", "太空站", "發射",
        "量子", "量子計算", "量子電腦", "量子科技", "量子加密", "量子通訊",
        "aerospace", "space", "satellite", "rocket", "launch", "nasa",
        "spacex", "blue origin", "boeing", "airbus", "aviation", "aircraft",
        "jet", "drone", "uav", "orbit", "mars", "moon", "lunar", "iss",
        "spacecraft", "milstar", "starlink", "kuiper", "hypersonic",
        "defense aerospace", "commercial space", "space tourism",
        "space station", "space telescope", "james webb", "artemis",
        "quantum", "quantum computing", "qubit", "quantum computer",
        "superposition", "entanglement", "quantum encryption",
        "quantum key distribution", "qkd", "post-quantum",
        "quantum sensing", "quantum metrology", "quantum algorithm",
        "quantum error correction", "photonic quantum", "topological quantum",
        "ibm quantum", "google quantum", "ionq", "rigetti", "d-wave",
        "quantum supremacy", "quantum advantage", "quantum internet",
        "neutral atom", "trapped ion", "superconducting qubit",
    ],
    "spiritual": [
        "靈性", "心靈", "冥想", "正念", "身心靈", "自我成長", "內在",
        "占星", "星座", "塔羅", "易經", "紫微", "八字", "風水", "能量",
        "spiritual", "spirituality", "meditation", "mindfulness",
        "astrology", "tarot", "zodiac", "horoscope", "i ching",
        "wellness", "holistic", "healing", "crystal", "chakra",
        "aura", "karma", "soul", "consciousness", "enlightenment",
        "yoga", "breathwork", "journaling", "self-care", "intuition",
        " manifestation", "gratitude", "affirmation", "ritual",
        "full moon", "new moon", "retrograde", "solstice", "equinox",
        "psychic", "mediumship", "palmistry", "numerology",
        "human design", "gene keys", "sacred geometry",
    ],
}

DOMAIN_KEYWORDS = _DOMAIN_KEYWORDS  # re-export for callers (e.g. queries)

import re as _re


def _kw_hit(kw, low):
    """ASCII keywords match on word boundaries ('ai' must not hit 'said');
    CJK keywords keep substring matching."""
    if kw.isascii() and kw.replace(" ", "").replace("-", "").isalpha():
        return _re.search(rf"\b{_re.escape(kw)}\b", low) is not None
    return kw in low


def classify_domain(title, summary):
    """Return the best-matching domain tag, or "" if no keyword hits."""
    low = ((title or "") + " " + (summary or "")).lower()
    best, best_score = "", 0
    for dom, kws in _DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in kws if _kw_hit(kw, low))
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
