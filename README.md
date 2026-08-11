# Gemini-Spark-Schedule

雲端排程每日報告系統 —— 每天清晨自動產生三份 A4 PDF 戰情報表（搭配 Obsidian 筆記與雲端分派），以 ReportLab 排版、由共用核心驅動，可在本機或 GitHub Actions 雲端排程執行。

> 三份報告共用一套設計系統（海軍藍 + 典雅金主色、A4 547pt 網格、雙字型中文/拉丁排版、燈號系統），各自擁有獨立的「分節色盤」與版面模板。

---

## 三份報告

| 報告 | 內容 | 排程（Asia/Taipei） | 版面風格 |
|---|---|---|---|
| **Financial Intelligence** | 每日投資趨勢：台股融資維持率、美股 VIX、美債殖利率、外匯、商品/加密，含進出場訊號與資產配置矩陣 | `30 7 * * *`（07:30） | Bloomberg 風格量化儀表板（5 頁） |
| **Global Intelligence** | 每日全球情報：5 大領域智庫焦點速讀（地緣、總經、AI/半導體、生技、硬體/能源） | `0 7 * * *`（07:00） | 智庫級 4 欄表格速讀（5 頁） |
| **Spiritual Intelligence** | 每日靈性覺察：人類圖、西洋占星、紫微斗數、八字、梅花易數五術，含五維度 AI 導引 | `30 6 * * *`（06:30） | 戰情卡片式編輯排版（5 頁，每頁一系統） |

---

## 架構

```
Gemini-Spark-Schedule/
├── core/                         # 共用核心（三份報告共同使用）
│   ├── design_tokens.py          #   主色 / 字級 / A4 網格 / 燈號（���一真相來源）
│   ├── fonts.py                  #   可攜字型解析 + 註冊（Windows/Linux/CI 通用）
│   ├── pdf_engine.py             #   雙字型 en()、標準樣式、表頭、頁尾、A4 文件工廠
│   ├── scheduler_base.py         #   BaseReportScheduler：階段化 pipeline + 優雅退回
│   ├── obsidian_writer.py        #   泛用 Markdown 寫檔
│   ├── data/fetchers.py          #   免 key 真實資料抓取（TWSE / RSS），失敗自動退回 sample
│   └── dispatch/                 #   Drive 上傳 / Gmail 寄送（介面已定義，待接憑證）
├── Financial_Intelligence/       # 各報告：scheduler + pdf_generator + obsidian_writer
├── Global_Intelligence/          #   （＋ Spiritual 的 systems_data.py 為五術單一資料源）
├── Spiritual_Intelligence/
├── config/                       # 設定（含範本；真實設定已 gitignore）
├── scripts/fetch_fonts.py        # 下載開源 CJK 字型
├── main.py                       # 統一入口
├── requirements.txt
├── .github/workflows/daily_reports.yml   # GitHub Actions 雲端排程測試
└── fonts/                        # 字型（執行期產生，已 gitignore）
```

**資料流（每份報告一致）：**

```
BaseReportScheduler.run()
  ├─ fetch_data()    → 真實來源（免 key：TWSE / RSS）；失敗或缺 key 自動退回 sample
  ├─ synthesize()    → 計分 / 評級（Financial）/ 資料整理
  ├─ render_pdf()    → 呼叫該報告的 pdf_generator（使用 core.pdf_engine）
  ├─ render_obsidian()→ 寫 Obsidian Markdown（使用 core.obsidian_writer）
  └─ dispatch()      → Drive 上傳 / Gmail（未設憑證時安全略過）
```

每一階段都被 `try/except` 包覆：**任何單一來源失敗都不會讓整條 pipeline 崩潰**——這讓排程在沒有 API key 的 CI 環境也能端到端產出報告。

---

## 快速開始

### 1. 安裝相依套件
```bash
pip install -r requirements.txt
```

### 2. 取得 CJK 字型（繁體中文必要）
```bash
python scripts/fetch_fonts.py        # 下載 Noto Sans TC 到 fonts/
```
> Linux / CI 也可改用系統字型：`sudo apt-get install -y fonts-droid-fallback fonts-liberation`
> 無字型時可檢查：`python main.py --fonts`

### 3. 產生報告
```bash
python main.py                      # 三份全部（今天）
python main.py financial            # 只跑 Financial
python main.py all --date 2026-08-11 --output-dir ./out
python main.py --list               # 看排程時間
```
PDF 與 Obsidian 筆記會輸出到 `output/`。

---

## GitHub Actions 雲端排程測試

`.github/workflows/daily_reports.yml` 提供：

- **排程觸發**：每日 22:30 UTC（= 隔日 06:30 Asia/Taipei，三份報告的最早時段）自動跑 `main.py all`。
- **手動 / push 觸發**：`workflow_dispatch` 可在 Actions 頁面手動執行；push 時也會跑一次驗收。
- **步驟**：安裝 reportlab/PyYAML/feedparser → `apt-get install fonts-droid-fallback` → `python main.py all` → 把產出的 PDF 上傳為 artifact（保留 14 天）。

推上 GitHub 後到 **Actions** 分頁即可看到執行結果與下載 PDF。沒有設定任何 Secret 也能跑（自動使用 sample data）。

---

## 設定與 Secrets（選用）

不須任何設定即可離線執行。要接個人設定時，複製範本：

```bash
cp config/spark.yaml.example config/spark.yaml             # 輸出目錄、Drive、RSS、收件 email
cp config/birth-profile.yaml.example config/birth-profile.yaml   # Spiritual 本命資料（含個資，勿提交）
```

| 想啟用的功能 | 設定方式 |
|---|---|
| Google Drive 上傳 / Gmail 寄送 | 設環境變數 `GOOGLE_APPLICATION_CREDENTIALS` 指向 service-account JSON，並實作 `core/dispatch/`（目前為 stub） |
| Spiritual 收件 email | `config/spark.yaml` → `spiritual.notify_email` |
| Spiritual 本命資料 | `config/birth-profile.yaml`（已 gitignore） |
| Global RSS 來源 | `config/spark.yaml` → `global.rss_feeds` |

> 🔒 個人資料（本命設定、email、Drive ID）一律走 config / 環境變數，**不寫在原始碼裡**。

---

## 設計系統

- **主色**：海軍藍 `#0F172A` + 典雅金 `#C5A059` + Slate 灰階（單一真相來源：`core/design_tokens.py`）
- **燈號**：🟢 進場 `#16A34A` / 🟡 觀望 `#CA8A04` / 🔴 減碼 `#DC2626`
- **網格**：A4、左右邊距 24pt、可列印寬 **547pt**；標準 4 欄表格 `[65,125,100,257]`
- **字型**：CJK（Noto Sans TC）為主，拉丁/數字可選用 Liberation Sans（`en()` 雙字型切換 + XML 跳脫）
- 各報告的「分節色盤」（市場/領域/五術）定義在各自的 `pdf_generator.py`，刻意保持差異以區分主題。

---

## 路線圖（P2 — 真實資料層）

目前三份報告在缺少 API key 時使用 sample data。規格書（各資料夾的 `*_Spec.md`）已寫好下列接點，待實作：

- **Financial**：TWSE（已接，免 key）、FRED（`DGS10/DGS2/T10Y2Y`，需 key）、Yahoo/FinMind 行情
- **Global**：RSS 智庫摘要 + LLM（Gemini/Claude）三段式摘要（What/Why/So What）
- **Spiritual**：Swiss Ephemeris（`pyswisseph`）真實流日引擎 + Gemini 五維度 persona 導引

接上時只要覆寫對應 scheduler 的 `fetch_data()`；pipeline 與排版無需改動。

---

## 附註

- 本專案進場時，多數 `.py` / `.md` 其實是被冠錯副檔名的 `.docx` 二進位檔，已全數還原為真實純文字（6 個 `.py` 通過 `py_compile`）。原始 Word 檔備份在本機 `_docx_backup/`（已 gitignore），確認無誤後可刪除。
- 詳細規格見各資料夾的 `*_Design_Spec.md` / `*_API_and_Code_Spec.md` / `*_Cloud_Architecture_Spec.md`。
