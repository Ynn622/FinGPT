"""Morning Report 普通股清單資料來源。"""

from typing import Optional, Set

import pandas as pd

from services.morning.cache import CACHE_DIR, atomic_write_json, read_json
from services.morning.utils import normalize_stock_code


def fetch_ordinary_stock_ids(stock_frame: Optional[pd.DataFrame] = None) -> Set[str]:
    """取得上市櫃普通股代號並在遠端失敗時使用本地快取。"""
    if stock_frame is not None:
        return {
            normalize_stock_code(value)
            for value in stock_frame["stock_id"].astype(str)
        }
    snapshot = CACHE_DIR / "stock_list_snapshot.json"
    try:
        from crawler.stock_list import StockList

        frame = StockList.get_all()
        ids = {
            normalize_stock_code(value)
            for value in frame["stock_id"].astype(str)
        }
        atomic_write_json(snapshot, sorted(ids))
        return ids
    except Exception:
        cached = read_json(snapshot)
        if isinstance(cached, list) and cached:
            return set(map(normalize_stock_code, cached))
        raise
