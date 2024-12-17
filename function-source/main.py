import json
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

import datetime
from openai import OpenAI
from yahoo_fin.stock_info import *
import pandas as pd

import requests
from bs4 import BeautifulSoup as bs
import time

import os      # 設定環境變數用

# OpenAI聊天
def talk(chatbot,record):
    response = chatbot.chat.completions.create(
        model="gpt-4o-mini",
        messages=record,
        max_tokens = 15000
    )
    return response

# 取得股價資料
def catch_Stock(stock):
    try:
        id = f'{stock}.TW'
        data = get_data(id)
        data["volume"]=data["volume"]*0.001
    except:
        try:
            id = f'{stock}.TWO'
            data = get_data(id)
            data["volume"]=data["volume"]*0.001
        except:
            id = str(stock)
            data = get_data(id)
    data = data.round(2).iloc[-25:,:6]
    del data["adjclose"]
    # data.index.name = "Date"
    data.index = data.index.strftime("%Y-%m-%d")
    data["5MA"]=data["close"].rolling(5).mean()
    data = data.dropna()
    try:
        data = data.drop("2024-11-20")  #資料異常
    except:
        pass
    return data, id

# 取得股票名稱
def catch_stock_name(stock_id):
    url = f"https://tw.stock.yahoo.com/quote/{stock_id}"
    web = requests.get(url)
    name = bs(web.text,'html.parser').find_all("h1")[1].text
    return name

# 取得新聞資訊
def get_news(stock_id):
    stock_name = catch_stock_name(stock_id)
    url = f"https://ess.api.cnyes.com/ess/api/v1/news/keyword?q={stock_name}&limit=10&page=1"
    json_news = requests.get(url).json()['data']['items']
    
    col = ["Date","Title","text"]
    data = []
    for item in json_news:
        id = item['newsId']  
        title = item['title']
        t = item['publishAt']+28800
        news_time = time.strftime("%Y/%m/%d", time.gmtime(t))
        news_url = f"https://news.cnyes.com/news/id/{id}"
        news = requests.get(news_url).text
        news_bs = bs(news,'html.parser')
        news_find = news_bs.find_all("p")[2:-9]
        news_data = "\n".join(x.text.strip() for x in news_find)
        data.append([news_time,title,news_data])
    
    df = pd.DataFrame(data,columns=col)
    df_str = df.to_string().replace("   ","")
    return df_str

# 生成
def generate(input):
    txt = ""
    try:
        stock_data, stock_id = catch_Stock(input)
        news_data = get_news(stock_id)
        txt += f"日期：{stock_data.index[-1]} \n股票代號：{stock_id} \n開盤價：{stock_data.iloc[-1,0]} \n收盤價：{stock_data.iloc[-1,3]}\n\n"
        # 初始化ai設定
        key = os.environ["OpenAI_key"]
        ai = OpenAI(api_key=key)
        # 對話開始
        talked = [{"role":"user","content":f"這是台股{stock_id}的資料\n{stock_data.to_string()} 以下是相關新聞可參考：{news_data} 請分析 並給出操作建議"}]
        del stock_data
        response = talk(ai,talked)
        txt += response.choices[0].message.content
        txt = txt.replace("#","~")
        print("Token Usage:",response.usage.total_tokens)
    except Exception as e:
        txt = "錯誤！請檢查代碼 或稍後再試～"
        print(e)
    return txt

# LineBot 接收&傳送
def linebot(request):
    try:
        access_token = os.environ["Line_token"]
        secret = os.environ["Line_secret"]
        body = request.get_data(as_text=True)
        json_data = json.loads(body)
        line_bot_api = LineBotApi(access_token)
        handler = WebhookHandler(secret)
        signature = request.headers['X-Line-Signature']
        handler.handle(body, signature)
        msg = json_data['events'][0]['message']['text']
        tk = json_data['events'][0]['replyToken']
        ans = generate(msg)
        line_bot_api.reply_message(tk,TextSendMessage(ans))
        print(msg, tk)
    except:
        print(request.args)
    return 'OK'
