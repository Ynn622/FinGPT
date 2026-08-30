"""盤前報告各層共用的型別資料模型。"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


class Serializable:
    def to_dict(self) -> Dict[str, Any]:
        """將資料模型遞迴轉換成字典。"""
        return asdict(self)


@dataclass
class MarketSnapshot(Serializable):
    key: str
    symbol: str
    last_close: float
    previous_close: float
    change: float
    change_pct: float
    source_date: str = ""


@dataclass
class StockCandidate(Serializable):
    stock_id: str
    stock_name: str
    market: str
    date: str
    close: float
    volume: float
    trade_value: float

    @property
    def yahoo_symbol(self) -> str:
        """依上市或上櫃市場產生 Yahoo Finance 股票代號。"""
        return f"{self.stock_id}.{'TW' if self.market == 'TWSE' else 'TWO'}"


@dataclass
class TechnicalFeatures(Serializable):
    stock_id: str
    date: str
    close: float
    previous_high: float
    previous_low: float
    ma5: float
    ma10: float
    ma20: float
    ma60: float
    ema5: float
    ema10: float
    ema20: float
    macd: float
    macd_signal: float
    macd_histogram: float
    rsi14: float
    roc5: float
    roc20: float
    atr14: float
    atr_pct: float
    volume_ma5: float
    volume_ma20: float
    volume_ratio: float
    clv: float
    return_1d: float
    return_5d: float
    return_20d: float
    high_20d: float
    low_20d: float
    ma20_slope: float
    avg_trade_value_20d: float


@dataclass
class InstitutionalData(Serializable):
    stock_id: str
    foreign_1d: float = 0
    foreign_3d: float = 0
    foreign_5d: float = 0
    trust_1d: float = 0
    trust_3d: float = 0
    trust_5d: float = 0
    dealer_1d: float = 0
    dealer_3d: float = 0
    dealer_5d: float = 0
    foreign_streak: int = 0
    trust_streak: int = 0
    dealer_streak: int = 0
    available: bool = True


@dataclass
class StockRiskFlag(Serializable):
    stock_id: str
    warning: bool = False
    disposal: bool = False
    altered_trading: bool = False
    can_day_trade: bool = False
    can_short_day_trade: bool = False


@dataclass
class IntradayRecommendation(Serializable):
    stock_id: str
    stock_name: str
    direction: str
    score: float
    previous_close: float
    entry: float
    stop: float
    tp1: float
    tp2: float
    atr_pct: float
    volume_ratio: float
    reasons: List[str] = field(default_factory=list)
    ai_comment: str = ""


@dataclass
class SwingRecommendation(Serializable):
    stock_id: str
    stock_name: str
    score: float
    previous_close: float
    trend: str
    support: float
    resistance: float
    return_20d: float
    volume_ratio: float
    institutional: str
    reasons: List[str] = field(default_factory=list)
    ai_comment: str = ""
    institutional_tone: str = "NEUTRAL"


@dataclass
class MorningReport(Serializable):
    report_date: str
    data_date: str
    market_score: float
    market_regime: str
    global_market: Dict[str, MarketSnapshot]
    tx_night: Optional[Dict[str, Any]]
    market_summary: str
    market_risk: str
    focus: List[str]
    intraday: List[IntradayRecommendation]
    swing: List[SwingRecommendation]
    news: Dict[str, Any] = field(default_factory=dict)
    disclaimer: str = "僅供研究與資訊參考，不構成投資建議。"
