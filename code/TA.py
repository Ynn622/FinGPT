import pandas as pd

def cal_RSI(df, period=5) -> pd.DataFrame:
    """ 計算相對強弱指標（RSI）。 """
    delta = df['Close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    avg_gain = gain.ewm(alpha=1/period).mean()
    avg_loss = loss.ewm(alpha=1/period).mean()

    rsi = avg_gain/(avg_gain+avg_loss)*100
    rsi = rsi.round(2)  # 四捨五入到小數點後兩位
    
    return rsi

def cal_KD(df, n=9):
    """ 計算 KD 指標。 """
    low_min = df['Low'].rolling(window=n, min_periods=1).min()
    high_max = df['High'].rolling(window=n, min_periods=1).max()
    rsv = (df['Close'] - low_min) / (high_max - low_min) * 100
    # 初始化K、D
    k_values = []
    d_values = []
    k, d = 50, 50
    # 計算K、D值
    for r in rsv:
        k = k * (2/3) + r * (1/3)
        d = d * (2/3) + k * (1/3)
        k_values.append(k)
        d_values.append(d)

    return k_values,d_values  # 返回 K 和 D 的 Series

def EMA(df, period=5):
    """ 計算指數移動平均線（EMA）。"""
    # 計算「短期EMA、長期EMA」
    ema = df['Close'].ewm(span=period, min_periods=period, adjust=False).mean()
    return ema

def cal_MACD(df, short=12, long=26, signal_window=9):
    """ 計算 MACD 指標。 """
    # 計算「短期EMA、長期EMA」
    short_ema = EMA(df, short)
    long_ema = EMA(df, long)
    # 計算「MACD」
    DIF = short_ema - long_ema
    # 計算「Signal」
    MACD = DIF.ewm(span=signal_window, adjust=False).mean()
    # 計算「OSC」
    OSC = DIF - MACD
    return DIF, MACD, OSC  # 返回 Series