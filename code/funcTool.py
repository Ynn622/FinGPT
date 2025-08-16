from agents import function_tool
from datetime import datetime, timedelta
import pandas as pd
import requests
from bs4 import BeautifulSoup as bs
import re
import html
import time
import yfinance as yf
import numpy as np

from supportFunc import *

@function_tool
async def get_current_time() -> str:
    """
    取得目前的時間。
    Returns: 
        str: 當前時間的字串，格式為 "YYYY-MM-DD HH:MM:SS"。
    """
    print("  -function_call: 調用 get_current_time()")
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@function_tool
async def fetch_stock(stockName: str) -> str:
    """
    股票代號&名稱查詢。
    Args:
        stockName (str): 股票名稱或代碼，例如 "鴻海" 或 "2317"。
    Returns:
        str: 包含股票代號與名稱的字串。
    Example:
        fetch_stockID("鴻海") -> ('2317.TW','鴻海')
    """
    print(f"  -function_call: 調用 fetch_stockID({stockName})")
    try:
        import requests
        url = f"https://tw.stock.yahoo.com/_td-stock/api/resource/WaferAutocompleteService;view=wafer&query={stockName}"
        response = requests.get(url)
        stockID = bs(response.json()["html"], features="lxml").find("a")["href"].split('stock_id=')[1]
        stockName = bs(response.json()["html"], features="lxml").find("span").text
        return stockID, stockName
    except Exception as e:
        print(f"   Error: fetch_stockID({stockName}): {str(e)}")
        return f"Error fetching data for {stockName}!"

@function_tool
async def get_stock_price(symbol: str, start: str, sdf_indicator_list: list[str]=[] ) -> str:
    """
    抓取 Yahoo Finance 的歷史股價資料與籌碼面資料。
    指數代號：（成交量單位為「億元」）
        - 加權指數：使用 "^TWII"
        - 櫃買指數：使用 "^TWOII"
    週線=5MA、月線=20MA、季線=60MA、半年線=120MA、年線=240MA
    Args:
        symbol (str): 股票代號，例如 "2330.TW" 或 "2317.TW"。
        start (str): 開始日期（格式："YYYY-MM-DD"），將只返回此日期之後的資料。
        sdf_indicator_list (list[str]): 欲計算的技術指標清單，stockstats - StockDataFrame 的指標名稱。
    Returns:
        str: 資料表格的字串格式。
    Example:
        get_stock_price("2330.TW", "1mo")
        get_stock_price("2330.TW", "2024-01-01", sdf_indicator_list=["close_5_sma", "close_10_ema", "macd", "kdjk", "kdjd", "rsi_5", "rsi_10"])
    """
    print(f"  -function_call: 調用 get_stock_price({symbol}, {start}, sdf_indicator_list: {sdf_indicator_list}")
    try:
        data = yf.Ticker(symbol).history(period="2y").round(2)
        del data["Dividends"], data["Stock Splits"]
        if "Capital Gains" in data.columns: del data["Capital Gains"]
        data.index = data.index.strftime("%Y-%m-%d")
        data["Volume"] = data["Volume"]*0.001  # 將成交量轉換為張數
        
        # 爬取現在即時股價資料
        live_df = get_live_price(symbol)
        if not live_df.empty:
            data = data.drop(live_df.index[0], errors='ignore') 
            data = pd.concat([data,live_df])
        
        # 指標計算
        if sdf_indicator_list:
            indicator_df = get_technical_indicators(data, sdf_indicator_list)
            try:
                data = pd.concat([data, indicator_df], axis=1)
            except Exception as e:
                print(f"   Error: 指標計算錯誤: {str(e)}")

        half_year_ago = (datetime.today() - timedelta(days=180)).strftime("%Y-%m-%d")
        start = start if start < half_year_ago else half_year_ago   # 最多取半年
        data = data[data.index >= start]  # 確保資料從指定日期開始
        data = data.dropna().round(2)  # 移除包含NaN的行 
        
        # yfinance 資料異常
        date_to_add = "2025-08-01"
        if (date_to_add not in data.index) and (start < date_to_add):
            data.loc[date_to_add] = [np.nan] * len(data.columns)
            data = data.sort_index()
        
        # 籌碼面資料
        if symbol not in ("^TWII", "^TWOII"): 
            chip_data = get_chip_data(symbol,data.index[0],data.index[-1])
            if not chip_data.empty:
                if len(chip_data)+1==len(data):
                    chip_data.loc[len(chip_data)] = [np.nan] * len(chip_data.columns)
                chip_data.index = data.index
                data = pd.concat([data, chip_data], axis=1)
        
        return data.to_string()
    except Exception as e:
        print(f"   Error: get_stock_price({symbol}, {start}): {str(e)}")
        return f"Error fetching data for {symbol}!"
        
@function_tool
async def fetch_stock_news(stock_name: str) -> str:
    """
    爬取指定股票的最新新聞資料。
    Args:
        stock_name (str): 股票名稱，例如 "台積電" 或 "鴻海"。
    Returns:
        str: 包含新聞日期、標題與內文的表格字串。
    Example:
        fetch_stock_news("台積電")
    """
    print(f"  -function_call: 調用 fetch_stock_news({stock_name})")
    try:
        data = []
        col = ["Date","Title","Content"]
        url = f"https://ess.api.cnyes.com/ess/api/v1/news/keyword?q={stock_name}&limit=10&page=1"
        json_news = requests.get(url).json()['data']['items']
        for item in json_news:
            id = item['newsId']
            title = item['title']
            title = re.sub(r'<.*?>', '', title)
            if "盤中速報" in title:continue
            t = item['publishAt']+28800
            if time.mktime(time.gmtime())-2592000>t:continue
            news_time = time.strftime("%Y/%m/%d", time.gmtime(t))
            news_url = f"https://news.cnyes.com/news/id/{id}"
            news = requests.get(news_url).text
            news_bs = bs(news,'html.parser')
            news_find = news_bs.find("main",class_="c1tt5pk2")
            news_data = "\n".join(x.text.strip() for x in news_find)
            news_data = news_data.replace("　　　","").replace("\n\n","")
            delete_strings = ["歡迎免費訂閱", "精彩影片","粉絲團", "Line ID","Line@","來源："]
            for delete_str in delete_strings:
                index = news_data.find(delete_str)
                if index != -1:
                    news_data = news_data[:index]  # 只保留不包含該字串的部分
                    break
            data.append([news_time,title,news_data])
        return pd.DataFrame(data,columns=col).to_string()
    except Exception as e:
        print(f"   Error: fetch_stock_news({stock_name}): {str(e)}")
        return f"Error fetching news for {stock_name}"

@function_tool
async def fetch_twii_news() -> str:
    """
    爬取台灣加權指數(^TWII)與櫃買市場(^TWOII)的最新新聞。
    Returns:
        str: 包含新聞時間、標題與內容的表格字串。
    Example:
        fetch_twii_news()
    """
    print("  -function_call: 調用 fetch_twii_news()")
    try:
        data = []
        col = ["Date","Title","Content"]
        start = datetime.now()
        end = start - timedelta(days=1)
        start = end - timedelta(days=20)
        url = f"https://api.cnyes.com/media/api/v1/newslist/category/tw_quo?page=1&limit=15&startAt={int(start.timestamp())}&endAt={int(end.timestamp())}"
        web = requests.get(url).json()['items']
        json_news = web['data']
        for i in range(web['to']-web['from']+1):
            content = json_news[i]["content"]
            content = re.sub(r'<.*?>', '', html.unescape(content))
            if content.find("http")!=-1:
                content = content[:content.find("http")]
            title = json_news[i]["title"]
            title = re.sub(r"^〈.*?〉", "", title)
            timestamp = json_news[i]["publishAt"]+28800
            news_time = time.strftime("%Y/%m/%d %H:%M", time.gmtime(timestamp))
            data.append([news_time,title,content])
        return pd.DataFrame(data,columns=col).to_string()
    except Exception as e:
        print(f"   Error: fetch_twii_news(): {str(e)}")
        return f"Error fetching TWII news"

@function_tool
async def ETF_Ingredients(ETF_name: str) -> str:
    """
    查詢 ETF 的成分股。
    Args:
        ETF_name (str): ETF 名稱，例如 "0050" 或 "00878"。
    Returns:
        pd.DataFrame: 包含成分股的 DataFrame，包含股票代號、名稱、權重等資訊。
    """
    try:
        url = f"https://tw.stock.yahoo.com/quote/{ETF_name}/holding"
        response = requests.get(url)
        soup = bs(response.text, "html.parser")
        table = soup.find_all("ul", class_="Bxz(bb) Bgc($c-light-gray) Bdrs(8px) P(20px)")[1].find_all("li")[1:]
        data = ""
        for i in table:
            data += i.text.strip() + "\n"
        return data
    except Exception as e:
        print(f"   Error: ETF_Ingredients({ETF_name}): {str(e)}")
        return f"Error fetching ETF ingredients for {ETF_name}"