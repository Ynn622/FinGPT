"""LINE 盤前報告白名單 multicast 傳送工具。"""

from typing import Any, Dict, List

from linebot.v3.messaging import (
    ApiClient, Configuration, FlexContainer, FlexMessage, MessagingApi, MulticastRequest,
)

from services.morning.subscribers import morning_alert_user_ids
from util.config import Env


MULTICAST_BATCH_SIZE = 500


def multicast_morning_report(payloads: List[Dict[str, Any]], alt_texts: List[str]) -> int:
    """將盤前報告 Flex 訊息分批傳給白名單使用者，並回傳收件人數。"""
    if not Env.LINE_TOKEN:
        raise RuntimeError("LINE_TOKEN is required for multicast")
    if len(payloads) != len(alt_texts) or not 1 <= len(payloads) <= 5:
        raise ValueError("LINE multicast requires 1-5 matching payloads and alt texts")
    recipients = morning_alert_user_ids()
    if not recipients:
        return 0
    messages = [
        FlexMessage(alt_text=alt, contents=FlexContainer.from_dict(payload))
        for payload, alt in zip(payloads, alt_texts)
    ]
    with ApiClient(Configuration(access_token=Env.LINE_TOKEN)) as api_client:
        messaging_api = MessagingApi(api_client)
        for offset in range(0, len(recipients), MULTICAST_BATCH_SIZE):
            messaging_api.multicast(
                MulticastRequest(
                    to=recipients[offset:offset + MULTICAST_BATCH_SIZE],
                    messages=messages,
                )
            )
    return len(recipients)
