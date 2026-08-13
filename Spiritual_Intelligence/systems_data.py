#!/usr/bin/env python3
"""Spiritual Intelligence — single source of truth for the 5 occult systems.

Consumed by the PDF generator, the scheduler and the Obsidian writer, so the
three can no longer disagree on a given day's reading (the original bug where
the Ziwei palace and I-Ching hexagram differed across files).

NOTE: the data here is currently a static sample (no real ephemeris engine is
wired yet). When a Swiss-Ephemeris / calculation layer is added, replace these
``spotlight`` / ``system_data_summary`` strings with computed values.
"""

# Colour helper kept inline so this module has no ReportLab import cost for the
# scheduler/obsidian consumers that only read text fields.
from reportlab.lib import colors as _colors


def _hex(h):
    return _colors.HexColor(h)


SYSTEMS_CONFIG = [
    {
        "id": "SYS_HD",
        "title": "人類圖 (Human Design)",
        "subtitle": "載具能量與當日流日閘門 (Vehicle Energy & Transit Gates)",
        "color_primary": _hex("#E8A33D"),      # Amber 暖琥珀
        "color_secondary": _hex("#F3CC8B"),    # Amber light
        "color_bg": _hex("#FCF0DC"),           # Amber tint
        "color_highlight": _hex("#B97A22"),    # Amber dark
        "color_text_dark": _hex("#5C4A22"),
        "motto": "「允許情緒如水流過，不急於為不安尋找答案；在對話中擁抱載具與限制，即是最好的修煉。」",
        "spotlight": "📍 流日太陽進入 4.2 閘門 (解迷) / 流日閘門 29 (承諾) 接通薦骨中心 / 閘門 57.1 點亮空白情緒中心",
        "system_data_summary": "類型：生產者 | 權威：薦骨權威 | 定義：三分人 | 人生角色：5/1 | 本命通道：61-24, 57-34, 7-31",
        "dimensions": [
            ("維度 A：心理狀態 (靈魂諮商師)", "流日 57 閘門進入開放情緒中心，容易吸收周遭緊張氣場。覺察焦慮並非本質，不急於為不安做決定，給薦骨充足時間回應。"),
            ("維度 B：生活實踐 (豐盛教練)", "力量通道 (57-34) 能量爆發，直覺力與身體動能極高。適合處理技術瓶頸、自動化測試腳本與高專注力工程任務。"),
            ("維度 C：社會網絡 (優雅協調者)", "Alpha 通道 (7-31) 帶來自然領導力。周遭團隊對你有解決問題的期待，保持傾聽並在被邀請時分享結構化洞見。"),
            ("維度 D：集體意識 (星際祭司)", "南北交點 24/44 軸線運作，潛意識對真理有強烈渴望。透過即興肢體流動或意識流寫作，讓頭腦在 61 號閘門真理中平靜。"),
            ("維度 E：全面捕捉 (全知引導者)", "左角度限制交叉 (42/32 | 60/56) 提醒：「接受限制，即是突變第一步。」以保守耐性完成今日每一項開始的任務。"),
        ],
        "what": "流日閘門 57.1 觸發開放情緒中心，激發對安全感與防衛機制的敏銳度。外部環境情緒容易被放大，頭腦產生強烈「想立刻消除不安」的迫切感，注意這非你本質的焦慮。",
        "why": "身為 5/1 薦骨生產者，當流日點亮空白中心時，容易將外在壓力誤認為個人責任。以 QA 工程思維視之，這是一次「系統邊界測試」——監控 Log，而非被 Log 帶偏。",
        "action": [
            "1. 當面對複雜技術疑問時，記錄問題並暫時放鬆，等待答案自然浮現。",
            "2. 僅對身體發出明確共鳴回應的任務承諾投入，拒絕頭腦逼迫的盲目忙碌。",
            "3. 晚間進行 15 分鐘筋膜放鬆，協助軀體釋放累積的思考壓力。",
        ],
        "harmony_note": "【系統綜合調和與心流指引】薦骨回應是心流的錨點。今日 4.2 閘門帶來邏輯衝動，請透過 10,000 步物理接地將思考壓力釋放到大能軀體中，並在晚間透過即興舞蹈或習慣活動讓身體完全放空，實現身心合一。",
    },
    {
        "id": "SYS_AST",
        "title": "西洋占星 (Western Astrology)",
        "subtitle": "黃道天象與相位解析 (Cosmic Transits & Natal Aspects)",
        "color_primary": _hex("#0E7C86"),      # Teal 科技青
        "color_secondary": _hex("#8FCAD0"),    # Teal light
        "color_bg": _hex("#E3F3F4"),           # Teal tint
        "color_highlight": _hex("#0A5A62"),    # Teal dark
        "color_text_dark": _hex("#063B40"),
        "motto": "「日月輝映於天地之間，理智與感性交織；在星體的秩序中，俯瞰生命的黃金平衡點。」",
        "spotlight": "📍 Transit 月亮合相本命月亮 (天秤座 17° / Orb 0.2°) / 水星六分火星 / 太陽合相本命水星",
        "system_data_summary": "太陽：白羊座 | 月亮：天秤座 | 上升：獅子座 | 核心相位：日水合相、火月方相、金木三分",
        "dimensions": [
            ("維度 A：心理狀態 (靈魂諮商師)", "Transit 火星方相本命月亮，心智對外界批評偏敏銳。允許情緒如雲過境，透過深呼吸平息內在防衛機制。"),
            ("維度 B：生活實踐 (豐盛教練)", "太陽合相本命水星，邏輯思維與語言表達清晰銳利。適合進行代碼重構、技術規格撰寫與架構提案。"),
            ("維度 C：社會網絡 (優雅協調者)", "金星三分本命木星帶來溫和貴人運。跨部門對話與合作氣氛和諧，適合進行對等契約簽署或關係維護。"),
            ("維度 D：集體意識 (星際祭司)", "月亮過境天秤座回歸本命月亮區間，靈魂直覺與藝術感知力達到峰值。適合進行夢境記錄與美學思考。"),
            ("維度 E：全面捕捉 (全知引導者)", "日水火金多重相位交織，理智與感性達致黃金平衡。從宏觀視野俯瞰全盤天象，導航當日人生決策。"),
        ],
        "what": "太陽合相水星賦予極佳的思維清晰度與代碼編寫速度，但火星方相月亮使情緒邊界偏向敏銳。對於技術架構提案擁有突破性動能，唯需注意對話語氣的分寸。",
        "why": "天秤座月亮追求對等與優雅，白羊水星與火星組合激發敏捷執行力。此天象最有利於高難度軟體架構優化與跨團隊和諧溝通。",
        "action": [
            "1. 善用上午 09:00-12:00 多巴胺高峰期，快速推進關鍵 Code 檢核與架構優化。",
            "2. 在團隊互動中展現天秤座的圓融傾聽，以客觀數據與溫和語氣達成共識。",
            "3. 記錄當日閃現之美學或技術靈感，儲存至個人知識資產庫。",
        ],
        "harmony_note": "【系統綜合調和與心流指引】月亮回歸是一月中情緒能量最為穩定舒暢的時刻。將水火六分的敏捷動能投注於專案突破，午後則享受金木三分帶來的和諧對話與閱讀滋養，實現理智與感性的完美和諧。",
    },
    {
        "id": "SYS_ZW",
        "title": "紫微斗數 (Ziwei Doushu)",
        "subtitle": "流日宮位與四化飛星 (Daily Palace & Four Transformations)",
        "color_primary": _hex("#7A4B6B"),      # Plum 紫 (Guide pairing)
        "color_secondary": _hex("#A07A92"),    # Plum light
        "color_bg": _hex("#F1E9EE"),           # Plum tint
        "color_highlight": _hex("#5C3850"),    # Plum dark
        "color_text_dark": _hex("#321F2C"),
        "motto": "「飛星交錯皆有定數，化忌即是修煉之門；涵養福德之祿，自能駕馭命宮吉凶。」",
        "spotlight": "📍 流日命宮在未 / 天機化祿入官祿 / 太陽化忌入官祿提醒決策審慎 / 太陰化祿入福德",
        "system_data_summary": "流日命宮：未宮 | 流日四化：廉貞化祿、破軍化權、武曲化科、太陽化忌 | 福德宮太陰化祿",
        "dimensions": [
            ("維度 A：心理狀態 (靈魂諮商師)", "紫微帝星化科入命，心境從昨日太陽化忌中平復，展現尊貴、客觀且包容的智者姿態。"),
            ("維度 B：生活實踐 (豐盛教練)", "天機化祿入官祿宮，代表機智靈變與企劃思維爆發。非常有利於軟體自動化流程設計與創新架構提案。"),
            ("維度 C：社會網絡 (優雅協調者)", "天梁化權入遷移宮，長輩緣與貴人運強勁，外在專業權威形象獲得高度認同與信任。"),
            ("維度 D：集體意識 (星際祭司)", "太陽化忌入官祿提醒事業決策宜審慎、避免躁進，轉向內在心靈投資與精神豐盛。"),
            ("維度 E：全知引導者 (全知引導者)", "機祿梁權會照，謀略與執行力兼備。善用天機之智慧與紫微之格局，綜觀全盤並穩健推進。"),
        ],
        "what": "流日天機化祿飛入官祿宮，事業面靈感湧現，邏輯與謀略能力大幅提升；太陽化忌同入官祿則提醒決策需審慎，勿因過度自信而躁進。",
        "why": "天機主智慧與企劃，化祿則帶來流暢的運作資源與機遇。此飛星結構是進行技術創新、撰寫架構規格與優化測試流水線的最佳契機，但須以化忌之審慎平衡之。",
        "action": [
            "1. 將今日產生的架構創意與企劃草案迅速記錄並整理成結構化文件。",
            "2. 跨部門交流中展現天梁化權的專業權威，提供具前瞻性的解決方案。",
            "3. 事業決策保持審慎（太陽化忌），聚焦於個人技術技能與內在涵養加值。",
        ],
        "harmony_note": "【系統綜合調和與心流指引】天機化祿與紫微化科帶來強大的智性力量。保持謙遜與務實，將這股靈變的智慧注入代碼自動化與專案規劃中，並在晚間進行日記歸納與感謝記錄，為今日成果畫下完滿句點。",
    },
    {
        "id": "SYS_BAZI",
        "title": "八字干支 (Bazi & Four Pillars)",
        "subtitle": "流日干支與十神沖合 (Daily Pillar & Ten Gods)",
        "color_primary": _hex("#6B8F71"),      # Sage 抹茶綠
        "color_secondary": _hex("#B7CCB9"),    # Sage light
        "color_bg": _hex("#E8F0E9"),           # Sage tint
        "color_highlight": _hex("#47654B"),    # Sage dark
        "color_text_dark": _hex("#2C3F2E"),
        "motto": "「丁未流日木火土相生，氣場順暢和諧；正財透干，腳踏實地必有厚報。」",
        "spotlight": "📍 丁未流日 (火土相生) / 正財透干 / 未土藏乙木食神滋養",
        "system_data_summary": "當日干支：丁未 | 十神：正財當權、食神生財 | 五行動能：火土和諧相生",
        "dimensions": [
            ("維度 A：心理狀態 (靈魂諮商師)", "丁火正財溫和明亮，地支未土帶木氣生火，心情平穩踏實，遠離急躁，展現沉穩氣度。"),
            ("維度 B：生活實踐 (豐盛教練)", "正財當權結合食神滋養，代表一步一腳印的實質產出。測試自動化腳本編寫與 CI/CD 維運穩健推進。"),
            ("維度 C：社會網絡 (優雅協調者)", "正財正官氣場溫和，職場信譽卓著。誠實守信的對話態度能獲得團隊長期信任與支持。"),
            ("維度 D：集體意識 (星際祭司)", "未土為木庫，藏有生命滋養之力。透過萬步接地與自然接觸，接引大地土元素之穩定氣場。"),
            ("維度 E：全面捕捉 (全知引導者)", "五行火土順生，氣場和諧。將熱情化為踏實行動，發揮「知行合一」的持之以恆精神。"),
        ],
        "what": "丁未日柱氣場溫和順暢，正財透干帶來踏實與務實的行動導向，食神暗藏則提供持續的創造力與細緻度。",
        "why": "火生土、土藏木，五行順生而無衝剋。非常有利於進行累積性、維運性與結構化的技術扎根工作。",
        "action": [
            "1. 專注於專案細節優化與自動化腳本覆蓋率提升，建立長期穩定品質。",
            "2. 保持日間萬步走動，吸收未土接地動能，維護強健體魄。",
            "3. 晚餐選擇清淡營養食材，照顧脾胃土元素健康。",
        ],
        "harmony_note": "【系統綜合調和與心流指引】丁未流日帶來溫和而源源不絕的踏實力量。順應這股五行相生的穩健氣場，在工作中保持精益求精，並透過萬步行走與充足睡眠修復肉體，實現生活與事業的雙重豐盛。",
    },
    {
        "id": "SYS_ICHING",
        "title": "梅花易數 (I Ching & Mei Hua)",
        "subtitle": "當日卦象與體用生克 (Daily Hexagram & Trigram Dynamics)",
        "color_primary": _hex("#EF6F53"),      # Coral 活力橘紅
        "color_secondary": _hex("#F6AD9B"),    # Coral light
        "color_bg": _hex("#FDE7E1"),           # Coral tint
        "color_highlight": _hex("#C24B32"),    # Coral dark
        "color_text_dark": _hex("#832F1E"),
        "motto": "「澤山咸卦感應天地，虛中受人；君子以虛受人，體用和和共臻大和。」",
        "spotlight": "📍 當日得《澤山咸》卦，動爻在五，變卦為《水山蹇》",
        "system_data_summary": "主卦：澤山咸 (兌上艮下) | 互卦：澤風大過 | 變卦：水山蹇 | 體用關係：兌金與艮土相生 (感應和合)",
        "dimensions": [
            ("維度 A：心理狀態 (靈魂諮商師)", "咸卦主感應與虛懷若谷。「虛中受人」，放下執念，保持心靈開放，感應周遭微妙萬物。"),
            ("維度 B：生活實踐 (豐盛教練)", "艮止兌悅，動靜得宜。在技術研發中既有山之沉穩，又有澤之愉悅，輕鬆高效完成任務。"),
            ("維度 C：社會網絡 (優雅協調者)", "咸卦為感應之始，人際互動真誠相感。無心之感最為高尚，能建立極具共鳴的合作關係。"),
            ("維度 D：集體意識 (星際祭司)", "變卦《水山蹇》提醒「見險思內，反身修德」。面對外在阻礙，回歸內在反省與身心覺察。"),
            ("維度 E：全面捕捉 (全知引導者)", "天地感而萬物化生。順應感應之理，以虛靜之心應萬變，實現物我融通之境界。"),
        ],
        "what": "主卦《澤山咸》象徵真誠感應與和諧互動，兌上艮下代表少女與少男之無心相感；九五動爻「咸其脢，無悔」，提醒以心靈深處之真誠回應世界。",
        "why": "土金相生，感應和合。變卦《水山蹇》則示警前有險阻時宜退而修德。這提示我們在推進事務時應以真誠感應人，遇到阻礙則回歸內在修煉。",
        "action": [
            "1. 保持開放虛懷的心態（虛中受人），傾聽他人意見與技術反饋。",
            "2. 若專案遭遇短暫瓶頸（蹇卦），不強行衝撞，而是反求諸己優化架構。",
            "3. 晚間進行 15 分鐘正念冥想，體驗與萬物融通之寧靜心流。",
        ],
        "harmony_note": "【系統綜合調和與心流指引】《澤山咸》卦帶來真誠與和諧的感應能量。保持「虛中受人」的謙遜心態，將這股感應力量注入身心覺察與職場溝通中，反身修德，自然能駕馭一切變化並獲得深層成長。",
    },
]


def spotlight_map():
    """Return {system_id: spotlight_text} for shared use by scheduler/obsidian."""
    return {s["id"]: s["spotlight"] for s in SYSTEMS_CONFIG}
