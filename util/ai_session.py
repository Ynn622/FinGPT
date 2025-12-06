from agents import SQLiteSession

from util.config import env

async def trim_session(session_id: str) -> SQLiteSession:
    """
    修剪對話紀錄至最近的 N 次 user->assistant 對話。
    Args:
        session_id (str): 對話會話的唯一識別碼。
    Returns:
        SQLiteSession: 修剪後的對話會話物件。
    """
    max_turns = env.SESSION_MAX_ITEMS
    session = SQLiteSession(session_id, "conversations.db")
    items = await session.get_items()

    # 找出所有 user 訊息的 index 值
    user_indices = [
        idx for idx, item in enumerate(items)
        if (item.get("role") if isinstance(item, dict) else getattr(item, "role", None)) == "user"
    ]
    # 若 user 訊息數量超過 max_turns，則修剪對話紀錄
    if len(user_indices) > max_turns:
        start_idx = user_indices[-max_turns]
        trimmed = items[start_idx:]
        await session.clear_session()
        await session.add_items(trimmed)
    return session

async def clear_session(session_id: str):
    """
    清除指定 session_id 的對話紀錄。
    Args:
        session_id (str): 對話會話的唯一識別碼。
    """
    session = SQLiteSession(session_id, "conversations.db")
    await session.clear_session()