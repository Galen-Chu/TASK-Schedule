全球情報每日趨勢報告 — 企業級雲端系統架構設計規格書 (Cloud Architecture Specification)
1. 執行摘要 (Executive Summary)
本文件定義「全球情報每日趨勢報告自動化系統」之企業級雲端架構設計。系統採用 無伺服器 (Serverless)、高可用 (High Availability) 與 事件驅動 (Event-Driven) 架構，每日定時自動採集國際與台灣國內權威智庫資訊，經由 LLM 降噪與結構化提煉，動態渲染智庫級 PDF 報告，並自動歸檔至 Google Drive 與透過 Gmail 分發。

後續擴充 (Phase 2 Expansion)：排程穩定運作後，於輸出層擴充 obsidian_writer.py 模組，將每日情報精簡摘要與命理觀測數據自動同步至個人 Obsidian Knowledge Vault。

2. 系統整體拓撲與資料流 (System Architecture & Topology)
+-----------------------------------------------------------------------------------+

|                            GCP / AWS Cloud Infrastructure                         |

|                                                                                   |

|  [Cloud Scheduler / EventBridge] ──(Cron: 0 7 * * *)                               |

|                 │                                                                 |

|                 ▼                                                                 |

|  [Cloud Pub/Sub / Event Topic]                                                    |

|                 │                                                                 |

|                 ▼                                                                 |

|  [Cloud Functions / AWS Lambda] (Python 3.11 Runtime)                             |

|                 │                                                                 |

|                 ├───► [Secret Manager] ──► (API Keys, Service Account Keys)       |

|                 │                                                                 |

|                 ├───► [1. Data Ingestion Engine]                                  |

|                 │        ├── 國際智庫 (CSIS, ECB, FDA, DOE, etc.)                  |

|                 │        └── 國內智庫 (CIER, TIER, ITRI, MIC, INDSR, etc.)          |

|                 │                                                                 |

|                 ├───► [2. LLM Processing Pipeline] (Gemini 1.5 Pro / Claude 3.5)  |

|                 │        ├── 三要素提煉 (What, Why, So What)                       |

|                 │        └── 多語文排點與半形化規範器 (Punctuation Normalizer)      |

|                 │                                                                 |

|                 ├───► [3. PDF Render Engine] (ReportLab Dual-Font System)         |

|                 │        └── Master Visual Identity (石墨藍 #0F172A / 典雅金 #C5A059)|

|                 │                                                                 |

|                 ├───► [4. Google Drive Storage Integration] (Google Drive API v3) |

|                 │                                                                 |

|                 ├───► [5. Gmail Dispatcher Service] (Gmail API v1)                 |

|                 │                                                                 |

|                 └───► [6. Obsidian Vault Integration] (obsidian_writer.py - 擴充)  |

|                          ├── 6.1 當日精簡摘要 ──► Daily/YYYY-MM-DD.md              |

|                          └── 6.2 完整命理盤與導師分析 ──► Awareness/Daily-Transit/ |

|                                                           YYYY-MM-DD.md (Wikilinks)|

|                                                                                   |

|  [Cloud Monitoring / CloudWatch] ◄─── Logging & Alerting Notification            |

+-----------------------------------------------------------------------------------+

3. 雲端基礎設施與模組組件設計 (Cloud Infrastructure Components)
3.1 觸發與排程層 (Scheduler Layer)
組件: Google Cloud Scheduler / AWS EventBridge
設定: Cron 表達式 0 7 * * *（時區：Asia/Taipei，每日上午 07:00 觸發）
重試機制: 最大重試次數 3 次，指數退避 (Exponential Backoff) 初始間隔 10s，最大間隔 300s。
3.2 無伺服器計算層 (Compute Layer)
組件: Google Cloud Functions (2nd Gen) / AWS Lambda
規格: Memory 1024 MB, Timeout 500s, Python 3.11 Runtime
併發控制: 限制最大實例數 5，避免超出外鏈採集與 API 配額。
3.3 憑證與密鑰管理 (Security & Secret Management)
組件: Google Secret Manager / AWS Secrets Manager
安全性: OAuth 2.0 Client Credentials, Service Account Key, LLM API Keys 統一加密存儲，透過 IAM 最小權限原則 (Least Privilege) 動態注入。
3.4 後續擴充：Obsidian Vault 模組設計 (Obsidian Vault Writer)
模組檔名: obsidian_writer.py
寫入目標 1 (Daily Note): Daily/YYYY-MM-DD.md
提取 5 大領域當日精簡摘要，插入至 ## 🌐 全球情報觀測 (Global Intelligence) 指定區塊。
寫入目標 2 (Transit & Analysis Note): Awareness/Daily-Transit/YYYY-MM-DD.md
寫入完整命理盤數據（Human Design / 星盤行運 Transit）與導師分析。
雙向連結 (Wikilinks): 於 Awareness/Daily-Transit/YYYY-MM-DD.md 標頭自動嵌入 [[Daily/YYYY-MM-DD|YYYY-MM-DD Daily Note]] 進行雙向回連。
3.5 監控與告警 (Monitoring & Observability)
組件: Google Cloud Logging / Cloud Monitoring
指標: 執行成功率、PDF 生成耗時、外部 API 採集成功率、Gmail 遞送狀態與 Obsidian 同步狀態。
告警: 執行失敗即時發送 Slack / Email 告警訊息。
