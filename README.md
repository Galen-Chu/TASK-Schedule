# Gemini-Spark-Schedule

雲端排程每日報告系統 —— 每天清晨自動產生三份 A4 PDF 戰情報表（搭配 Obsidian 筆記與雲端分派），以 ReportLab 排版、由共用核心驅動，可在本機或 GitHub Actions 雲端排程執行。

> 三份報告共用一套設計系統（海軍藍 + 典雅金主色、A4 547pt 網格、雙字型中文/拉丁排版、燈號系統），各自擁有獨立的「分節色盤」與版面模板。

---

## 三份報告

| 報告 | 內容 | 排程（Asia/Taipei） | 版面風格 |
|---|---|---|---|
| **Financial Intelligence** | 每日投資趨勢：台股融資維持率、美股 VIX、美債殖利率、外匯、商品/加密，含進出場訊號與資產配置矩陣 | `30 6 * * *`（06:30） | Bloomberg 風格量化儀表板（5 頁） |
| **Global Intelligence** | 每日全球情報：5 大領域智庫焦點速讀（地緣、總經、AI/半導體、生技、硬體/能源） | `30 6 * * *`（06:30） | 智庫級 4 欄表格速讀（5 頁） |
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

## 資料來源

每份報告都「能免 key 就接真實資料，缺 key / 失敗就優雅退回 sample」，所以 CI 無 secret 也能端到端跑。

| 報告 | 真實來源 | 免 key？ | 缺來源時 |
|---|---|---|---|
| **Financial** | Yahoo Finance（VIX / DXY / 黃金 / BTC / 原油） | ✅ | 退回 sample |
| **Financial** | 美國財政部每日殖利率曲線 CSV（2Y / 10Y / 利差） | ✅ | 退回 sample |
| **Financial** | Fear & Greed 指數（alternative.me） | ✅ | 退回 sample |
| **Financial** | TWSE 大盤融資維持率 | ✅ | 退回 sample |
| **Global** | RSS 即時快訊（BBC World 等）→ 寫進 Obsidian note | ✅（需 `feedparser`） | note 標示離線 |
| **Spiritual** | Swiss Ephemeris（`pyswisseph`）算當日太陽/月亮/水星真實位置 | ✅（需 `pyswisseph`） | 退回 sample 五術資料 |

> 三份報告現在 **完全零 key**——沒有任何欄位需要 API key，CI 無 secret 即可跑真實資料。

### 還沒接的（屬路線圖 B）
- **LLM 摘要/導引**（Global 三段式 What/Why/So What、Spiritual 五維度）：需 `GEMINI_API_KEY`，目前用編輯樣板。
- **總經日曆**（CPI / 非農 / Core PCE）：PDF 第 3 頁目前為編輯固定值，這類月頻總經數據接進去價值有限。

---

## 路線圖

- **B（未來）**：統一檢索層 —— 跨多來源搜尋/排序/刪重，再餵給各報告。對 Global（多智庫來源篩選）最有價值，接近 RAG 架構。
- Drive 上傳 / Gmail 寄送：實作 `core/dispatch/`（接 `google-api-python-client` + `GOOGLE_APPLICATION_CREDENTIALS`）。

---

## 進階資料層（已實作）

### Spiritual — 五術真實計算
`core/data/divination.py` 每日計算全部五術（皆免 key）：
- **西洋占星**：Swiss Ephemeris（`pyswisseph`）算太陽/月亮/水星黃道位置與相位 orb。
- **人類圖**：太陽黃經 → 64 閘門 Mandala 對應 + 動爻。
- **紫微斗數**：`lunar_python` 日支定位流日命宮 + 干支輪轉四化。
- **八字**：`lunar_python` 取當日干支（年/月/日柱）+ 五行動能。
- **梅花易數**：太陽黃經取上下卦 + 日序取動爻，得當日卦象。
任一術算不出就保留該頁靜態樣板。

### LLM 敘事增強（Gemini，key 選用）
`core/llm.py` 用官方 `google-genai` SDK。設 `GEMINI_API_KEY` 後：
- **Global**：RSS 即時快訊 → Gemini 萃取 **What / Why / So What** 三段摘要，印成 PDF 第 1 頁「AI 智庫摘要」卡。
- 缺 key / 套件未裝 / API 失敗 → 一律自動退回編輯樣板（CI 即走此路徑）。

### Monthly Macro Digest（Financial，月度排程）
與每日報告**不同節奏**的第二條 Financial 排程：
- **每日** `30 6 * * *`（06:30 台北）：行情報價 + signal score（盤中/價格資料）。
- **月度** `0 9 2 * *`（每月 2 號 09:00）：結構性總經指標（CPI / Core CPI / 失業率 / NFP / 殖利率曲線），來自免 key 的 BLS + 美國財政部。

月度排程產出 `Monthly_Macro_Digest.pdf`（1 頁計分卡）。執行：`python main.py macro`。

### Google Drive 上傳（service account，選用）
每份報告的 PDF 自動上傳到 Drive——一個根資料夾下，每份報告各自的子資料夾（Financial / Global / Spiritual / Macro）。缺憑證時安全略過（CI 即如此）。

**設定步驟**（service account，最適合無人值守排程）：
1. 到 [Google Cloud Console](https://console.cloud.google.com/) 建專案，啟用 **Google Drive API**。
2. 「IAM 與管理 → 服務帳戶」建立一個 service account，下載 **JSON 金鑰**。
3. 在 Google Drive 建一個資料夾，把 service account 的 email（如 `xxx@yyy.iam.gserviceaccount.com`）加為**編輯者**。
4. 設環境變數：
   - `GOOGLE_APPLICATION_CREDENTIALS` = 金鑰 JSON 的路徑
   - 在 `config/spark.yaml` 設 `drive_folder_id`（資料夾 URL 中 `folders/` 後面那段 ID）
5. GitHub Actions：把金鑰 JSON 內容存成 Secret `GCP_SA_KEY`，workflow 寫成檔案再設環境變數（見 workflow 註解）。

> 排程自動在根資料夾下建立/重用 `Financial`、`Global`、`Spiritual`、`Macro` 四個子資料夾。

---

## Docker

提供 `Dockerfile`，可在本機或雲端容器內跑完整 pipeline：

```bash
docker build -t spark-schedule .
docker run --rm -v "$PWD/output:/app/output" -v "$PWD/fonts:/app/fonts" spark-schedule all
docker run --rm -e GEMINI_API_KEY=... -e GOOGLE_APPLICATION_CREDENTIALS=/key.json -v ... spark-schedule all
```

映像檔基於 `python:3.11-slim`，預裝字型（fonts-noto-cjk）與所有相依套件。

## 測試

```bash
pip install pytest
pytest -q          # 模組測試 + 煙霧測試（三份日報 + macro 產 PDF、頁數正確）
```

CI 會在 push / PR 時自動跑 pytest。

---

## 附註

- 本專案進場時，多數 `.py` / `.md` 其實是被冠錯副檔名的 `.docx` 二進位檔，已全數還原為真實純文字（6 個 `.py` 通過 `py_compile`）。原始 Word 檔備份在本機 `_docx_backup/`（已 gitignore），確認無誤後可刪除。
- 詳細規格見各資料夾的 `*_Design_Spec.md` / `*_API_and_Code_Spec.md` / `*_Cloud_Architecture_Spec.md`。
