"""JSON 快取與本地推播冪等控制。"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional


CACHE_DIR = Path("data/cache")
OUTPUT_DIR = Path("data/output")
PUSH_STATE = CACHE_DIR / "morning_push_state.json"


def read_json(path: Path) -> Optional[Any]:
    """讀取 JSON 檔案並在格式或存取失敗時回傳空值。"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def atomic_write_json(path: Path, payload: Any) -> None:
    """透過暫存檔原子寫入 JSON 資料。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, default=str)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def was_pushed(report_date: str) -> bool:
    """判斷指定報告日期是否已成功推播。"""
    state = read_json(PUSH_STATE) or {}
    return state.get("last_successful_push_date") == report_date


def mark_pushed(report_date: str) -> None:
    """將指定報告日期記錄為已成功推播。"""
    atomic_write_json(PUSH_STATE, {"last_successful_push_date": report_date})
