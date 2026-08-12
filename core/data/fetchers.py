"""Best-effort, keyless data fetchers.

Every function returns ``None`` / ``[]`` on any failure so callers can fall
back to bundled sample data without crashing. The keyless sources (TWSE open
API, public RSS feeds) need no credentials, which is what lets the pipeline
run end-to-end inside GitHub Actions.
"""
import json
import logging
import urllib.request
import urllib.error

log = logging.getLogger("fetchers")
TIMEOUT = 12


def _get_json(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SparkSchedule/2.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError) as exc:
        log.info("GET %s failed: %s", url, exc)
        return None


def fetch_twse_margin(date_str):
    """TWSE 大盤融資融券維持率（公開、免 key）。回傳 dict 或 None。"""
    d = str(date_str).replace("-", "")
    url = f"https://www.twse.com.tw/exchangeReport/MI_MARGIN?response=json&date={d}"
    data = _get_json(url)
    if not data or "data" not in data:
        return None
    return {"source": "TWSE MI_MARGIN", "date": date_str, "raw": data}


def fetch_rss_items(url, limit=6):
    """剖析 RSS/Atom feed（需要 feedparser）。回傳 list 或 []。"""
    try:
        import feedparser
    except ImportError:
        log.info("feedparser 未安裝，跳過 RSS：%s", url)
        return []
    try:
        feed = feedparser.parse(url)
        return [
            {"title": e.get("title", ""), "link": e.get("link", ""), "summary": e.get("summary", "")}
            for e in feed.entries[:limit]
        ]
    except Exception as exc:  # noqa: BLE001
        log.info("RSS 解析失敗 (%s)：%s", url, exc)
        return []


def fetch_json(url):
    """Generic keyless JSON GET. Returns parsed JSON or None."""
    return _get_json(url)


# ---- Yahoo Finance (keyless) ----------------------------------------------
_YAHOO_SYMBOLS = {
    "vix": "^VIX",          # 恐慌指數
    "dxy": "DX-Y.NYB",      # 美元指數
    "gold": "GC=F",         # 黃金 (USD/oz)
    "btc": "BTC-USD",       # 比特幣
    "wti": "CL=F",          # 紐約原油
}


def fetch_yahoo_quote(symbol):
    """Keyless Yahoo Finance v8 chart quote. Returns float price or None."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
    data = _get_json(url)
    try:
        return float(data["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def fetch_market_snapshot():
    """Fetch the Financial report's headline indicators from Yahoo Finance.

    Returns a dict of {key: price} for whichever symbols resolved, or None if
    nothing came back (caller then falls back to sample).
    """
    out = {}
    for key, sym in _YAHOO_SYMBOLS.items():
        price = fetch_yahoo_quote(sym)
        if price is not None:
            out[key] = round(price, 2)
    return out or None


# ---- FRED (needs key) ------------------------------------------------------
def fetch_fred_series(series_id, api_key):
    """FRED observation (last value). Requires an API key. Returns float or None."""
    if not api_key:
        return None
    url = (f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}"
           f"&api_key={api_key}&file_type=json&sort_order=desc&limit=1")
    data = _get_json(url)
    try:
        return float(data["observations"][0]["value"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None
