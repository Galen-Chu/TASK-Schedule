# TASK-Schedule 開發指南（Claude Session 接續用）

雲端排程每日報告系統：三份 7 頁 A4 PDF（Financial / Global / Spiritual），
GitHub Actions 每日 07:30 台北（23:30 UTC）產出，共用 `core/` 核心
（ReportLab 排版、RSS 檢索語料庫、Gemini 選用增強、統一設計 token）。
詳細規格見 README.md 與各報告資料夾的 `*_Spec.md`。

## 當前狀態（2026-08-31 更新）

- 原路線圖 A~H+E 全數完成（檢索層 Phase 1-3、NFP、跨域摘要 G、方案 C 分頁、
  P1 新聞多樣化、P5 六商品+走勢圖、七術向量圖示、交易判斷橫幅）。
- 2026-08-31：修復 LLM 空回應根因（flash-lite 思考預算吃掉 max_output_tokens，
  見地雷 5）＋ Global 新聞卡與 P1 摘要改 GIVEN-WHEN-THEN 三欄帶標籤呈現
  （Financial/Spiritual 不變）；92 tests 全綠、7-7-7 驗證通過。
- 未來候選項盤點在 **README.md「未來評估開發項目」**（A 設定即用／B 中期／
  C 長期／D 維運觀察）——接續開發先讀那一節。

## 常用指令

```bash
python main.py all            # 產三份報告到 output/
python main.py financial      # 單份；--date / --output-dir 可用
python main.py --stats        # 語料庫健康度（feed 活躍度/領域分布/未分類樣本）
python main.py --reclassify   # 以現行關鍵字重分類語料
python -m pytest -q           # 全測試（~40s；含三份報告煙霧測試）
python scripts/fetch_fonts.py # 重建 fonts/ 靜態字型（見下方字型地雷）
```

## 地雷與慣例（血淚教訓，勿再踩）

1. **字型**：`fetch_fonts.py` 用 fonttools instancer 把 Noto TC 可變字型
   實例化為靜態 wght=400/700。ReportLab 遇 variable font 會嵌**預設實例
   （Thin）**，小字白字會趨近隱形。任何字面調整後，用 fontTools cmap 掃
   PDF 逐字符驗證零缺字（emoji 皆不在字集 → `en()` 的 `_map_emoji` 已自動
   映射成 ●▲→✓ 等安全字符；新增特殊符號先查 cmap）。
2. **ReportLab 圖表**：時間序列要用 `HorizontalLineChart`——類別軸在 X。
   `VerticalLineChart` 是「類別軸垂直」，圖會側躺（已修正，勿回頭）。
3. **CI 與 commit**：push 尖端 commit 的標題**與內文**都不可含 skip-ci 標記
   字樣；語料/快取（`data/`）的 chore commit 放中間，實質 commit 收尾。
   跑報告或測試都會 ingest 語料 → `git checkout` 切分支前先 commit `data/`。
4. **驗證慣例**：改版面後至少（a）全套件 pytest（b）`python main.py all`
   產出（c）頁數 = 7/7/7（d）pymupdf 抽文字/像素驗證重點區塊在新位置。
   本機已裝 pymupdf；宣稱「已完成」必須有本輪真實工具輸出佐證。
5. **LLM**：CI 有 GEMINI_API_KEY（gemini-flash-lite-latest，每日額度守門
   60 於 `data/llm_usage.json`）；本機未設 → 本機跑是無 LLM fallback 路徑。
   LLM 相關功能（Global GIVEN-WHEN-THEN 卡、跨域摘要卡）要看效果請看
   CI artifact；`generate()` 的 `max_tokens` **必須 > 思考下限 512＋內容**
   （flash-lite 思考 token 計入 max_output_tokens，2026-08-31 前上限
   420/600 太低 → 每次回空、功能從未渲染而 CI 全綠；已釘
   thinking_budget=512 並在空回應時 log.warning，新增呼叫點照此辦理）。
6. **開發流程**：feature branch → 測試+產出驗證 → 邏輯分層 commit →
   fast-forward merge main → push → 等 CI 綠 → 回報。使用者偏好繁中回報、
   重大變更先提方案。

## 接下來最可能做的事（2026-08-27 盤點摘要）

- 設定即用：Drive 上傳（GCP_SA_KEY/DRIVE_FOLDER_ID）、BLS_API_KEY、本機 Gemini key
- 中期：H 報表歷史對比（pymupdf 已裝）、Global 徽章對比統一、域分類調校、
  易經卦象大圖、P5 白銀/銅走勢圖
- 長期：I 互動 Dashboard、J 多租戶、檢索層 remote store
- 維運：cron 23:30 可靠性觀察、LLM 額度、artifact 14 天保留

細節與前置條件見 README.md 路線圖與「未來評估開發項目」區塊。
