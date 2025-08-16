import pandas as pd
from stockstats import StockDataFrame as Sdf
import cloudscraper
import requests
from bs4 import BeautifulSoup as bs

def get_technical_indicators(data, sdf_indicator_list):
    """
    計算技術指標
    Args:
        data(DataFrame): 股價歷史資料
        sdf_indicator_list (list): 欲計算的技術指標清單
    """
    indicator_dict = {
        'close_5_sma':'SMA_5',
        'close_10_sma':'SMA_10',
        'close_20_sma':'SMA_20',
        'close_60_sma':'SMA_60',
        'close_5_ema':'EMA_5',
        'close_10_ema':'EMA_10',
        'close_20_ema':'EMA_20',
        'macd': 'MACD',
        'macds': 'Signal Line',
        'macdh': 'Histogram',
        'kdjk': '%K',
        'kdjd': '%D',
        'rsi_5': 'RSI_5',
        'rsi_10': 'RSI_10',
        'close_5_roc': 'ROC',
        'boll_ub': 'BOLL_UPPER',
        'boll': 'BOLL_MIDDLE',
        'boll_lb': 'BOLL_LOWER',
        'change': 'PCT'
    }

    # 計算技術指標
    stock_df = Sdf.retype(data)
    indicator_data = stock_df[sdf_indicator_list].copy()
    indicator_data.rename(columns=indicator_dict, inplace=True)  # 將指標名稱轉換
    indicator_data = indicator_data.round(2)
    
    return indicator_data


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
            tds = i.find_all("td")[1:5]
            texts = [td.text.strip() for td in tds]
            # 偵測是否有 '--'
            if any(text == '--' for text in texts):
                continue  # 不繼續處理這筆資料
            # 正常處理數字
            row = [int(text.replace(",", "")) for text in texts]
            data.append(row)
        df = pd.DataFrame(data, columns=col)
        return df
    except Exception as e:
        print(f"   Error: get_chip_data({symbol}): {str(e)}")
        return pd.DataFrame()