"""盤前推播訂閱者白名單。"""

from pathlib import Path
from threading import Lock
from typing import List

from services.morning import cache


MORNING_ALERT_WHITELIST = Path("data/cache/morning_alert_whitelist.json")
_WHITELIST_LOCK = Lock()


def morning_alert_user_ids() -> List[str]:
    """讀取已訂閱盤前推播的 LINE user ID，並排除無效與重複資料。"""
    payload = cache.read_json(MORNING_ALERT_WHITELIST) or {}
    values = payload.get("user_ids", []) if isinstance(payload, dict) else []
    if not isinstance(values, list):
        return []
    return sorted({value.strip() for value in values if isinstance(value, str) and value.strip()})


def subscribe_morning_alert(user_id: str) -> bool:
    """將 LINE user ID 原子加入白名單；新加入時回傳 True。"""
    normalized = user_id.strip() if isinstance(user_id, str) else ""
    if not normalized:
        raise ValueError("LINE user ID is required")

    with _WHITELIST_LOCK:
        user_ids = set(morning_alert_user_ids())
        if normalized in user_ids:
            return False
        user_ids.add(normalized)
        cache.atomic_write_json(
            MORNING_ALERT_WHITELIST,
            {"user_ids": sorted(user_ids)},
        )
    return True
