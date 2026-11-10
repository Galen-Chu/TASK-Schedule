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

2026-11-10 改版：**分級制評分**（graded bands）。原單段二元模型在
2026-09-30～11-05 連續 38 天釘死在 50（融資波段整月不觸發、VIX<25 不觸發、
利差 +10 與外資 OI -10 天天互相抵銷；恐貪與 DXY 根本不是輸入）。
改版原則：每因子分級給分、門檻與表列 verdict（`_market_verdicts`）完全
同檻（橫幅與明細表不可能矛盾）、缺值不給分（可見失敗教義）。
權威實作以 `pdf_generator.calculate_signal_score` 為準，摘要如下：

```python
score = 50  # 中性基準分

# 1) VIX（與美股 verdict 同檻 25/15，分級）
#    >=30:+8（恐慌極端買點） 25~30:+6  15~25:+3  12~15:+1  <12:0（自滿）
# 2) 恐貪指數（加密市場版，逆向）：<=24:+7  25~44:+4  45~55:+2
#    56~75:0  >75:-5（極度貪婪）
# 3) 10Y-2Y 利差（與債券 verdict 同檻 0/-0.5）：>0:+5  -0.5~0:+1  <-0.5:-6
# 4) 台股融資餘額（ceiling 預設 9,000,000 張；與台股 verdict 同檻）：
#    <ceiling:+10  <1.05×ceiling:+3（貼近門檻）  >=1.05×ceiling:-8（槓桿過熱）
# 5) 外資台指期淨 OI（媒體口徑 TX，分級）：>-1萬:+5  -1~-3萬:+2
#    -3~-6萬:-3  <=-6萬:-8
# 6) DXY（與外匯 verdict 同檻 101/104.5）：<=101:+4  101~104.5:+1  >=104.5:-4
# 7) 台指選 P/C OI 比（與表列判讀同檻 80/120）：<80:+4  80~120:+1  >120:-4
# 8) 上市漲跌家數廣度（與表列判讀同檻 1.5/0.67）：
#    >1.5:+4  1.0~1.5:+2  0.67~1.0:0  <0.67:-4

# 燈號判定（不變）
score >= 65 → 🟢 偏多進場 / 尋找超跌加碼點
45 <= score < 65 → 🟡 中性觀望 / 等待訊號確認
score < 45 → 🔴 偏空減碼 / 提高現金比重
```

回測（Library `raw/reports/` 的 41 天真實輸入）：舊模型全期僅 2 種分數
（50/60）；新模型 12 種、範圍 43–61、40 個相鄰日中 26 日逐日變動。
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
