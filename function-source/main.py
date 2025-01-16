import json
from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    TemplateMessage,
    URIAction,
    CarouselTemplate,
    CarouselColumn
)

import os      # 設定環境變數用
import traceback

from stock import generate    # stock.py

# LineBot 接收&傳送
def linebot(request):
    try:
        access_token = os.environ["Line_token"]
        secret = os.environ["Line_secret"]
        body = request.get_data(as_text=True)
        json_data = json.loads(body)   # json格式 資料
        messaging_api = MessagingApi(ApiClient(Configuration(access_token=access_token)))  # 確認 token 是否正確
        handler = WebhookHandler(secret)                     # 確認 secret 是否正確
        signature = request.headers['X-Line-Signature']
        handler.handle(body, signature)
        msg = json_data['events'][0]['message']['text']
        tk = json_data['events'][0]['replyToken']
        send = msg.replace(" ","\n").split("\n")
        send = list(filter(None,send))  # 去除空格
        symbol = send[0]
        user_question = ",".join(s for s in send[1:])
        ans,lineColTmp = generate(symbol,user_question)
        message = [TextMessage(text=ans)]
        if lineColTmp!=[]:
            message.extend([TextMessage(text="📢 相關新聞如下："),lineColTmp])
        messaging_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=tk,
                messages=message
            )
        )
        print(msg, tk)
    except Exception as e:
        print("發生錯誤",traceback.format_exc())
        print(request.args)
    return 'OK'
