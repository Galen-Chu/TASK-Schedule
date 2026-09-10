"""Best-effort, keyless data fetchers.

Every function returns ``None`` / ``[]`` on any failure so callers can fall
back to bundled sample data without crashing. The keyless sources (TWSE open
API, public RSS feeds) need no credentials, which is what lets the pipeline
run end-to-end inside GitHub Actions.
"""
import json
import logging
import os
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
    """TWSE 集中市場融資/融券餘額加總（公開、免 key）。

    MI_MARGN 是「個股」明細（openapi.twse.com.tw）；全市場維持率並非
    公開資料集，因此改彙總全市場融資/融券今日餘額（單位：張）。
    回傳 {"total_margin_balance": int, "total_short_balance": int} 或 None。
    """
    import ssl
    url = "https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN"
    try:
        # TWSE endpoint occasionally trips default cert verification on some
        # hosts; use a lenient context (same as the BLS fetcher).
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8", "ignore"))
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError) as exc:
        log.info("TWSE MI_MARGN GET failed: %s", exc)
        return None
    if not isinstance(data, list) or not data:
        return None
    margin = short = 0
    for r in data:
        mv = str(r.get("融資今日餘額", "")).replace(",", "")
        sv = str(r.get("融券今日餘額", "")).replace(",", "")
        if mv.isdigit():
            margin += int(mv)
        if sv.isdigit():
            short += int(sv)
    if not margin:
        return None
    return {"source": "TWSE MI_MARGN", "date": date_str,
            "total_margin_balance": margin, "total_short_balance": short}


def fetch_twse_institutional(date_str, lookback=5):
    """TWSE 全市場外資/投信買賣超股數加總（legacy T86 JSON，單位：股）。

    openapi.twse.com.tw 沒有對應日報（TWT38U/TWT74U/T86 皆 404），但
    www.twse.com.tw 的舊版 JSON 介面可用：/fund/T86?response=json。假日
    回「查無資料」，故由 date_str 起往回最多 ``lookback`` 天找最近交易日。
    回傳 {"date": 交易日, "foreign_net_shares": int, "trust_net_shares": int}
    或 None（防呆：任何失敗回 None，版面顯示待補）。
    """
    import datetime as _dt
    for back in range(lookback):
        day = (_dt.date.fromisoformat(str(date_str)) - _dt.timedelta(days=back))
        url = ("https://www.twse.com.tw/fund/T86?response=json&date="
               f"{day.strftime('%Y%m%d')}&selectType=ALL")
        data = None
        try:
            import json as _json
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0",
                              "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = _json.loads(resp.read().decode("utf-8", "ignore"))
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError):
            continue
        if not isinstance(data, dict) or data.get("stat") != "OK":
            continue
        fields = data.get("fields") or []
        rows = data.get("data") or []
        if not rows:
            continue

        def _col(sub):
            for i, f in enumerate(fields):
                if sub in str(f):
                    return i
            return None

        fi, ti = _col("外陸資買賣超"), _col("投信買賣超")
        if fi is None or ti is None:
            return None
        foreign = trust = 0
        for r in rows:
            for idx, acc in ((fi, "foreign"), (ti, "trust")):
                if idx >= len(r):
                    continue
                v = str(r[idx]).replace(",", "").replace(" ", "")
                if v and (v.lstrip("-").isdigit()):
                    if acc == "foreign":
                        foreign += int(v)
                    else:
                        trust += int(v)
        if not (foreign or trust):
            return None
        return {"source": "TWSE T86", "date": day.isoformat(),
                "foreign_net_shares": foreign, "trust_net_shares": trust}
    return None


def _taifex_get(url, timeout=15):
    """GET a TAIFEX OpenAPI JSON array（Cloudflare 前緣，帶瀏覽器 UA）。"""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                               "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", "ignore"))
            return data if isinstance(data, list) else None
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError) as exc:
        log.info("TAIFEX GET failed: %s (%s)", url, exc)
        return None


def _taifex_tx_oi_from_rows(rows):
    """TAIFEX「三大法人-區分各期貨契約」rows -> 外資臺股期貨（TX）淨部位。

    數字欄位是字串（可含逗點）；Date 欄（YYYYMMDD）是資料的實際交易日
    ——API 對無資料日期（假日/盤前）會靜默回退到最近交易日，故日期必須
    取自 row 本身，不可標查詢日。Exposed for tests（離線解析契約）。
    回傳 {"date", "net_oi", "trade_net"} 或 None。
    """
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        if str(r.get("Item", "")).strip() != "外資及陸資":
            continue
        if str(r.get("ContractCode", "")).strip() != "臺股期貨":
            continue

        def _int(v):
            v = str(v or "").replace(",", "").strip()
            return int(v) if v.lstrip("-").isdigit() else None

        oi = _int(r.get("OpenInterest(Net)"))
        d = str(r.get("Date", ""))
        if oi is None or not d.isdigit():
            return None
        return {"date": f"{d[:4]}-{d[4:6]}-{d[6:8]}",
                "net_oi": oi, "trade_net": _int(r.get("TradingVolume(Net)"))}
    return None


def fetch_taifex_foreign_futures_oi(date_str, lookback=4):
    """外資臺股期貨（TX）多空未平倉淨額（TAIFEX OpenAPI、免 key）。

    2026-09-10 重新查證找到 openapi.taifex.com.tw/v1（09-08 誤判「無
    keyless API」——當時只查了官網 JS 表單與 data.gov.tw）。日期參數
    YYYY/MM/DD；假日/盤前 API 會靜默回退到最近交易日的資料（日期以 row
    的 Date 欄為準），``lookback`` 迴圈只為應付偶發的空回應。取「臺股
    期貨」單一契約（媒體引用口徑），不用總表（全商品合計會被股票期貨
    幾十萬口淹沒）。回傳 {"source", "date", "net_oi", "trade_net"} 或
    None（版面待補）。
    """
    import datetime as _dt
    for back in range(lookback):
        day = (_dt.date.fromisoformat(str(date_str)) - _dt.timedelta(days=back))
        ds = day.strftime("%Y/%m/%d")
        url = ("https://openapi.taifex.com.tw/v1/"
               "MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate"
               f"?dateStart={ds}&dateEnd={ds}")
        rows = _taifex_get(url)
        if not rows:
            continue
        hit = _taifex_tx_oi_from_rows(rows)
        if hit:
            hit["source"] = "TAIFEX OpenAPI"
            return hit
    return None


def _put_call_from_rows(rows, ymd):
    """PutCallRatio rows（API 忽略日期範圍、回多日）-> Date<=ymd 最新一列。

    Exposed for tests。回傳 {"pc_oi", "pc_volume", "date"} 或 None。
    """
    best = None
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        d = str(r.get("Date", ""))
        if not d.isdigit() or d > ymd:
            continue
        if best is None or d > best[0]:
            best = (d, r)
    if not best:
        return None

    def _f(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    oi = _f(best[1].get("PutCallOIRatio%"))
    if oi is None:
        return None
    d = best[0]
    return {"pc_oi": oi, "pc_volume": _f(best[1].get("PutCallVolumeRatio%")),
            "date": f"{d[:4]}-{d[4:6]}-{d[6:8]}"}


def fetch_taifex_put_call(date_str):
    """臺指選擇權 Put/Call 比（成交量% 與 OI%，TAIFEX OpenAPI、免 key）。

    API 的 dateStart/dateEnd 會被忽略（回傳最近多日、降冪），故抓回後取
    Date<=date_str 的最新一列（週末自動落到上一交易日）。
    回傳 {"source", "date", "pc_oi", "pc_volume"} 或 None。
    """
    import datetime as _dt
    day = _dt.date.fromisoformat(str(date_str))
    ds = day.strftime("%Y/%m/%d")
    url = (f"https://openapi.taifex.com.tw/v1/PutCallRatio?dateStart={ds}&dateEnd={ds}")
    rows = _taifex_get(url)
    if not rows:
        return None
    hit = _put_call_from_rows(rows, day.strftime("%Y%m%d"))
    if hit:
        hit["source"] = "TAIFEX OpenAPI"
    return hit


def _breadth_from_mi_index(payload):
    """MI_INDEX 的「漲跌證券數合計」表 -> 上市股票漲/跌家數。

    取「股票」欄（不含權證）；家數值可能帶「(漲停)」後綴，取括號前數字。
    Exposed for tests。回傳 {"advance", "decline"} 或 None。
    """
    tables = payload.get("tables") if isinstance(payload, dict) else None
    for t in tables or []:
        if "漲跌證券數合計" not in str(t.get("title", "")):
            continue
        fields = [str(f) for f in (t.get("fields") or [])]
        if "股票" not in fields:
            break
        ci = fields.index("股票")
        got = {}
        for r in (t.get("data") or t.get("rows") or []):
            kind = str(r[0]) if r else ""
            val = str(r[ci]) if ci < len(r) else ""
            num = val.split("(")[0].replace(",", "").strip()
            if not num.isdigit():
                continue
            if kind.startswith("上漲"):
                got["advance"] = int(num)
            elif kind.startswith("下跌"):
                got["decline"] = int(num)
        if got.get("advance") is not None and got.get("decline") is not None:
            return got
        break
    return None


def fetch_twse_breadth(date_str, lookback=4):
    """TWSE 上市股票漲/跌家數（市場廣度，MI_INDEX type=ALL 的統計表）。

    MI_INDEX 是「每日收盤行情(全部)」大 JSON（約 4-5MB），漲跌家數在其
    「漲跌證券數合計」表。假日回「查無資料」，由 date_str 往回找最近
    交易日（同 T86 模式）。回傳 {"source", "date", "advance", "decline"}
    或 None（版面待補）。
    """
    import datetime as _dt
    for back in range(lookback):
        day = (_dt.date.fromisoformat(str(date_str)) - _dt.timedelta(days=back))
        url = ("https://www.twse.com.tw/exchangeReport/MI_INDEX"
               f"?response=json&date={day.strftime('%Y%m%d')}&type=ALL")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                                   "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8", "ignore"))
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError) as exc:
            log.info("TWSE MI_INDEX GET failed: %s (%s)", url, exc)
            continue
        if not isinstance(payload, dict) or payload.get("stat") != "OK":
            continue
        got = _breadth_from_mi_index(payload)
        if got:
            got.update({"source": "TWSE MI_INDEX", "date": day.isoformat()})
            return got
    return None


def _feed_items(feed, limit):
    """Map feedparser entries to plain dicts. Exposed for tests.

    ``published`` is the item's real publish date (RFC822 ``published`` or
    ``updated`` for Atom feeds) — the retrieval layer ages/filters on it.
    Losing it (2026-09-08 audit: the corpus had 0/1483 items with published)
    made every card display our fetched_at stamp instead, and up-to-7-day-old
    items kept qualifying as "fresh".
    """
    return [
        {"title": e.get("title", ""), "link": e.get("link", ""),
         "summary": e.get("summary", ""),
         "published": e.get("published") or e.get("updated") or ""}
        for e in feed.entries[:limit]
    ]


def fetch_rss_items(url, limit=6):
    """剖析 RSS/Atom feed（需要 feedparser）。回傳 list 或 []。"""
    try:
        import feedparser
    except ImportError:
        log.info("feedparser 未安裝，跳過 RSS：%s", url)
        return []
    try:
        feed = feedparser.parse(url)
        return _feed_items(feed, limit)
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
    "silver": "SI=F",       # 白銀 (USD/oz)
    "copper": "HG=F",       # 銅 (USD/lb)
    "natgas": "NG=F",       # 天然氣 (USD/MMBtu)
    # 2026-09-08 B案：取代表內寫死的 2024 期樣板指數/匯率（S&P 5,420、
    # TWD 32.15 等）。全部走同一個 mirror-host 備援通道，缺值由版面「待補」。
    "spx": "^GSPC",         # S&P 500
    "ndx": "^IXIC",         # Nasdaq 綜合指數
    "sox": "^SOX",          # 費城半導體
    "usdjpy": "JPY=X",      # 美元/日圓
    "usdtwd": "TWD=X",      # 美元/新台幣
    "twii": "^TWII",        # 台灣加權指數
}


_YAHOO_HOSTS = ("query1", "query2")


def _yahoo_chart(symbol, query):
    """v8 chart JSON with mirror-host fallback and a short backoff.

    Yahoo's keyless endpoint intermittently throttles individual requests
    (429/401) from shared runner IPs — 2026-09-04 ^VIX alone failed for a
    whole CI run while the 7 other symbols resolved. A 200 whose body is a
    chart error ({"chart": {"result": null}}) also counts as a failure so
    the mirror host gets tried too.
    """
    import time as _time
    for i, host in enumerate(_YAHOO_HOSTS):
        if i:
            _time.sleep(1.5)
        data = _get_json(f"https://{host}.finance.yahoo.com/v8/finance/chart/{symbol}?{query}")
        if data and (data.get("chart") or {}).get("result"):
            return data
    return None


def fetch_yahoo_quote(symbol):
    """Keyless Yahoo Finance v8 chart quote. Returns float price or None."""
    data = _yahoo_chart(symbol, "interval=1d&range=1d")
    try:
        return float(data["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def fetch_yahoo_history(symbol, months=3):
    """Keyless daily close history from the Yahoo v8 chart endpoint.

    Returns [{"date": "MM/DD", "v": close}, ...] oldest→newest (nulls
    skipped), or None on any failure. ~63 sessions for 3 months.
    """
    import datetime as _dt
    data = _yahoo_chart(symbol, f"interval=1d&range={months}mo")
    try:
        result = data["chart"]["result"][0]
        ts = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError):
        return None
    out = []
    for t, c in zip(ts, closes):
        if c is None:
            continue
        try:
            # UTC, not the host's zone: the label must not shift between the
            # UTC CI runner and a +08:00 local build for the same session.
            d = _dt.datetime.fromtimestamp(t, tz=_dt.timezone.utc).strftime("%m/%d")
        except (ValueError, OSError, OverflowError):
            continue
        out.append({"date": d, "v": round(float(c), 2)})
    return out or None


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
        dated_rows = []
        for r in rows[1:]:
            if idate is not None and len(r) > idate:
                try:
                    d = _dt.datetime.strptime(r[idate].strip(), "%m/%d/%Y").date()
                except ValueError:
                    continue
                dated_rows.append((d, r))
                if d > latest_d:
                    latest_d, last = d, r
        if last is None:
            last = rows[-1]
        # ~1 month earlier row (for the 債券表「上月數據」欄，取代寫死的 4.15/4.30).
        # File order is newest-first, so take the max-dated row ≤ cutoff —
        # not the last one seen (that silently ends on the oldest row).
        prev_row = None
        cutoff = latest_d - _dt.timedelta(days=28)
        for d, r in dated_rows:
            if d <= cutoff and (prev_row is None or d > prev_row[0]):
                prev_row = (d, r)
        if prev_row is not None:
            prev_row = prev_row[1]
        elif len(dated_rows) > 1:
            prev_row = dated_rows[0][1]

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
        if prev_row is not None:
            try:
                if i2 is not None and prev_row[i2]:
                    out["2y_prev"] = float(prev_row[i2])
                if i10 is not None and prev_row[i10]:
                    out["10y_prev"] = float(prev_row[i10])
                if "2y_prev" in out and "10y_prev" in out:
                    out["spread_prev"] = round(out["10y_prev"] - out["2y_prev"], 2)
                out["_prev_date"] = prev_row[0]
            except (ValueError, IndexError):
                pass
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

    Keyless by default. Set BLS_API_KEY env var for higher rate limits
    (free registration → 500 requests/day vs 25/day keyless).
    Returns dict {value, year, period_name} or None on failure.
    Note: the v2 payload nests under ``Results`` (capital R).
    """
    import ssl
    api_key = os.environ.get("BLS_API_KEY", "")
    url = f"https://api.bls.gov/publicAPI/v2/timeseries/data/{series_id}"
    if latest:
        url += "?latest=true"
        if api_key:
            url += f"&registrationkey={api_key}"
    elif api_key:
        url += f"?registrationkey={api_key}"
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


# ---- FRED keyless CSV (high-yield credit spread) ----------------------------
def fetch_fred_series(series_id):
    """Latest + ~1-month-earlier value of a FRED series via the keyless
    fredgraph.csv endpoint (ascending DATE,VALUE rows; '.' = missing).

    Returns {"value", "date", "prev", "prev_date"} or None. Used for the
    ICE BofA US high-yield OAS (BAMLH0A0HYM2) that replaced the hardcoded
    "340 bps" editorial value.
    """
    import datetime as _dt
    text = _get_text(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}")
    if not text:
        return None
    pts = []
    for line in text.strip().splitlines()[1:]:
        try:
            d_str, v_str = line.split(",", 1)
            d = _dt.date.fromisoformat(d_str)
            v = float(v_str)
        except (ValueError, IndexError):
            continue  # header, '.', or malformed row
        pts.append((d, v))
    if len(pts) < 2:
        return None
    last_d, last_v = pts[-1]
    cutoff = last_d - _dt.timedelta(days=28)
    prev = next(((d, v) for d, v in reversed(pts) if d <= cutoff), pts[0])
    return {"value": round(last_v, 2), "date": last_d.isoformat(),
            "prev": round(prev[1], 2), "prev_date": prev[0].isoformat()}


# ---- Macro chart data (keyless) --------------------------------------------
_TENORS = [("1 Mo", "1M"), ("3 Mo", "3M"), ("6 Mo", "6M"), ("1 Yr", "1Y"),
           ("2 Yr", "2Y"), ("3 Yr", "3Y"), ("5 Yr", "5Y"), ("7 Yr", "7Y"),
           ("10 Yr", "10Y"), ("20 Yr", "20Y"), ("30 Yr", "30Y")]


def fetch_treasury_curve():
    """Latest full US Treasury yield curve (keyless CSV, newest row by date).

    Returns {"date": "MM/DD/YYYY", "curve": {"1M": float, ..., "30Y": float}}
    or None."""
    import csv as _csv
    import io as _io
    import datetime as _dt
    year = _dt.date.today().year
    url = (f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
           f"daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve"
           f"&field_tdr_date_value={year}&_format=csv")
    text = _get_text(url)
    if not text:
        return None
    try:
        rows = list(_csv.reader(_io.StringIO(text)))
        hdr = [h.strip() for h in rows[0]]
        idate = hdr.index("Date")
        latest = None
        latest_d = _dt.date.min
        for r in rows[1:]:
            if len(r) > idate:
                try:
                    d = _dt.datetime.strptime(r[idate].strip(), "%m/%d/%Y").date()
                except ValueError:
                    continue
                if d > latest_d:
                    latest_d, latest = d, r
        if latest is None:
            return None
        curve = {}
        for col, label in _TENORS:
            if col in hdr:
                i = hdr.index(col)
                if len(latest) > i and latest[i]:
                    try:
                        curve[label] = float(latest[i])
                    except ValueError:
                        pass
        if not curve:
            return None
        return {"date": latest[0], "curve": curve}
    except (ValueError, IndexError) as exc:
        log.info("Treasury curve parse failed: %s", exc)
        return None


def fetch_treasury_10y_series():
    """Daily US 10Y yields for the current year (keyless CSV), oldest→newest.

    Returns [{"date": "MM/DD/YYYY", "v": float}, ...] or None."""
    import csv as _csv
    import io as _io
    import datetime as _dt
    year = _dt.date.today().year
    url = (f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
           f"daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve"
           f"&field_tdr_date_value={year}&_format=csv")
    text = _get_text(url)
    if not text:
        return None
    try:
        rows = list(_csv.reader(_io.StringIO(text)))
        hdr = [h.strip() for h in rows[0]]
        idate, i10 = hdr.index("Date"), hdr.index("10 Yr")
        pts = []
        for r in rows[1:]:
            if len(r) > i10 and r[i10]:
                try:
                    pts.append((_dt.datetime.strptime(r[idate].strip(), "%m/%d/%Y").date(),
                                float(r[i10])))
                except ValueError:
                    continue
        pts.sort()
        return [{"date": d.strftime("%m/%d/%Y"), "v": v} for d, v in pts] or None
    except (ValueError, IndexError) as exc:
        log.info("Treasury 10Y series parse failed: %s", exc)
        return None


def fetch_bls_history(series_id, months=13):
    """Last ~N observations of a BLS series (keyless v2 POST, range-limited).

    Returns a newest-first list of {"year", "period_name", "value"} or None."""
    import ssl
    import datetime as _dt
    y2 = _dt.date.today().year
    body = json.dumps({"seriesid": [series_id],
                       "startyear": str(y2 - 2), "endyear": str(y2)}).encode()
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            "https://api.bls.gov/publicAPI/v2/timeseries/data/",
            data=body, method="POST",
            headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8", "ignore"))
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError) as exc:
        log.info("BLS history POST failed: %s", exc)
        return None
    try:
        arr = (data.get("Results") or data.get("results") or {})["series"][0]["data"]
        return [{"year": x["year"], "period_name": x["periodName"], "value": x["value"]}
                for x in arr[:months]]
    except (KeyError, IndexError, TypeError):
        return None
