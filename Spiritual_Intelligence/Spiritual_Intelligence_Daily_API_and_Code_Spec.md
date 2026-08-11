Spiritual Intelligence API 與程式碼開發規格書 (API and Code Specification)
一、 模組目錄結構與軟體架構
專案依據 Python 模組化規範劃分計算引擎、AI 解析器、PDF 報表與 API 調用元件：

spiritual-intelligence/

├── config/

│   └── birth-profile.yaml                          # SSOT 個人本命盤參數與設定

├── engines/

│   ├── __init__.py

│   ├── hd_engine.py                                # 人類圖流日計算引擎

│   ├── astrology_engine.py                         # 西洋占星相位計算引擎 (Swiss Ephemeris)

│   ├── ziwei_engine.py                             # 紫微斗數流日飛星模組

│   ├── bazi_engine.py                              # 八字干支與十神沖合模組

│   └── iching_engine.py                            # 梅花易數當日起卦模組

├── ai_brain/

│   ├── __init__.py

│   ├── prompt_templates.py                         # 五維度 Persona Prompt 模板

│   ├── spotlight_detector.py                       # 相位與通道點名觸發器 (Orb < 1.0°)

│   └── ttf_cjk_subsetter.py                        # TrueType 向量輪廓字型生成器

├── generators/

│   ├── __init__.py

│   └── pdf_generator.py                            # ReportLab 5 頁 A4 報表生成器 (v13)

├── dispatchers/

│   ├── __init__.py

│   ├── drive_uploader.py                           # Google Drive API v3 上傳模組

│   ├── email_dispatcher.py                         # [v1 Paused] Gmail API 郵件推送模組

│   └── obsidian_writer.py                          # [v2 Extension] Obsidian Vault 寫入模組

├── tests/

│   ├── test_engines.py                             # 命理計算單元測試

│   ├── test_pdf.py                                 # PDF 生成與內嵌字型驗證測試

│   └── test_dispatchers.py                         # Drive/Gmail 整合測試

├── cloud_daily_spiritual_report_scheduler.py       # Pipeline 5 主排程進入點

├── .env.example

├── Dockerfile

├── requirements.txt

└── README.md

二、 核心 Pydantic Schema 與資料模型
from pydantic import BaseModel, Field

from typing import List, Dict, Optional

class SystemTransitDetail(BaseModel):

    system_id: str                                  # SYS_HD, SYS_AST, SYS_ZW, SYS_BAZI, SYS_ICHING

    title: str                                      # 頁面主標題 (例如: Spiritual Intelligence 每日覺察運勢報告 ── 人類圖)

    subtitle: str                                   # 頁面副標題

    motto: str                                      # 【意識定錨座右銘】

    spotlight_alert: str                            # 【宇宙點名卡片】

    system_data_summary: str                        # 【系統關鍵參數】

    dimensions_analysis: List[Dict[str, str]]       # 五大維度深度覺察 (A/B/C/D/E)

    what_observation: str                           # 📍 覺察觀察 (What)

    why_logic: str                                  # 💡 轉化思維 (Why)

    action_anchors: List[str]                       # 🎯 定錨行動 (So What)

    harmony_flow_note: str                          # 【系統綜合調和與心流指引】

class DailyReportPayload(BaseModel):

    date_str: str                                   # 2026-08-11

    location_str: str                               # 臺北市大安區

    generated_at: str                               # 06:30 (UTC+8)

    systems: List[SystemTransitDetail]             # 5 個命理系統陣列

三、 TrueType CJK 向量字型轉換演算法 (ttf_cjk_subsetter.py)
為解決跨檢視器亂碼與英數字不預期換行，調用 fontTools 將 CFF 出樣點轉換為 TrueType glyf 二次貝西爾曲線輪廓：

import string

import fontTools.subset

from fontTools.ttLib import TTFont, newTable

from fontTools.pens.ttGlyphPen import TTGlyphPen

from fontTools.pens.cu2quPen import Cu2QuPen

def build_truetype_cjk_font(source_ttc_path: str, output_ttf_path: str, report_text: str):

    ascii_chars = string.ascii_letters + string.digits + string.punctuation + " °–—│……\u00a0\xa0\u2013\u2014"

    full_text = ascii_chars + report_text

    options = fontTools.subset.Options()

    options.flavor = None

    options.font_number = 0

    subsetter = fontTools.subset.Subsetter(options=options)

    subsetter.populate(text=full_text)

    font = TTFont(source_ttc_path, fontNumber=0)

    subsetter.subset(font)

    glyph_set = font.getGlyphSet()

    glyf_table = newTable('glyf')

    glyf_table.glyphs = {}

    for name in font.getGlyphOrder():

        pen = TTGlyphPen(glyph_set)

        cu2qu_pen = Cu2QuPen(pen, max_err=1.0)

        glyph_set[name].draw(cu2qu_pen)

        glyf_table.glyphs[name] = pen.glyph()

    if 'CFF ' in font:

        del font['CFF ']

    if 'VORG' in font:

        del font['VORG']

    font['glyf'] = glyf_table

    font['loca'] = newTable('loca')

    font.sfntVersion = '\x00\x01\x00\x00'

    # Rebuild maxp table

    maxp = font['maxp']

    maxp.tableVersion = 0x00010000

    maxp.numGlyphs = len(font.getGlyphOrder())

    font.save(output_ttf_path)

    print(f"TrueType vector outline font successfully built at: {output_ttf_path}")
