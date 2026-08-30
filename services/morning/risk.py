"""風險過濾與台股合法跳動單位交易計畫。"""

import math
from typing import Dict, Tuple

from services.morning.models import StockRiskFlag, TechnicalFeatures
from services.morning.utils import clamp
from util.taiwan_market import get_tick_size


def round_to_valid_tick(price: float, mode: str = "nearest") -> float:
    """反覆取整價格以處理結果跨越跳動級距的情況。"""
    value = float(price)
    for _ in range(3):
        tick = get_tick_size(value)
        units = value / tick
        if mode == "up":
            rounded = math.ceil(units - 1e-10) * tick
        elif mode == "down":
            rounded = math.floor(units + 1e-10) * tick
        else:
            rounded = round(units) * tick
        value = rounded
    return round(value, 2)


def daily_price_limits(reference_price: float, limit_pct: float = .10) -> Tuple[float, float]:
    """依開盤競價基準計算不超過漲跌幅限制的合法跌停與漲停價。"""
    lower = round_to_valid_tick(reference_price * (1 - limit_pct), "up")
    upper = round_to_valid_tick(reference_price * (1 + limit_pct), "down")
    return lower, upper


def _within_daily_limits(price: float, lower: float, upper: float) -> float:
    """將已對齊 Tick 的交易價位限制於當日合法價格區間。"""
    return min(upper, max(lower, price))


def trade_plan(feature: TechnicalFeatures, direction: str) -> Tuple[float, float, float, float]:
    """依技術特徵與交易方向計算進場、停損及目標價。"""
    lower_limit, upper_limit = daily_price_limits(feature.close)
    risk_pct = clamp(0.35 * feature.atr14 / feature.close, 0.008, 0.018)
    if direction == "LONG":
        entry = round_to_valid_tick(feature.previous_high + get_tick_size(feature.previous_high), "up")
        stop = round_to_valid_tick(entry * (1 - risk_pct), "up")
        risk = entry - stop
        tp1 = round_to_valid_tick(entry + 1.5 * risk, "down")
        tp2 = round_to_valid_tick(entry + 2.0 * risk, "down")
    else:
        entry = round_to_valid_tick(feature.previous_low - get_tick_size(feature.previous_low), "down")
        stop = round_to_valid_tick(entry * (1 + risk_pct), "down")
        risk = stop - entry
        tp1 = round_to_valid_tick(entry - 1.5 * risk, "up")
        tp2 = round_to_valid_tick(entry - 2.0 * risk, "up")
    return tuple(
        _within_daily_limits(price, lower_limit, upper_limit)
        for price in (entry, stop, tp1, tp2)
    )


def reward_risk_ratio(entry: float, stop: float, target: float, direction: str) -> float:
    """依實際合法價位計算目標價的報酬風險比，無有效風險時回傳零。"""
    if direction == "LONG":
        risk, reward = entry - stop, target - entry
    else:
        risk, reward = stop - entry, entry - target
    if risk <= 0 or reward <= 0:
        return 0.0
    return reward / risk


def swing_support(feature: TechnicalFeatures) -> float:
    """取價格下方最近均線作為支撐，無可用均線時改用 ATR。"""
    moving_averages = (feature.ma5, feature.ma10, feature.ma20)
    supports = [level for level in moving_averages if 0 < level < feature.close]
    raw_support = max(supports) if supports else max(0.01, feature.close - feature.atr14)
    return round_to_valid_tick(raw_support, "down")


def merge_flags(*sources: Dict[str, StockRiskFlag]) -> Dict[str, StockRiskFlag]:
    """合併多個來源的股票風險與當沖資格標記。"""
    result: Dict[str, StockRiskFlag] = {}
    for source in sources:
        for code, current in source.items():
            target = result.setdefault(code, StockRiskFlag(stock_id=code))
            target.warning |= current.warning
            target.disposal |= current.disposal
            target.altered_trading |= current.altered_trading
            target.can_day_trade |= current.can_day_trade
            target.can_short_day_trade |= current.can_short_day_trade
    return result
