from dotenv import load_dotenv, find_dotenv
import os

# 自動尋找專案根目錄的 .env
load_dotenv(find_dotenv(), override=False)

# 統一管理環境變數
class Env:
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    LINE_TOKEN: str = os.getenv("LINE_TOKEN", "")
    LINE_SECRET: str = os.getenv("LINE_SECRET", "")
    DOCS_PASSWORD: str = os.getenv("DOCS_PASSWORD", "")
    DOCS_USERNAME: str = os.getenv("DOCS_USERNAME", "")
    AI_MODEL: str = os.getenv("AI_MODEL", "gpt-5.6-luna")
    RELOAD: bool = os.getenv("RELOAD", "").lower() == "true"
    SESSION_MAX_ITEMS: int = int(os.getenv("SESSION_MAX_ITEMS", 4))
    PORT: int = int(os.getenv("PORT", 7860))    # Hugging Face Spaces 預設使用 7860 port
    MORNING_AI_MODEL: str = os.getenv("MORNING_AI_MODEL", "gpt-5.6-luna")
    MORNING_TOP_N: int = int(os.getenv("MORNING_TOP_N", "100"))
    MORNING_DEEP_N: int = int(os.getenv("MORNING_DEEP_N", "20"))
    MORNING_INTRADAY_N: int = int(os.getenv("MORNING_INTRADAY_N", "5"))
    MORNING_SWING_N: int = int(os.getenv("MORNING_SWING_N", "5"))
    MORNING_MIN_SCORE: float = float(os.getenv("MORNING_MIN_SCORE", "60"))
    MORNING_INCOMPLETE_SCORE_CAP: float = float(os.getenv("MORNING_INCOMPLETE_SCORE_CAP", "75"))
    MORNING_SWING_BEARISH_MIN_SCORE: float = float(os.getenv("MORNING_SWING_BEARISH_MIN_SCORE", "68"))
    MORNING_SWING_EXTREME_BEARISH_MIN_SCORE: float = float(os.getenv("MORNING_SWING_EXTREME_BEARISH_MIN_SCORE", "75"))
    MORNING_MIN_AVG_TRADE_VALUE: float = float(os.getenv("MORNING_MIN_AVG_TRADE_VALUE", "100000000"))
    MORNING_INTRADAY_MAX_CLOSE: float = float(os.getenv("MORNING_INTRADAY_MAX_CLOSE", "300"))
    MORNING_MIN_TP1_REWARD_RISK: float = float(os.getenv("MORNING_MIN_TP1_REWARD_RISK", "1.1"))
    MORNING_SCHEDULE_HOUR: int = int(os.getenv("MORNING_SCHEDULE_HOUR", "7"))
    MORNING_SCHEDULE_MINUTE: int = int(os.getenv("MORNING_SCHEDULE_MINUTE", "0"))
    ENABLE_MORNING_SCHEDULER: bool = os.getenv("ENABLE_MORNING_SCHEDULER", "true").lower() == "true"
    MORNING_PUSH_ENABLED: bool = os.getenv("MORNING_PUSH_ENABLED", "true").lower() == "true"
    MORNING_YF_BATCH_SIZE: int = int(os.getenv("MORNING_YF_BATCH_SIZE", "40"))
    MORNING_HTTP_MAX_WORKERS: int = int(os.getenv("MORNING_HTTP_MAX_WORKERS", "8"))
    
env = Env()
