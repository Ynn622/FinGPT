"""使用 Responses API 補充文字並提供確定性備援內容。"""

import json
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List

from openai import OpenAI

from services.morning.models import IntradayRecommendation, MarketSnapshot, SwingRecommendation
from util.config import Env
from util.logger import Color, Log


AI_INSTRUCTION = (
    "你是台股盤前報告文字編輯，只能根據輸入生成繁體中文摘要。"
    "不得修改、推測或補充數值，不得改排名、價格、分數與股票。"
    "不用再重複輸入的數據，僅生成摘要文字。"
    "市場摘要140至220字。"
    "個股評論不得重述、改寫或拼接reasons，也不得重複技術指標。"
    "每檔評論只能根據news中相同股票代號的新聞，補充一項催化因素、風險或後續觀察，30至60字。"
    "若該股票沒有直接相關新聞，評論必須回傳空字串。"
    "focus必須是3至5則統整輸入新聞後的極簡摘要，每則16~24字，避免重複與空泛題材名稱。"
)


def _normalize_text(value: str) -> str:
    """移除標點與空白，供評論重複度檢查。"""
    return re.sub(r"[^\w\u4e00-\u9fff]", "", value).lower()


def _comment_repeats_reasons(comment: str, reasons: List[str]) -> bool:
    """阻擋只把量化理由重新順句的 AI 評論。"""
    normalized = _normalize_text(comment)
    if not normalized:
        return False
    reason_texts = [_normalize_text(reason) for reason in reasons if reason]
    if any(text and (normalized in text or text in normalized) for text in reason_texts):
        return True
    combined = "".join(reason_texts)
    return bool(combined) and SequenceMatcher(None, normalized, combined).ratio() >= .65


def _sanitize_stock_comments(
    result: Dict[str, Any],
    intraday: List[IntradayRecommendation],
    swing: List[SwingRecommendation],
    news: Dict[str, Any],
) -> Dict[str, Any]:
    """沒有個股新聞或內容重複時移除評論，確保 AI 觀察提供新資訊。"""
    for key, recommendations in (("intraday_comments", intraday), ("swing_comments", swing)):
        comments = result.get(key)
        if not isinstance(comments, dict):
            result[key] = {}
            continue
        for item in recommendations:
            comment = str(comments.get(item.stock_id, "")).strip()
            has_stock_news = isinstance(news.get(item.stock_id), list) and bool(news[item.stock_id])
            if not has_stock_news or _comment_repeats_reasons(comment, item.reasons):
                comment = ""
            comments[item.stock_id] = comment
    return result


def _fallback_news_digest(news: Dict[str, Any]) -> List[str]:
    """從新聞資料整理最多三則備援焦點標題。"""
    digest: List[str] = []
    for items in news.values():
        if not isinstance(items, list):
            continue
        for item in items:
            title = str(item.get("Title", "")).strip() if isinstance(item, dict) else ""
            if title and title not in digest:
                digest.append(title[:28])
            if len(digest) == 3:
                return digest
    return digest or ["市場新聞資料暫缺"]


def template_summary(
    market: Dict[str, MarketSnapshot], tx: Any, regime: str, news: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """依市場資料產生不依賴 AI 的盤前摘要。"""
    parts = []
    for key, label in (("nasdaq", "NASDAQ"), ("tsm", "TSM ADR")):
        if key in market:
            parts.append(f"{label} {market[key].change_pct:+.2f}%")
    if tx:
        parts.append(f"台指夜盤 {tx['change_pct']:+.2f}%")
    context = "、".join(parts) or "部分海外市場資料暫缺"
    return {
        "market_summary": f"今日市場判定為{regime}，{context}。早盤僅在量化觸發價出現後評估進場。",
        "market_risk": "盤前資訊可能受開盤跳空影響，未觸發不進場並嚴守止損。",
        "focus": _fallback_news_digest(news or {}),
        "intraday_comments": {},
        "swing_comments": {},
    }


def generate_summary(
    market: Dict[str, MarketSnapshot], tx: Any, regime: str,
    intraday: List[IntradayRecommendation], swing: List[SwingRecommendation], news: Dict[str, Any],
) -> Dict[str, Any]:
    """呼叫 OpenAI 產生盤前摘要並在失敗時使用範本。"""
    fallback = template_summary(market, tx, regime, news)
    if not Env.OPENAI_API_KEY: return fallback
    payload = {
        "market": {key: value.to_dict() for key, value in market.items()},
        "tx_night": tx, 
        "market_regime": regime,
        "intraday": [item.to_dict() for item in intraday],
        "swing": [item.to_dict() for item in swing], 
        "news": news,
    }
    intraday_properties = {item.stock_id: {"type": "string"} for item in intraday}
    swing_properties = {item.stock_id: {"type": "string"} for item in swing}
    schema = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "market_summary": {"type": "string"}, "market_risk": {"type": "string"},
            "focus": {"type": "array", "items": {"type": "string"}},
            "intraday_comments": {
                "type": "object", "additionalProperties": False,
                "properties": intraday_properties, "required": list(intraday_properties),
            },
            "swing_comments": {
                "type": "object", "additionalProperties": False,
                "properties": swing_properties, "required": list(swing_properties),
            },
        },
        "required": ["market_summary", "market_risk", "focus", "intraday_comments", "swing_comments"],
    }
    try:
        response = OpenAI(api_key=Env.OPENAI_API_KEY, timeout=20).responses.create(
            model=Env.MORNING_AI_MODEL,
            instructions=AI_INSTRUCTION,
            input=json.dumps(payload, ensure_ascii=False, default=str),
            text={"format": {"type": "json_schema", "name": "morning_report", "strict": True, "schema": schema}},
            store=False,
        )
        parsed = json.loads(response.output_text)
        return _sanitize_stock_comments(parsed, intraday, swing, news) if isinstance(parsed, dict) else fallback
    except Exception as error:
        Log(f"[Morning] OpenAI summary fallback: {error}", color=Color.YELLOW)
        return fallback
