"""盤前報告資料抓取、評分、產出與推播流程。"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

from crawler import taifex, tpex, twse, yahoo
from crawler.morning import institutional, news
from services.morning import cache
from services.morning.flex_builder import build_flex_payloads, validate_flex_payload_size
from services.morning.line_broadcast import multicast_morning_report
from services.morning.market_regime import market_score, regime
from services.morning.models import (
    InstitutionalData, IntradayRecommendation, MorningReport, StockCandidate,
    StockRiskFlag, SwingRecommendation, TechnicalFeatures,
)
from services.morning.report_ai import generate_summary
from services.morning.risk import (
    merge_flags, reward_risk_ratio, round_to_valid_tick, swing_support, trade_plan,
)
from services.morning.scanner import merge_candidates
from services.morning.scoring import institutional_flow_ratio, intraday_scores, swing_score
from util.config import Env
from util.logger import Color, Log
from util.technical_indicators import calculate_features
from util.taiwan_time import TaiwanTime


def _safe(label: str, function: Any, default: Any) -> Any:
    """安全執行資料函式並在失敗時回傳預設值。"""
    try:
        return function()
    except Exception as error:
        Log(f"[Morning] {label} unavailable: {error}", color=Color.YELLOW)
        return default


def _fetch_candidates() -> Tuple[List[StockCandidate], List[StockCandidate]]:
    """並行取得上市與上櫃股票候選清單。"""
    with ThreadPoolExecutor(max_workers=2) as executor:
        jobs = {executor.submit(twse.fetch_candidates): "twse", executor.submit(tpex.fetch_candidates): "tpex"}
        result: Dict[str, List[StockCandidate]] = {"twse": [], "tpex": []}
        for future, market in jobs.items():
            result[market] = _safe(f"{market.upper()} candidates", future.result, [])
    return result["twse"], result["tpex"]


def _fetch_institutions(candidates: List[StockCandidate], data_date: str) -> Dict[str, InstitutionalData]:
    """只補充深度候選股的法人資料，供最終評分使用。"""
    institutions: Dict[str, InstitutionalData] = {}
    workers = max(1, min(Env.MORNING_HTTP_MAX_WORKERS, 10))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        jobs = {
            executor.submit(institutional.fetch, candidate.stock_id, data_date): candidate
            for candidate in candidates
        }
        for future in as_completed(jobs):
            candidate = jobs[future]
            try:
                value = future.result()
                if value is not None:
                    institutions[candidate.stock_id] = value
            except Exception as error:
                Log(f"[Morning] institution failed for {candidate.stock_id}: {error}", color=Color.YELLOW)
    return institutions


def _fetch_selected_news(candidates: List[StockCandidate]) -> Dict[str, Any]:
    """只抓取最終入選股票的新聞，並補上市場新聞。"""
    selected = {candidate.stock_id: candidate for candidate in candidates}
    result: Dict[str, Any] = {}
    workers = max(1, min(Env.MORNING_HTTP_MAX_WORKERS, 10))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        jobs = {
            executor.submit(news.fetch_stock, candidate.stock_name, 3): candidate
            for candidate in selected.values()
        }
        market_job = executor.submit(news.fetch_market, 5)
        for future in as_completed(jobs):
            candidate = jobs[future]
            try:
                value = future.result()
                if value:
                    result[candidate.stock_id] = value
            except Exception as error:
                Log(f"[Morning] news failed for {candidate.stock_id}: {error}", color=Color.YELLOW)
        try:
            result["market"] = market_job.result() or []
        except Exception as error:
            Log(f"[Morning] market news unavailable: {error}", color=Color.YELLOW)
            result["market"] = []
    return result


def _score_with_completeness_cap(score: float, complete: bool) -> float:
    """限制缺少完整資料的分數上限，避免成為最高分標的。"""
    return score if complete else min(score, Env.MORNING_INCOMPLETE_SCORE_CAP)


def _swing_min_score(market_bias: float) -> float:
    """依市場空方程度提高波段做多的最低分數。"""
    if market_bias <= -35:
        return max(Env.MORNING_MIN_SCORE, Env.MORNING_SWING_EXTREME_BEARISH_MIN_SCORE)
    if market_bias <= -10:
        return max(Env.MORNING_MIN_SCORE, Env.MORNING_SWING_BEARISH_MIN_SCORE)
    return Env.MORNING_MIN_SCORE


def _institutional_summary(data: InstitutionalData, feature: TechnicalFeatures) -> Tuple[str, str]:
    """濃縮成適合 Flex 單行顯示的籌碼結論與色彩方向。"""
    agencies = (
        ("外資", data.foreign_streak, data.foreign_1d, data.foreign_5d, 1.0),
        ("投信", data.trust_streak, data.trust_1d, data.trust_5d, 1.25),
        ("自營", data.dealer_streak, data.dealer_1d, data.dealer_5d, .5),
    )
    one_day = sum(row[2] * row[4] for row in agencies)
    five_day = sum(row[3] * row[4] for row in agencies)

    # 最新一天與五日方向相反時，反轉訊號優先於所有其他資訊。
    reversals = [row for row in agencies if row[2] * row[3] < 0]
    if five_day > 0 > one_day:
        actor = max(reversals or agencies, key=lambda row: abs(row[2] * row[4]))
        return f"轉弱｜{actor[0]}單日轉賣", "BEARISH"
    if five_day < 0 < one_day:
        actor = max(reversals or agencies, key=lambda row: abs(row[2] * row[4]))
        return f"轉強｜{actor[0]}單日轉買", "BULLISH"

    streaks = [row for row in agencies if abs(row[1]) >= 2]
    if streaks:
        actor = max(streaks, key=lambda row: abs(row[1]) * row[4])
        action = "連買" if actor[1] > 0 else "連賣"
        tone = "BULLISH" if actor[1] > 0 else "BEARISH"
        conclusion = "偏多" if tone == "BULLISH" else "偏空"
        return f"{conclusion}｜{actor[0]}{action}{abs(actor[1])}日", tone

    ratio = institutional_flow_ratio(data, feature)
    if ratio >= .005:
        conclusion, tone = "偏多", "BULLISH"
    elif ratio <= -.005:
        conclusion, tone = "偏空", "BEARISH"
    else:
        conclusion, tone = "中性", "NEUTRAL"
    actor = max(agencies, key=lambda row: abs(row[3] * row[4]))
    action = "主買" if actor[3] > 0 else "主賣" if actor[3] < 0 else "觀望"
    return f"{conclusion}｜{actor[0]}{action}", tone


def _select_deep_candidates(
    candidates: List[StockCandidate],
    features: Dict[str, TechnicalFeatures],
    market_returns: Dict[str, float],
    bias: float,
    limit: int,
) -> List[StockCandidate]:
    """合併獨立的當沖與波段排名，避免單一策略排擠另一策略。"""
    values = sorted(item.trade_value for item in candidates)
    intraday_ranked: List[Tuple[float, StockCandidate]] = []
    swing_ranked: List[Tuple[float, StockCandidate]] = []
    for item in candidates:
        current = features.get(item.stock_id)
        if current is None:
            continue
        percentile = (
            sum(value <= item.trade_value for value in values) - 1
        ) / max(1, len(values) - 1)
        long_score, short_score, _, _ = intraday_scores(current, percentile, None, bias)
        swing_value, _ = swing_score(current, market_returns.get(item.market), None)
        intraday_ranked.append((max(long_score, short_score), item))
        swing_ranked.append((swing_value, item))

    intraday_top = sorted(intraday_ranked, key=lambda row: row[0], reverse=True)[:limit]
    swing_top = sorted(swing_ranked, key=lambda row: row[0], reverse=True)[:limit]
    merged: Dict[str, Tuple[float, StockCandidate]] = {}
    for score, item in intraday_top + swing_top:
        previous = merged.get(item.stock_id)
        if previous is None or score > previous[0]:
            merged[item.stock_id] = (score, item)
    return [
        item for _, item in sorted(merged.values(), key=lambda row: row[0], reverse=True)
    ]


def _build_recommendations(
    candidates: List[StockCandidate], features: Dict[str, TechnicalFeatures],
    flags: Dict[str, StockRiskFlag], institutions: Dict[str, InstitutionalData],
    market_returns: Dict[str, float], bias: float,
) -> Tuple[List[IntradayRecommendation], List[SwingRecommendation]]:
    """依候選股特徵、風險與籌碼建立當沖及波段建議。"""
    by_id = {item.stock_id: item for item in candidates}
    trade_values = sorted(item.trade_value for item in candidates)
    intraday_rows, swing_rows = [], []
    for code, feature in features.items():
        candidate = by_id[code]
        flag = flags.get(code, StockRiskFlag(stock_id=code))
        if flag.disposal or flag.altered_trading:
            continue
        liquidity = (sum(value <= candidate.trade_value for value in trade_values) - 1) / max(1, len(trade_values) - 1)
        institution = institutions.get(code)
        has_institution = institution is not None and institution.available
        long_score, short_score, long_reasons, short_reasons = intraday_scores(
            feature, liquidity, institution, bias
        )
        direction = "LONG" if long_score > short_score else "SHORT"
        selected = _score_with_completeness_cap(
            long_score if direction == "LONG" else short_score,
            has_institution,
        )
        eligible = flag.can_day_trade if direction == "LONG" else flag.can_short_day_trade
        if (
            feature.avg_trade_value_20d >= Env.MORNING_MIN_AVG_TRADE_VALUE
            and feature.close <= Env.MORNING_INTRADAY_MAX_CLOSE
            and not flag.warning and eligible and abs(long_score - short_score) >= 8
            and selected >= Env.MORNING_MIN_SCORE
        ):
            entry, stop, tp1, tp2 = trade_plan(feature, direction)
            if reward_risk_ratio(entry, stop, tp1, direction) > Env.MORNING_MIN_TP1_REWARD_RISK:
                intraday_rows.append(IntradayRecommendation(
                    stock_id=code, stock_name=candidate.stock_name, direction=direction,
                    score=round(selected, 1), previous_close=feature.close,
                    entry=entry, stop=stop, tp1=tp1, tp2=tp2,
                    atr_pct=feature.atr_pct, volume_ratio=feature.volume_ratio,
                    reasons=long_reasons if direction == "LONG" else short_reasons,
                ))
        swing_value, swing_reasons = swing_score(
            feature, market_returns.get(candidate.market), institution
        )
        swing_value = _score_with_completeness_cap(
            swing_value,
            has_institution and market_returns.get(candidate.market) is not None,
        )
        if swing_value >= _swing_min_score(bias):
            if bias <= -10:
                swing_reasons = ["逆勢多方，市場環境偏空", *swing_reasons][:3]
            institution_text = "資料暫缺"
            institution_tone = "NEUTRAL"
            inst = institution
            if inst:
                institution_text, institution_tone = _institutional_summary(inst, feature)
            swing_rows.append(SwingRecommendation(
                stock_id=code, stock_name=candidate.stock_name, score=round(swing_value, 1),
                previous_close=feature.close, trend="多頭排列" if feature.close > feature.ma20 > feature.ma60 else "趨勢轉強",
                support=swing_support(feature),
                resistance=round_to_valid_tick(feature.high_20d, "up"),
                return_20d=feature.return_20d, volume_ratio=feature.volume_ratio,
                institutional=institution_text, reasons=swing_reasons,
                institutional_tone=institution_tone,
            ))
    intraday_rows.sort(key=lambda item: item.score, reverse=True)
    swing_rows.sort(key=lambda item: item.score, reverse=True)
    return intraday_rows[: Env.MORNING_INTRADAY_N], swing_rows[: Env.MORNING_SWING_N]


async def run_morning_pipeline(push: bool = True, force: bool = False) -> Optional[MorningReport]:
    """執行一次盤前流程，force 模式會略過休市與重複推播檢查。"""
    started = time.monotonic()
    now = TaiwanTime.now()
    report_date = now.date().isoformat()
    Log("[Morning] Pipeline started", color=Color.BLUE)
    if not force and not await asyncio.to_thread(twse.is_trading_day, now.date()):
        Log("[Morning] Non-trading day; no push", color=Color.YELLOW)
        return None
    if push and not force and cache.was_pushed(report_date):
        Log("[Morning] Already pushed today; skipped", color=Color.YELLOW)
        return None
    Log("[Morning] Trading date confirmed", color=Color.GREEN)

    global_task = asyncio.to_thread(_safe, "global market", yahoo.fetch_global_market, {})
    tx_task = asyncio.to_thread(
        _safe, "TX night", lambda: taifex.fetch_tx_night(report_date), None
    )
    candidate_task = asyncio.to_thread(_fetch_candidates)
    global_market, tx_night, (twse_rows, tpex_rows) = await asyncio.gather(global_task, tx_task, candidate_task)
    Log(f"[Morning] TWSE stocks loaded: {len(twse_rows)}", color=Color.GREEN)
    Log(f"[Morning] TPEx stocks loaded: {len(tpex_rows)}", color=Color.GREEN)
    if not twse_rows and not tpex_rows:
        Log("Morning Pipeline aborted: candidate universe unavailable", color=Color.RED)
        return None
    twse_dates = {item.date for item in twse_rows}
    tpex_dates = {item.date for item in tpex_rows}
    if twse_dates and tpex_dates and max(twse_dates) != max(tpex_dates):
        Log(
            f"[Morning] Source date mismatch: TWSE={max(twse_dates)}, TPEx={max(tpex_dates)}; using latest common/older complete date",
            color=Color.YELLOW,
        )
    candidates = await asyncio.to_thread(merge_candidates, twse_rows, tpex_rows, Env.MORNING_TOP_N)
    if not candidates:
        Log("Morning Pipeline aborted: no ordinary-share candidates", color=Color.RED)
        return None
    data_date = candidates[0].date
    if tx_night is not None and not taifex.is_current_for_stock_date(tx_night, data_date):
        Log(
            f"[Morning] TX night stale: source={tx_night.get('date')}, stock_data={data_date}; excluded",
            color=Color.YELLOW,
        )
        tx_night = None
    Log(f"[Morning] Candidate Top{len(candidates)} ready ({data_date})", color=Color.GREEN)

    histories = await asyncio.to_thread(yahoo.fetch_histories, candidates)
    features = {code: value for code, frame in histories.items() if (value := calculate_features(code, frame)) is not None}
    Log(f"[Morning] Historical data ready: {len(features)}/{len(candidates)}", color=Color.GREEN)
    if not features:
        Log("Morning Pipeline aborted: historical data unavailable", color=Color.RED)
        return None
    Log("[Morning] Technical scoring complete", color=Color.GREEN)

    bias = market_score(global_market, tx_night)
    market_returns = await asyncio.to_thread(_safe, "market returns", yahoo.fetch_market_returns, {})
    # 先獨立排列兩種策略，再抓取成本較高的深度資料。
    deep = _select_deep_candidates(
        candidates, features, market_returns, bias, Env.MORNING_DEEP_N
    )
    Log(
        f"[Morning] Deep analysis union: {len(deep)} "
        f"(intraday Top{Env.MORNING_DEEP_N} + swing Top{Env.MORNING_DEEP_N})",
        color=Color.GREEN,
    )
    institutions = await asyncio.to_thread(_fetch_institutions, deep, data_date)

    risk_results = await asyncio.gather(
        asyncio.to_thread(_safe, "TWSE eligibility", twse.fetch_day_trade_flags, {}),
        asyncio.to_thread(_safe, "TPEx eligibility", tpex.fetch_day_trade_flags, {}),
        asyncio.to_thread(_safe, "TWSE risk", twse.fetch_risk_flags, {}),
        asyncio.to_thread(_safe, "TPEx risk", tpex.fetch_risk_flags, {}),
    )
    flags = merge_flags(*risk_results)
    intraday_recs, swing_recs = _build_recommendations(
        deep, {item.stock_id: features[item.stock_id] for item in deep}, flags,
        institutions, market_returns, bias,
    )
    Log(f"[Morning] Intraday recommendations: {len(intraday_recs)}", color=Color.GREEN)
    Log(f"[Morning] Swing recommendations: {len(swing_recs)}", color=Color.GREEN)
    selected_ids = {item.stock_id for item in [*intraday_recs, *swing_recs]}
    selected_candidates = [item for item in deep if item.stock_id in selected_ids]
    report_news = await asyncio.to_thread(_fetch_selected_news, selected_candidates)
    Log(f"[Morning] Selected-stock news ready: {len(selected_candidates)} stocks", color=Color.GREEN)
    market_regime = regime(bias)
    summary = await asyncio.to_thread(
        generate_summary, global_market, tx_night, market_regime,
        intraday_recs, swing_recs, report_news,
    )
    Log("[Morning] OpenAI summary complete (or deterministic fallback)", color=Color.GREEN)
    for item in intraday_recs:
        item.ai_comment = summary.get("intraday_comments", {}).get(item.stock_id, "")
    for item in swing_recs:
        item.ai_comment = summary.get("swing_comments", {}).get(item.stock_id, "")
    report = MorningReport(
        report_date=report_date, data_date=data_date, market_score=bias,
        market_regime=market_regime, global_market=global_market, tx_night=tx_night,
        market_summary=summary["market_summary"], market_risk=summary["market_risk"],
        focus=summary.get("focus", []), intraday=intraday_recs, swing=swing_recs, news=report_news,
    )
    flex_payloads = build_flex_payloads(report)
    flex_kb = sum(validate_flex_payload_size(payload) for payload in flex_payloads) / 1024
    Log(f"[Morning] Flex built: {len(flex_payloads)} messages / {flex_kb:.1f} KB", color=Color.GREEN)
    cache.atomic_write_json(cache.OUTPUT_DIR / f"morning_report_{report_date}.json", report.to_dict())
    cache.atomic_write_json(cache.OUTPUT_DIR / f"morning_flex_{report_date}.json", {"messages": flex_payloads})
    names = ["market"]
    if intraday_recs:
        names.append("intraday")
    if swing_recs:
        names.append("swing")
    for name, payload in zip(names, flex_payloads):
        cache.atomic_write_json(cache.OUTPUT_DIR / f"morning_flex_{name}_{report_date}.json", payload)
    if push:
        if not Env.MORNING_PUSH_ENABLED:
            Log("[Morning] MORNING_PUSH_ENABLED=false; multicast skipped", color=Color.YELLOW)
        else:
            alt_texts = [f"FinGPT {now:%m/%d} 台股盤前情報"]
            if intraday_recs:
                alt_texts.append(f"FinGPT {now:%m/%d} 當沖精選")
            if swing_recs:
                alt_texts.append(f"FinGPT {now:%m/%d} 波段精選")
            recipient_count = await asyncio.to_thread(multicast_morning_report, flex_payloads, alt_texts)
            if recipient_count:
                cache.mark_pushed(report_date)
                Log(f"[Morning] LINE multicast success: {recipient_count} recipients", color=Color.GREEN)
            else:
                Log("[Morning] LINE multicast skipped: whitelist is empty", color=Color.YELLOW)
    Log(f"[Morning] Pipeline finished in {time.monotonic() - started:.1f}s", color=Color.GREEN)
    return report
