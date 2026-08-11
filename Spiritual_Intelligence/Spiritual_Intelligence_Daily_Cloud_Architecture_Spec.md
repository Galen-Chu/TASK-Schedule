Spiritual Intelligence 雲端架構與系統設計規格書 (Cloud Architecture Specification)
一、 系統架構圖 (SGC Pipeline 5 Architecture)
系統銜接 personal-automation 排程專案與 SGC Stack，採用 「Hook 觸發、Runner 編排、計算引擎獨立、AI 導師解讀、雲端多管道推送」 的分層微服務架構：

+-------------------------------------------------------------------------+

| Layer 1: Trigger / Hook Layer                                           |

| - Cron / systemd timer (Daily 06:30 AM Asia/Taipei)                      |

| - On-Demand CLI / FastAPI Webhook                                       |

+-------------------------------------------------------------------------+

                                    │

                                    ▼

+-------------------------------------------------------------------------+

| Layer 2: Pipeline Runner & Configuration                                 |

| - cloud_daily_spiritual_report_scheduler.py                             |

| - config/birth-profile.yaml (SSOT Natal Parameters)                    |

+-------------------------------------------------------------------------+

                                    │

                                    ▼

+-------------------------------------------------------------------------+

| Layer 3: Calculation Engines (Pure Deterministic Python Code)          |

| - pyswisseph / Swiss Ephemeris C-Extension                              |

| - HD Transit Engine (Gates/Lines, Transit Channels, Open Centers)       |

| - Astrology Engine (Transit vs Natal Aspect, Orb < 1.0° Trigger)        |

| - Ziwei Engine (Daily Palace & Four Transformations)                    |

| - Bazi Engine (Daily Pillar & Ten Gods Relationships)                   |

| - Mei Hua Engine (Daily Hexagram & Trigram Interactions)                |

+-------------------------------------------------------------------------+

                                    │

                                    ▼

+-------------------------------------------------------------------------+

| Layer 4: AI Synthesis & Persona Engine (Gemini Pro / Flash)            |

| - 5 Dimensions Persona Matrix (A/B/C/D/E)                               |

| - Spotlight Trigger ("宇宙正在為你點名...")                              |

| - Single CJK TrueType Outline Font & CJK WordWrap Alignment             |

+-------------------------------------------------------------------------+

                                    │

                                    ▼

+-------------------------------------------------------------------------+

| Layer 5: Output & Distribution Layer                                    |

| - pdf_generator.py (ReportLab 5-Page A4 Engine)                         |

| - drive_uploader.py (Google Drive API v3 -> Upload & Sharing Link)       |

| - [v1 Optional] email_dispatcher.py (Gmail API - Currently Paused)      |

| - [v2 Extension] obsidian_writer.py (Obsidian Vault Write-back)         |

+-------------------------------------------------------------------------+

二、 執行環境與容器化設計 (Execution Environment & Docker)
基礎設施與環境：
系統運行於 Docker 容器環境（基於 python:3.11-slim 映像檔）。
預裝必要 C-Extension 依賴（如 swisseph, reportlab, pydantic, fontTools, google-api-python-client）。
金鑰與憑證安全管理 (.env)：
憑證文件與 API 金鑰一律禁止進入 Git 版控：
.env（管理 GEMINI_API_KEY, GOOGLE_DRIVE_FOLDER_ID）
credentials.json 與 token.json（Google OAuth 2.0 / Service Account Credentials）
無狀態與靜態分離原則：
pipelines/ 與 runner/ 為純程式碼進入 Git。
生成之 PDF 臨時檔（命名：YYYY-MM-DD_Spiritual_Intelligence_每日覺察運勢報告.pdf）於 /tmp/ 處理，完成 Drive 上傳後自動清理，不留佇留狀態。

三、 Google API 整合架構 (Drive API v3)
目標資料匣：Spiritual_Intelligence/Daily_Reports/YYYY-MM/
檔案規格：YYYY-MM-DD_Spiritual_Intelligence_每日覺察運勢報告.pdf (application/pdf)
權限管理：自動對文件設定 view 權限並回傳 webViewLink 超連結。
