from functools import wraps
import inspect
from enum import Enum

from util.config import Env
from util.taiwan_time import TaiwanTime

# === 顏色設定 ===
class Color(Enum):
    RESET = "\033[0m"
    PURPLE = "\033[95m"   # 紫色
    RED = "\033[91m"      # 紅色
    BLUE = "\033[94m"     # 藍色
    GREEN = "\033[92m"    # 綠色
    YELLOW = "\033[93m"   # 黃色
    ORANGE = "\033[38;5;208m"   # 橙色

# 顏色對應 icon
ICON_BY_COLOR = {
    Color.PURPLE: "🟣",
    Color.RED: "🔴",
    Color.BLUE: "🔵",
    Color.GREEN: "🟢",
    Color.YELLOW: "🟡",
    Color.ORANGE: "🟠",
}

# === 日誌裝飾器 ===
def log_print(func):
    """裝飾函式並記錄呼叫參數、成功結果與例外。"""
    def build_arg_string(args, kwargs):
        """將位置參數與關鍵字參數組合成日誌字串。"""
        parts = []
        if args:
            parts.append(", ".join(map(str, args)))
        if kwargs:
            parts.append(", ".join(f"{k}={v}" for k, v in kwargs.items()))
        return ", ".join(parts)

    if inspect.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            """包裝非同步函式並輸出執行日誌。"""
            func_name = func.__name__
            arg_str = build_arg_string(args, kwargs)
            try:
                print(f"{TaiwanTime.string(ms=True)} | "
                      f"{Color.PURPLE.value}🟣 [FunctionCall] {func_name}({arg_str}){Color.RESET.value}")

                return await func(*args, **kwargs)
            except Exception as e:
                print(f"{TaiwanTime.string(ms=True)} | "
                      f"{Color.RED.value}🔴 [Error] {func_name}: {e}{Color.RESET.value}")
                raise
        return async_wrapper
    else:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            """包裝同步函式並輸出執行日誌。"""
            func_name = func.__name__
            arg_str = build_arg_string(args, kwargs)
            try:
                print(f"{TaiwanTime.string(ms=True)} | "
                      f"{Color.BLUE.value}🔵 [Function] {func_name}({arg_str}){Color.RESET.value}")
                return func(*args, **kwargs)
            except Exception as e:
                print(f"{TaiwanTime.string(ms=True)} | "
                      f"{Color.RED.value}🔴 [Error] {func_name}: {e}{Color.RESET.value}")
                raise
        return sync_wrapper

def Log(*args, color: Color = Color.BLUE, sep=" ", end="\n", reload_only: bool = False):
    """
    印出帶有時間戳記與顏色的日誌訊息。
    Args:
        *args: 要印出的訊息內容。
        color (Color): 訊息顏色，預設為藍色。
        sep (str): 訊息間的分隔符號，預設為空格。
        end (str): 訊息結尾的字元，預設為換行符號。
        reload_only (bool): 是否僅在 Env.RELOAD=True 時印出訊息，預設為 False。
    """
    if reload_only and not Env.RELOAD:
        return
    icon = ICON_BY_COLOR.get(color, "")
    message = sep.join(str(arg) for arg in args)
    print(f"{TaiwanTime.string(ms=True)} | {icon} {color.value}{message}{Color.RESET.value}", end=end)
