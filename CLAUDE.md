# TASK-Schedule 開發指南（Claude Session 接續用）

雲端排程每日報告系統：三份 7 頁 A4 PDF（Financial / Global / Spiritual），
GitHub Actions 每日 07:30 台北（23:30 UTC）產出，共用 `core/` 核心
（ReportLab 排版、RSS 檢索語料庫、Gemini 選用增強、統一設計 token）。
詳細規格見 README.md 與各報告資料夾的 `*_Spec.md`。

## 當前狀態（2026-09-08 更新）

- 2026-09-08 第二波（晚）：
  * **紫微本命全盤**——`natal.ziwei_chart()` 十四主星全盤（五行局算術法、
    安紫微訣借數奇退偶進、天府寅申軸鏡像、紫微系逆行/天府系順行；規則
    以 iztro 安星訣＋福山堂例題交叉驗證，Galen 盤=土5局命宮丙戌〔巨門〕、
    紫貪同宮酉/武破同宮巳）。本命對照卡顯示全盤＋流日落宮主星。
  * **五維度論述＋三段式改 LLM 生成**——`llm.spiritual_system_brief()`
    依「流日×本命」逐系統生成（max_tokens=2400；缺欄位→整頁保留樣板，
    標題「AI 依流日×本命生成」vs「編輯樣板」分明）；7 呼叫/日仍在額度內。
  * **TAIFEX 期貨 OI 結論**——官方頁 futContractsDate 表單由 JS 動態構建
    （僅 pstring token），opendata API 不存在、data.gov.tw 無直接 CSV：
    keyless 抓取不可行，futures_net_oi 維持 None/待補（誠實呈現）；要補
    需瀏覽器級抓取，屬後續評估。
  * **feed 替換**——IEEE Spectrum 半導體 feed（7-12 天一篇）→
    EE Times（每日、純半導體）＋ Semiconductor Engineering（產業深度）；
    權重 1.2。TrendForce/鉅亨 RSS 不可達。
  * CI「產生兩次」虛驚：dispatch 補跑（#91）被 4 分鐘後的 push（#92）
    cancel-in-progress 取消，殘留 249KB 半成品 artifact（14 天自動過期）。
- 原路線圖 A~H+E 全數完成（檢索層 Phase 1-3、NFP、跨域摘要 G、方案 C 分頁、
  P1 新聞多樣化、P5 六商品+走勢圖、七術向量圖示、交易判斷橫幅）。
- 2026-09-08 內容誠實化五件套：
  ① **Global published 一條龍**——`fetch_rss_items` 現在帶回 `published/
  updated`（此前語料 1483 筆全空、時效全靠 fetched_at），`retrieve` 的
  年齡過濾與 recency 以 published 優先（見地雷 9）。舊語料無 published
  者依 fetched_at 計齡、7 天窗口自然代謝。
  ② **Financial B案**——「當前數據」欄全部接真源（^GSPC/^IXIC/^SOX/JPY=X/
  TWD=X/^TWII、TWSE T86 三大法人、FRED 高收益 OAS、Treasury 上月回溯列）；
  signal_score 永遠重算（樣本 72 曾與實算 60 同報告矛盾）；KPI 標籤隨值
  變動；監控表燈號接 `_market_verdicts`；Yahoo 斷線值標「（樣本）」；
  futures_net_oi 無源→None 不計分；F&G 正名加密市場版；`&amp;` 雙重
  轉義一併修（顯示層字串一律寫裸 `&`，href 屬性內才手動轉義）。
  ③ **Spiritual 基準與座右銘**——頁首標流日基準（報告日 12:00 台北）；
  motto＝固定核心金句＋「今日錨點」關鍵詞（與 spotlight 同源，見
  `divination.motto_keywords` docstring 的資料流說明）。
  ④ **轉換點偵測**——`divination.transitions()` 比較 date±1：行星換座／
  HD 換閘／節氣換月柱，頁面以 ◆ 徽章呈現（紫微四化逐日輪替、梅花六爻
  塔羅逐日起卦，無跨日連續性，不在偵測列）。
  ⑤ **本命分區**——每系統頁新增【個人本命對應】卡（示範本命 Galen
  1995-04-15 12:52 澎湖，`core/data/natal.py`）；七術引擎全面正統化：
  HD 真實曼陀羅（閘41=寶瓶2°、閘N=易經N卦；Galen 回推 5/1 交叉驗證）、
  紫微正統十天干四化表、梅花年月日時起卦、六爻通用爻位釋義、卦名改
  (上卦,下卦) 顯式表。
- 2026-09-07：修復 Electrek 等 WordPress 全文 RSS 的「截斷 HTML 殘骸」炸掉
  ReportLab（週末潛伏、週一語料排名洗牌才選中引爆；見地雷 8）——文字一律
  先過 `core.text_clean.strip_html()` 再截斷，語料已全量清理並每日自癒。
- 2026-09-04：修復 Yahoo `^VIX` 限流導致排程失敗——抓取加 query1→query2
  鏡像備援、決策欄位（vix/dxy/spread/融資/恐貪）缺值改 None→「數據待補」
  而非靜默沿用樣本（見地雷 7）、快照測試改 ≥9/14 軟門檻。
- 未來候選項盤點在 **README.md「未來評估開發項目」**（A 設定即用／B 中期／
  C 長期／D 維運觀察）——接續開發先讀那一節。下一步最自然：五維度論述
  與三段式導引改由 LLM 依「流日×本命」生成（現為通用編輯樣板）。

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
7. **決策欄位缺值要「可見失敗」**：verdict/訊號分的輸入（vix/dxy/
   spread_10y2y/tw_margin/fear_and_greed）抓不到時 scheduler 一律設 None
   → 報告顯示「數據待補」，**不可靜默沿用 sample**（2026-09-04 ^VIX 被
   Yahoo 限流，樣本 28.4 會偽造恐慌買點、當日實值僅 ~14）；展示型欄位
   （gold/btc/t10/tws…）仍可退回 sample。Yahoo 抓取已加 query1→query2
   鏡像備援（`_yahoo_chart`），`test_market_snapshot_or_skip` 為 ≥5/8
   符號軟門檻——單一符號缺席屬正常第三方行為，不是 CI 失敗。
8. **RSS 摘要是原始 HTML，截斷前必先消毒**：WordPress 全文 feed
   （Electrek/SpaceNews/QuantumInsider）的 summary 帶完整標籤；任何截斷
   （store 的 `[:500]`、卡片的 `[:200]`）都可能切在標籤中間，未閉合殘骸
   過得了 `<[^>]+>` 剝除、又被 `en()` 黏進 `<font>` 包裹躲過轉義 →
   paraparser「invalid attribute name」炸掉整份報告（2026-09-07；地雷在
   語料躺 5 天、等 BM25 排名洗牌把它選進卡片才引爆）。規則：外部文字
   一律先 `core.text_clean.strip_html()` 再截斷；`en()` 的 `_LATIN_RUN_RE`
   字元類別**不可**含 `<`/`>`（會把殘骸黏進 font 標籤內）；語料由
   `sanitize_summaries()` 維持純文字（`compact()` 每日自癒）。
9. **時間基準要同源：顯示用什麼欄位，篩選/排序就用什麼欄位**：2026-09-08
   前語料的「時效」全靠 `fetched_at`（我們幾時抓到），卡片卻顯示
   `published`——而 fetcher 根本沒帶 published（1483 筆全空），導致一週
   前舊文天天以「新鮮」身分入選。規則：`fetch_rss_items` 必帶
   `published/updated`；`retrieve._age_days` 以 published 優先、無則退
   fetched_at；新增任何時間欄位時，顯示端與過濾端必須掛同一個來源。
   另：排程器用到的新 fetcher 記得加進檔頭 import——NameError 會被
   BaseReportScheduler 的 catch-all 吃掉、整份報告靜默退回全樣本
   （2026-09-08 fetch_twse_institutional 實例，日志只有一行 WARNING）。

## 接下來最可能做的事（2026-08-27 盤點摘要）

- 設定即用：Drive 上傳（GCP_SA_KEY/DRIVE_FOLDER_ID）、BLS_API_KEY、本機 Gemini key
- 中期：H 報表歷史對比（pymupdf 已裝）、Global 徽章對比統一、域分類調校、
  易經卦象大圖、P5 白銀/銅走勢圖
- 長期：I 互動 Dashboard、J 多租戶、檢索層 remote store
- 維運：cron 23:30 可靠性觀察、LLM 額度、artifact 14 天保留

細節與前置條件見 README.md 路線圖與「未來評估開發項目」區塊。
