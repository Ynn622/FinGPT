from openai import OpenAI
import yfinance as yf
import pandas as pd

import requests
from bs4 import BeautifulSoup as bs
import time
import re
import html

import os      # 設定環境變數用
import traceback
from LineTemplate import *   # LineTemplate.py

# OpenAI聊天
def talk(chatbot,record):
    response = chatbot.chat.completions.create(
        model="gpt-4.1-nano",
        messages=record,
        max_tokens = 16000
    )
    return response

# 檢驗是否開盤
def isOpen():
    x = False
    now = time.time()+28800
    gmt = time.gmtime(now)
    now_year = time.strftime("%Y", gmt)
    now_day = time.strftime("%Y-%m-%d", gmt)
    now_time = time.strftime("%H:%M:%S", gmt)
    now_week = time.strftime("%w", gmt)
    try:
        # 爬取證交所 今年營業資訊
        url = f"https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule?date={now_year}0101&response=json&_=1735104108487"
        web_json = requests.get(url).json()["data"]
        closed = [i[0] for i in web_json]

        if (now_week not in ["6","7"]) and (now_day not in closed):
            if "13:30:05">now_time>"09:00:00":
                x = True
            else:
                x = False
        else:
            x = False
        return x
    except:
        return False

# 取得台股即時報價
def live_price(stock_id):
    try:
        header = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}
        url = f"https://tw.stock.yahoo.com/quote/{stock_id}"
        web = requests.get(url,headers=header,timeout=5)
        bs_web = bs(web.text,"html.parser")
        table = bs_web.find("ul",class_="D(f) Fld(c) Flw(w) H(192px) Mx(-16px)").find_all("li")
        name = ["Close","Open","High","Low","Volume"]
        dic = {}
        s_list = [0,1,2,3,9] if stock_id!="^TWII" else [0,1,2,3,5]  # 爬取的欄位
        for i in range(5):
            search = s_list[i]
            row = table[search].find_all("span")[1].text
            row = float(row.replace(",",""))
            if search==5:row*=1000
            dic[name[i]]=[row]
        tt = bs_web.find("time").find_all("span")[2].text
        tt = pd.to_datetime(tt).strftime("%Y-%m-%d")
        df = pd.DataFrame(dic,index=[tt])
    except Exception as e:
        print("取得即時報價錯誤：",e)
        df = pd.DataFrame()
    return df

# 取得股價資料
def catch_Stock(stock):
    for suffix in [".TW",".TWO",""]:
        id = f'{stock}{suffix}'
        try:
            data = yf.Ticker(id).history(period="6mo")
            if data.empty: continue
            if suffix!="":
                data["Volume"]=data["Volume"]*0.001
            break
        except Exception as stock_Error:
            continue
    del data["Dividends"]
    del data["Stock Splits"]
    data = data.round(2).iloc[-100:,:6].dropna()
    # data.index.name = "Date"
    data.index = data.index.strftime("%Y-%m-%d")
    # 取得最後更新資訊
    live_df = live_price(stock)
    if not (live_df.empty):
        data = data.drop(live_df.index[0], errors='ignore') 
        data = pd.concat([data,live_df])
    # 大盤單位 改成億元
    if id=="^TWII":
        data["Volume"] = data["Volume"]*0.001

    data["5MA"]=data["Close"].rolling(5).mean()
    data["10MA"]=data["Close"].rolling(10).mean()
    data["60MA"]=data["Close"].rolling(60).mean()
    data = data.dropna().round(2)
    if id[-3:]==".TW":
        data = data.drop("2024-11-20", errors='ignore')  # 資料異常
    print(data.tail(2))
    return data, id

# 取得股票名稱
def catch_stock_name(stock_id):
    try:
        header = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}
        url = f"https://tw.stock.yahoo.com/quote/{stock_id}"
        web = requests.get(url,headers=header,timeout=5)
        name = bs(web.text,'html.parser').find_all("h1")[1].text
        return name
    except Exception as e:
        print("抓取股名錯誤：",e)
        print("發生錯誤",traceback.format_exc())
        return stock_id

# 取得「新聞資訊」
def get_news(stock_id):
    data = []
    col = ["Date","Title","Content","NewsId"]
    if stock_id=="^TWII":
        url = f"https://api.cnyes.com/media/api/v1/newslist/category/tw_stock_news?page=1&limit=10&isCategoryHeadline=1"
        json_news = requests.get(url).json()['items']['data']
        for i in range(10):
            id = json_news[i]["newsId"]
            content = json_news[i]["content"]
            content = re.sub(r'<.*?>', '', html.unescape(content))
            if content.find("http")!=-1:
                content = content[:content.find("http")]
            summary = json_news[i]["summary"]
            t = json_news[i]["publishAt"]+28800
            news_time = time.strftime("%Y/%m/%d", time.gmtime(t))
            data.append([news_time,summary,content,id])
    else:
        stock_name = catch_stock_name(stock_id)
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
            data.append([news_time,title,news_data,id])
        
    df = pd.DataFrame(data,columns=col)
    return df

# 生成
def generate(id,question):
    analysis = ""
    try:
        news_df = get_news(id)
        stock_data, stock_id = catch_Stock(id)
        LineColTemp = ColTemplate(news_df)   # Line圖文模板
        del news_df["NewsId"]
        news_data = news_df.to_string().replace("   ","")
        open = isOpen()
        show = "目前價格" if open else "收盤價"  # 判斷是否開盤
        TR = ((stock_data.iloc[-1,3]/stock_data.iloc[-2,3]-1)*100).round(2)
        TRsymbol = "▲" if TR>=0 else "▼"
        analysis += f"日期：{stock_data.index[-1]} \n股票代號：{stock_id} \n開盤價：{stock_data.iloc[-1,0]} \n{show}：{stock_data.iloc[-1,3]}({TRsymbol}{abs(TR)}%)\n\n"
        # 初始化ai設定
        key = os.environ["OpenAI_key"]
        ai = OpenAI(api_key=key)
        # 對話開始
        unit = "volume單位:張" if id!="^TWII" else "volume單位:億元"
        question = question or "請分析後 給出未來操作建議或價位"
        talked = [{"role":"assistant","content":f"你是一名股市分析師,今日是{stock_data.index[-1]}"},
                  {"role":"user","content":f"這是台股{stock_id}的資料\n{stock_data} {unit},以下是相關近期新聞 可參考：{news_data}，請分析"},
                  {"role":"user","content":f"{question} (Reply in 繁體中文)"}
                 ]
        del stock_data
        response = talk(ai,talked)
        print("Token Usage:",response.usage.total_tokens)
        analysis += response.choices[0].message.content
        analysis = analysis.replace("#","~")
    except Exception as e:
        analysis = "錯誤！請檢查代碼 或稍後再試～"
        LineColTemp = []
        print(traceback.format_exc())
    return analysis,LineColTemp
