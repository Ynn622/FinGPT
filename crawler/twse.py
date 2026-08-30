"""臺灣證券交易所公開資料來源。"""

from datetime import date, datetime
from typing import Dict, Iterable, List, Set

from services.morning.cache import CACHE_DIR, atomic_write_json, read_json
from crawler.http import get_json
from services.morning.models import StockCandidate, StockRiskFlag
from services.morning.utils import normalize_stock_code, number
from util.taiwan_time import TaiwanTime


BASE = "https://openapi.twse.com.tw/v1"


def fetch_candidates() -> List[StockCandidate]:
    """取得上市市場每日收盤的股票候選資料。"""
    rows = get_json(f"{BASE}/exchangeReport/STOCK_DAY_ALL")
    return [
        StockCandidate(
            stock_id=normalize_stock_code(row["Code"]),
            stock_name=str(row["Name"]).strip(),
            market="TWSE",
            date=TaiwanTime.roc_date(row["Date"]),
            close=number(row["ClosingPrice"]),
            volume=number(row["TradeVolume"]),  # 官方單位：股
            trade_value=number(row["TradeValue"]),  # 官方單位：新台幣
        )
        for row in rows
        if number(row.get("ClosingPrice")) > 0 and number(row.get("TradeValue")) > 0
    ]


def fetch_day_trade_flags() -> Dict[str, StockRiskFlag]:
    """取得上市股票的當沖與先賣後買資格。"""
    rows = get_json(f"{BASE}/exchangeReport/TWTB4U")
    result: Dict[str, StockRiskFlag] = {}
    for row in rows:
        code = normalize_stock_code(row.get("Code", ""))
        # 出現在清單即代表可先買後賣；依官方欄位，暫停註記代表不可先賣後買。
        suspended = str(row.get("Suspension", "")).strip() not in {"", "-"}
        result[code] = StockRiskFlag(
            stock_id=code, can_day_trade=True, can_short_day_trade=not suspended
        )
    return result


def _codes(path: str, field: str = "Code") -> Set[str]:
    """從指定證交所 API 路徑整理股票代號集合。"""
    return {
        normalize_stock_code(row.get(field, ""))
        for row in get_json(f"{BASE}{path}")
        if row.get(field)
    }


def fetch_risk_flags() -> Dict[str, StockRiskFlag]:
    """取得上市股票的注意、處置與變更交易風險標記。"""
    def safe(path: str) -> Set[str]:
        """安全取得指定路徑的股票代號集合。"""
        try:
            return _codes(path)
        except Exception:
            return set()
    warning = safe("/announcement/notice")
    disposal = safe("/announcement/punish")
    altered = safe("/exchangeReport/TWT85U")
    return {
        code: StockRiskFlag(
            stock_id=code,
            warning=code in warning,
            disposal=code in disposal,
            altered_trading=code in altered,
        )
        for code in warning | disposal | altered
    }


def fetch_holiday_dates(year: int) -> Set[str]:
    """取得指定年度的證交所休市日期並寫入快取。"""
    cache_path = CACHE_DIR / f"twse_holidays_{year}.json"
    try:
        rows = get_json(f"{BASE}/holidaySchedule/holidaySchedule")
        dates = sorted(
            {
                TaiwanTime.roc_date(row.get("Date", ""))
                for row in rows
                if TaiwanTime.roc_date(row.get("Date", "")).startswith(str(year))
            }
        )
        atomic_write_json(cache_path, dates)
        return set(dates)
    except Exception:
        cached = read_json(cache_path)
        if isinstance(cached, list):
            return set(cached)
        raise


def is_trading_day(day: date) -> bool:
    """判斷指定日期是否為台股交易日。"""
    if day.weekday() >= 5:
        return False
    try:
        return day.isoformat() not in fetch_holiday_dates(day.year)
    except Exception:
        # 休市服務失敗時不可誤判為休市，排程仍會以候選資料日期再次確認。
        return True
