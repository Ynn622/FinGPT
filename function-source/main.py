import json
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

import datetime
from openai import OpenAI
from yahoo_fin.stock_info import *
import pandas as pd

import os      # 設定環境變數用

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

# OpenAI聊天
def talk(chatbot,record):
    response = chatbot.chat.completions.create(
        model="gpt-4o-mini",
        messages=record,
        max_tokens = 15000
    )
    return response

# 生成
def generate(input):
    txt = ""
    try:
        stock_data, stock_id = catch_Stock(input)
        txt += f"日期：{stock_data.index[-1]} \n股票代號：{stock_id} \n開盤價：{stock_data.iloc[-1,0]} \n收盤價：{stock_data.iloc[-1,3]}\n\n"
        # 初始化ai設定
        key = os.environ["OpenAI_key"]
        ai = OpenAI(api_key=key)
        # 對話開始
        talked = [{"role":"user","content":f"這是台股 {stock_id}的資料 請幫我分析\n{stock_data.to_string()} 並給出操作建議"}]
        del stock_data
        response = talk(ai,talked)
        txt += response.choices[0].message.content
        txt = txt.replace("#","~")
    except Exception as e:
        txt = "錯誤！請檢查代碼 或稍後再試～"
        print(e)
    return txt

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
