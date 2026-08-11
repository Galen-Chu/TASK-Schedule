全球情報每日趨勢報告 — API 介面、數據 Schema 與程式碼開發規格書 (API & Code Specification)
1. 核心數據 Schema (OpenAPI 3.0 / Pydantic Models)
1.1 TopicItem (焦點新聞單項 Schema)
{

  "type": "object",

  "required": ["type_label", "title", "source_name", "pub_time", "url", "what", "why", "so_what"],

  "properties": {

    "type_label": {

      "type": "string",

      "enum": ["[外來智庫]", "[國內智庫]"],

      "description": "智庫來源分類"

    },

    "title": { "type": "string", "description": "新聞/報告焦點標題" },

    "source_name": { "type": "string", "description": "權威機構/智庫名稱" },

    "pub_time": { "type": "string", "example": "2026-08-10 09:00 EDT" },

    "url": { "type": "string", "format": "uri" },

    "what": { "type": "string" },

    "why": { "type": "string" },

    "so_what": { "type": "string" }

  }

}
1.2 ObsidianPayload Schema (Obsidian Vault 擴充 Schema)
{

  "type": "object",

  "required": ["date_str", "daily_summary", "transit_data", "mentor_analysis"],

  "properties": {

    "date_str": { "type": "string", "example": "2026-08-10" },

    "daily_summary": { "type": "string", "description": "當日 5 大領域精簡摘要" },

    "transit_data": { "type": "object", "description": "完整命理盤/行運數據 (Human Design & Transit)" },

    "mentor_analysis": { "type": "string", "description": "導師深度分析內容" }

  }

}

2. Python API 介面規格 (Module Interfaces)
2.1 Normalizer API (punctuation_normalizer.py)
def to_halfwidth(text: str) -> str:

    """將全形 ASCII 數字與字母強制轉換為標準半形 ASCII"""

def normalize_multilingual_text(text: str) -> str:

    """對中英文混合字串執行標點規範化、半形轉換與中英文間距 (1 空格) 修正"""

def format_latin_text(text: str, is_bold: bool = False) -> str:

    """將字串中英文字詞與數字包覆於 LiberationSans 字型標籤中，保持標點符號於 CJK 字型避免 PUA 碼"""
2.2 PDF Render Engine API (pdf_renderer.py)
def build_pdf_report(domains_data: list[dict], date_str: str, output_pdf_path: str) -> str:

    """

    依據設計規格渲染 5 頁 A4 PDF 報告。

    元數據排版採用獨立二行架構 (行 1: 報導來源 + 超連結; 行 2: 發布時間)。

    """
2.3 Obsidian Writer API (obsidian_writer.py - 後續擴充模組)
class ObsidianWriter:

    def __init__(self, vault_path: str):

        self.vault_path = vault_path

    def update_daily_note(self, date_str: str, summary_markdown: str, block_name: str = "## 🌐 全球情報觀測 (Global Intelligence)") -> bool:

        """

        將當日精簡摘要寫入 Daily/YYYY-MM-DD.md 之指定區塊

        """

    def create_transit_note(self, date_str: str, transit_data: dict, mentor_analysis: str) -> str:

        """

        將完整命理盤數據與導師分析另存至 Awareness/Daily-Transit/YYYY-MM-DD.md，

        並嵌入 Wikilink [[Daily/YYYY-MM-DD|YYYY-MM-DD Daily Note]] 回連。

        """
2.4 Workspace Integration API (workspace_integration.py)
def upload_to_google_drive(file_path: str, mime_type: str, title: str) -> dict:

    """呼叫 Google Drive API v3 上傳檔案並返回 fileId 與 webViewLink"""

def send_gmail_digest(to_email: str, subject: str, html_body: str, plain_body: str) -> dict:

    """呼叫 Gmail API v1 發送即時通知郵件"""
