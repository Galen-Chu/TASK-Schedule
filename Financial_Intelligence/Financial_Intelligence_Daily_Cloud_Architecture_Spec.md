# Financial Intelligence 每日投資趨勢報告 — 雲端架構與自動化部署規格書 (Cloud Architecture Specification)

## 1. 系統整體架構與資料流 (System Architecture & Pipeline)

```text
[ Cloud Scheduler / Cron Trigger ] (每日早上 07:30 AM UTC+8)
        │
        ▼
[ Serverless Engine (GCP Cloud Functions / GitHub Actions) ]
        │
        ├──► 1. Data Aggregator Module
        │     ├── TWSE / OTC API (台股融資維持率、三大法人現貨/期貨未平倉)
        │     ├── FRED API (美債 10Y/2Y 殖利率、CPI、PCE、NFP、PMI)
        │     └── Yahoo Finance / FinMind (S&P500, VIX, DXY, USD/TWD, Gold, BTC)
        │
        ├──► 2. Quantitative Scoring & Decision Engine
        │     ├── 融資維持率超跌/過熱區間判定 (150% / 160% / 175%)
        │     └── 進出場燈號矩陣計算 (🟢 Buy / 🟡 Hold / 🔴 Sell)
        │
        ├──► 3. ReportLab PDF Generator Engine
        │     ├── 5 頁版面渲染 (5 Asset Markets + Page 5 Entry/Exit Targets)
        │     └── 套用高對比色彩、雙字型系統與 XML 防呆機制
        │
        ├──► 4. Google Drive Storage API Module
        │     └── 自動將產出之 PDF 歸檔上傳至 Drive 指定資料夾
        │
        └──► 5. Obsidian Knowledge Base Sync Module
              └── 預寫含有 Frontmatter 與 Callout 之 Markdown 筆記
```

---

## 2. 雲端部署方案規格 (Cloud Deployment Specifications)

### 方案 A：GCP (Google Cloud Platform) — 企業級無伺服器架構
- **Cloud Scheduler**：設定 Cron 運算式 `30 7 * * *` (時區：`Asia/Taipei`)。
- **Cloud Pub/Sub**：作為解耦消息佇列，觸發 Cloud Functions。
- **Cloud Functions (Python 3.11)**：
  - 記憶體配置：`512 MB` / 執行逾時時間：`60 秒`。
  - 環境變數：託管 `GOOGLE_DRIVE_FOLDER_ID`, `OBSIDIAN_VAULT_PATH`。

### 方案 B：GitHub Actions — 免費開源 CI/CD 排程
- **Workflow 配置**：`.github/workflows/daily_report.yml`
- **Secrets**：託管 `GCP_SERVICE_ACCOUNT_KEY`, `GOOGLE_DRIVE_TOKEN`。

---

## 3. 容錯與重試機制 (Error Handling & Retry Policies)
1. **API 採集備援 (Data Fallback)**：當主 API (如 TWSE) 逾時時，自動切換至歷史快取或備援爬蟲。
2. **零阻斷防呆 (Zero-Downtime Pipeline)**：數據缺失時填入歷史最新有效值 (Forward Fill)，並於報告中標註 `(預估/前值)`。
3. **雲端檔案覆寫與版本控制**：每日上傳時自動攜帶帶有 `YYYY-MM-DD` 時間戳記之標準檔名，避免檔案名稱衝突。
