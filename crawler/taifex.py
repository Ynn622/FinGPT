"""臺灣期貨交易所台指期夜盤資料來源。"""

import re
from datetime import date, timedelta
from io import BytesIO
from typing import Any, Dict, Optional

import pandas as pd
from bs4 import BeautifulSoup

from crawler.http import get_json, session
from services.morning.cache import CACHE_DIR, atomic_write_json, read_json
from services.morning.utils import number
from util.logger import Color, Log
from util.taiwan_time import TaiwanTime


TX_NIGHT_CACHE = CACHE_DIR / "tx_night_latest.json"
TAIFEX_OPENAPI_URL = "https://openapi.taifex.com.tw/v1/DailyMarketReportFut"


def fetch_tx_night_history(
    start_date: str,
    end_date: str,
    front_month_only: bool = True,
) -> pd.DataFrame:
    """分批下載指定日期範圍的台指期夜盤歷史行情。"""
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if start > end:
        raise ValueError("start_date 不可晚於 end_date")
    
    def _parse_futures_csv(content: bytes) -> pd.DataFrame:
        """解析期交所 CP950 編碼的期貨每日行情 CSV。"""
        frame = pd.read_csv(BytesIO(content), encoding="cp950", dtype=str, index_col=False)
        frame.columns = frame.columns.str.strip()
        for column in frame.columns:
            frame[column] = frame[column].str.strip()
        return frame
    
    def _date_chunks(start_date: date, end_date: date):
        """將日期範圍切成期交所允許的最長一個月區間。"""
        current = start_date
        while current <= end_date:
            chunk_end = min(end_date, (pd.Timestamp(current) + pd.DateOffset(months=1)).date())
            yield current, chunk_end
            current = chunk_end + timedelta(days=1)

    client = session()
    frames = []
    for chunk_start, chunk_end in _date_chunks(start, end):
        response = client.post(
            "https://www.taifex.com.tw/cht/3/futDataDown",
            data={
                "down_type": "1",
                "queryStartDate": chunk_start.strftime("%Y/%m/%d"),
                "queryEndDate": chunk_end.strftime("%Y/%m/%d"),
                "commodity_id": "TX",
                "commodity_id2": "",
            },
            timeout=10,
        )
        response.raise_for_status()
        frames.append(_parse_futures_csv(response.content))

    columns = [
        "date", "symbol", "contract", "open", "high", "low", "close",
        "change", "change_pct", "volume", "session", "source",
    ]
    if not frames:
        return pd.DataFrame(columns=columns)

    frame = pd.concat(frames, ignore_index=True)
    required = {
        "交易日期", "契約", "到期月份(週別)", "開盤價", "最高價", "最低價",
        "收盤價", "漲跌價", "漲跌%", "成交量", "交易時段",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"期交所 CSV 缺少欄位: {', '.join(sorted(missing))}")

    frame = frame[
        (frame["契約"] == "TX")
        & (frame["交易時段"] == "盤後")
        & frame["到期月份(週別)"].str.fullmatch(r"\d{6}", na=False)
    ].copy()
    frame["交易日期"] = pd.to_datetime(frame["交易日期"], errors="coerce")
    frame = frame[
        frame["交易日期"].dt.date.between(start, end, inclusive="both")
    ]
    frame.sort_values(["交易日期", "到期月份(週別)"], inplace=True)
    if front_month_only:
        frame = frame.drop_duplicates(subset=["交易日期"], keep="first")

    rename = {
        "交易日期": "date",
        "契約": "symbol",
        "到期月份(週別)": "contract",
        "開盤價": "open",
        "最高價": "high",
        "最低價": "low",
        "收盤價": "close",
        "漲跌價": "change",
        "漲跌%": "change_pct",
        "成交量": "volume",
        "交易時段": "session",
    }
    frame.rename(columns=rename, inplace=True)
    frame["date"] = frame["date"].dt.strftime("%Y-%m-%d")
    frame["session"] = "night"
    for column in ("open", "high", "low", "close", "change", "change_pct", "volume"):
        frame[column] = pd.to_numeric(
            frame[column].str.replace(",", "", regex=False).str.replace("%", "", regex=False),
            errors="coerce",
        )
    frame["source"] = "TAIFEX_DOWNLOAD"
    return frame[columns].drop_duplicates().reset_index(drop=True)


def is_current_for_stock_date(tx_night: Optional[Dict[str, Any]], stock_date: str) -> bool:
    """判斷台指期夜盤資料是否不早於最近現貨交易日。"""
    return bool(tx_night and str(tx_night.get("date", "")) >= stock_date)


def _signed_number(value: object) -> float:
    """移除漲跌符號並轉換成數值。"""
    return number(str(value).replace("▲", "").replace("▼", ""))


def parse_tx_night_html(html: str, trading_date: str) -> Optional[Dict[str, Any]]:
    """解析期交所網頁中最近月份的有效台指期夜盤資料。"""
    soup = BeautifulSoup(html, "lxml")
    contracts = []
    for table in soup.select("table.table_f"):
        for row in table.select("tbody tr"):
            cells = [" ".join(cell.get_text(" ", strip=True).split()) for cell in row.find_all("td")]
            if len(cells) < 9 or cells[0].strip() != "TX":
                continue
            contract = cells[1].strip()
            if not re.fullmatch(r"\d{6}", contract):
                continue  # 排除價差契約與非月份契約
            volume = number(cells[8])
            close = number(cells[5])
            if volume <= 0 or close <= 0:
                continue
            contracts.append((contract, cells))
        if contracts:
            break
    if not contracts:
        return None
    contract, cells = min(contracts, key=lambda item: item[0])
    return {
        "symbol": "TX", "session": "night", "contract": contract,
        "date": trading_date, "open": number(cells[2]), "high": number(cells[3]),
        "low": number(cells[4]), "close": number(cells[5]),
        "change": _signed_number(cells[6]), "change_pct": _signed_number(cells[7]),
        "volume": number(cells[8]), "source": "TAIFEX_WEB",
    }


def fetch_tx_night_from_web(trading_date: str) -> Optional[Dict[str, Any]]:
    """從期交所網頁取得指定日期的台指期夜盤資料。"""
    response = session().post(
        "https://www.taifex.com.tw/cht/3/futDailyMarketReport",
        data={
            "queryType": "2", "marketCode": "1", "MarketCode": "1",
            "queryDate": trading_date.replace("-", "/"),
            "commodity_id": "TX", "commodity_idt": "TX", "commodity_id2": "",
        },
        timeout=10,
    )
    response.raise_for_status()
    return parse_tx_night_html(response.text, trading_date)


def fetch_tx_night_from_openapi() -> Optional[Dict[str, Any]]:
    """從期交所 OpenAPI 取得最近月份的台指期夜盤資料。"""
    rows = [
        row for row in get_json(TAIFEX_OPENAPI_URL)
        if row.get("Contract") == "TX"
        and row.get("TradingSession") == "盤後"
        and re.fullmatch(r"\d{6}", str(row.get("ContractMonth(Week)", "")))
        and number(row.get("Volume")) > 0 and number(row.get("Last")) > 0
    ]
    if not rows:
        return None
    row = min(rows, key=lambda item: str(item.get("ContractMonth(Week)", "")))
    return {
        "symbol": "TX", "session": "night", "contract": row.get("ContractMonth(Week)"),
        "date": TaiwanTime.roc_date(row.get("Date")), "open": number(row.get("Open")),
        "high": number(row.get("High")), "low": number(row.get("Low")),
        "close": number(row.get("Last")), "change": number(row.get("Change")),
        "change_pct": number(row.get("%")), "volume": number(row.get("Volume")),
        "source": "TAIFEX_OPENAPI_FALLBACK",
    }


def fetch_tx_night(trading_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """取得官方台指期夜盤資料並優先採用較即時的網頁來源。"""
    date_value = trading_date or TaiwanTime.string(time=False)
    try:
        web_result = fetch_tx_night_from_web(date_value)
        if web_result is not None:
            atomic_write_json(TX_NIGHT_CACHE, web_result)
            return web_result
    except Exception as error:
        Log(f"[Morning] TAIFEX website failed; using OpenAPI fallback: {error}", color=Color.YELLOW)
    try:
        openapi_result = fetch_tx_night_from_openapi()
        if openapi_result is not None:
            atomic_write_json(TX_NIGHT_CACHE, openapi_result)
            return openapi_result
    except Exception as error:
        Log(f"[Morning] TAIFEX OpenAPI failed; using local cache: {error}", color=Color.YELLOW)
    cached = read_json(TX_NIGHT_CACHE)
    if not isinstance(cached, dict):
        return None
    result = dict(cached)
    result["cached_source"] = result.get("source", "")
    result["source"] = "TAIFEX_CACHE"
    return result
