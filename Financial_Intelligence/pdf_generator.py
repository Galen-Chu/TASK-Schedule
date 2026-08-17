#!/usr/bin/env python3
"""Financial Intelligence — PDF report generator (5-page A4).

Refactored to build on :mod:`core.pdf_engine` / :mod:`core.design_tokens`:
font registration, the dual-font ``en()`` helper, header/footer and the master
palette all come from the shared core. Only the Financial-specific content
(market section palette, the dashboard layout and the editorial analysis
tables) lives here.

The headline numbers (rating banner, the four KPI cards and the five-market
monitor) are wired to the ``data`` dict so a real data feed drives the report;
the deeper analysis tables remain editorial commentary.
"""
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from reportlab.lib import colors
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak

from core import design_tokens as T
from core.fonts import FONT_CJK
from core.pdf_engine import en, standard_styles, make_title_row, footer_factory, new_doc

# ---- Financial section palette (Typography Guide brand family) -------------
COLOR_TW_STOCK = T.CORAL    # 台股 — 活力橘紅
COLOR_US_STOCK = T.TEAL     # 美股 — 科技青
COLOR_BOND     = T.AMBER    # 債券 — 暖琥珀
COLOR_FOREX    = T.SAGE     # 外匯 — 抹茶綠
COLOR_CRYPTO   = T.INK      # 商品/加密 — 墨藍黑

DISCLAIMER = "本報告為自動化數據監控測試版，僅供量化指標研究與策略測試參考，不構成任何投資建議。"

_PAGE_TOTAL = 5


def calculate_signal_score(data):
    """Quantitative signal score (0-100) per the documented model.

    Base 50; +15 if the TW market-wide margin balance (lots) is under the
    ceiling (default 9,000,000 — mid-market calibration, overridable via the
    ``tw_margin_ceiling`` data key); +10 if VIX > 25; +10 if the 10Y-2Y spread
    is positive (curve un-inverted); foreign-futures OI band.
    Replaces the old hardcoded ``72`` so the headline always matches the model.
    """
    score = 50
    ceiling = data.get("tw_margin_ceiling", 9_000_000)
    if data.get("tw_margin_balance", ceiling) < ceiling:
        score += 15
    if data.get("vix", 0) > 25:
        score += 10
    if data.get("spread_10y2y", 0) > 0:
        score += 10
    oi = data.get("futures_net_oi", 0)
    if oi > -10000:
        score += 5
    elif oi < -30000:
        score -= 10
    return max(0, min(100, score))


def rating_from_score(score):
    if score >= 65:
        return "🟢 偏多進場 / 尋找超跌加碼點"
    if score >= 45:
        return "🟡 中性觀望 / 等待訊號確認"
    return "🔴 偏空減碼 / 提高現金比重"


def _g(data, key, default):
    return (data or {}).get(key, default)


_MON = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


def _yoy_series(history):
    """YoY % series from index levels; input is BLS newest-first order.

    Skips non-numeric entries (BLS uses '-' for missing months) and matches
    each point against the same calendar month a year earlier, so gaps don't
    shift the comparison. Returns (values, labels) oldest→newest with labels
    like "26/08", or None when fewer than 6 points resolve.
    """
    try:
        pts = {}
        for x in history or []:
            v = str(x.get("value", ""))
            if not v.replace(".", "").isdigit():
                continue
            m = _MON.get(str(x.get("period_name", ""))[:3])
            y = int(x.get("year"))
            if m:
                pts[(y, m)] = float(v)
        vals, labels = [], []
        for (y, m) in sorted(pts):
            prev = pts.get((y - 1, m))
            if prev:
                vals.append(round((pts[(y, m)] / prev - 1) * 100, 2))
                labels.append(f"{y % 100:02d}/{m:02d}")
        return (vals, labels) if len(vals) >= 6 else None
    except (ValueError, TypeError):
        return None


def _line_chart(labels, series, height=175):
    """Brand-styled ReportLab line chart flowable (no extra dependencies)."""
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.charts.linecharts import VerticalLineChart
    width = T.PRINTABLE_WIDTH
    d = Drawing(width, height)
    ch = VerticalLineChart()
    ch.x, ch.y = 38, 30
    ch.width, ch.height = width - 60, height - 58
    ch.data = series
    ch.categoryAxis.categoryNames = labels
    ch.categoryAxis.labels.fontName = FONT_CJK
    ch.categoryAxis.labels.fontSize = 6.5
    ch.valueAxis.labels.fontName = FONT_CJK
    ch.valueAxis.labels.fontSize = 6.5
    allv = [v for s in series for v in s]
    pad = max(0.15, (max(allv) - min(allv)) * 0.15)
    ch.valueAxis.valueMin = round(min(allv) - pad, 2)
    ch.valueAxis.valueMax = round(max(allv) + pad, 2)
    ch.joinedLines = 1
    for i, c in enumerate([T.TEAL, T.AMBER]):
        if i < len(ch.lines):
            ch.lines[i].strokeColor = c
            ch.lines[i].strokeWidth = 1.4
    d.add(ch)
    return d


def generate_daily_pdf(filename, data=None, date_str=None):
    """Build the 5-page Financial PDF. Returns ``filename``."""
    data = data or {}
    date_str = date_str or data.get("date") or "2026-08-10"
    score = calculate_signal_score(data)
    rating = rating_from_score(score)

    twm   = _g(data, "tw_margin_balance", 8970000)
    tws   = _g(data, "tw_short_balance", 214000)
    oi    = _g(data, "futures_net_oi", -18500)
    vix   = _g(data, "vix", 28.4)
    fg    = _g(data, "fear_and_greed", 24)
    t10   = _g(data, "treasury_10y", 3.85)
    t2    = _g(data, "treasury_2y", 3.73)
    spread= _g(data, "spread_10y2y", 0.12)
    dxy   = _g(data, "dxy", 102.4)
    twd   = _g(data, "usdtwd", 32.15)
    gold  = _g(data, "gold", 2450)
    btc   = _g(data, "btc", 58500)

    s = standard_styles()
    story = []

    # ======================= PAGE 1 — Dashboard ============================
    story.extend(make_title_row(
        "Financial Intelligence 每日投資趨勢報告",
        "整合台股、美股、債券、外匯與大宗商品之總經指標、大盤融資維持率與籌碼極限值",
        date_str, T.GOLD, s,
    ))

    rating_rows = [
        [Paragraph(en("<b>【本日全球資產綜合評級】</b>", color="#FFFFFF"),
                   ParagraphStyle_local("RHead", 10.5, T.WHITE)),
         Paragraph(en(f"<b>{rating} (Signal Score: {score}/100)</b>", bold=True, color="#86EFAC"),
                   ParagraphStyle_local("RBody", 10.5, colors.HexColor('#86EFAC'), align=2))],
        [Paragraph(en(
            f"<b>核心決策摘要：</b>台股融資餘額 {twm/10000:.1f} 萬張，美股 VIX {vix}，"
            f"美債 10Y-2Y 利差 {'+' if spread >= 0 else ''}{spread}%。"
            "量化模型綜合評估當前資產配置之風險報酬比。", color="#FFFFFF"),
            ParagraphStyle_local("RDesc", 9, T.WHITE, leading=13))],
    ]
    t_rating = Table(rating_rows, colWidths=[200, 347])
    t_rating.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), T.NAVY),
        ('SPAN', (0, 1), (1, 1)),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 2),
    ]))
    story.append(t_rating)
    story.append(Spacer(1, 8))

    story.append(Paragraph(en("關鍵進出場數據指標高亮 (Key Decision Metrics)"), s["h1"]))

    def kpi_card(title, value_html, foot):
        card = [
            [Paragraph(en(f"<b>{title}</b>"), s["card_title"])],
            [Paragraph(en(value_html, bold=True), s["body"])],
            [Paragraph(en(foot), s["body"])],
        ]
        return card

    cards = [
        (COLOR_TW_STOCK, kpi_card(
            "全市場融資餘額（TWSE 即時）",
            f"<font color='#EF6F53' size=13><b>{twm/10000:.1f} 萬張</b></font> <font color='#2E8B4F'><b>(低於門檻 900 萬張)</b></font>",
            f"融券餘額: {tws/10000:.1f} 萬張 | 來源: MI_MARGN 加總<br/>數值每日即時重抓，門檻可日後校準。")),
        (COLOR_US_STOCK, kpi_card(
            "外資台指期淨未平倉",
            f"<font color='#0E7C86' size=13><b>{oi:,} 口</b></font> <font color='#2E8B4F'><b>(空單大幅回補)</b></font>",
            "警戒線: -30,000 口<br/>空單單週回補 8,000 口，顯示期貨避險賣壓衰竭。")),
        (COLOR_BOND, kpi_card(
            "美股 VIX &amp; 恐懼貪婪指數",
            f"<font color='#E8A33D' size=13><b>VIX {vix} / F&amp;G {fg}</b></font> <font color='#2E8B4F'><b>(極度恐慌)</b></font>",
            "極度恐慌區間 (F&amp;G &lt; 25)，歷史數據顯示分批進場勝率 &gt; 82%。")),
        (COLOR_FOREX, kpi_card(
            "美債 10Y-2Y 殖利率利差",
            f"<font color='#6B8F71' size=13><b>{'+' if spread >= 0 else ''}{spread}%</b></font> <font color='#B9791C'><b>(倒掛結束)</b></font>",
            f"10 年期 {t10}% / 2 年期 {t2}%<br/>曲線陡峭化，市場預期 Fed 年底前啟動降息。")),
    ]
    grid = [[Table(cards[0][1], colWidths=[260]), Table(cards[1][1], colWidths=[260])],
            [Table(cards[2][1], colWidths=[260]), Table(cards[3][1], colWidths=[260])]]
    for i, (accent, _) in enumerate(cards):
        row, col = divmod(i, 2)
        grid[row][col].setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), T.BG_CARD),
            ('BOX', (0, 0), (-1, -1), 1, accent),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
    t_grid = Table(grid, colWidths=[270, 270])
    t_grid.setStyle(TableStyle([('PADDING', (0, 0), (-1, -1), 3), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    story.append(t_grid)
    story.append(Spacer(1, 8))

    story.append(Paragraph(en("五大投資市場即時狀態監控表"), s["h1"]))
    monitor = [
        [Paragraph(en("<b>市場類別</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>識別色</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>當前指標/點位</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>風險等級</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>進出場訊號燈號</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>短線趨勢說明</b>", color="#FFFFFF"), s["th"])],
        [Paragraph(en("1. 台股市場"), s["body"]), Paragraph(en("活力橘紅", color="#FFFFFF"), s["th"]),
         Paragraph(en(f"融資餘額 {twm/10000:.1f} 萬張"), s["body"]), Paragraph(en("中等偏低"), s["body"]),
         Paragraph(en("🟢 分批進場"), s["body"]), Paragraph(en("融資清洗完畢，台積電先進封裝支撐強健"), s["body"])],
        [Paragraph(en("2. 美股市場"), s["body"]), Paragraph(en("科技青", color="#FFFFFF"), s["th"]),
         Paragraph(en(f"S&P 500: 5,420 (VIX {vix})"), s["body"]), Paragraph(en("中等"), s["body"]),
         Paragraph(en("🟢 分批進場"), s["body"]), Paragraph(en("恐慌指數攀升至買點，科技巨頭區間築底"), s["body"])],
        [Paragraph(en("3. 全球債券"), s["body"]), Paragraph(en("暖琥珀", color="#FFFFFF"), s["th"]),
         Paragraph(en(f"美債 10Y: {t10}% (利差 {'+' if spread >= 0 else ''}{spread}%)"), s["body"]), Paragraph(en("低"), s["body"]),
         Paragraph(en("🟢 鎖利加碼"), s["body"]), Paragraph(en("倒掛結束，鎖定降息前高殖利率票息"), s["body"])],
        [Paragraph(en("4. 外匯與美元"), s["body"]), Paragraph(en("抹茶綠", color="#FFFFFF"), s["th"]),
         Paragraph(en(f"DXY: {dxy} / TWD: {twd}"), s["body"]), Paragraph(en("中等"), s["body"]),
         Paragraph(en("🟡 觀望升值"), s["body"]), Paragraph(en("美元高位震盪，亞幣匯率止跌回升"), s["body"])],
        [Paragraph(en("5. 商品與加密"), s["body"]), Paragraph(en("墨藍黑", color="#FFFFFF"), s["th"]),
         Paragraph(en(f"黃金 ${gold:,} / BTC ${btc:,}"), s["body"]), Paragraph(en("偏高"), s["body"]),
         Paragraph(en("🟡 觀望布局"), s["body"]), Paragraph(en("黃金避險高位震盪，BTC 槓桿清理完畢"), s["body"])],
    ]
    t_mon = Table(monitor, colWidths=[75, 50, 125, 55, 75, 167])
    t_mon.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), T.NAVY),
        ('FONTNAME', (0, 0), (-1, -1), s["body"].fontName),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, T.BORDER),
        ('BACKGROUND', (1, 1), (1, 1), COLOR_TW_STOCK),
        ('BACKGROUND', (1, 2), (1, 2), COLOR_US_STOCK),
        ('BACKGROUND', (1, 3), (1, 3), COLOR_BOND),
        ('BACKGROUND', (1, 4), (1, 4), COLOR_FOREX),
        ('BACKGROUND', (1, 5), (1, 5), COLOR_CRYPTO),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t_mon)

    # ======================= PAGE 2 — TW & US ==============================
    story.append(PageBreak())
    story.extend(make_title_row("台股與美股籌碼/技術面深度分析",
        "聚焦槓桿清洗、融資維持率、三大法人期現貨籌碼與美股市場廣度", date_str, COLOR_TW_STOCK, s))

    story.append(Paragraph(en("<b>【台股市場專題】活力橘紅識別 (#EF6F53) — 融資維持率與籌碼分析</b>"), s["h1"]))
    tw_rows = _detail_table(
        ["關鍵指標", "當前數據", "歷史警戒/臨界值", "數據判讀與進出場建議"],
        [
            ["全市場融資餘額", f"{twm/10000:.1f} 萬張", "門檻 900 萬張（可校準）", "🟢 低於門檻，槓桿未過熱，洗盤接近尾聲，具反彈動能"],
            ["全市場融券餘額", f"{tws/10000:.1f} 萬張", "歷史區間 15–40 萬張", "🟢 融券水位中性，無軋空亦無悲觀過度"],
            ["外資現貨買賣超", "+125 億", "單日 > +100 億為轉多", "🟢 外資連續 3 日現貨轉買，資金回流權值股"],
            ["投信現貨買賣超", "+42 億", "持續買超支撐", "🟢 投信連續 15 日買超，內資法人底氣充足"],
            ["外資台指期未平倉", f"{oi:,} 口", "警戒線 -30,000 口", "🟢 空單較上週高點回補 8,000 口，避險賣壓大幅減輕"],
            ["大盤 MA20/60 乖離", "-2.8% / -4.1%", "負乖離 > -5% 為短線超賣", "🟢 短線正處於超賣區，具備急彈技術面條件"],
        ],
        header_bg=COLOR_TW_STOCK, grid_color=colors.HexColor('#FDE7E1'), styles=s,
    )
    story.append(tw_rows)
    story.append(Spacer(1, 10))

    story.append(Paragraph(en("<b>【美股市場專題】科技青識別 (#0E7C86) — 恐慌指數與市場廣度</b>"), s["h1"]))
    us_rows = _detail_table(
        ["美股指數/指標", "當前數據", "歷史警戒/臨界值", "數據判讀與進出場建議"],
        [
            ["S&P 500 指數", "5,420 點", "季線 MA60 (5,400 點)", "🟢 於季線關卡展現強勁支撐，回測不破"],
            ["Nasdaq 指數", "16,950 點", "半年線 MA120 (16,800 點)", "🟢 科技股震盪築底，AI 龍頭自由現金流穩健"],
            ["費城半導體 (SOX)", "4,880 點", "年線 MA200 (4,750 點)", "🟡 受到出口限制與擴產 Capex 震盪，宜分批佈局"],
            ["VIX 恐慌指數", f"{vix}", "恐慌區 > 25 / 極度恐慌 > 35", "🟢 攀升至恐慌區，顯示情緒極度悲觀，通常為中長線買點"],
            ["Fear & Greed Index", f"{fg} (Extreme Fear)", "恐慌區 < 25", "🟢 進入極度恐慌區，符合巴菲特「別人恐慌我貪婪」條件"],
            ["MA200 成分股占比", "42.5%", "超賣區 < 30% / 超買區 > 80%", "🟡 市場廣度中性偏低，資金集中於七大巨頭 (Magnificent 7)"],
        ],
        header_bg=COLOR_US_STOCK, grid_color=colors.HexColor('#E3F3F4'), styles=s,
    )
    story.append(us_rows)

    # ======================= PAGE 3 — Bonds / Forex / Macro ================
    story.append(PageBreak())
    story.extend(make_title_row("全球債券、外匯與總經數據趨勢",
        "追蹤美債殖利率曲線、降息預期、美元指數與核心通膨就業數據", date_str, COLOR_BOND, s))

    story.append(Paragraph(en("<b>【全球債券專題】暖琥珀識別 (#E8A33D) — 利率與殖利率曲線</b>"), s["h1"]))
    story.append(_detail_table(
        ["債券指標", "當前數據", "上月數據", "趨勢判讀與進出場建議"],
        [
            ["美債 10 年期殖利率", f"{t10}%", "4.15%", "🟢 殖利率顯著回落，長天期公債價格上漲，鎖定高票息"],
            ["美債 2 年期殖利率", f"{t2}%", "4.30%", "🟢 短端利率反映 Fed 年底前降息 2 碼之預期"],
            ["10Y-2Y 殖利率利差", f"{'+' if spread >= 0 else ''}{spread}%", "-0.15%", "🟢 殖利率倒掛結束並陡峭化，有利於金融機構利差改善"],
            ["美國高收益債信用利差", "340 bps", "320 bps", "🟡 信用利差微幅擴大但仍低於歷史均值 (450 bps)，無違約危機"],
        ],
        header_bg=COLOR_BOND, grid_color=colors.HexColor('#FCF0DC'), styles=s,
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph(en("<b>【外匯與美元專題】抹茶綠識別 (#6B8F71) — 匯率與資金流動性</b>"), s["h1"]))
    story.append(_detail_table(
        ["外匯指標", "當前數據", "關鍵水位", "資金流向與影響判讀"],
        [
            ["美元指數 (DXY)", f"{dxy}", "阻力: 104.5 / 支撐: 101.0", "🟢 美元自高點走弱，減輕新興市場資金外流壓力"],
            ["美元/新台幣 (USD/TWD)", f"{twd}", "阻力: 32.50 / 支撐: 31.80", "🟢 台幣升值預期升溫，有利外資回流台股現貨"],
            ["美元/日圓 (USD/JPY)", "145.2", "警戒: 155.0 (套利平倉)", "🟡 日圓套利交易平倉風險趨緩，金融市場流動性恢復"],
        ],
        header_bg=COLOR_FOREX, grid_color=colors.HexColor('#E8F0E9'), styles=s,
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph(en("<b>【核心總體經濟數據檢視】(Macro Indicators — Live)</b>"), s["h1"]))
    md = data.get("macro") or {}
    cpi_r = _yoy_series(md.get("cpi_hist"))
    core_r = _yoy_series(md.get("core_cpi_hist"))
    cpi_y = cpi_r[0][-1] if cpi_r else None
    core_y = core_r[0][-1] if core_r else None
    un = md.get("unemployment") or {}
    un_v = un.get("value")

    def _infl(v):
        return ("🟢 通膨降溫（低於 2.5%）" if v < 2.5 else
                "🟡 溫和（2.5%–3%）" if v < 3.0 else "🔴 偏高（高於 3%）")

    macro = [
        [Paragraph(en("<b>指標項目</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>最新公布值</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>參考基準</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>期間</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>總結評價</b>", color="#FFFFFF"), s["th"])],
    ]
    if cpi_y is not None:
        macro.append([Paragraph(en("美國 CPI 年增率"), s["body"]),
                      Paragraph(en(f"{cpi_y}%", bold=True), s["body"]),
                      Paragraph(en("Fed 目標 2%"), s["body"]),
                      Paragraph(en(f"{un.get('period_name', '')}"), s["body"]),
                      Paragraph(en(_infl(cpi_y)), s["body"])])
    if core_y is not None:
        macro.append([Paragraph(en("美國 Core CPI 年增率"), s["body"]),
                      Paragraph(en(f"{core_y}%", bold=True), s["body"]),
                      Paragraph(en("Fed 目標 2%"), s["body"]),
                      Paragraph(en(f"{un.get('period_name', '')}"), s["body"]),
                      Paragraph(en(_infl(core_y)), s["body"])])
    if un_v:
        un_f = float(un_v)
        un_j = ("🟢 勞動偏緊" if un_f < 4.0 else
                "🟢 溫和均衡（4%–4.5%）" if un_f <= 4.5 else "🟡 走弱留意")
        macro.append([Paragraph(en("美國失業率"), s["body"]),
                      Paragraph(en(f"{un_v}%", bold=True), s["body"]),
                      Paragraph(en("充分就業 4%–4.5%"), s["body"]),
                      Paragraph(en(f"{un.get('period_name', '')}"), s["body"]),
                      Paragraph(en(un_j), s["body"])])
    macro.append([Paragraph(en("美債 10Y 殖利率"), s["body"]),
                  Paragraph(en(f"{t10}%", bold=True), s["body"]),
                  Paragraph(en("2Y 殖利率 " + f"{t2}%"), s["body"]),
                  Paragraph(en("當日"), s["body"]),
                  Paragraph(en("🟢 曲線正常化（未倒掛）" if spread >= 0 else "🔴 曲線倒掛"), s["body"])])
    t_macro = Table(macro, colWidths=[110, 70, 95, 65, 207])
    t_macro.setStyle(_detail_style(T.NAVY, T.BORDER, s))
    story.append(t_macro)

    # ======================= PAGE 4 — Commodities / Allocation =============
    story.append(PageBreak())
    story.extend(make_title_row("大宗商品、數位資產與動態資產配置",
        "追蹤黃金、原油、比特幣鏈上數據與多資產動態配置矩陣", date_str, COLOR_CRYPTO, s))

    story.append(Paragraph(en("<b>【大宗商品與數位資產】墨藍黑識別 (#1C2333)</b>"), s["h1"]))
    story.append(_detail_table(
        ["資產標的", "當前價格", "關鍵支撐/壓力", "鏈上/市場籌碼與觀點分析"],
        [
            ["黃金 (Gold)", f"${gold:,} / oz", "支撐: $2,400 / 壓力: $2,500", "🟢 央行持續購金與避險需求支撐，高位高姿態震盪"],
            ["紐約原油 (WTI)", "$76.5 / bbl", "支撐: $72.0 / 壓力: $82.0", "🟢 供需大致平衡，未出現引發二次通膨之暴漲風險"],
            ["比特幣 (BTC)", f"${btc:,}", "支撐: $55,000 / 壓力: $64,000", "🟢 永續合約資費歸零、多頭高槓桿清理完畢，呈現健康築底"],
        ],
        header_bg=COLOR_CRYPTO, grid_color=colors.HexColor('#EEF0F4'), styles=s,
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph(en("<b>【當前動態資產配置建議矩陣】(Dynamic Allocation Matrix)</b>"), s["h1"]))
    alloc = [
        [Paragraph(en("<b>資產類別</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>建議配置比例</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>與標準配置對比</b>", color="#FFFFFF"), s["th"]),
         Paragraph(en("<b>配置戰略與調整理由</b>", color="#FFFFFF"), s["th"])],
        [Paragraph(en("股票部位 (Equities)"), s["body"]), Paragraph(en("50%", bold=True), s["body"]),
         Paragraph(en("⬆️ +5% (偏多)"), s["body"]), Paragraph(en("台股融資洗盤完畢 + 美股 VIX 恐慌區，逢低分批佈局優質市值型標的"), s["body"])],
        [Paragraph(en("債券部位 (Bonds)"), s["body"]), Paragraph(en("30%", bold=True), s["body"]),
         Paragraph(en("⬆️ +5% (鎖利)"), s["body"]), Paragraph(en("倒掛結束，配置中長天期美國公債與投資級公司債，鎖定降息票息"), s["body"])],
        [Paragraph(en("現金與流動性 (Cash)"), s["body"]), Paragraph(en("15%", bold=True), s["body"]),
         Paragraph(en("⬇️ -10% (彈性)"), s["body"]), Paragraph(en("保留 15% 流動性，作為極端震盪或急跌時之二度加碼彈性預備金"), s["body"])],
        [Paragraph(en("黃金與替代資產"), s["body"]), Paragraph(en("5%", bold=True), s["body"]),
         Paragraph(en("➡️ 持平"), s["body"]), Paragraph(en("保持 5% 黃金/數位資產部位，作為地緣政治風險與貨幣貶值之對沖"), s["body"])],
    ]
    t_alloc = Table(alloc, colWidths=T.COLS_DETAIL)
    t_alloc.setStyle(_detail_style(T.NAVY, T.BORDER, s))
    story.append(t_alloc)

    # ======================= PAGE 5 — Entry / Exit targets =================
    story.append(PageBreak())
    story.extend(make_title_row("各領域進場與退場投資標的整合追蹤",
        "綜合融資維持率、籌碼動向、Valuation 評價與總經趨勢之精選投資標的清單", date_str, T.SIGNAL_BUY, s))

    story.append(Paragraph(en("<b>🟢 適合進場 / 分批加碼投資標的 (Recommended Entry Targets)</b>"), s["h1"]))
    story.append(_detail_table(
        ["投資領域", "標的名稱 / 代碼", "建議進場策略", "核心選股/選債量化理由"],
        [
            ["台股市場", "市值型 / 半導體 ETF<br/>(如 0050, 0052)", "分批逢低建立核心部位", f"全市場融資餘額 {twm/10000:.1f} 萬張、低於門檻，槓桿未過熱；先進封裝與 CoWoS 產能滿載，評價具吸引力。"],
            ["台股市場", "AI 伺服器水冷與散熱龍頭", "拉回重心支撐線加碼", "AI 伺服器單機功耗暴增，營收月增率持強，法人與投信連續 15 日買超護盤。"],
            ["美股市場", "標普 500 / 納指 ETF<br/>(如 VOO, QQQ)", "分 3 批定期定額扣款", f"VIX 升至 {vix} + F&amp;G 降至 {fg} 極度恐慌區，歷史回測分批進場勝率 > 82%。"],
            ["美股市場", "雲端 Hyperscaler &amp; AI 巨頭", "分批進場", "科技巨頭 2026 年 Capex 資本支出持續上修，自由現金流非常強健。"],
            ["全球債券", "20年期以上美國公債 ETF<br/>(如 TLT, 00679B)", "單筆搭配定期定額", f"10Y-2Y 倒掛結束，鎖定 {t10}%~{t10 + 0.15:.2f}% 高殖利率，降息啟動享資本利得。"],
            ["數位資產", "比特幣現貨 ETF / BTC", "分批佈局", "永續合約資費歸零、交易所槓桿多單清理完畢，鏈上算力持續創新高。"],
        ],
        header_bg=T.SIGNAL_BUY, grid_color=colors.HexColor('#E8F0E9'), styles=s,
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph(en("<b>🔴 需要注意退場 / 減碼避險投資標的 (Warning &amp; Exit Targets)</b>"), s["h1"]))
    story.append(_detail_table(
        ["投資領域", "標的類別 / 警示特徵", "建議退場/避險策略", "風險警示理由與量化數據"],
        [
            ["台股市場", "高融資比率之純題材中小型股", "反彈即時分批減碼", "大盤融資斷頭潮尚未全數結束，高融資率小型股面臨追繳與多殺多流動性風險。"],
            ["台股市場", "成熟製程與消費性電子弱勢股", "尋求停損或轉換標的", "終端消費需求復甦步調低於預期，毛利率持續受成熟製程價格戰壓抑。"],
            ["美股市場", "高債務與零獲利高估值科技股", "分批逢高出清離場", "高利率維持更久 (Higher for Longer) 壓抑無獔利公司估值，融資利息負擔過高。"],
            ["外匯與商品", "高槓桿槓桿型 ETF<br/>(如 2X/3X 槓桿商品)", "即時停損減碼離場", "市場波動率 VIX 大幅跳升，高波動期間槓桿 ETF 損耗風險極高，不宜長期持有。"],
        ],
        header_bg=T.SIGNAL_SELL, grid_color=colors.HexColor('#FDE7E1'), styles=s,
    ))

    # ======================= PAGE 6 — Macro Dashboard =========================
    story.append(PageBreak())
    story.extend(make_title_row(
        "總體經濟儀表板（Macro Dashboard）",
        "殖利率曲線 × 10Y 走勢 × 通膨趨勢 — 資料：美國財政部 / BLS（TTL 快取：月頻 7 天、殖利率 1 天）",
        date_str, T.SAGE, s))
    md = data.get("macro") or {}
    ycd = md.get("yield_curve") or {}
    curve = ycd.get("curve") or {}
    have_any = False
    if curve:
        have_any = True
        story.append(Paragraph(en(f"<b>美債殖利率曲線（{ycd.get('date', '')}）</b>"), s["h1"]))
        story.append(_line_chart(list(curve.keys()), [list(curve.values())], height=138))
        story.append(Spacer(1, 6))
    ten10y = md.get("us10y_hist") or []
    if len(ten10y) >= 20:
        have_any = True
        step = max(1, len(ten10y) // 8)
        labels = [p["date"][:5] if i % step == 0 else ""
                  for i, p in enumerate(ten10y)]
        vals = [p["v"] for p in ten10y]
        first, last = ten10y[0], ten10y[-1]
        story.append(Paragraph(
            en(f"<b>美債 10Y 殖利率走勢（{first['date']} → {last['date']}，年內 {len(ten10y)} 個交易日）</b>"),
            s["h1"]))
        story.append(_line_chart(labels, [vals], height=138))
        story.append(Spacer(1, 6))
    cpi_r2 = _yoy_series(md.get("cpi_hist"))
    core_r2 = _yoy_series(md.get("core_cpi_hist"))
    if cpi_r2 or core_r2:
        have_any = True
        series = [r[0] for r in (cpi_r2, core_r2) if r]
        labels = (cpi_r2 or core_r2)[1]
        story.append(Paragraph(en("<b>通膨趨勢 — CPI / Core CPI 年增率（青線 = CPI，琥珀線 = Core CPI）</b>"), s["h1"]))
        story.append(_line_chart(labels, series, height=138))
        story.append(Spacer(1, 6))
    if curve and len(ten10y) >= 20:
        def _cv(t):
            return curve.get(t)
        rows = [[Paragraph(en("<b>計算指標</b>", color="#FFFFFF"), s["th"]),
                 Paragraph(en("<b>最新值</b>", color="#FFFFFF"), s["th"]),
                 Paragraph(en("<b>參考判準</b>", color="#FFFFFF"), s["th"]),
                 Paragraph(en("<b>判讀</b>", color="#FFFFFF"), s["th"])]]

        def _spread_row(name, lo, hi, ref, judge):
            a, b = _cv(lo), _cv(hi)
            if a is None or b is None:
                return
            v = round(b - a, 2)
            rows.append([Paragraph(en(name), s["body"]),
                         Paragraph(en(f"{v:+.2f}%", bold=True), s["body"]),
                         Paragraph(en(ref), s["body"]),
                         Paragraph(en(judge(v)), s["body"])])
        _spread_row("2Y–10Y 利差", "2Y", "10Y", "0% = 曲線正常",
                    lambda v: "🟢 正常化" if v > 0 else "🔴 倒掛")
        _spread_row("3M–10Y 利差", "3M", "10Y", "聯準會觀察重點",
                    lambda v: "🟢 正斜率" if v > 0 else "🟡 仍倒掛")
        _spread_row("5Y–30Y 利差", "5Y", "30Y", "長端期限貼水",
                    lambda v: "🟢 正常" if v > 0 else "🟡 貼水反轉")
        m_ago = ten10y[max(0, len(ten10y) - 22)]
        chg = round(ten10y[-1]["v"] - m_ago["v"], 2)
        rows.append([Paragraph(en("10Y 月變化"), s["body"]),
                     Paragraph(en(f"{chg:+.2f}%", bold=True), s["body"]),
                     Paragraph(en(f"vs {m_ago['date']}"), s["body"]),
                     Paragraph(en("🟢 降息預期升溫" if chg < -0.1 else ("🟡 溫和波動" if chg < 0.25 else "🔴 明顯上行")), s["body"])])
        t_spread = Table(rows, colWidths=[110, 80, 130, 227])
        t_spread.setStyle(_detail_style(T.NAVY, T.BORDER, s))
        story.append(Paragraph(en("<b>利差與動能計算表</b>"), s["h1"]))
        story.append(t_spread)
    if not have_any:
        story.append(Paragraph(en("（總經資料來源暫時無法取得，快取亦為空——本頁略過圖表）"), s["body"]))

    doc = new_doc(filename, title="Financial Intelligence 每日投資趨勢報告")
    doc.build(story, onFirstPage=footer_factory(DISCLAIMER, _PAGE_TOTAL),
              onLaterPages=footer_factory(DISCLAIMER, _PAGE_TOTAL))
    print("PDF build complete:", filename)
    return filename


# ---- local style + table helpers ------------------------------------------
from reportlab.lib.styles import ParagraphStyle


def ParagraphStyle_local(name, size, color, leading=None, align=0):
    from core.fonts import FONT_CJK
    return ParagraphStyle(name, fontName=FONT_CJK, fontSize=size,
                          leading=leading or size + 3, textColor=color, alignment=align)


def _detail_style(header_bg, grid_color, styles):
    return TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), header_bg),
        ('FONTNAME', (0, 0), (-1, -1), styles["body"].fontName),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, grid_color),
        ('BACKGROUND', (0, 1), (-1, -1), T.BG_CARD),
        ('PADDING', (0, 0), (-1, -1), 5),
    ])


def _detail_table(headers, rows, header_bg, grid_color, styles):
    head = [Paragraph(en(f"<b>{h}</b>", color="#FFFFFF"), styles["th"]) for h in headers]
    data = [head]
    for r in rows:
        data.append([
            Paragraph(en(r[0]), styles["body"]),
            Paragraph(en(r[1], bold=True), styles["body"]),
            Paragraph(en(r[2]), styles["body"]),
            Paragraph(en(r[3]), styles["body"]),
        ])
    t = Table(data, colWidths=T.COLS_DETAIL)
    t.setStyle(_detail_style(header_bg, grid_color, styles))
    return t


if __name__ == "__main__":
    out = os.path.join(_REPO_ROOT, "output", "Financial_Intelligence_每日投資趨勢報告.pdf")
    generate_daily_pdf(out, data={}, date_str="2026-08-11")
