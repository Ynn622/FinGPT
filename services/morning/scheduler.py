"""單一行程 APScheduler 排程整合。"""

from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from services.morning.pipeline import run_morning_pipeline
from util.config import Env
from util.logger import Color, Log
from util.taiwan_time import TaiwanTime


_scheduler: Optional[AsyncIOScheduler] = None


def start_scheduler() -> Optional[AsyncIOScheduler]:
    """依環境設定啟動盤前報告排程器。"""
    global _scheduler
    if not Env.ENABLE_MORNING_SCHEDULER:
        Log("[Morning] Scheduler disabled", color=Color.YELLOW)
        return None
    if _scheduler and _scheduler.running:
        return _scheduler
    _scheduler = AsyncIOScheduler(timezone=TaiwanTime.TIMEZONE)
    _scheduler.add_job(
        run_morning_pipeline, "cron", day_of_week="mon-fri",
        hour=Env.MORNING_SCHEDULE_HOUR, minute=Env.MORNING_SCHEDULE_MINUTE,
        kwargs={"push": True, "force": False}, id="morning-report-v1",
        replace_existing=True, max_instances=1, coalesce=True,
    )
    _scheduler.start()
    Log("[Morning] Scheduler started", color=Color.GREEN)
    return _scheduler


def stop_scheduler() -> None:
    """安全關閉盤前報告排程器並清除實例。"""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        Log("[Morning] Scheduler stopped", color=Color.YELLOW)
    _scheduler = None
