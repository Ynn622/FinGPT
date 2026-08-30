import cloudscraper
import pandas as pd
from bs4 import BeautifulSoup as bs

from util.logger import Color, Log


def get_chip_data(symbol: str, start: str, end: str) -> pd.DataFrame:
    """取得指定股票的三大法人買賣超資料。"""
    if symbol in ("^TWII", "^TWOII"):
        Log(f"[function] get_chip_data(): 不提供籌碼面資料: {symbol}", color=Color.PURPLE)
        return pd.DataFrame()

    symbol = symbol.split(".")[0]
    url = f"https://fubon-ebrokerdj.fbs.com.tw/z/zc/zcl/zcl.djhtm?a={symbol}&c={start}&d={end}"
    web = cloudscraper.create_scraper().get(url, timeout=10).text
    rows = bs(web, "html.parser").find("table", class_="t01").find_all("tr")[7:-1]
    data = []
    date_index = []
    for row in rows[::-1]:
        cells = row.find_all("td")[:5]
        date = cells.pop(0).text.split("/")
        texts = [cell.text.strip() for cell in cells]
        if any(text == "--" for text in texts):
            continue
        data.append([int(text.replace(",", "")) for text in texts])
        date_index.append(f"{int(date[0]) + 1911}-{date[1]}-{date[2]}")
    return pd.DataFrame(
        data,
        columns=["外資", "投信", "自營商", "三大法人合計"],
        index=date_index,
    )
