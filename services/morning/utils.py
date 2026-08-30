"""資料正規化與評分輔助工具。"""

import math
from typing import Dict, Optional


def normalize_stock_code(value: str) -> str:
    """移除股票市場後綴並統一代號格式。"""
    return str(value).strip().upper().split(".")[0]


def number(value: object, default: float = 0.0) -> float:
    """將含逗號或百分比的值安全轉換為浮點數。"""
    text = str(value).replace(",", "").replace("%", "").strip()
    if text in {"", "-", "--", "NULL", "nan", "None"}:
        return default
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def clamp(value: float, low: float, high: float) -> float:
    """將數值限制在指定上下界之間。"""
    return max(low, min(high, value))


def weighted_score(
    components: Dict[str, Optional[float]], weights: Dict[str, float]
) -> Optional[float]:
    """依可用因子重新正規化並回傳零至一百分。"""
    active = [(key, value) for key, value in components.items() if value is not None]
    denominator = sum(weights.get(key, 0) for key, _ in active)
    if not denominator:
        return None
    earned = sum(float(value) for key, value in active)
    return clamp(earned / denominator * 100.0, 0.0, 100.0)


def finite(value: float) -> bool:
    """判斷數值是否存在且為有限值。"""
    return value is not None and math.isfinite(float(value))
