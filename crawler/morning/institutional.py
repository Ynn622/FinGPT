"""Morning Report 法人籌碼資料來源。"""

from datetime import timedelta
from typing import Optional

import pandas as pd

from crawler.institutional import get_chip_data
from services.morning.models import InstitutionalData


def fetch(stock_id: str, data_date: str) -> Optional[InstitutionalData]:
    """取得指定股票近五日的三大法人買賣超統計。"""
    end = pd.Timestamp(data_date)
    start = end - timedelta(days=14)
    frame = get_chip_data(stock_id, start.date().isoformat(), end.date().isoformat())
    if frame.empty:
        return None
    frame = frame.tail(5)

    def total(column: str, days: int) -> float:
        """加總指定法人欄位最近數日的買賣超。"""
        return float(frame[column].tail(days).sum())

    def streak(column: str) -> int:
        """計算截至資料日真正連續買超（正）或賣超（負）的日數。"""
        values = pd.to_numeric(frame[column], errors="coerce").fillna(0).tolist()
        if not values or values[-1] == 0:
            return 0
        sign = 1 if values[-1] > 0 else -1
        count = 0
        for value in reversed(values):
            if value * sign <= 0:
                break
            count += 1
        return sign * count

    return InstitutionalData(
        stock_id=stock_id,
        foreign_1d=total("外資", 1), foreign_3d=total("外資", 3), foreign_5d=total("外資", 5),
        trust_1d=total("投信", 1), trust_3d=total("投信", 3), trust_5d=total("投信", 5),
        dealer_1d=total("自營商", 1), dealer_3d=total("自營商", 3), dealer_5d=total("自營商", 5),
        foreign_streak=streak("外資"), trust_streak=streak("投信"),
        dealer_streak=streak("自營商"),
    )
