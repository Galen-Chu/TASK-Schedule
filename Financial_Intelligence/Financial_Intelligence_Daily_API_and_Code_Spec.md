# Financial Intelligence 每日投資趨勢報告 — API 接口與代碼規格書 (API & Code Specification)

## 1. 外部 API 資料源接口規格 (Data Ingestion API Contracts)

### (1) 台灣證券交易所 (TWSE API)
- **Endpoint**: `https://www.twse.com.tw/exchangeReport/MI_MARGIN`
- **主要欄位**:
  - `MarginMaintenanceRatio`: 大盤融資維持率（單位: `%`）
  - `MarginBalance`: 融資餘額（單位: 億新台幣）
  - `InstitutionalTrading`: 外資、投信、自營商買賣超金額
  - `ForeignFuturesNetOI`: 外資台指期未平倉淨口數

### (1b) 臺灣期貨交易所 OpenAPI（2026-09-10 起接入，免 key）
- **Base**: `https://openapi.taifex.com.tw/v1`（Swagger 於 `/swagger.json`；
  09-08 曾誤判「無 keyless API」，實為期交所官方 OpenAPI，Cloudflare 前緣需瀏覽器 UA）
- **端點**:
  - `MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate?dateStart=&dateEnd=`
    （YYYY/MM/DD）：三大法人-區分各期貨契約-依日期 → 取 `Item=外資及陸資`、
    `ContractCode=臺股期貨`（TX）的 `OpenInterest(Net)`＝外資台指期淨未平倉
    （媒體引用口徑；總表 GeneralBytheDate 為全商品合計，會被股票期貨淹没，勿用）。
    注意：對無資料日期（假日/盤前）API 會靜默回退到最近交易日，日期以 row 的
    `Date` 欄為準。
  - `PutCallRatio`: 臺指選擇權 Put/Call 比（`PutCallOIRatio%`／`PutCallVolumeRatio%`；
    日期參數會被忽略，回傳最近多日，自行取 `Date <= 報告日` 最新一列）。
- **實作**: `core/data/fetchers.fetch_taifex_foreign_futures_oi` / `fetch_taifex_put_call`

### (1c) TWSE 漲跌家數（市場廣度，2026-09-10 起接入）
- **Endpoint**: `https://www.twse.com.tw/exchangeReport/MI_INDEX?response=json&date=YYYYMMDD&type=ALL`
- **欄位**: `tables[漲跌證券數合計].data` 的「股票」欄 → 上漲/下跌家數（值可帶
  `(漲停)` 後綴，取括號前數字；約 4-5MB 大 JSON）
- **實作**: `core/data/fetchers.fetch_twse_breadth`

### (2) 美國聖路易聯儲 (FRED API)
- **Endpoint**: `https://api.stlouisfed.org/fred/series/observations`
- **Series IDs**:
  - `DGS10`: 10 年期美國公債殖利率
  - `DGS2`: 2 年期美國公債殖利率
  - `T10Y2Y`: 10Y-2Y 殖利率利差
  - `CPIAUCSL`: 美國 CPI 消費者物價指數

### (3) Yahoo Finance / FinMind API
- **Ticker Codes**:
  - `^GSPC`: S&P 500 指數
  - `^IXIC`: Nasdaq 指數
  - `^SOX`: 費城半導體指數
  - `^VIX`: VIX 恐慌指數
  - `DX-Y.NYB`: 美元指數 (DXY)
  - `USDTWD=X`: 美元/新台幣匯率
  - `GC=F`: 紐約期黃金
  - `BTC-USD`: 比特幣

---

## 2. 核心量化評級與買賣訊號模型算法 (Signal Model Logic)

```python
def calculate_market_signal_score(data):
    """
    量化評級算分模型 (滿分 100 分)
    """
    score = 50  # 中性基準分

    # 1. 台股融資維持率評分 (權重 35%)
    mmr = data.get("margin_maintenance_ratio", 160)
    if mmr < 150:
        score += 25  # 極度超跌區，強買進訊號
    elif mmr < 160:
        score += 15  # 接近臨界買點
    elif mmr > 175:
        score -= 20  # 槓桿過熱警戒

    # 2. 美股 VIX 與恐慌指數評分 (權重 25%)
    vix = data.get("vix", 20)
    if vix > 30:
        score += 20  # 極度恐慌，長線高勝率買點
    elif vix > 25:
        score += 10
    elif vix < 13:
        score -= 15  # 市場過度自滿，防拉回

    # 3. 美債 10Y-2Y 倒掛與利差 (權重 20%)
    spread = data.get("spread_10y2y", 0)
    if spread > 0:
        score += 10  # 倒掛結束，利差陡峭化

    # 4. 外資期貨淨未平倉口數 (權重 20%)
    oi = data.get("futures_net_oi", -20000)
    if oi > -10000:
        score += 15  # 空單回補
    elif oi < -30000:
        score -= 15  # 空頭壓境

    # 燈號判定
    if score >= 65:
        rating = "🟢 偏多進場 / 尋找超跌加碼點"
    elif score <= 40:
        rating = "🔴 減碼避險 / 提高現金比重"
    else:
        rating = "🟡 觀望持股 / 區間震盪"

    return score, rating
```

---

## 3. Python 模組 Function 介面合約 (Function Contracts)

### `pdf_generator.generate_daily_pdf(filename, title, date_str, data)`
- **說明**：獨立 ReportLab PDF 生成函式。
- **輸入**：檔案路徑、報告標題、發布日期字串、數據字典。
- **輸出**：產出 5 頁版高對比雙字型 PDF 檔案。

### `obsidian_writer.write_obsidian_note(data, output_dir)`
- **說明**：Obsidian Markdown 預寫函式。
- **輸入**：數據字典、輸出資料夾。
- **輸出**：產出含有 YAML Frontmatter 與 Callout 之 `.md` 筆記。
