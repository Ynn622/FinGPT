"""Yahoo Finance 市場資料來源。"""

from typing import Dict, Iterable, List

import pandas as pd
import yfinance as yf

from services.morning.models import MarketSnapshot, StockCandidate
from util.config import Env


GLOBAL_SYMBOLS = {
    "sp500": "^GSPC",
    "nasdaq": "^IXIC",
    "sox": "^SOX",
    "tsm": "TSM",
    "nvda": "NVDA",
    "amd": "AMD",
    "mu": "MU",
    "avgo": "AVGO",
    "usdtwd": "TWD=X",
}


def _symbol_frame(download: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """從 Yahoo 批次下載結果中取出指定商品的資料表。"""
    if isinstance(download.columns, pd.MultiIndex):
        if symbol in download.columns.get_level_values(-1):
            return download.xs(symbol, axis=1, level=-1).dropna(how="all")
        if symbol in download.columns.get_level_values(0):
            return download[symbol].dropna(how="all")
    return download.dropna(how="all")


def fetch_global_market() -> Dict[str, MarketSnapshot]:
    """取得海外指數、科技股與美元兌台幣的近期行情。"""
    symbols = list(GLOBAL_SYMBOLS.values())
    data = yf.download(
        symbols, period="7d", interval="1d", group_by="column",
        auto_adjust=False, progress=False, threads=True,
    )
    result: Dict[str, MarketSnapshot] = {}
    for key, symbol in GLOBAL_SYMBOLS.items():
        frame = _symbol_frame(data, symbol)
        column = "Adj Close" if "Adj Close" in frame else "Close"
        series = frame[column].dropna()
        if len(series) < 2:
            continue
        last, previous = float(series.iloc[-1]), float(series.iloc[-2])
        result[key] = MarketSnapshot(
            key=key,
            symbol=symbol,
            last_close=round(last, 2),
            previous_close=round(previous, 2),
            change=round(last - previous, 2),
            change_pct=round((last / previous - 1) * 100, 2),
            source_date=pd.Timestamp(series.index[-1]).date().isoformat(),
        )
    return result


def fetch_histories(candidates: List[StockCandidate]) -> Dict[str, pd.DataFrame]:
    """分批取得候選股票近六個月的日線資料。"""
    result: Dict[str, pd.DataFrame] = {}
    size = max(1, Env.MORNING_YF_BATCH_SIZE)
    for start in range(0, len(candidates), size):
        batch = candidates[start : start + size]
        symbols = [candidate.yahoo_symbol for candidate in batch]
        data = yf.download(
            symbols, period="6mo", interval="1d", group_by="column",
            auto_adjust=False, progress=False, threads=True,
        )
        for candidate in batch:
            try:
                frame = _symbol_frame(data, candidate.yahoo_symbol)
                needed = ["Open", "High", "Low", "Close", "Volume"]
                frame = frame[needed].dropna(subset=needed).copy()
                # 07:00 下載理應止於前一交易日，此處也會排除意外取得的當日未完成 K 棒。
                frame = frame.loc[pd.to_datetime(frame.index).date <= pd.Timestamp(candidate.date).date()]
                if len(frame) >= 60:
                    result[candidate.stock_id] = frame
            except (KeyError, TypeError, ValueError):
                continue
    return result


def fetch_market_returns() -> Dict[str, float]:
    """取得上市與櫃買市場最近二十個交易日的報酬率。"""
    data = yf.download(
        ["^TWII", "^TWOII"], period="2mo", interval="1d", group_by="column",
        auto_adjust=False, progress=False, threads=True,
    )
    result = {}
    for market, symbol in (("TWSE", "^TWII"), ("TPEX", "^TWOII")):
        frame = _symbol_frame(data, symbol)
        series = frame["Close"].dropna()
        if len(series) >= 21:
            result[market] = (float(series.iloc[-1]) / float(series.iloc[-21]) - 1) * 100
    return result


def fetch_backtest_history(symbols: List[str], start: str, end: str) -> pd.DataFrame:
    """取得市場評分回測所需的多商品歷史日線資料。"""
    return yf.download(symbols, start=start, end=end, interval="1d", group_by="column")
