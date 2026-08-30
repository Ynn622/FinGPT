"""台灣證券市場共用交易規則。"""


def get_tick_size(price: float) -> float:
    """依台股價格級距取得合法跳動單位。"""
    if price < 10:
        return 0.01
    if price < 50:
        return 0.05
    if price < 100:
        return 0.1
    if price < 500:
        return 0.5
    if price < 1000:
        return 1.0
    return 5.0
