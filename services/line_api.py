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
import time

from util.config import Env
from util.logger import Log, Color

from services.function_tools import ask_AI_Agent   # 引入自定義工具函數

router = APIRouter(prefix="/api", tags=["LineBot"])

# LineBot 接收&傳送
@router.post('/linebot')
async def linebot(request: Request, x_line_signature: str = Header(None)):
    start_time = time.time()
    body = (await request.body()).decode("utf-8")
    try:
        line_token = Env.LINE_TOKEN
        line_secret = Env.LINE_SECRET
        json_data = json.loads(body)
        messaging_api = MessagingApi(ApiClient(Configuration(access_token=line_token)))  # 確認 token 是否正確
        handler = WebhookHandler(line_secret)   # 確認 secret 是否正確
        handler.handle(body, x_line_signature)
        if json_data['events'] == []: 
            Log('Verify Success', color=Color.ORANGE)  # Line Bot 驗證成功
            return 'Verify Success'
        replyToken = json_data['events'][0]['replyToken']
        user_id = json_data['events'][0]['source']['userId']
        
        user_question = json_data['events'][0]['message']['text']
        Log(f"[Receive] {user_id[:10]}(Token: {replyToken[:6]}): {user_question}", color=Color.BLUE)
        try:
            if user_question == "clear session":
                from util.ai_session import clear_session
                await clear_session(user_id)
                send_reply_message(messaging_api, replyToken, "已清除對話記憶!")
                Log(f"[Send] {user_id[:10]}(Token: {replyToken[:6]}) -> Clear Session (use {time.time() - start_time:.2f}s)", color=Color.GREEN)
                return 'Clear Session Done!'
            ans = await ask_AI_Agent(user_question, session_id=user_id)
            send_reply_message(messaging_api, replyToken, ans)
            Log(f"[Send] {user_id[:10]}(Token: {replyToken[:6]}) -> Success (use {time.time() - start_time:.2f}s)", color=Color.GREEN)
        except Exception as e:
            Log(f"[Error] AI處理時 發生錯誤\n{e}", color=Color.RED)
            send_reply_message(messaging_api, replyToken, "發生錯誤,請稍後再試!")
            Log(f"[Send] {user_id[:10]}(Token: {replyToken[:6]}) -> Error (use {time.time() - start_time:.2f}s)", color=Color.RED)
    except Exception as e:
        Log(f"[Error] 發生錯誤\n{traceback.format_exc()}", color=Color.RED)
    return 'OK'

def send_reply_message(messaging_api: MessagingApi ,reply_token: str, text: str):
    """封裝 Line 訊息回覆功能"""
    message = [TextMessage(text=text)]
    messaging_api.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=message
        )
    )
    Log(f"Reply Message Sent: {text[:30]}...", color=Color.PURPLE)