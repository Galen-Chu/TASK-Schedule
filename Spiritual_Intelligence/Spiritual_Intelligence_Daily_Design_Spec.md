Spiritual Intelligence 系統視覺排版與設計規格書 (Design Specification)
一、 核心設計理念與視覺語彙
Spiritual Intelligence 每日覺察運勢報告係專為高密度自我覺察與工程化實踐打造的 A4 戰情報表。系統採用 「單頁單系統（Single Page, Single System）」 的樞紐結構（Pivot Swap），每一頁 A4 紙張承載一個命理系統（人類圖、西洋占星、紫微斗數、八字干支、梅花易數），並於每頁內部透過 五大維度（A/B/C/D/E）AI 導師視角 進行深度解讀。

全份文件遵循 「黃金滿頁比例（88%–92% 頁面涵蓋率）」 與 「高對比度卡片容器」 規範，確保字體閱讀舒展、版面和諧不緊湊。

二、 全報告統一品牌主標題色系與 5 系統主題配色
為建立跨頁面的統一品牌識別，頂部 Header 卡片統一套用 Master Brand Navy 品牌海軍石藍色系；同時，各命理系統保有其獨立之卡片、邊框與高亮色：

全報告 Master Header 主色：

背景填充：#F8FAFC (Slate Light Gray)
主標題字體：#0F172A (Master Slate Navy)
副標題字體：#334155 (Master Slate Blue)
底部分割線：#1E293B (Master Dark Slate Line)

五大命理系統專屬卡片配色：

頁碼與命理系統
色彩語意與風格
主色 (Primary)
次色 (Secondary)
背景色 (Card Fill)
警示/高亮 (Highlight)
深色文字 (Text Dark)

Page 1: 人類圖 (HD)
能量圖金赭色
#B86B14 (Amber Gold)
#D9822B (Warm Gold)
#FAF4EB (Cream Gold)
#8C2F00 (Crimson)
#331E0A

Page 2: 西洋占星 (Ast)
深穹星空藍
#1E3A8A (Deep Navy)
#3B82F6 (Celestial Blue)
#EFF6FF (Ice Sky)
#1D4ED8 (Sapphire)
#0F172A

Page 3: 紫微斗數 (ZW)
紫微帝星紫
#581C87 (Imperial Violet)
#8B5CF6 (Amethyst)
#FAF5FF (Violet Cream)
#7E22CE (Royal Purple)
#2E1065

Page 4: 八字干支 (Bazi)
五行翡翠綠
#065F46 (Jade Emerald)
#10B981 (Emerald Green)
#ECFDF5 (Jade Tint)
#047857 (Forest Emerald)
#022C22

Page 5: 梅花易數 (IC)
水墨硃砂紅
#78350F (Charcoal Bronze)
#D97706 (Vermilion Amber)
#FEF3C7 (Paper Cream)
#991B1B (Deep Vermilion)
#451A03

三、 TrueType 實體內嵌字型規格 (TrueType Embedded Font)
解決跨平台與跨 PDF 檢視器亂碼、缺字與英數字斷行問題：

TrueType 向量輪廓完全內嵌 (NotoSansTC_RealTrueType.ttf)：
透過 CFF 轉二次貝西爾曲線（Quadratic Glyf Outlines）技術，將完整字型輪廓數據直接寫入嵌入至 PDF 文件結構中 (/Subtype /TrueType)。
完整包含白名單：包含全套 ASCII 字母 (A-Z, a-z, 0-9, 全部標點符號如 Ziwei, Bazi, QA, Log)、破折號 ──、度數 °、圖示 (📍, 💡, 🎯) 與報告全部繁體中文字元。
無內聯標籤切換與 CJK 自然斷行 (wordWrap='CJK')：
不在 CJK 文字中嵌入 <font> 標籤，避免 ReportLab 建立樣式切換邊界，徹底消除 QA、29、10,000 後方的孤立換行問題。

四、 A4 單頁垂直卡片佈局與階層結構
每頁 A4 尺寸為 595.27 x 841.89 pt，邊距設定 24pt：

+-------------------------------------------------------------------+

| 1. Header Card (單行主標題、副標題、日期、地點； Master Navy 色系) |

|-------------------------------------------------------------------|

| 2. 【意識定錨座右銘卡片】 (~20–30 字哲理座右銘)                  |

|-------------------------------------------------------------------|

| 3. 【宇宙點名卡片】 (當日重大相位、流日閘門、飛星高亮)            |

|-------------------------------------------------------------------|

| 4. 【系統關鍵參數卡片】 (基礎命盤參數：類型、權威、日主等)         |

|-------------------------------------------------------------------|

| 5. 【五大維度深度覺察卡片】 (A/B/C/D/E 導師觀點解析)              |

|-------------------------------------------------------------------|

| 6. 【三段式結構導引卡片】 (📍 What / 💡 Why / 🎯 So What)          |

|-------------------------------------------------------------------|

| 7. 【系統綜合調和與心流指引卡片】 (將命理氣場融入 SGC 五階段作息) |

|-------------------------------------------------------------------|

| 8. Footer Line (系統來源 + Page X of 5 頁碼)                     |

+-------------------------------------------------------------------+
間距與容器參數：
卡片外間距 (Spacer)：8pt–12pt
卡片內邊距 (Padding)：6pt–7pt
文字行高 (Leading)：主標題 15pt，區塊標題 14pt，內文 11.8pt–12.5pt，頁面涵蓋率 88%–92%。
