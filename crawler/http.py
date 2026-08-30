"""爬蟲共用 HTTP 客戶端。"""

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def session() -> requests.Session:
    """建立具備重試與逾時設定的 HTTP 連線。"""
    retry = Retry(
        total=2,
        backoff_factor=0.4,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST"),
    )
    client = requests.Session()
    client.headers.update({"User-Agent": "FinGPT-Morning/1.0"})
    client.mount("https://", HTTPAdapter(max_retries=retry))
    return client


def get_json(url: str) -> Any:
    """向指定網址取得 JSON 資料並檢查回應狀態。"""
    response = session().get(url, timeout=10)
    response.raise_for_status()
    return response.json()
