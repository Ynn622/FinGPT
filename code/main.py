from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from agents import Agent, Runner, function_tool
import asyncio
import os      # 設定環境變數用
import traceback
import json

# 引入自定義工具函數
from funcTool import get_current_time, fetch_stock, get_stock_price, fetch_stock_news, fetch_twii_news, ETF_Ingredients

async def main(question):
    agent = Agent(
        name="Finance Agent",
        model="gpt-4.1-mini",
        instructions="你是一名台灣股票分析師，請使用提供的工具，分析股票並給予投資建議。",
        tools=[get_current_time, fetch_stock, get_stock_price, fetch_stock_news, fetch_twii_news, ETF_Ingredients],
    )
    result = await Runner.run(agent, question+"（1.如果查無資料，可嘗試使用工具查詢代碼\n 2.若未提及需要分析的時間，預設的分析時間為一個月，請先查詢今日日期\n 3.若無特別提及技術指標，請使用5MA即可）")    
    #print("Agent:",result.final_output)
    return result.final_output


# LineBot 接收&傳送
def linebot(request):
    body = request.get_data(as_text=True)
    try:
        access_token = os.environ["Line_token"]
        secret = os.environ["Line_secret"]
        json_data = json.loads(body)   # json格式 資料
        messaging_api = MessagingApi(ApiClient(Configuration(access_token=access_token)))  # 確認 token 是否正確
        handler = WebhookHandler(secret)                     # 確認 secret 是否正確
        signature = request.headers['X-Line-Signature']
        handler.handle(body, signature)
        if json_data['events'] == []: 
            print('Verify Success')  # Line Bot 驗證成功
            return 'Verify Success'
        user_question = json_data['events'][0]['message']['text']
        print("User:",user_question)
        tk = json_data['events'][0]['replyToken']
        try:
            ans = asyncio.run(main(user_question))
            message = [TextMessage(text=ans)]
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=tk,
                    messages=message
                )
            )
            print("Message Sent!",tk)
        except Exception as e:
            print("發生錯誤",traceback.format_exc())
            error_message = [TextMessage(text="發生錯誤，請稍後再試!")]
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=tk,
                    messages=error_message
                )
            )
            print("Error Message Sent!",tk)
    except Exception as e:
        print("發生錯誤",traceback.format_exc())
        print(request.args)
    return 'OK'
