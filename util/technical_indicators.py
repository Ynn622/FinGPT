"""共用技術指標計算工具。"""

from typing import Optional

import pandas as pd
from stockstats import StockDataFrame as Sdf

from services.morning.models import TechnicalFeatures


def _as_sdf(data: pd.DataFrame) -> Sdf:
    """建立不修改呼叫端資料的 StockDataFrame。"""
    return Sdf.retype(data.copy().sort_index())


def get_technical_indicators(data, sdf_indicator_list):
    """計算並回傳指定的技術指標。"""
    indicator_dict = {
        "close": "Close",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "volume": "Volume",
        "close_5_sma": "SMA_5",
        "close_10_sma": "SMA_10",
        "close_20_sma": "SMA_20",
        "close_60_sma": "SMA_60",
        "close_5_ema": "EMA_5",
        "close_10_ema": "EMA_10",
        "close_20_ema": "EMA_20",
        "macd": "MACD",
        "macds": "Signal Line",
        "macdh": "Histogram",
        "kdjk": "%K",
        "kdjd": "%D",
        "rsi_5": "RSI_5",
        "rsi_10": "RSI_10",
        "rsi_14": "RSI_14",
        "close_5_roc": "ROC_5",
        "close_20_roc": "ROC_20",
        "atr_14": "ATR_14",
        "volume_5_sma": "VOLUME_SMA_5",
        "volume_20_sma": "VOLUME_SMA_20",
        "boll_ub": "BOLL_UPPER",
        "boll": "BOLL_MIDDLE",
        "boll_lb": "BOLL_LOWER",
        "change": "PCT",
    }

    stock_df = _as_sdf(data)
    valid_indicators = []
    for name in sdf_indicator_list:
        try:
            stock_df[name]
            valid_indicators.append(name)
        except (KeyError, AttributeError, TypeError, ValueError):
            continue
    indicator_data = stock_df[valid_indicators].copy()
    indicator_data.rename(columns=indicator_dict, inplace=True)
    indicator_data = indicator_data.round(2)
    new_columns = [column for column in indicator_data.columns if column not in data.columns]
    return indicator_data[new_columns]


def true_range(frame: pd.DataFrame) -> pd.Series:
    """使用 StockDataFrame 計算每日真實波幅。"""
    return pd.Series(_as_sdf(frame)["tr"], index=frame.sort_index().index, dtype=float)


def atr_wilder(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    """使用 StockDataFrame 的 Wilder SMMA 計算 ATR。"""
    return pd.Series(
        _as_sdf(frame)[f"atr_{period}"], index=frame.sort_index().index, dtype=float,
    )


def close_location_value(close: float, high: float, low: float) -> float:
    """計算收盤價位於當日高低區間的位置比例。"""
    return 0.5 if high == low else (close - low) / (high - low)


def calculate_features(stock_id: str, frame: pd.DataFrame) -> Optional[TechnicalFeatures]:
    """以 SDF 為主，從已完成日 K 棒建立晨報所需技術特徵。"""
    if len(frame) < 60:
        return None
    data = frame.copy().sort_index()
    stock = _as_sdf(data)
    close = stock["close"].astype(float)
    high = stock["high"].astype(float)
    low = stock["low"].astype(float)
    volume = stock["volume"].astype(float)

    ma5 = stock["close_5_sma"]
    ma10 = stock["close_10_sma"]
    ma20 = stock["close_20_sma"]
    ma60 = stock["close_60_sma"]
    ema5 = stock["close_5_ema"]
    ema10 = stock["close_10_ema"]
    ema20 = stock["close_20_ema"]
    macd = stock["macd"]
    signal = stock["macds"]
    histogram = stock["macdh"]
    rsi = stock["rsi_14"]
    roc5 = stock["close_5_roc"]
    roc20 = stock["close_20_roc"]
    atr = stock["atr_14"]
    vol_ma5 = stock["volume_5_sma"]
    vol_ma20 = stock["volume_20_sma"]

    # 評分使用「當日量 / 前 20 個完成交易日均量」，不可把當日量放入分母。
    previous_20_volume = volume.shift(1).rolling(20).mean()
    trade_value = close * volume
    high_20 = high.rolling(20).max()
    low_20 = low.rolling(20).min()
    last = -1
    required = (
        ma60.iloc[last], rsi.iloc[last], atr.iloc[last], previous_20_volume.iloc[last],
    )
    if any(pd.isna(value) for value in required):
        return None

    return TechnicalFeatures(
        stock_id=stock_id,
        date=pd.Timestamp(data.index[last]).date().isoformat(),
        close=float(close.iloc[last]),
        previous_high=float(high.iloc[last]),
        previous_low=float(low.iloc[last]),
        ma5=float(ma5.iloc[last]), ma10=float(ma10.iloc[last]),
        ma20=float(ma20.iloc[last]), ma60=float(ma60.iloc[last]),
        ema5=float(ema5.iloc[last]), ema10=float(ema10.iloc[last]), ema20=float(ema20.iloc[last]),
        macd=float(macd.iloc[last]), macd_signal=float(signal.iloc[last]),
        macd_histogram=float(histogram.iloc[last]), rsi14=float(rsi.iloc[last]),
        roc5=float(roc5.iloc[last]), roc20=float(roc20.iloc[last]),
        atr14=float(atr.iloc[last]), atr_pct=float(atr.iloc[last] / close.iloc[last]),
        volume_ma5=float(vol_ma5.iloc[last]), volume_ma20=float(vol_ma20.iloc[last]),
        volume_ratio=float(volume.iloc[last] / previous_20_volume.iloc[last]),
        clv=float(close_location_value(close.iloc[last], high.iloc[last], low.iloc[last])),
        return_1d=float(close.pct_change().iloc[last] * 100),
        return_5d=float(close.pct_change(5).iloc[last] * 100),
        return_20d=float(close.pct_change(20).iloc[last] * 100),
        high_20d=float(high_20.iloc[last]), low_20d=float(low_20.iloc[last]),
        ma20_slope=float(ma20.diff(5).iloc[last] / 5),
        avg_trade_value_20d=float(trade_value.rolling(20).mean().iloc[last]),
    )
