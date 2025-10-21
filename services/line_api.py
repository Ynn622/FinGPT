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
from fastapi import Request, APIRouter, Header
import traceback
import json
import os
from dotenv import load_dotenv
from util.logger import Log, Color
import time

from services.function_tools import askAI   # 引入自定義工具函數

load_dotenv()  # 讀取 .env 檔案

router = APIRouter(prefix="/api", tags=["LineBot"])

# LineBot 接收&傳送
@router.post('/linebot')
async def linebot(request: Request, x_line_signature: str = Header(None)):
    start_time = time.time()
    body = (await request.body()).decode("utf-8")
    try:
        line_token = os.environ["Line_token"]
        line_secret = os.environ["Line_secret"]
        json_data = json.loads(body)
        messaging_api = MessagingApi(ApiClient(Configuration(access_token=line_token)))  # 確認 token 是否正確
        handler = WebhookHandler(line_secret)   # 確認 secret 是否正確
        handler.handle(body, x_line_signature)
        if json_data['events'] == []: 
            Log('Verify Success', color=Color.YELLOW)  # Line Bot 驗證成功
            return 'Verify Success'
        tk = json_data['events'][0]['replyToken']
        user_id = json_data['events'][0]['source']['userId']
        
        user_question = json_data['events'][0]['message']['text']
        Log(f"🔵 [Receive] {user_id[:10]}(Token: {tk[:6]}): {user_question}", color=Color.BLUE)
        try:
            ans = await askAI(user_question)
            message = [TextMessage(text=ans)]
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=tk,
                    messages=message
                )
            )
            Log(f"🟢 [Send] {user_id[:10]}(Token: {tk[:6]}) -> Success (use {time.time() - start_time:.2f}s)", color=Color.GREEN)
        except Exception as e:
            Log(f"🔴 [Error] AI處理時 發生錯誤\n{traceback.format_exc()}", color=Color.RED)
            error_message = [TextMessage(text="發生錯誤，請稍後再試！")]
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=tk,
                    messages=error_message
                )
            )
            Log(f"🔴 [Send] {user_id[:10]}(Token: {tk[:6]}) -> Error (use {time.time() - start_time:.2f}s)", color=Color.RED)
    except Exception as e:
        Log(f"🔴 [Error] 發生錯誤\n{traceback.format_exc()}", color=Color.RED)
    return 'OK'