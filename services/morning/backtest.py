"""盤前市場分數的歷史校準與回測工具。"""

from __future__ import annotations

import argparse
import itertools
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence

import numpy as np
import pandas as pd

from crawler.yahoo import _symbol_frame, fetch_backtest_history
from services.morning import cache
from services.morning.market_regime import WEIGHTS


SYMBOLS = {
    "nasdaq": "^IXIC", "sox": "^SOX", "tsm": "TSM",
    "usdtwd": "TWD=X", "twii": "^TWII",
}
FACTOR_SCALES = {
    "nasdaq": 2.0, "sox": 2.0, "tsm": 2.0, "tx": 2.0, "usdtwd": 0.5,
}


def _series(frame: pd.DataFrame, column: str) -> pd.Series:
    """將指定欄位整理成無時區、無重複且依日期排序的數列。"""
    result = pd.to_numeric(frame[column], errors="coerce").dropna().copy()
    result.index = pd.DatetimeIndex(result.index).tz_localize(None).normalize()
    return result[~result.index.duplicated(keep="last")].sort_index()


def _next_session_signal(changes: pd.Series, sessions: pd.DatetimeIndex) -> pd.Series:
    """將來源收盤訊號延後對齊至下一個台灣交易日。"""
    shifted = changes.copy()
    shifted.index = shifted.index + pd.Timedelta(days=1)
    return shifted.reindex(sessions, method="ffill")


def load_backtest_frame(years: int = 3, tx_csv: Optional[Path] = None) -> pd.DataFrame:
    """下載並整理指定年數的盤前市場回測資料。"""
    end = date.today() + timedelta(days=1)
    start = end - timedelta(days=max(1, years) * 366 + 90)
    downloaded = fetch_backtest_history(
        list(SYMBOLS.values()), start.isoformat(), end.isoformat()
    )
    twii = _symbol_frame(downloaded, SYMBOLS["twii"])
    twii_open, twii_close = _series(twii, "Open"), _series(twii, "Close")
    target = pd.DataFrame(index=twii_close.index)
    target["twii_open_to_close_pct"] = (twii_close / twii_open - 1) * 100
    target["twii_close_to_close_pct"] = twii_close.pct_change() * 100

    for key in ("nasdaq", "sox", "tsm", "usdtwd"):
        source = _symbol_frame(downloaded, SYMBOLS[key])
        close = _series(source, "Close")
        target[key] = _next_session_signal(close.pct_change() * 100, target.index)

    if tx_csv is not None:
        tx = pd.read_csv(tx_csv)
        if not {"date", "change_pct"}.issubset(tx.columns):
            raise ValueError("TX CSV 必須包含 date、change_pct 欄位")
        tx_changes = pd.Series(
            pd.to_numeric(tx["change_pct"], errors="coerce").to_numpy(),
            index=pd.to_datetime(tx["date"], errors="coerce"),
        ).dropna()
        tx_changes.index = pd.DatetimeIndex(tx_changes.index).tz_localize(None).normalize()
        target["tx"] = _next_session_signal(tx_changes.sort_index(), target.index)

    cutoff = pd.Timestamp(end - timedelta(days=max(1, years) * 366))
    return target.loc[target.index >= cutoff].dropna(subset=["twii_open_to_close_pct"])


def factor_frame(frame: pd.DataFrame, factors: Sequence[str]) -> pd.DataFrame:
    """依各因子尺度與方向將回測資料正規化。"""
    normalized = pd.DataFrame(index=frame.index)
    for key in factors:
        values = frame[key] / FACTOR_SCALES[key]
        normalized[key] = (-values if key == "usdtwd" else values).clip(-1, 1)
    return normalized


def score_frame(frame: pd.DataFrame, weights: Dict[str, float]) -> pd.Series:
    """依權重計算每個交易日的市場分數。"""
    factors = [key for key in weights if key in frame.columns]
    normalized = factor_frame(frame, factors)
    weight_series = pd.Series({key: float(weights[key]) for key in factors})
    available_weight = normalized.notna().mul(weight_series, axis=1).sum(axis=1)
    weighted = normalized.mul(weight_series, axis=1).sum(axis=1, min_count=1)
    return (weighted / available_weight.replace(0, np.nan) * 100).rename("market_score")


def _safe_correlation(left: pd.Series, right: pd.Series) -> float:
    """在樣本與變異足夠時安全計算兩個數列的相關係數。"""
    common = pd.concat([left, right], axis=1).dropna()
    if len(common) < 3 or common.iloc[:, 0].nunique() < 2 or common.iloc[:, 1].nunique() < 2:
        return 0.0
    return float(common.iloc[:, 0].corr(common.iloc[:, 1]))


def evaluate(scores: pd.Series, target: pd.Series) -> Dict[str, object]:
    """評估市場分數的相關性、方向準確率與各情境報酬。"""
    sample = pd.concat([scores, target.rename("target")], axis=1).dropna()
    active = sample[sample["market_score"].abs() >= 10]
    extreme = sample[sample["market_score"].abs() >= 35]

    def accuracy(rows: pd.DataFrame) -> Optional[float]:
        """計算有效樣本的多空方向準確率。"""
        if rows.empty:
            return None
        return float((np.sign(rows["market_score"]) == np.sign(rows["target"])).mean())

    regimes = pd.cut(
        sample["market_score"], bins=[-np.inf, -35, -10, 10, 35, np.inf],
        labels=["極空", "偏空", "震盪中性", "偏多", "極多"], right=False,
    )
    regime_returns: Dict[str, Dict[str, float]] = {}
    for label, rows in sample.groupby(regimes, observed=False):
        if not rows.empty:
            regime_returns[str(label)] = {
                "count": int(len(rows)),
                "avg_open_to_close_pct": round(float(rows["target"].mean()), 4),
            }
    direction_accuracy = accuracy(active)
    extreme_accuracy = accuracy(extreme)
    return {
        "samples": int(len(sample)),
        "correlation": round(_safe_correlation(sample["market_score"], sample["target"]), 4),
        "direction_samples": int(len(active)),
        "direction_accuracy": None if direction_accuracy is None else round(direction_accuracy, 4),
        "extreme_samples": int(len(extreme)),
        "extreme_accuracy": None if extreme_accuracy is None else round(extreme_accuracy, 4),
        "regime_returns": regime_returns,
    }


def _weight_combinations(factors: Sequence[str], step: int) -> Iterable[Dict[str, int]]:
    """產生符合加總限制的市場因子權重組合。"""
    units = 100 // step
    for cuts in itertools.combinations(range(1, units), len(factors) - 1):
        parts = np.diff((0, *cuts, units))
        weights = {key: int(value * step) for key, value in zip(factors, parts)}
        if "usdtwd" in weights and weights["usdtwd"] > 25:
            continue
        yield weights


def optimize_weights(frame: pd.DataFrame, factors: Sequence[str], step: int = 5) -> Dict[str, int]:
    """以訓練資料搜尋目標函式最佳的市場因子權重。"""
    if 100 % step:
        raise ValueError("step 必須可整除 100")
    target = frame["twii_open_to_close_pct"]
    best_weights: Optional[Dict[str, int]] = None
    best_objective = -float("inf")
    for weights in _weight_combinations(factors, step):
        scores = score_frame(frame, weights)
        correlation = _safe_correlation(scores, target)
        active = pd.concat([scores, target], axis=1).dropna()
        active = active[active.iloc[:, 0].abs() >= 10]
        accuracy = 0.5 if active.empty else float(
            (np.sign(active.iloc[:, 0]) == np.sign(active.iloc[:, 1])).mean()
        )
        objective = correlation + 0.25 * (accuracy - 0.5)
        if objective > best_objective:
            best_objective, best_weights = objective, weights
    if best_weights is None:
        raise ValueError("沒有可用的權重組合")
    return best_weights


def run_backtest(
    years: int = 3, train_ratio: float = 0.7, step: int = 5,
    tx_csv: Optional[Path] = None, output: Optional[Path] = None,
) -> Dict[str, object]:
    """切分訓練與測試資料、校準權重並輸出回測報告。"""
    if not 0.5 <= train_ratio <= 0.9:
        raise ValueError("train_ratio 必須介於 0.5 到 0.9")
    frame = load_backtest_frame(years, tx_csv)
    factors = [key for key in WEIGHTS if key in frame.columns and frame[key].notna().sum() >= 30]
    if len(factors) < 2:
        raise ValueError("可用歷史因子不足，至少需要兩項")
    complete = frame.dropna(subset=["twii_open_to_close_pct", *factors]).copy()
    if len(complete) < 100:
        raise ValueError(f"有效歷史樣本不足：{len(complete)}")
    split = min(len(complete) - 30, max(70, int(len(complete) * train_ratio)))
    train, test = complete.iloc[:split], complete.iloc[split:]
    current = {key: WEIGHTS[key] for key in factors}
    suggested = optimize_weights(train, factors, step)

    result_output = output or cache.OUTPUT_DIR / f"morning_backtest_{date.today().isoformat()}.json"
    dataset_output = result_output.with_suffix(".csv")
    dataset = complete.copy()
    dataset["current_score"] = score_frame(complete, current)
    dataset["suggested_score"] = score_frame(complete, suggested)
    dataset_output.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(dataset_output, index_label="date")

    result: Dict[str, object] = {
        "generated_date": date.today().isoformat(),
        "period": {"start": complete.index[0].date().isoformat(), "end": complete.index[-1].date().isoformat()},
        "target": "同一台灣交易日開盤至收盤報酬率",
        "alignment": "海外／匯率／夜盤日期皆延後至少一個日曆日，再對齊下一個台灣交易日",
        "train_samples": int(len(train)), "test_samples": int(len(test)),
        "factors": factors,
        "missing_factors": [key for key in WEIGHTS if key not in factors],
        "current_weights": current, "suggested_weights": suggested,
        "production_weights_changed": False,
        "current": {
            "train": evaluate(score_frame(train, current), train["twii_open_to_close_pct"]),
            "test": evaluate(score_frame(test, current), test["twii_open_to_close_pct"]),
        },
        "suggested": {
            "train": evaluate(score_frame(train, suggested), train["twii_open_to_close_pct"]),
            "test": evaluate(score_frame(test, suggested), test["twii_open_to_close_pct"]),
        },
        "dataset_csv": str(dataset_output),
        "note": "建議權重只供檢視；必須確認樣本外結果後才可人工調整正式設定。",
    }
    cache.atomic_write_json(result_output, result)
    result["result_json"] = str(result_output)
    return result


def main() -> None:
    """解析命令列參數並執行市場分數回測。"""
    parser = argparse.ArgumentParser(description="FinGPT 盤前市場分數歷史回測")
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--step", type=int, default=5)
    parser.add_argument("--tx-csv", type=Path, help="選填；欄位需為 date,change_pct")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_backtest(args.years, args.train_ratio, args.step, args.tx_csv, args.output)
    print(f"Backtest: {result['result_json']}")
    print(f"Dataset: {result['dataset_csv']}")
    print(f"Current test: {result['current']['test']}")
    print(f"Suggested weights: {result['suggested_weights']}")
    print(f"Suggested test: {result['suggested']['test']}")


if __name__ == "__main__":
    main()
