"""隔夜市場偏向計算工具。"""

from typing import Dict, Optional

from services.morning.models import MarketSnapshot
from services.morning.utils import clamp


WEIGHTS = {"nasdaq": 15, "sox": 20, "tsm": 20, "tx": 35, "usdtwd": 10}


def market_score(global_market: Dict[str, MarketSnapshot], tx_night: Optional[dict]) -> float:
    """依海外市場與台指期夜盤計算加權市場分數。"""
    factors = {}
    for key in ("nasdaq", "sox", "tsm"):
        if key in global_market:
            factors[key] = clamp(global_market[key].change_pct / 2.0, -1, 1)
    if "usdtwd" in global_market:
        factors["usdtwd"] = -clamp(global_market["usdtwd"].change_pct / 0.5, -1, 1)
    if tx_night is not None:
        factors["tx"] = clamp(float(tx_night["change_pct"]) / 2.0, -1, 1)
    denominator = sum(WEIGHTS[key] for key in factors)
    return 0.0 if not denominator else round(sum(factors[key] * WEIGHTS[key] for key in factors) / denominator * 100, 1)


def regime(score: float) -> str:
    """將市場分數轉換成多空情境標籤。"""
    if score >= 35:
        return "極多"
    if score >= 10:
        return "偏多"
    if score > -10:
        return "震盪中性"
    if score > -35:
        return "偏空"
    return "極空"
