from agents import function_tool
from datetime import datetime, timedelta
import pandas as pd
import requests
from bs4 import BeautifulSoup as bs
import re
import html
import time
import yfinance as yf
import cloudscraper

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
async def fetch_stockID(stockName: str) -> str:
    """
    根據股票名稱查詢其對應的股票代號。
    Args:
        stockName (str): 股票名稱，例如 "鴻海"
    Returns:
        str: 股票的代號，例如 "2317.TW"。
    Example:
        fetch_stockID("鴻海") -> "2317.TW"
    """
    print(f"  -function_call: 調用 fetch_stockID({stockName})")
    try:
        import requests
        url = f"https://tw.stock.yahoo.com/_td-stock/api/resource/WaferAutocompleteService;view=wafer&query={stockName}"
        response = requests.get(url)
        stockID = bs(response.json()["html"], features="lxml").find("a")["href"].split('stock_id=')[1]
        return stockID
    except Exception as e:
        print(f"   Error: fetch_stockID({stockName}): {str(e)}")
        return f"Error fetching data for {stockName}!"

@function_tool
async def get_stock_price(symbol: str, period: str, chip: bool=True) -> str:
    """
    抓取 Yahoo Finance 的歷史股價資料與籌碼面資料。
    指數代號：（成交量單位為「億元」）
        - 加權指數：使用 "^TWII"
        - 櫃買指數：使用 "^TWOII"
    若不需籌碼資料，請將 `chip` 設為 False（指數不提供籌碼資料）。
    Args:
        symbol (str): 股票代號，例如 "2330.TW" 或 "2317.TW"。
        period (str): 查詢歷史股價的期間。可接受值："1d", "5d", "1mo", "3mo", "6mo", "1y", "ytd"。如果沒有符合的時間，請使用更長的時間範圍。
        chip (bool): 是否抓取籌碼面資料，預設為 True。
    Returns:
        str: 資料表格的字串格式。
    Example:
        get_stock_price("2330.TW", "1mo")
    """
    print(f"  -function_call: 調用 get_stock_price({symbol}, {period}, {chip})")
    try:
        data = yf.Ticker(symbol).history(period=period).round(2)
        del data["Dividends"], data["Stock Splits"]
        if "Capital Gains" in data.columns: del data["Capital Gains"]
        data.index = data.index.strftime("%Y-%m-%d")
        data["Volume"] = data["Volume"]*0.001  # 將成交量轉換為張數
        
        live_df = get_live_price(symbol)   # 爬取現在即時股價資料
        if not live_df.empty:
            data = data.drop(live_df.index[0], errors='ignore') 
            data = pd.concat([data,live_df])
        # 大盤單位 改成億元
        if id=="^TWII": data["Volume"] = data["Volume"]*0.001
        
        # 籌碼面資料
        if chip: 
            chip_data = get_chip_data(symbol,data.index[0],data.index[-1])
            if not chip_data.empty:
                chip_data.index = data.index
                data = pd.concat([data, chip_data], axis=1)
        return data.to_string()  # 返回 DataFrame 的字串表示
    except Exception as e:
        print(f"   Error: get_stock_price({symbol}, {period}): {str(e)}")
        return f"Error fetching data for {symbol}!"

def get_live_price(symbol: str) -> pd.DataFrame:
    """
    用於取得最新即時股價資料。
    get_stock_price() 會自動調用此函數。
    """
    try:
        header = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}
        url = f"https://tw.stock.yahoo.com/quote/{symbol}"
        web = requests.get(url,headers=header,timeout=5)
        bs_web = bs(web.text,"html.parser")
        table = bs_web.find("ul",class_="D(f) Fld(c) Flw(w) H(192px) Mx(-16px)").find_all("li")
        name = ["Close","Open","High","Low","Volume"]
        dic = {}
        s_list = [0,1,2,3,5 if symbol in ("^TWII", "^TWOII") else 9]  # 大盤&櫃買 抓取欄位不同
        for i in range(5):
            search = s_list[i]
            row = float(table[search].find_all("span")[1].text.replace(",",""))
            dic[name[i]]=[row]
        nowtime = bs_web.find("time").find_all("span")[2].text
        nowtime = pd.to_datetime(nowtime).strftime("%Y-%m-%d")
        return pd.DataFrame(dic,index=[nowtime])
    except Exception as e:
        print(f"   Error: get_live_price({symbol}): {str(e)}")
        return pd.DataFrame()  # 返回空的 DataFrame
    
def get_chip_data(symbol: str, start: str, end: str) -> pd.DataFrame:
    """
    用於取得最新籌碼面資料。
    get_stock_price() 會自動調用此函數。
    """
    if symbol in ("^TWII", "^TWOII"):
        print(f"  -function_call: 不提供籌碼面資料: {symbol}")
        return pd.DataFrame()
    try:
        symbol = symbol.split(".")[0]  # 去除後綴
        url = f"https://fubon-ebrokerdj.fbs.com.tw/z/zc/zcl/zcl.djhtm?a={symbol}&c={start}&d={end}"
        scraper = cloudscraper.create_scraper()  # 使用 cloudscraper 爬取
        web = scraper.get(url).text
        bs_table = bs(web, "html.parser").find("table", class_="t01").find_all("tr")[7:-1]  # 跳過前7行和最後一行
        col = ["外資", "投信", "自營商", "三大法人合計"]
        data = []
        for i in bs_table[::-1]: # 反向遍歷，因為最新的資料在最後一行
            row = []
            for j in i.find_all("td")[1:5]:
                row.append(int(j.text.replace(",", "")))
            data.append(row)
        df = pd.DataFrame(data, columns=col)
        return df
    except Exception as e:
        print(f"   Error: get_chip_data({symbol}): {str(e)}")
        return pd.DataFrame()
    
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
