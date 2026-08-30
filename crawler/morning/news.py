"""Morning Report 新聞資料來源。"""

from typing import Any, Dict, List

from crawler.news import FetchStockNews, FetchTwiiNews


def fetch_stock(stock_name: str, limit: int = 3) -> List[Dict[str, Any]]:
    """取得指定股票的近期新聞並限制內文長度。"""
    frame = FetchStockNews(stock_name).head(limit)
    rows = frame.to_dict(orient="records")
    for row in rows:
        row["Content"] = str(row.get("Content", ""))[:1000]
    return rows


def fetch_market(limit: int = 5) -> List[Dict[str, Any]]:
    """取得台股市場的近期新聞並限制內文長度。"""
    rows = FetchTwiiNews().head(limit).to_dict(orient="records")
    for row in rows:
        row["Content"] = str(row.get("Content", ""))[:1000]
    return rows
