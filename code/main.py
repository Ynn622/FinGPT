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
import asyncio
import traceback
import json
import os

from functionTools import askAI   # 引入自定義工具函數

# LineBot 接收&傳送
def linebot(request):
    body = request.get_data(as_text=True)
    try:
        lineToken = os.environ["Line_token"]
        lineSecret = os.environ["Line_secret"]
        json_data = json.loads(body)
        messaging_api = MessagingApi(ApiClient(Configuration(access_token=lineToken)))  # 確認 token 是否正確
        handler = WebhookHandler(lineSecret)   # 確認 secret 是否正確
        signature = request.headers['X-Line-Signature']
        handler.handle(body, signature)
        if json_data['events'] == []: 
            print('Verify Success')  # Line Bot 驗證成功
            return 'Verify Success'
        tk = json_data['events'][0]['replyToken']
        
        user_question = json_data['events'][0]['message']['text']
        print(f"🟣 [Msg] {tk[:6]}: {user_question}")
        try:
            ans = asyncio.run(askAI(user_question))
            message = [TextMessage(text=ans)]
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=tk,
                    messages=message
                )
            )
            print(f"🟣 [Msg] {tk[:6]}: Message Sent! ")
        except Exception as e:
            print(f"🔴 [Error] 發生錯誤\n{traceback.format_exc()}")
            error_message = [TextMessage(text="發生錯誤，請稍後再試！")]
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=tk,
                    messages=error_message
                )
            )
            print(f"🟣 [Msg] {tk[:6]}: Error Sent!")
    except Exception as e:
        print(f"🔴 [Error] 發生錯誤\n{traceback.format_exc()}")
        print(request.args)
    return 'OK'
