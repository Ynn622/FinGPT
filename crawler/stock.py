import numpy as np
import pandas as pd
import requests
import yfinance as yf
from bs4 import BeautifulSoup as bs
from datetime import datetime, timedelta

from crawler.institutional import get_chip_data
from util.logger import Color, Log
from util.technical_indicators import get_technical_indicators


def getStockPrice(symbol: str, start: str, sdf_indicator_list: list[str] = []) -> pd.DataFrame:
    """取得指定股票的歷史股價、即時股價與籌碼資料。"""
    data = yf.Ticker(symbol).history(period="2y").round(2)
    del data["Dividends"], data["Stock Splits"]
    if "Capital Gains" in data.columns:
        del data["Capital Gains"]
    data.index = data.index.strftime("%Y-%m-%d")
    data["Volume"] = data["Volume"] * 0.001

    try:
        live_df = get_live_price(symbol)
        data = data.drop(live_df.index[0], errors="ignore")
        data = pd.concat([data, live_df])
    except Exception as e:
        Log(f"[Error] 爬取即時股價資料錯誤: {str(e)}", color=Color.RED)

    if sdf_indicator_list:
        try:
            indicator_df = get_technical_indicators(data, sdf_indicator_list)
            data = pd.concat([data, indicator_df], axis=1)
        except Exception as e:
            Log(f"[Error] 指標計算錯誤: {str(e)}", color=Color.RED)

    half_year_ago = (datetime.today() - timedelta(days=180)).strftime("%Y-%m-%d")
    start = max(start, half_year_ago)
    data = data[data.index >= start]
    data = data.dropna().round(2)

    date_to_add = "2025-08-01"
    if date_to_add not in data.index and start < date_to_add:
        data.loc[date_to_add] = [np.nan] * len(data.columns)
        data = data.sort_index()

    if symbol not in ("^TWII", "^TWOII"):
        try:
            chip_data = get_chip_data(symbol, data.index[0], data.index[-1]).reindex(data.index)
            data = pd.concat([data, chip_data], axis=1)
        except Exception as e:
            Log(f"[Error] 籌碼面資料錯誤: {str(e)}", color=Color.RED)

    return data


def get_live_price(symbol: str) -> pd.DataFrame:
    """取得最新即時股價資料。"""
    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    }
    url = f"https://tw.stock.yahoo.com/quote/{symbol}"
    web = requests.get(url, headers=header, timeout=5)
    bs_web = bs(web.text, "html.parser")
    table = bs_web.find("ul", class_="D(f) Fld(c) Flw(w) H(192px) Mx(-16px)").find_all("li")
    names = ["Close", "Open", "High", "Low", "Volume"]
    values = {}
    source_indexes = [0, 1, 2, 3, 5 if symbol in ("^TWII", "^TWOII") else 9]
    for name, source_index in zip(names, source_indexes):
        value = float(table[source_index].find_all("span")[1].text.replace(",", ""))
        values[name] = [value]
    nowtime = bs_web.find("time").find_all("span")[2].text
    nowtime = pd.to_datetime(nowtime).strftime("%Y-%m-%d")
    return pd.DataFrame(values, index=[nowtime])
