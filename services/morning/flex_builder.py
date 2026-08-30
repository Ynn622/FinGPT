"""將市場、當沖與波段內容組成 LINE Flex 訊息。"""

import json
from typing import Any, Dict, List, Optional

from services.morning.models import MorningReport


MAX_CAROUSEL_BYTES = 50 * 1024
MAX_BUBBLE_BYTES = 30 * 1024


def _text(text: str, **kwargs: Any) -> Dict[str, Any]:
    """建立具備自動換行設定的 Flex 文字元件。"""
    return {"type": "text", "text": str(text), "wrap": True, **kwargs}


def _row(label: str, value: str, value_color: str = "#111827") -> Dict[str, Any]:
    """建立標籤與數值左右排列的 Flex 資料列。"""
    return {
        "type": "box", "layout": "horizontal", "alignItems": "center",
        "contents": [
            _text(label, size="sm", color="#6B7280", flex=3),
            _text(value, size="sm", color=value_color, weight="bold", align="end", flex=6),
        ],
    }


def _header(title: str, accent: str, score: Optional[float] = None) -> Dict[str, Any]:
    """建立含標題與可選分數徽章的 Flex 頁首。"""
    contents = [_text(title, color="#FFFFFF", weight="bold", size="lg", flex=6)]
    if score is not None:
        score_text = f"{score:+.0f}" if title.startswith("FinGPT") else f"{score:.0f}分"
        contents.append({
            "type": "box", "layout": "vertical", "backgroundColor": "#F8FAFC",
            "cornerRadius": "8px", "paddingAll": "6px", "flex": 0,
            "contents": [_text(score_text, color=accent, weight="bold", size="md", align="center")],
        })
    return {
        "type": "box", "layout": "horizontal", "alignItems": "center",
        "backgroundColor": accent, "paddingAll": "18px", "contents": contents,
    }


def _bubble(
    title: str,
    subtitle: Any,
    rows: List[Dict[str, Any]],
    notes: List[str],
    accent: str,
    score: Optional[float] = None,
    section_label: str = "理由",
    size: str = "mega",
    footer: Optional[Dict[str, Any]] = None,
    note_limit: int = 5,
    ai_comment: str = "",
) -> Dict[str, Any]:
    """建立可重用的 Flex Bubble 基本結構。"""
    body = [subtitle if isinstance(subtitle, dict) else _text(subtitle, size="xl", weight="bold", color="#111827")]
    body.extend(rows)
    if notes:
        body.append(_text(section_label, size="sm", weight="bold", color="#374151", margin="md"))
        body.extend(_text(f"• {note}", size="sm", color="#4B5563") for note in notes[:note_limit])
    if ai_comment:
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs", "margin": "md",
            "paddingAll": "8px", "cornerRadius": "8px", "backgroundColor": "#F5F3FF",
            "borderWidth": "1px", "borderColor": "#DDD6FE",
            "contents": [
                _text("AI 觀察", size="xs", weight="bold", color="#6D28D9"),
                _text(ai_comment, size="sm", color="#3F3F46"),
            ],
        })
    bubble = {
        "type": "bubble", "size": size, "header": _header(title, accent, score),
        "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": body},
    }
    if footer:
        bubble["footer"] = footer
    return bubble


def _disclaimer_footer(disclaimer: str) -> Dict[str, Any]:
    """建立總表卡片共用的免責聲明頁尾。"""
    return {
        "type": "box", "layout": "vertical", "spacing": "sm",
        "paddingTop": "8px", "paddingBottom": "14px", "paddingStart": "18px", "paddingEnd": "18px",
        "contents": [
            {"type": "separator", "color": "#E5E7EB"},
            _text(disclaimer, size="xxs", color="#94A3B8", align="center"),
        ],
    }


def _price(value: float, key: str) -> str:
    """依市場商品類型格式化顯示價格。"""
    if key in {"sp500", "nasdaq"}:
        return f"{value:,.2f}"
    if key == "tx":
        return f"{value:,.0f}"
    if key == "usdtwd":
        return f"{value:.2f}"
    return f"{value:,.2f}"


def _market_direction_row(regime: str, score: float, color: str) -> Dict[str, Any]:
    """建立市場情境與分數資料列。"""
    return {
        "type": "box", "layout": "horizontal", "alignItems": "center",
        "contents": [
            _text("今日市場", size="sm", color="#6B7280", flex=3),
            {"type": "box", "layout": "horizontal", "justifyContent": "flex-end", "alignItems": "center",
             "spacing": "sm", "flex": 6, "contents": [
                 _text(regime, size="sm", color=color, weight="bold", align="end", flex=0),
                 _text(f"（{score:.0f}分）", size="xs", color=color, weight="bold", align="end", flex=0),
             ]},
        ],
    }


def _market_price_row(
    label: str, price: str, change: str, change_pct: float, color: str,
) -> Dict[str, Any]:
    """建立市場價格、漲跌值與漲跌幅資料列。"""
    return {
        "type": "box", "layout": "horizontal", "alignItems": "center",
        "contents": [
            _text(label, size="sm", color="#6B7280", flex=3),
            {"type": "box", "layout": "vertical", "alignItems": "flex-end",
             "spacing": "none", "flex": 6, "contents": [
                 _text(price, size="sm", color=color, weight="bold", align="end"),
                 _text(f"（{change}｜{change_pct:+.2f}%）", size="xxs", color=color, align="end"),
             ]},
        ],
    }


def _stock_heading(stock_id: str, stock_name: str, direction: str, color: str) -> Dict[str, Any]:
    """建立股票代號、名稱與交易方向標題。"""
    background = "#FEF2F2" if color == "#DC2626" else "#F0FDF4"
    return {
        "type": "box", "layout": "horizontal", "alignItems": "center", "contents": [
            _text(f"{stock_id} {stock_name}", size="xl", weight="bold", color="#111827", flex=1),
            {"type": "box", "layout": "vertical", "flex": 0, "backgroundColor": background,
             "cornerRadius": "8px", "paddingAll": "6px",
             "contents": [_text(direction, size="sm", color=color, weight="bold", align="center")]},
        ],
    }


def _summary_row(
    rank: int,
    stock_id: str,
    stock_name: str,
    direction: str,
    score: float,
    direction_color: str,
    price: Optional[float] = None,
) -> Dict[str, Any]:
    """建立排行榜中的單一股票摘要列。"""
    score_background = "#FEF2F2" if direction_color == "#DC2626" else "#F0FDF4"
    score_badge = {
        "type": "box", "layout": "vertical", "flex": 0, "backgroundColor": "#E2E8F0",
        "cornerRadius": "7px", "paddingAll": "5px",
        "contents": [_text(f"{score:.0f}分", size="sm", color="#334155", weight="bold", align="center")],
    }
    direction_badge = {
        "type": "box", "layout": "vertical", "flex": 0, "backgroundColor": score_background,
        "cornerRadius": "7px", "paddingAll": "5px", "margin": "sm",
        "contents": [_text(direction, size="sm", color=direction_color, weight="bold", align="center")],
    }
    contents: List[Dict[str, Any]] = [
        _text(f"#{rank}", size="sm", color="#475569", weight="bold", align="center", flex=1),
        {"type": "box", "layout": "vertical", "flex": 5, "spacing": "none", "margin": "sm", "contents": [
            _text(stock_id, size="sm", color="#111827", weight="bold"),
            _text(stock_name, size="xs", color="#64748B"),
        ]},
    ]
    if price is not None:
        contents.append(_text(
            f"${price:g}", size="xs", color=direction_color, weight="bold", align="center", flex=0,
        ))
    contents.extend([direction_badge, score_badge])
    return {
        "type": "box", "layout": "horizontal", "alignItems": "center", "paddingAll": "10px",
        "cornerRadius": "10px", "backgroundColor": "#F8FAFC", "contents": contents,
    }


def _price_marker(label: str, value: str, color: str, flex: int = 2) -> Dict[str, Any]:
    """建立交易價位標籤與色條元件。"""
    return {
        "type": "box", "layout": "vertical", "alignItems": "center", "spacing": "xs", "flex": flex,
        "contents": [
            _text(label, size="xxs", color="#64748B", align="center"),
            {"type": "box", "layout": "vertical", "height": "5px", "backgroundColor": color,
             "cornerRadius": "3px", "contents": []},
            _text(value, size="xs", color=color, weight="bold", align="center"),
        ],
    }


def _intraday_price_bar(item: Any, direction_color: str, stop_color: str, target_color: str) -> Dict[str, Any]:
    """建立當沖前收、觸發、停損與目標價橫列。"""
    return {
        "type": "box", "layout": "horizontal", "alignItems": "center", "spacing": "xs",
        "margin": "md", "paddingAll": "10px", "cornerRadius": "10px", "backgroundColor": "#F8FAFC",
        "contents": [
            _price_marker("前收", f"{item.previous_close:g}", "#64748B"),
            _price_marker("觸發", f"{item.entry:g}", direction_color),
            _price_marker("止損", f"{item.stop:g}", stop_color),
            _price_marker("TP1 / TP2", f"{item.tp1:g}/{item.tp2:g}", target_color, 3),
        ],
    }


def _intraday_summary_bubble(report: MorningReport) -> Dict[str, Any]:
    """建立當沖推薦總表 Bubble。"""
    rows = []
    for index, item in enumerate(report.intraday, 1):
        is_long = item.direction == "LONG"
        rows.append(_summary_row(
            index, item.stock_id, item.stock_name,
            "多" if is_long else "空", item.score,
            "#DC2626" if is_long else "#15803D",
            item.entry,
        ))
    return _bubble(
        "🔥 當沖 Top5 總表", f"{report.report_date.replace('-', '/')} 當沖精選", rows,
        [], "#B91C1C",
        footer=_disclaimer_footer(report.disclaimer),
    )


def _swing_summary_bubble(report: MorningReport) -> Dict[str, Any]:
    """建立波段推薦總表 Bubble。"""
    rows = []
    for index, item in enumerate(report.swing, 1):
        rows.append(_summary_row(
            index, item.stock_id, item.stock_name, "多", item.score, "#DC2626",
        ))
    return _bubble(
        "📈 波段 Top5 總表", f"{report.report_date.replace('-', '/')} 波段精選", rows,
        [], "#4338CA",
        footer=_disclaimer_footer(report.disclaimer),
    )


def _market_bubble(report: MorningReport) -> Dict[str, Any]:
    """建立盤前市場總覽 Bubble。"""
    # 台股慣例使用紅色表示上漲或偏多，綠色表示下跌或偏空。
    regime_color = "#DC2626" if report.market_score >= 10 else "#15803D" if report.market_score <= -10 else "#475569"
    rows = [_market_direction_row(report.market_regime, report.market_score, regime_color)]
    for key, label in (
        ("sp500", "S&P 500"), ("nasdaq", "NASDAQ"), ("sox", "費城半導體"),
        ("tsm", "台積電ADR"), ("usdtwd", "USD/TWD"),
    ):
        snapshot = report.global_market.get(key)
        if snapshot:
            color = "#DC2626" if snapshot.change_pct >= 0 else "#15803D"
            change = f"{snapshot.change:+,.2f}"
            rows.append(_market_price_row(label, _price(snapshot.last_close, key), change, snapshot.change_pct, color))
    if report.tx_night:
        change_pct = float(report.tx_night["change_pct"])
        color = "#DC2626" if change_pct >= 0 else "#15803D"
        change = f"{float(report.tx_night.get('change', 0)):+,.0f}"
        rows.append(_market_price_row("台指期夜盤", _price(float(report.tx_night["close"]), "tx"), change, change_pct, color))
    else:
        rows.append(_row("台指期夜盤", "官方資料更新中", "#64748B"))
    availability = []
    if len(report.intraday) < 5:
        availability.append(f"今日符合當沖條件標的僅 {len(report.intraday)} 檔，其餘建議觀望")
    if len(report.swing) < 5:
        availability.append(f"今日符合波段條件標的僅 {len(report.swing)} 檔，其餘建議觀望")
    return _bubble(
        f"FinGPT 盤前情報｜{report.report_date.replace('-', '/')}", "盤前預估", rows,
        [report.market_summary[:320], *[f"新聞｜{item}" for item in report.focus[:5]], *availability],
        "#123B63", None, "盤前重點", "giga",
        _disclaimer_footer(report.disclaimer),
        8,
    )


def _intraday_bubbles(report: MorningReport) -> List[Dict[str, Any]]:
    """建立所有當沖推薦的詳細 Bubble。"""
    bubbles = []
    for index, item in enumerate(report.intraday, 1):
        is_long = item.direction == "LONG"
        direction_color = "#DC2626" if is_long else "#15803D"
        direction_label = "做多" if is_long else "做空"
        stop_color = "#15803D" if is_long else "#DC2626"
        target_color = "#DC2626" if is_long else "#15803D"
        bubbles.append(_bubble(
            f"🔥 當沖 #{index}", _stock_heading(item.stock_id, item.stock_name, direction_label, direction_color),
            [_intraday_price_bar(item, direction_color, stop_color, target_color),
             _row("ATR", f"{item.atr_pct*100:.1f}%"),
             _row("昨/20日均量", f"{item.volume_ratio:.1f} 倍")],
            item.reasons,
            direction_color, item.score,
            ai_comment=item.ai_comment,
        ))
    return bubbles


def _swing_bubbles(report: MorningReport) -> List[Dict[str, Any]]:
    """建立所有波段推薦的詳細 Bubble。"""
    bubbles = []
    for index, item in enumerate(report.swing, 1):
        institution_color = (
            "#DC2626" if item.institutional_tone == "BULLISH"
            else "#15803D" if item.institutional_tone == "BEARISH"
            else "#64748B"
        )
        bubbles.append(_bubble(
            f"📈 波段 #{index}", _stock_heading(item.stock_id, item.stock_name, "做多", "#DC2626"),
            [{"type": "box", "layout": "horizontal", "spacing": "xs", "margin": "md",
              "paddingAll": "10px", "cornerRadius": "10px", "backgroundColor": "#F8FAFC",
              "contents": [_price_marker("前收", f"{item.previous_close:g}", "#64748B"),
                           _price_marker("支撐", f"{item.support:g}", "#15803D"),
                           _price_marker("壓力", f"{item.resistance:g}", "#DC2626")]},
             _row("趨勢", item.trend, "#DC2626"),
             _row("20D 報酬", f"{item.return_20d:+.1f}%"),
             _row("昨/20日均量", f"{item.volume_ratio:.1f} 倍"),
             _row("籌碼", item.institutional, institution_color)],
            item.reasons, "#4338CA", item.score,
            ai_comment=item.ai_comment,
        ))
    return bubbles


def build_flex_payloads(report: MorningReport) -> List[Dict[str, Any]]:
    """建立單次 LINE 廣播所需的最多三個 Flex 容器。"""
    payloads: List[Dict[str, Any]] = [_market_bubble(report)]
    intraday = _intraday_bubbles(report)
    swing = _swing_bubbles(report)
    if intraday:
        payloads.append({"type": "carousel", "contents": [_intraday_summary_bubble(report), *intraday]})
    if swing:
        payloads.append({"type": "carousel", "contents": [_swing_summary_bubble(report), *swing]})
    for payload in payloads:
        validate_flex_payload_size(payload)
    return payloads


def validate_flex_payload_size(payload: Dict[str, Any]) -> int:
    """驗證 Flex Bubble、Carousel 數量與位元組大小限制。"""
    if payload.get("type") == "bubble":
        size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        if size > MAX_BUBBLE_BYTES:
            raise ValueError("LINE Flex bubble exceeds 30 KB")
        return size
    bubbles = payload.get("contents", [])
    if len(bubbles) > 12:
        raise ValueError("LINE Flex carousel may contain at most 12 bubbles")
    for bubble in bubbles:
        if len(json.dumps(bubble, ensure_ascii=False).encode("utf-8")) > MAX_BUBBLE_BYTES:
            raise ValueError("LINE Flex bubble exceeds 30 KB")
    size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    if size > MAX_CAROUSEL_BYTES:
        raise ValueError("LINE Flex carousel exceeds 50 KB")
    return size
