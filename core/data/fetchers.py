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
    """TWSE 集中市場融資維持率（公開、免 key）。目前回傳 None。

    TWSE openapi 只提供「個股」融資融券餘額（MI_MARGN），並未直接公開
    「全市場融資維持率」這個彙總值；要取該比率需另找資料源。在此之前報告
    使用內建 sample 維持率，signal 模型維持不變。
    （備註：舊程式用的 www.twse.com.tw/exchangeReport/MI_MARGIN 已 404；
    正確代碼為 MI_MARGN，位於 openapi.twse.com.tw 。）
    """
    return None


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


# ---- U.S. Treasury daily yield curve (keyless, official CSV) ---------------
def _get_text(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SparkSchedule/2.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        log.info("GET %s failed: %s", url, exc)
        return None


def fetch_treasury_yields(year=None):
    """Latest U.S. Treasury daily yield curve from treasury.gov (keyless).

    Returns a dict like {"2y": 3.66, "10y": 4.19, "spread_10y2y": 0.53} for
    whichever tenors resolved, or None on failure. ``year`` defaults to the
    current year.
    """
    import csv as _csv
    import io as _io
    import datetime as _dt
    year = year or _dt.date.today().year
    url = (f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
           f"daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve"
           f"&field_tdr_date_value={year}&_format=csv")
    text = _get_text(url)
    if not text:
        return None
    try:
        rows = list(_csv.reader(_io.StringIO(text)))
        if len(rows) < 2:
            return None
        hdr = [h.strip() for h in rows[0]]

        def col(name):
            return hdr.index(name) if name in hdr else None

        # The Treasury CSV is newest-first; pick the most recent date row so we
        # never report stale yields (the old rows[-1] grabbed the OLDEST row and
        # the report had been showing ~January figures for months).
        idate = col("Date")
        last = None
        latest_d = _dt.date.min
        for r in rows[1:]:
            if idate is not None and len(r) > idate:
                try:
                    d = _dt.datetime.strptime(r[idate].strip(), "%m/%d/%Y").date()
                except ValueError:
                    continue
                if d > latest_d:
                    latest_d, last = d, r
        if last is None:
            last = rows[-1]

        # Treasury CSV uses "2 Mo" (no 2 Yr), "10 Yr"
        i2 = col("2 Yr") if "2 Yr" in hdr else col("2 Mo")
        i10 = col("10 Yr")
        out = {}
        if i2 is not None and last[i2]:
            out["2y"] = float(last[i2])
        if i10 is not None and last[i10]:
            out["10y"] = float(last[i10])
        if "2y" in out and "10y" in out:
            out["spread_10y2y"] = round(out["10y"] - out["2y"], 2)
        out["_date"] = last[0] if last else None
        return out or None
    except (ValueError, IndexError, KeyError) as exc:
        log.info("Treasury CSV parse failed: %s", exc)
        return None


# ---- Fear & Greed Index (keyless) -----------------------------------------
def fetch_fear_greed():
    """CNN-style Fear & Greed value (0-100) from alternative.me (keyless).

    Returns an int, or None on failure.
    """
    data = _get_json("https://api.alternative.me/fng/?limit=1")
    try:
        return int(data["data"][0]["value"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


# ---- Macro indicators (keyless BLS public API) ----------------------------
# BLS series IDs (https://www.bls.gov/help/hlpforma.htm). keyless via v2.
_BLS_SERIES = {
    "cpi_core": "CUUR0000SA0L1E",     # Core CPI (less food & energy), YoY-ish
    "cpi_headline": "CUUR0000SA0",    # Headline CPI
    "unemployment": "LNS14000000",     # Unemployment rate
    "nfp": "CES0000000001",            # Total nonfarm payrolls (thousands)
}


def fetch_bls_series(series_id, latest=True):
    """Fetch the latest observation for a BLS series via the public v2 API.

    Keyless. Returns dict {value, year, period_name} or None on failure.
    Note: the v2 payload nests under ``Results`` (capital R).
    """
    import ssl
    url = f"https://api.bls.gov/publicAPI/v2/timeseries/data/{series_id}"
    if latest:
        url += "?latest=true"
    # BLS endpoint occasionally trips default cert verification on some hosts;
    # use a lenient context so a stale CA bundle doesn't break the fetch.
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={"User-Agent": "SparkSchedule/2.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8", "ignore"))
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError) as exc:
        log.info("BLS GET %s failed: %s", url, exc)
        return None
    try:
        results = data.get("Results") or data.get("results") or {}
        s = results["series"][0]["data"][0]
        return {"value": s["value"], "year": s["year"], "period_name": s["periodName"]}
    except (KeyError, IndexError, TypeError):
        return None


def fetch_macro_snapshot():
    """Fetch a bundle of monthly macro indicators (keyless BLS).

    Returns {key: {value, year, period_name}} for whichever resolved, or None.
    """
    out = {}
    for key, sid in _BLS_SERIES.items():
        rec = fetch_bls_series(sid)
        if rec:
            out[key] = rec
    return out or None
