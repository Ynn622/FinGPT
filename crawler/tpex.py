"""證券櫃檯買賣中心公開資料來源。"""

from typing import Dict, List, Set

from crawler.http import get_json
from services.morning.models import StockCandidate, StockRiskFlag
from services.morning.utils import normalize_stock_code, number
from util.taiwan_time import TaiwanTime


BASE = "https://www.tpex.org.tw/openapi/v1"


def fetch_candidates() -> List[StockCandidate]:
    """取得櫃買市場每日收盤的股票候選資料。"""
    rows = get_json(f"{BASE}/tpex_mainboard_daily_close_quotes")
    return [
        StockCandidate(
            stock_id=normalize_stock_code(row["SecuritiesCompanyCode"]),
            stock_name=str(row["CompanyName"]).strip(),
            market="TPEX",
            date=TaiwanTime.roc_date(row["Date"]),
            close=number(row["Close"]),
            volume=number(row["TradingShares"]),  # 官方單位：股
            trade_value=number(row["TransactionAmount"]),  # 官方單位：新台幣
        )
        for row in rows
        if number(row.get("Close")) > 0 and number(row.get("TransactionAmount")) > 0
    ]


def fetch_day_trade_flags() -> Dict[str, StockRiskFlag]:
    """取得櫃買股票的當沖與先賣後買資格。"""
    rows = get_json(f"{BASE}/tpex_securities")
    result: Dict[str, StockRiskFlag] = {}
    for row in rows:
        code = normalize_stock_code(row.get("證券代號", ""))
        suspended = str(row.get("暫停現股賣出後現款買進當沖註記", "")).strip() not in {
            "",
            "-",
        }
        result[code] = StockRiskFlag(
            stock_id=code, can_day_trade=True, can_short_day_trade=not suspended
        )
    return result


def _codes(endpoint: str) -> Set[str]:
    """從指定櫃買 API 端點整理股票代號集合。"""
    return {
        normalize_stock_code(row.get("SecuritiesCompanyCode", ""))
        for row in get_json(f"{BASE}/{endpoint}")
        if row.get("SecuritiesCompanyCode")
    }


def fetch_risk_flags() -> Dict[str, StockRiskFlag]:
    """取得櫃買股票的注意、處置與變更交易風險標記。"""
    def safe(endpoint: str) -> Set[str]:
        """安全取得指定端點的股票代號集合。"""
        try:
            return _codes(endpoint)
        except Exception:
            return set()
    warning = safe("tpex_trading_warning_information")
    disposal = safe("tpex_disposal_information")
    try:
        altered = {
            normalize_stock_code(row.get("SecuritiesCompanyCode", ""))
            for row in get_json(f"{BASE}/tpex_cmode")
            if str(row.get("AlteredTrading", "")).strip().upper() in {"Y", "Ｙ"}
        }
    except Exception:
        altered = set()
    return {
        code: StockRiskFlag(
            stock_id=code,
            warning=code in warning,
            disposal=code in disposal,
            altered_trading=code in altered,
        )
        for code in warning | disposal | altered
    }
