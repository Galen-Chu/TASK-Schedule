每日產業局勢報告 — 介面排版與設計規格文件 (Design Specification)
1. 頁面配置與容器規格 (Page Setup & Container Specifications)
頁面尺寸 (Page Size): 標準 A4 (210mm x 297mm)
頁面邊距 (Document Margins):
上邊距 (Top Margin): 18 pt (~6.3 mm)
下邊距 (Bottom Margin): 18 pt (~6.3 mm)
左邊距 (Left Margin): 24 pt (~8.5 mm)
右邊距 (Right Margin): 24 pt (~8.5 mm)
版面容器與卡片內邊距 (Card Padding & Spacing):
頂部 Banner 內距 (Top Banner Padding): 5 pt
分類標籤 (Category Badge) 內距: 2.5 pt
摘要卡片 (Executive Summary Box) 內距: 5 pt
新聞焦點卡片 (Topic Container Card) 內距: 4 pt 上下, 6 pt 左右
卡片外間距 (Spacing Between Cards): 4 pt

2. 共有主視覺配色系統 (Master Visual Palette)
整份報告建立統一的智庫級品牌視覺系統，並輔以五大領域專屬分類色：
2.1 品牌核心共有配色 (Master Brand Colors)
主品牌色 (Master Obsidian Navy): #0F172A （用於頂欄背景、標題文字、內文強標）
品牌輔助色 (Master Champagne Gold): #C5A059 （用於頂欄 Logo 文字、分割線、Footer 標示）
邊框與分隔線 (Master Border & Rules): #E2E8F0（卡片外框）、#CBD5E1（摘要框線）
通用內文文字色: #1E293B（深灰，極佳可讀性，避免純黑生硬）
2.2 五大領域專屬分類配色 (Domain Accent Themes)
領域代碼與名稱
分類徽章背景 (Badge BG)
特色邊條 (Accent Stripe)
卡片底色 (Card BG)
摘要底色 (Summary BG)

01. 地緣政治與國際關係
帝國深藍 #1B365D
深緋紅 #A22C2C
冰藍灰 #F3F6FA
明亮藍 #E8EEF5

02. 巨觀經濟與金融市場
翡翠墨綠 #0F4C3A
資本綠 #2E7D32
綠意淡彩 #F2F8F4
薄荷綠 #E8F5E9

03. 資訊科技與人工智慧
科技深靛藍 #1A237E
霓虹青藍 #0284C7
科技冷藍 #F0F4FF
藍靛彩 #E0E7FF

04. 生物科技與健康醫療
醫學深孔雀綠 #004D40
活力翡翠 #059669
醫學淡綠 #F0FDF4
清新綠 #E6F4EA

05. 硬體工程、自動化與能源轉型
暖炭工業黑 #262626
電力太陽橘 #D97706
暖灰卡片 #FAF8F5
暖金底 #FEF3C7

3. 全內嵌式雙字型排版系統 (Embedded TrueType Font Specifications)
為徹底修復雲端檢視器（如 Google Drive / Chrome PDF Viewer）之亂碼問題，採用 全內嵌 TrueType 複合字型系統 (Embedded TrueType Font Subsetting)：

核心字型引擎: PerfectCJK.ttf (Regular) 與 PerfectCJK-Bold.ttf (Bold)
字型技術: 由 fontTools 融合 LiberationSans 之 ASCII 數字英文字形輪廓 (glyf) 與 DroidSansFallbackFull 之 CJK 繁體中文字形輪廓，具備 100% 內嵌性。
字級與行高規範 (Font Size & Leading):
主標題 (Master Banner Title): 10.0 pt, leading 13 pt (Bold, #C5A059 / White)
分類大標題 (Category Title): 11.5 pt, leading 15 pt (Bold, #0F172A)
分類徽章 (Category Badge): 8.0 pt, leading 10 pt (Bold, White)
今日摘要 (Summary Text): 8.5 pt, leading 12.5 pt (#0F172A)
焦點標題 (Topic Title): 9.5 pt, leading 13 pt (Bold, #0F172A)
元數據標示 (Metadata Line): 8.0 pt, leading 11 pt (#334155)
內文 (What / Why / So What): 8.2 pt, leading 11.8 pt (#1E293B)
頁尾註腳 (Footer Note): 7.5 pt, leading 10 pt (#64748B)

4. 多語文標點與括號排版規範 (Multilingual Punctuation & Bracket Rules)
半形字元強制轉換: 所有西元年分、日期、時間、百分比與機構英文縮寫（如 2026-08-11 09:00 EDT、3.50%–3.75%、CSIS、TSMC）嚴格強制轉換為半形 ASCII 字元。
專有名詞括號標準: 統一採用「中文詞彙 ＋ 1 格半形空格 ＋ (半形英文縮寫)」，如 台積電 (TSMC)、聯準會 (Fed)。
中英文呼吸間距: 中文漢字與半形英文/數字之間自動加入 1 個半形空格（如 2026 年 8 月 11 日、AI 算力）。
標點符號全半形分流:
中文內文句中：統一採用全形中文標點（：、，、。）。
英文、數字、時間與網址：統一採用半形 ASCII 標點（:, ,, ., -, %）。

5. 超連結與二行化元數據對齊規格 (Two-Row Metadata & Link Alignment)
獨立二行化排版架構 (Two-Row Metadata):
第一行 (Row 1): 📍 報導來源：&nbsp;&nbsp;<a href="URL" color="#0284C7"><u><b>Source Name</b></u></a>
第二行 (Row 2): 🕒 發布時間：&nbsp;&nbsp;2026-08-11 09:00 EDT
設計效益: 給予超長機構名稱/網址完整的單行橫向空間，徹底解決擠壓發布時間致使文字溢出內文框的問題。
超連結底線隔離規格:
於 📍 報導來源： 全形冒號後插入非換行空格 &nbsp;&nbsp;，底線標籤 <u> 僅包含經 strip() 清除前後空格的媒體名稱，確保藍色底線 100% 從媒體名稱第一個字元開始劃記，絕不重疊前方的冒號標點。

6. 內容結構與檔名輸出規範 (Content & Output Specifications)
輸出檔名與雲端標題: YYYY-MM-DD_Global_Intelligence_每日產業局勢報告.pdf
頁數與飽滿度: 標準 5 頁 A4，每頁對應 1 個主題領域，頁面高度充實率達 85%–95%。
每領域 4 份核心報告結構 (4 Core Topics per Domain):
2 份國外智庫/國際權威媒體 (2 International Think Tanks / Global Outlets)：如 CSIS, The Conference Board, ECB, FDA, US DOE, Stanford SETR 等。
2 份國內智庫/台灣權威機構 (2 Domestic Taiwan Think Tanks)：如 中華經濟研究院 (CIER), 台灣經濟研究院 (TIER), 工研院 (ITRI), 資策會 (MIC), 國防院 (INDSR), 國衛院 (NHRI), 國研院 (NARLabs), 生技中心 (DCB) 等。
交付與擴充機制:
Google Drive 自動歸檔: 每日 07:00 AM 自動上傳 PDF 至 Global_Intelligence 資料夾。
Gmail 寄送: 已停用。
Obsidian Vault 擴充 (Phase 2): 相容 obsidian_writer.py 模組，可同步精簡摘要至 Daily/YYYY-MM-DD.md 與 Awareness/Daily-Transit/YYYY-MM-DD.md (Wikilinks)。
