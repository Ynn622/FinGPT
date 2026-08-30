"""確定性的當沖與波段評分工具。"""

from typing import Dict, List, Optional, Tuple

from services.morning.models import InstitutionalData, TechnicalFeatures
from services.morning.utils import clamp, weighted_score


INTRADAY_WEIGHTS = {
    "liquidity": 20, "volatility": 20, "volume": 15,
    "structure": 20, "momentum": 15, "institutional": 10,
}
SWING_WEIGHTS = {
    "trend": 30, "momentum": 20, "volume": 15,
    "institutional": 25, "relative_strength": 10,
}


def volatility_points(atr_pct: float) -> float:
    """依 ATR 波動率計算當沖波動分數。"""
    pct = atr_pct * 100
    if pct < 1:
        return 2
    if pct < 1.5:
        return 8
    if pct < 2.5:
        return 15
    if pct < 4.5:
        return 20
    if pct < 6:
        return 12
    return 5


def volume_points(ratio: float, maximum: float = 15) -> float:
    """依成交量比率換算指定上限的量能分數。"""
    points = 15 if ratio >= 2 else 12 if ratio >= 1.5 else 9 if ratio >= 1.2 else 5 if ratio >= 0.8 else 2
    return points / 15 * maximum


def _structure(feature: TechnicalFeatures, direction: str) -> Tuple[float, List[str]]:
    """依價格結構與交易方向計算分數及理由。"""
    points, reasons = 0.0, []
    if direction == "LONG":
        points += 8 if feature.clv >= .8 else 5 if feature.clv >= .6 else 2 if feature.clv >= .4 else 0
        if feature.clv >= .6: reasons.append("收盤位於日內區間上緣")
        if feature.return_1d > 0: points += 4; reasons.append("前一交易日收紅")
        if feature.close >= feature.high_20d * .97: points += 4; reasons.append("距20日高點3%內")
        if feature.close > feature.ma20: points += 4; reasons.append("收盤站上MA20")
    else:
        points += 8 if feature.clv <= .2 else 5 if feature.clv <= .4 else 2 if feature.clv <= .6 else 0
        if feature.clv <= .4: reasons.append("收盤位於日內區間下緣")
        if feature.return_1d < 0: points += 4; reasons.append("前一交易日收黑")
        if feature.close <= feature.low_20d * 1.03: points += 4; reasons.append("距20日低點3%內")
        if feature.close < feature.ma20: points += 4; reasons.append("收盤跌破MA20")
    return min(points, 20), reasons


def _momentum(feature: TechnicalFeatures, direction: str) -> Tuple[float, List[str]]:
    """依技術動能與交易方向計算分數及理由。"""
    points, reasons = 0.0, []
    if direction == "LONG":
        if feature.close > feature.ma5 > feature.ma20: points += 4; reasons.append("短均線多頭排列")
        if feature.macd_histogram > 0: points += 3; reasons.append("MACD動能偏多")
        if feature.roc5 > 0: points += 3
        if feature.roc20 > 0: points += 2
        if 50 <= feature.rsi14 <= 72: points += 3
    else:
        if feature.close < feature.ma5 < feature.ma20: points += 4; reasons.append("短均線空頭排列")
        if feature.macd_histogram < 0: points += 3; reasons.append("MACD動能偏空")
        if feature.roc5 < 0: points += 3
        if feature.roc20 < 0: points += 2
        if 28 <= feature.rsi14 <= 50: points += 3
    return points, reasons


def _institutional_points(
    data: Optional[InstitutionalData], feature: TechnicalFeatures, direction: str, maximum: float
) -> Optional[float]:
    """依法人買賣超連續性與成交量占比計算籌碼分數。"""
    if data is None or not data.available or feature.volume_ma20 <= 0:
        return None
    # 富邦爬蟲的單位為張，Yahoo Finance 的成交量單位為股。
    ratio = institutional_flow_ratio(data, feature)
    directional = ratio if direction == "LONG" else -ratio
    continuity = 0.0
    direction_sign = 1 if direction == "LONG" else -1
    if all(direction_sign * value > 0 for value in (data.foreign_1d, data.foreign_3d, data.foreign_5d)):
        continuity += maximum * .08
    if all(direction_sign * value > 0 for value in (data.trust_1d, data.trust_3d, data.trust_5d)):
        continuity += maximum * .12
    return clamp(maximum / 2 + directional * maximum * 20 + continuity, 0, maximum)


def institutional_flow_ratio(data: InstitutionalData, feature: TechnicalFeatures) -> float:
    """回傳加權法人日均買賣超占 20 日平均成交量的比例。"""
    if feature.volume_ma20 <= 0:
        return 0.0
    one_day = data.foreign_1d + 1.25 * data.trust_1d + .5 * data.dealer_1d
    three_day = (data.foreign_3d + 1.25 * data.trust_3d + .5 * data.dealer_3d) / 3
    five_day = (data.foreign_5d + 1.25 * data.trust_5d + .5 * data.dealer_5d) / 5
    signed_lots = .2 * one_day + .3 * three_day + .5 * five_day
    return signed_lots * 1000 / feature.volume_ma20


def intraday_scores(
    feature: TechnicalFeatures,
    liquidity_percentile: float,
    institution: Optional[InstitutionalData] = None,
    market_bias: float = 0,
) -> Tuple[float, float, List[str], List[str]]:
    """計算當沖多空雙向分數與主要理由。"""
    liquidity = clamp(liquidity_percentile, 0, 1) * 20
    common = {
        "liquidity": liquidity,
        "volatility": volatility_points(feature.atr_pct),
        "volume": volume_points(feature.volume_ratio),
    }
    long_structure, long_reasons = _structure(feature, "LONG")
    short_structure, short_reasons = _structure(feature, "SHORT")
    long_momentum, more_long = _momentum(feature, "LONG")
    short_momentum, more_short = _momentum(feature, "SHORT")
    long_reasons.extend(more_long)
    short_reasons.extend(more_short)
    long = weighted_score({**common, "structure": long_structure, "momentum": long_momentum, "institutional": _institutional_points(institution, feature, "LONG", 10)}, INTRADAY_WEIGHTS) or 0
    short = weighted_score({**common, "structure": short_structure, "momentum": short_momentum, "institutional": _institutional_points(institution, feature, "SHORT", 10)}, INTRADAY_WEIGHTS) or 0
    if market_bias >= 35: long += 5; short -= 5
    elif market_bias >= 10: long += 2
    elif market_bias <= -35: short += 5; long -= 5
    elif market_bias <= -10: short += 2
    return clamp(long, 0, 100), clamp(short, 0, 100), long_reasons[:3], short_reasons[:3]


def swing_score(
    feature: TechnicalFeatures,
    market_return_20d: Optional[float],
    institution: Optional[InstitutionalData] = None,
) -> Tuple[float, List[str]]:
    """計算波段做多分數與主要理由。"""
    trend, reasons = 0.0, []
    if feature.close > feature.ma20: trend += 8; reasons.append("收盤站上MA20")
    if feature.ma20 > feature.ma60: trend += 8; reasons.append("MA20>MA60")
    if feature.ma20_slope > 0: trend += 6; reasons.append("MA20斜率向上")
    if feature.close > feature.ma5: trend += 4
    if feature.close >= feature.high_20d * .95: trend += 4; reasons.append("接近20日高點")
    momentum = 0.0
    if feature.macd_histogram > 0: momentum += 5
    if feature.roc5 > 0: momentum += 4
    if feature.roc20 > 0: momentum += 5
    if 50 <= feature.rsi14 <= 72: momentum += 4
    if market_return_20d is not None and feature.return_20d > market_return_20d: momentum += 2
    relative = None if market_return_20d is None else clamp(5 + (feature.return_20d - market_return_20d), 0, 10)
    institution_points = _institutional_points(institution, feature, "LONG", 25)
    score = weighted_score({"trend": min(trend,30), "momentum": min(momentum,20), "volume": volume_points(feature.volume_ratio), "institutional": institution_points, "relative_strength": relative}, SWING_WEIGHTS) or 0
    if relative is not None and relative >= 7: reasons.append("20日表現強於大盤")
    if institution_points is not None and institution_points >= 15: reasons.append("法人籌碼偏多")
    return score, reasons[:3]
