"""候選股票池正規化與普通股篩選。"""

from typing import Iterable, List, Optional, Set

import pandas as pd

from crawler.morning.universe import fetch_ordinary_stock_ids
from services.morning.models import StockCandidate


def ordinary_stock_ids(stock_frame: Optional[pd.DataFrame] = None) -> Set[str]:
    """取得候選股票篩選所需的普通股代號。"""
    return fetch_ordinary_stock_ids(stock_frame)


def merge_candidates(
    twse: Iterable[StockCandidate],
    tpex: Iterable[StockCandidate],
    top_n: int = 100,
    valid_ids: Optional[Set[str]] = None,
) -> List[StockCandidate]:
    """合併上市櫃候選股、過濾普通股並依成交金額排序。"""
    rows = list(twse) + list(tpex)
    if not rows:
        return []
    allowed = ordinary_stock_ids() if valid_ids is None else valid_ids
    filtered = [row for row in rows if row.stock_id in allowed]
    # 來源日期不一致時只保留最近共同日期，避免用不同日期資料混合排名。
    twse_dates = {row.date for row in filtered if row.market == "TWSE"}
    tpex_dates = {row.date for row in filtered if row.market == "TPEX"}
    common = twse_dates & tpex_dates
    if common:
        source_date = max(common)
    else:
        # OpenAPI 更新時間可能不同，無共同日期時只使用較舊的完整快照。
        latest_twse = max(twse_dates) if twse_dates else None
        latest_tpex = max(tpex_dates) if tpex_dates else None
        source_date = min(value for value in (latest_twse, latest_tpex) if value)
    filtered = [row for row in filtered if row.date == source_date]
    return sorted(filtered, key=lambda item: item.trade_value, reverse=True)[:top_n]
