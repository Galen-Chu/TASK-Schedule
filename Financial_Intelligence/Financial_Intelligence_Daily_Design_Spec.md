# Financial Intelligence 每日投資趨勢報告 — 視覺設計與 PDF 排版規格書 (Design Specification)

## 1. 視覺設計定位與核心原則 (Design Philosophy)
本系統設計旨在打造符合 Bloomberg Terminal 與頂尖投研機構（Morgan Stanley, Goldman Sachs）水準的 **量化決策儀表板**。排版強調數據高對比度、資訊層級清晰、無懸掛斷字，並以雙字型系統解決中英文數字並存時的視覺和諧性。

---

## 2. 版面佈局與網格規範 (Page Grid & Layout System)
- **紙張規格**：標準 A4 (`210mm x 297mm` / `595.27pt x 841.89pt`)。
- **頁面邊界 (Margins)**：
  - 上邊界 (`topMargin`)：`28pt` (移除頂部深色 Header，開啟明亮視野)。
  - 下邊界 (`bottomMargin`)：`42pt` (留給 Footer 免責聲明與頁碼)。
  - 左右邊界 (`left/rightMargin`)：`24pt` (可列印寬度: `547.27pt`)。
- **標題列排版 (Title Block)**：
  - 採用雙欄緊湊 Table，左側置放主標題，右側靠右貼齊發布日期與版本號（如 `發布日期：2026-08-10 | v1.5`）。

---

## 3. 五大投資市場專屬色彩系統 (5 Asset Market Color Tokens)

| 市場類別 | 色彩名稱 | Hex 色碼 | 視覺意義與應用場景 |
| :--- | :--- | :--- | :--- |
| **主視覺標頭** | **海軍深藍 (Primary Navy)** | `#0F172A` | 報告主標題、全區標頭、總覽卡片 |
| **主視覺強調色** | **典雅金 (Accent Gold)** | `#C5A059` | 頁首分隔線、評級 Banner 邊框 |
| **1. 台股市場** | **熾緋紅 (Taiwan Crimson)** | `#DC2626` | 代表台股大盤、融資維持率與三大法人籌碼 |
| **2. 美股市場** | **華爾街藍 (Wall Street Navy)** | `#1E40AF` | 代表美股四大指數、VIX 與市場廣度 |
| **3. 全球債券** | **避險琥珀金 (Bond Amber)** | `#D97706` | 代表美債殖利率、倒掛利差與信用利差 |
| **4. 外匯與美元** | **匯市翡翠綠 (Forex Emerald)** | `#059669` | 代表美元指數 (DXY) 與新台幣匯率 |
| **5. 商品與加密** | **前沿紫羅蘭 (Crypto Violet)** | `#7C3AED` | 代表黃金、原油與比特幣鏈上數據 |

---

## 4. 進出場決策訊號燈號 (Signal Badge Palette)
- 🟢 **進場 / 加碼 (Buy / Accumulate)**：`#16A34A` (Emerald Green)
- 🟡 **觀望 / 持股 (Hold / Neutral)**：`#CA8A04` (Warm Amber)
- 🔴 **減碼 / 避險 (Reduce / Risk-Off)**：`#DC2626` (Bright Red)

---

## 5. 雙字型系統與 XML 轉義防呆 (Dual-Font & Sanitization Spec)
- **中文字型**：`DroidSansFallback`（完整支援 Traditional Chinese 繁體中文）。
- **英數/符號字型**：`LiberationSans` (Regular) / `LiberationSans-Bold` (Bold)。
- **XML 轉義規範**：所有數據與文字輸入必須經過 `en(text)` 轉義，強制將 `&` 轉為 `&amp;`，`<` 轉為 `&lt;`，`>` 轉為 `&gt;`，徹底消除 ReportLab PDF 繪製與文字解析錯誤。

---

## 6. 四欄式表格縱向對齊網格 (Table Alignment System)
全報告 Page 2 至 Page 5 之 4 欄式表格統一採用固定欄寬網格：
- **Col 1 (領域/類別)**：`65pt`
- **Col 2 (標的名稱/指標)**：`125pt`
- **Col 3 (策略/當前數據)**：`100pt`
- **Col 4 (核心理由/分析)**：`257pt`
- **總寬度**：`547pt` (精準填滿 A4 可列印區塊)。
- **對齊與 Padding**：`VALIGN = MIDDLE`，內部垂直 Padding `5pt`。
