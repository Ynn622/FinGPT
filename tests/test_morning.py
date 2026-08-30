import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
from linebot.v3.messaging import FlexContainer

from services.morning import cache
from services.morning import subscribers
from services.morning.flex_builder import build_flex_payloads, validate_flex_payload_size
from services.morning.line_broadcast import multicast_morning_report
from services.morning.report_ai import _comment_repeats_reasons, _sanitize_stock_comments
from services.morning.models import (
    InstitutionalData, IntradayRecommendation, MarketSnapshot, MorningReport, StockCandidate,
    SwingRecommendation, TechnicalFeatures,
)
from services.morning.risk import (
    daily_price_limits, reward_risk_ratio, round_to_valid_tick, swing_support, trade_plan,
)
from services.morning.scanner import merge_candidates
from services.morning.scoring import intraday_scores
from services.morning.market_regime import market_score, regime
from services.morning.utils import normalize_stock_code, weighted_score
from crawler.taifex import (
    fetch_tx_night,
    fetch_tx_night_from_openapi,
    fetch_tx_night_history,
    is_current_for_stock_date,
    parse_tx_night_html,
)
from crawler.twse import is_trading_day
from services.morning.backtest import _next_session_signal, evaluate, optimize_weights, score_frame
from services.morning.pipeline import (
    _fetch_selected_news, _institutional_summary, _score_with_completeness_cap,
    _select_deep_candidates, _swing_min_score,
    run_morning_pipeline,
)
from util.technical_indicators import (
    atr_wilder, calculate_features, close_location_value, get_technical_indicators,
)
from util.taiwan_market import get_tick_size


def feature(**changes):
    """建立可依參數覆寫的標準技術特徵測試資料。"""
    values = dict(
        stock_id="2330", date="2026-08-21", close=100, previous_high=101,
        previous_low=98, ma5=99, ma10=98, ma20=95, ma60=90,
        ema5=99, ema10=98, ema20=96, macd=2, macd_signal=1,
        macd_histogram=1, rsi14=60, roc5=3, roc20=10, atr14=3,
        atr_pct=.03, volume_ma5=2_000_000, volume_ma20=1_000_000,
        volume_ratio=2, clv=.85, return_1d=2, return_5d=4,
        return_20d=10, high_20d=102, low_20d=85, ma20_slope=.2,
        avg_trade_value_20d=200_000_000,
    )
    values.update(changes)
    return TechnicalFeatures(**values)


class TickTests(unittest.TestCase):
    def test_tick_bands(self):
        """驗證各價格級距使用正確的台股跳動單位。"""
        expected = [(9.5, .01), (20, .05), (70, .1), (200, .5), (800, 1), (1200, 5)]
        self.assertEqual([(value, get_tick_size(value)) for value, _ in expected], expected)

    def test_trade_plan_uses_valid_ticks(self):
        """驗證多空交易計畫的所有價位皆符合跳動單位。"""
        for direction in ("LONG", "SHORT"):
            prices = trade_plan(feature(), direction)
            for price in prices:
                self.assertEqual(price, round_to_valid_tick(price))
        entry, stop, tp1, tp2 = trade_plan(feature(), "LONG")
        self.assertLess(stop, entry); self.assertGreater(tp1, entry); self.assertGreater(tp2, tp1)

    def test_daily_price_limits_follow_twse_rounding_example(self):
        """驗證漲停向下、跌停向上取合法 Tick，且不超過百分之十。"""
        self.assertEqual(daily_price_limits(40.60), (36.55, 44.65))
        lower, upper = daily_price_limits(49.9)
        self.assertEqual((lower, upper), (44.95, 54.8))
        self.assertGreaterEqual(lower, 49.9 * .9)
        self.assertLessEqual(upper, 49.9 * 1.1)

    def test_trade_plan_prices_are_clamped_to_daily_limits(self):
        """驗證極端前高低與 ATR 不會讓觸發、停損或目標價超出漲跌停。"""
        bullish = feature(close=100, previous_high=120, previous_low=95, atr14=30)
        bearish = feature(close=100, previous_high=105, previous_low=80, atr14=30)
        for current, direction in ((bullish, "LONG"), (bearish, "SHORT")):
            lower, upper = daily_price_limits(current.close)
            prices = trade_plan(current, direction)
            self.assertTrue(all(lower <= price <= upper for price in prices))
            self.assertTrue(all(price == round_to_valid_tick(price) for price in prices))

    def test_tp1_reward_risk_calculation_supports_strict_threshold(self):
        """驗證多空 TP1 可用實際價位套用嚴格大於 1.1 的推薦門檻。"""
        self.assertGreater(reward_risk_ratio(100, 98, 103, "LONG"), 1)
        self.assertEqual(reward_risk_ratio(100, 98, 102, "LONG"), 1)
        self.assertGreater(reward_risk_ratio(100, 98, 102.5, "LONG"), 1.1)
        self.assertGreater(reward_risk_ratio(100, 102, 97, "SHORT"), 1)
        self.assertEqual(reward_risk_ratio(100, 102, 98, "SHORT"), 1)
        self.assertEqual(reward_risk_ratio(100, 100, 103, "LONG"), 0)

    def test_swing_support_uses_nearest_moving_average_below_close(self):
        """驗證波段支撐採用收盤價下方最近的移動平均線。"""
        self.assertEqual(swing_support(feature()), 99.0)
        self.assertEqual(swing_support(feature(ma5=101, ma10=97.8, ma20=95)), 97.8)

    def test_swing_support_falls_back_to_one_atr_when_averages_are_above(self):
        """驗證均線皆高於收盤價時改用一倍 ATR 支撐。"""
        self.assertEqual(swing_support(feature(ma5=101, ma10=102, ma20=103, atr14=3)), 97.0)


class IndicatorTests(unittest.TestCase):
    def test_atr_constant_range(self):
        """驗證固定高低區間下的 Wilder ATR 計算結果。"""
        frame = pd.DataFrame({"High": [11.] * 20, "Low": [9.] * 20, "Close": [10.] * 20})
        self.assertAlmostEqual(atr_wilder(frame).iloc[-1], 2.0)

    def test_clv(self):
        """驗證收盤位置值在高點、低點與無區間時的結果。"""
        self.assertEqual(close_location_value(10, 10, 5), 1)
        self.assertEqual(close_location_value(5, 10, 5), 0)
        self.assertEqual(close_location_value(5, 5, 5), .5)

    def test_shared_sdf_indicators_are_generated_without_mutating_input(self):
        """驗證共用工具可動態產生 SDF 指標且不修改原始欄位。"""
        index = pd.date_range("2026-01-01", periods=30, freq="B")
        source = pd.DataFrame({
            "Open": np.arange(30) + 99,
            "High": np.arange(30) + 102,
            "Low": np.arange(30) + 98,
            "Close": np.arange(30) + 100,
            "Volume": np.arange(30) + 1_000,
        }, index=index)
        original_columns = source.columns.tolist()
        result = get_technical_indicators(source, ["close_5_sma", "rsi_14", "atr_14"])
        self.assertEqual(source.columns.tolist(), original_columns)
        self.assertEqual(result.columns.tolist(), ["SMA_5", "RSI_14", "ATR_14"])
        self.assertAlmostEqual(result.iloc[-1]["SMA_5"], 127.0)

    def test_morning_features_use_sdf_and_preserve_no_lookahead_volume_ratio(self):
        """驗證晨報特徵由 SDF 計算，量比仍只使用前 20 日作分母。"""
        index = pd.date_range("2026-01-01", periods=80, freq="B")
        close = pd.Series(100 + np.arange(80) * .3 + np.sin(np.arange(80)), index=index)
        volume = pd.Series(1_000 + np.arange(80) * 10, index=index)
        frame = pd.DataFrame({
            "Open": close - .5, "High": close + 2, "Low": close - 2,
            "Close": close, "Volume": volume,
        })
        result = calculate_features("2330", frame)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.ma5, close.rolling(5).mean().iloc[-1])
        expected_ratio = volume.iloc[-1] / volume.iloc[-21:-1].mean()
        self.assertAlmostEqual(result.volume_ratio, expected_ratio)
        self.assertTrue(np.isfinite(result.rsi14))


class ScoreTests(unittest.TestCase):
    def test_market_score_includes_sox_with_rebalanced_weights(self):
        """驗證市場分數納入費半並依可用因子重新配置權重。"""
        market = {
            "nasdaq": MarketSnapshot("nasdaq", "^IXIC", 102, 100, 2, 2),
            "sox": MarketSnapshot("sox", "^SOX", 98, 100, -2, -2),
            "tsm": MarketSnapshot("tsm", "TSM", 101, 100, 1, 1),
            "usdtwd": MarketSnapshot("usdtwd", "TWD=X", 30.15, 30, .15, .5),
        }
        tx = {"change_pct": 1}
        self.assertEqual(market_score(market, tx), 12.5)

    def test_extreme_market_regime_labels(self):
        """驗證極端市場分數對應正確的多空標籤。"""
        self.assertEqual(regime(35), "極多")
        self.assertEqual(regime(-35), "極空")

    def test_weighted_missing_is_renormalized(self):
        """驗證缺少評分因子時會依剩餘權重重新正規化。"""
        score = weighted_score({"a": 20, "b": None}, {"a": 20, "b": 80})
        self.assertEqual(score, 100)

    def test_intraday_long_and_short(self):
        """驗證多方與空方技術特徵分別產生較高方向分數。"""
        long, short, _, _ = intraday_scores(feature(), 1)
        self.assertGreater(long, short)
        bearish = feature(close=90, previous_high=94, previous_low=89, ma5=92, ma20=95,
                          macd_histogram=-1, roc5=-3, roc20=-8, rsi14=40, clv=.1,
                          return_1d=-2, low_20d=88, high_20d=110)
        long, short, _, _ = intraday_scores(bearish, 1)
        self.assertGreater(short, long)

    def test_incomplete_scores_are_capped(self):
        """驗證資料不完整時評分不會超過設定上限。"""
        self.assertEqual(_score_with_completeness_cap(92, complete=False), 75)
        self.assertEqual(_score_with_completeness_cap(72, complete=False), 72)
        self.assertEqual(_score_with_completeness_cap(92, complete=True), 92)

    def test_bearish_market_raises_long_only_swing_threshold(self):
        """驗證偏空市場會提高波段做多的最低分數。"""
        self.assertEqual(_swing_min_score(0), 60)
        self.assertEqual(_swing_min_score(-10), 68)
        self.assertEqual(_swing_min_score(-35), 75)

    def test_deep_analysis_unions_independent_rankings(self):
        """驗證深度分析會合併當沖與波段的獨立排名。"""
        candidates = [
            StockCandidate("1111", "當沖股", "TWSE", "2026-08-21", 100, 1, 300),
            StockCandidate("2222", "波段股", "TWSE", "2026-08-21", 100, 1, 200),
        ]
        features = {"1111": feature(stock_id="1111"), "2222": feature(stock_id="2222")}

        def intraday(current, *_args):
            """回傳測試用的固定當沖分數。"""
            return ((90, 10, [], []) if current.stock_id == "1111" else (50, 10, [], []))

        def swing(current, *_args):
            """回傳測試用的固定波段分數。"""
            return ((95, []) if current.stock_id == "2222" else (40, []))

        with patch("services.morning.pipeline.intraday_scores", side_effect=intraday), \
             patch("services.morning.pipeline.swing_score", side_effect=swing):
            selected = _select_deep_candidates(candidates, features, {"TWSE": 0}, 0, 1)
        self.assertEqual({item.stock_id for item in selected}, {"1111", "2222"})

    def test_institutional_summary_separates_flows_and_flags_reversal(self):
        """驗證法人摘要分列三大法人並顯示單日反轉與相對量。"""
        data = InstitutionalData(
            "2330", foreign_1d=-100, foreign_5d=1_000,
            trust_1d=50, trust_5d=300, dealer_1d=-20, dealer_5d=-80,
            trust_streak=3,
        )
        summary, tone = _institutional_summary(data, feature(volume_ma20=1_000_000))
        self.assertEqual(summary, "轉弱｜外資單日轉賣")
        self.assertEqual(tone, "BEARISH")

    def test_institutional_summary_shows_only_strongest_streak(self):
        """驗證 Flex 摘要只保留一個最重要的連續籌碼訊號。"""
        data = InstitutionalData(
            "2330", foreign_1d=100, foreign_5d=500, trust_1d=80, trust_5d=300,
            foreign_streak=2, trust_streak=4,
        )
        summary, tone = _institutional_summary(data, feature())
        self.assertEqual(summary, "偏多｜投信連買4日")
        self.assertEqual(tone, "BULLISH")


class BacktestTests(unittest.TestCase):
    def test_signal_is_shifted_to_next_session(self):
        """驗證海外收盤訊號只會對齊至下一個台灣交易日。"""
        source = pd.Series([1.0, 2.0], index=pd.to_datetime(["2026-08-21", "2026-08-24"]))
        sessions = pd.to_datetime(["2026-08-21", "2026-08-24", "2026-08-25"])
        aligned = _next_session_signal(source, sessions)
        self.assertTrue(pd.isna(aligned.iloc[0]))
        self.assertEqual(aligned.iloc[1], 1.0)
        self.assertEqual(aligned.iloc[2], 2.0)

    def test_backtest_score_and_optimizer_use_training_data(self):
        """驗證回測評分與權重最佳化能辨識有效因子。"""
        index = pd.date_range("2025-01-01", periods=120, freq="B")
        signal = np.tile([-1.0, 1.0], 60)
        frame = pd.DataFrame({
            "nasdaq": signal * 2,
            "sox": -signal * 2,
            "twii_open_to_close_pct": signal,
        }, index=index)
        scores = score_frame(frame, {"nasdaq": 80, "sox": 20})
        metrics = evaluate(scores, frame["twii_open_to_close_pct"])
        self.assertEqual(metrics["direction_accuracy"], 1.0)
        suggested = optimize_weights(frame, ["nasdaq", "sox"], step=10)
        self.assertGreater(suggested["nasdaq"], suggested["sox"])


class CandidateTests(unittest.TestCase):
    def test_merge_and_etf_filter(self):
        """驗證上市櫃候選股合併後會排除非普通股商品。"""
        twse = [StockCandidate("2330", "台積電", "TWSE", "2026-08-21", 100, 1, 300)]
        tpex = [
            StockCandidate("6488", "環球晶", "TPEX", "2026-08-21", 80, 1, 200),
            StockCandidate("00679B", "ETF", "TPEX", "2026-08-21", 20, 1, 999),
        ]
        result = merge_candidates(twse, tpex, 100, {"2330", "6488"})
        self.assertEqual([item.stock_id for item in result], ["2330", "6488"])
        self.assertEqual(normalize_stock_code("6488.TWO"), "6488")

    def test_news_is_fetched_only_for_final_selected_stocks(self):
        """驗證新聞階段只處理傳入的最終入選股票並抓取市場新聞。"""
        selected = [
            StockCandidate("2330", "台積電", "TWSE", "2026-08-28", 100, 1, 300),
            StockCandidate("6488", "環球晶", "TPEX", "2026-08-28", 80, 1, 200),
        ]
        with patch("services.morning.pipeline.news.fetch_stock", side_effect=lambda name, _limit: [name]) as stock_news, \
             patch("services.morning.pipeline.news.fetch_market", return_value=["市場"]) as market_news:
            result = _fetch_selected_news(selected)
        self.assertEqual(stock_news.call_count, 2)
        market_news.assert_called_once_with(5)
        self.assertEqual(set(result), {"2330", "6488", "market"})


class FlexTests(unittest.TestCase):
    def test_carousel_limits(self):
        """驗證 Flex 輪播內容、樣式與大小符合 LINE 限制。"""
        long_recommendation = IntradayRecommendation(
            "2330", "台積電", "LONG", 80, 100, 102, 100, 105, 106,
            .03, 2, ["量價轉強"], ai_comment="先進製程需求提供催化，仍須留意短線追價風險。",
        )
        short_recommendation = IntradayRecommendation(
            "2303", "聯電", "SHORT", 75, 50, 49, 50, 47, 46,
            .02, 1.5, ["動能轉弱"],
        )
        market = {
            "nasdaq": MarketSnapshot("nasdaq", "^IXIC", 20000, 19800, 200, 1.01),
            "sp500": MarketSnapshot("sp500", "^GSPC", 5000, 5010, -10, -.2),
            "sox": MarketSnapshot("sox", "^SOX", 7000, 6900, 100, 1.45),
            "tsm": MarketSnapshot("tsm", "TSM", 250, 248, 2, .81),
            "usdtwd": MarketSnapshot("usdtwd", "TWD=X", 31.815, 31.80, .015, .05),
        }
        report = MorningReport(
            "2026-08-24", "2026-08-21", 20, "偏多", market,
            {"close": 44532, "change": -208, "change_pct": -.46},
            "市場摘要", "風險", [], [long_recommendation, short_recommendation], [],
        )
        payloads = build_flex_payloads(report)
        self.assertEqual(payloads[0]["type"], "bubble")
        self.assertEqual(payloads[1]["type"], "carousel")
        self.assertEqual(len(payloads), 2)
        market_json = json.dumps(payloads[0], ensure_ascii=False)
        self.assertIn("20,000.00", market_json)
        self.assertIn("（+200.00｜+1.01%）", market_json)
        self.assertNotIn("點｜", market_json)
        self.assertIn("31.82", market_json)
        self.assertIn("44,532", market_json)
        self.assertNotIn("44,532.00", market_json)
        self.assertIn("台指期夜盤", market_json)
        self.assertNotIn("TX 夜盤", market_json)
        self.assertIn('"text": "20,000.00", "wrap": true, "size": "sm", "color": "#DC2626"', market_json)
        self.assertIn("費城半導體", market_json)
        self.assertIn("台積電ADR", market_json)
        self.assertNotIn("費半指數", market_json)
        self.assertNotIn("TSM ADR", market_json)
        self.assertIn("7,000.00", market_json)
        self.assertEqual(payloads[0]["size"], "giga")
        self.assertIn("盤前預估", market_json)
        self.assertNotIn("07:00 盤前預估", market_json)
        self.assertNotIn("資料基準：2026-08-21 收盤", market_json)
        footer = payloads[0]["footer"]
        self.assertEqual(len(footer["contents"]), 2)
        self.assertEqual(footer["contents"][0]["type"], "separator")
        self.assertEqual(footer["contents"][1]["text"], "僅供研究與資訊參考，不構成投資建議。")
        self.assertNotIn("資料基準日", market_json)
        self.assertEqual(len(payloads[0]["header"]["contents"]), 1)
        self.assertIn("偏多", market_json)
        self.assertIn("（20分）", market_json)
        intraday = payloads[1]["contents"]
        self.assertEqual(len(intraday), 3)
        summary_json = json.dumps(intraday[0], ensure_ascii=False)
        self.assertIn("當沖 Top5 總表", summary_json)
        self.assertNotIn("操作提醒", summary_json)
        self.assertNotIn("未觸發不進場", summary_json)
        self.assertEqual(intraday[0]["footer"]["contents"][-1]["text"], report.disclaimer)
        self.assertIn("2026/08/24 當沖精選", summary_json)
        self.assertIn("$102", summary_json)
        self.assertIn("2330", summary_json)
        self.assertIn('"text": "2330"', summary_json)
        self.assertIn('"text": "台積電"', summary_json)
        self.assertIn('"text": "多"', summary_json)
        self.assertIn("2303", summary_json)
        self.assertIn('"text": "空"', summary_json)
        self.assertIn("#FEF2F2", summary_json)
        self.assertIn("#F0FDF4", summary_json)
        self.assertIn('"text": "做多"', json.dumps(intraday[1], ensure_ascii=False))
        self.assertIn("#DC2626", json.dumps(intraday[1], ensure_ascii=False))
        self.assertIn('"text": "做空"', json.dumps(intraday[2], ensure_ascii=False))
        self.assertIn("#15803D", json.dumps(intraday[2], ensure_ascii=False))
        detail_json = json.dumps(intraday[1], ensure_ascii=False)
        self.assertNotIn("footer", intraday[1])
        self.assertNotIn("footer", intraday[2])
        self.assertIn("TP1 / TP2", detail_json)
        self.assertIn('"height": "5px"', detail_json)
        self.assertIn('"text": "ATR"', detail_json)
        self.assertIn('"text": "昨/20日均量"', detail_json)
        self.assertNotIn('"text": "量比"', detail_json)
        self.assertIn("2.0 倍", detail_json)
        self.assertIn("AI 觀察", detail_json)
        self.assertIn("先進製程需求提供催化", detail_json)
        self.assertNotIn("• 先進製程需求提供催化", detail_json)
        self.assertIn('"backgroundColor": "#F5F3FF"', detail_json)
        self.assertIn('"borderColor": "#DDD6FE"', detail_json)
        self.assertIn('"color": "#6D28D9"', detail_json)
        self.assertNotIn("未觸發不進場", detail_json)
        score_badge = intraday[1]["header"]["contents"][-1]
        self.assertEqual(score_badge["backgroundColor"], "#F8FAFC")
        self.assertEqual(score_badge["contents"][0]["text"], "80分")
        for payload in payloads:
            self.assertLessEqual(validate_flex_payload_size(payload), 50 * 1024)
            self.assertIsNotNone(FlexContainer.from_dict(payload))

    def test_swing_summary_omits_price(self):
        """驗證波段總表不顯示前收價格。"""
        swing = SwingRecommendation(
            "2330", "台積電", 88, 100, "多頭排列", 95, 110,
            8, 1.5, "近5日外資+投信 +1,000張", ["收盤站上MA20"],
        )
        report = MorningReport(
            "2026-08-24", "2026-08-21", 0, "震盪中性", {}, None,
            "市場摘要", "風險", [], [], [swing], [],
        )
        payloads = build_flex_payloads(report)
        summary_json = json.dumps(payloads[1]["contents"][0], ensure_ascii=False)
        self.assertNotIn("閱讀提示", summary_json)
        self.assertNotIn("左右滑動", summary_json)
        self.assertEqual(payloads[1]["contents"][0]["footer"]["contents"][-1]["text"], report.disclaimer)
        self.assertNotIn("footer", payloads[1]["contents"][1])
        self.assertIn('"text": "2330"', summary_json)
        self.assertIn('"text": "台積電"', summary_json)
        self.assertIn('"text": "多"', summary_json)
        self.assertNotIn("$100", summary_json)


class AICommentTests(unittest.TestCase):
    def test_repeated_reason_is_detected(self):
        """驗證直接改寫量化理由的評論會被辨識為重複。"""
        self.assertTrue(_comment_repeats_reasons("收盤站上MA20，短線維持強勢。", ["收盤站上MA20"]))
        self.assertFalse(_comment_repeats_reasons("新產品量產提供催化，但仍須留意追價風險。", ["收盤站上MA20"]))

    def test_comments_require_stock_news_and_new_information(self):
        """驗證無個股新聞或重複理由時清空，新聞觀察則保留。"""
        recommendation = IntradayRecommendation(
            "2330", "台積電", "LONG", 80, 100, 102, 100, 105, 106,
            .03, 2, ["收盤站上MA20"],
        )
        repeated = {"intraday_comments": {"2330": "收盤站上MA20，走勢偏多。"}, "swing_comments": {}}
        cleaned = _sanitize_stock_comments(repeated, [recommendation], [], {"2330": [{"Title": "新聞"}]})
        self.assertEqual(cleaned["intraday_comments"]["2330"], "")

        distinct = {"intraday_comments": {"2330": "先進製程需求提供催化，但需留意追價風險。"}, "swing_comments": {}}
        cleaned = _sanitize_stock_comments(distinct, [recommendation], [], {"2330": [{"Title": "新聞"}]})
        self.assertNotEqual(cleaned["intraday_comments"]["2330"], "")

        no_news = {"intraday_comments": {"2330": "任何評論"}, "swing_comments": {}}
        cleaned = _sanitize_stock_comments(no_news, [recommendation], [], {"market": []})
        self.assertEqual(cleaned["intraday_comments"]["2330"], "")


class CalendarAndCacheTests(unittest.TestCase):
    def test_weekend_is_closed_without_network(self):
        """驗證週末可在不連網的情況下判定為休市。"""
        self.assertFalse(is_trading_day(date(2026, 8, 23)))

    def test_stale_tx_night_is_rejected(self):
        """驗證早於現貨資料日的台指期夜盤會被拒絕。"""
        self.assertFalse(is_current_for_stock_date({"date": "2026-08-21"}, "2026-08-24"))
        self.assertTrue(is_current_for_stock_date({"date": "2026-08-25"}, "2026-08-24"))

    def test_taifex_web_parser_uses_nearest_outight_month(self):
        """驗證期交所網頁解析會選擇最近的單式月份契約。"""
        html = """
        <table class="table_f"><tbody>
          <tr><td><div>TX</div></td><td><div>202609</div></td>
              <td>44658</td><td>45015</td><td>44270</td><td>44532</td>
              <td><span>▼-208</span></td><td><span>▼-0.46%</span></td><td>32394</td></tr>
          <tr><td>TX</td><td>202609/202610</td><td>1</td><td>2</td><td>1</td>
              <td>2</td><td>-</td><td>-</td><td>10</td></tr>
        </tbody></table>
        """
        result = parse_tx_night_html(html, "2026-08-25")
        self.assertEqual(result["contract"], "202609")
        self.assertEqual(result["close"], 44532)
        self.assertEqual(result["change_pct"], -.46)
        self.assertEqual(result["source"], "TAIFEX_WEB")

    def test_taifex_openapi_uses_official_json_endpoint(self):
        """驗證 OpenAPI 備援使用官方 JSON 網域並選擇 TX 夜盤近月。"""
        rows = [{
            "Date": "20260828", "Contract": "TX", "ContractMonth(Week)": "202609",
            "Open": "45000", "High": "45500", "Low": "44900", "Last": "45400",
            "Change": "400", "%": "0.89%", "Volume": "30000", "TradingSession": "盤後",
        }]
        with patch("crawler.taifex.get_json", return_value=rows) as getter:
            result = fetch_tx_night_from_openapi()
        self.assertEqual(getter.call_args.args[0], "https://openapi.taifex.com.tw/v1/DailyMarketReportFut")
        self.assertEqual(result["date"], "2026-08-28")
        self.assertEqual(result["close"], 45400)

    def test_taifex_uses_cached_value_when_both_live_sources_fail(self):
        """驗證即時來源都失敗時安全讀取最近成功快取。"""
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "tx.json"
            cached = {"date": "2026-08-28", "close": 45400, "source": "TAIFEX_WEB"}
            cache.atomic_write_json(cache_path, cached)
            with patch("crawler.taifex.TX_NIGHT_CACHE", cache_path), \
                 patch("crawler.taifex.fetch_tx_night_from_web", side_effect=ValueError("html")), \
                 patch("crawler.taifex.fetch_tx_night_from_openapi", side_effect=ValueError("json")):
                result = fetch_tx_night("2026-08-29")
        self.assertEqual(result["source"], "TAIFEX_CACHE")
        self.assertEqual(result["cached_source"], "TAIFEX_WEB")

    def test_taifex_default_date_uses_taiwan_time(self):
        """驗證未指定日期時統一由 TaiwanTime 提供台灣日期。"""
        with patch("crawler.taifex.TaiwanTime.string", return_value="2026-08-29") as taiwan_date, \
             patch("crawler.taifex.fetch_tx_night_from_web", return_value=None) as web, \
             patch("crawler.taifex.fetch_tx_night_from_openapi", return_value=None), \
             patch("crawler.taifex.read_json", return_value=None):
            self.assertIsNone(fetch_tx_night())
        taiwan_date.assert_called_once_with(time=False)
        web.assert_called_once_with("2026-08-29")

    def test_taifex_history_download_chunks_and_selects_front_month(self):
        """驗證歷史下載會跨月分批並只保留近月夜盤。"""
        csv_text = """交易日期,契約,到期月份(週別),開盤價,最高價,最低價,收盤價,漲跌價,漲跌%,成交量,結算價,未沖銷契約數,最後最佳買價,最後最佳賣價,歷史最高價,歷史最低價,是否因訊息面暫停交易,交易時段,價差對單式委託成交量
2025/07/01,TX,202507,22197,22593,22191,22353,209,0.94%,86050,-,-,-,-,-,-,,一般,
2025/07/01,TX,202507,22138,22160,22013,22160,16,0.07%,28118,-,-,-,-,-,-,,盤後,
2025/07/01,TX,202508,21951,21990,21851,21990,23,0.10%,396,-,-,-,-,-,-,,盤後,
"""
        response = unittest.mock.Mock()
        response.content = csv_text.encode("cp950")
        client = unittest.mock.Mock()
        client.post.return_value = response
        with patch("crawler.taifex.session", return_value=client):
            frame = fetch_tx_night_history("2025-07-01", "2025-08-05")
        self.assertEqual(client.post.call_count, 2)
        self.assertEqual(len(frame), 1)
        self.assertEqual(frame.iloc[0]["contract"], "202507")
        self.assertEqual(frame.iloc[0]["session"], "night")
        self.assertEqual(frame.iloc[0]["close"], 22160)

    def test_idempotency_and_force_semantics(self):
        """驗證本地推播狀態的冪等記錄與讀取。"""
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            with patch.object(cache, "PUSH_STATE", state):
                self.assertFalse(cache.was_pushed("2026-08-24"))
                cache.mark_pushed("2026-08-24")
                self.assertTrue(cache.was_pushed("2026-08-24"))
                # force 模式由流程略過此檢查，因此快取函式本身仍應回傳已推播。
                self.assertTrue(json.loads(state.read_text())["last_successful_push_date"] == "2026-08-24")


class PipelineIdempotencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_duplicate_push_stops_before_datasources(self):
        """驗證重複推播會在讀取外部資料前停止。"""
        with patch("services.morning.pipeline.twse.is_trading_day", return_value=True), \
             patch("services.morning.pipeline.cache.was_pushed", return_value=True), \
             patch("services.morning.pipeline._fetch_candidates") as fetch:
            result = await run_morning_pipeline(push=True, force=False)
            self.assertIsNone(result)
            fetch.assert_not_called()

    async def test_force_bypasses_duplicate_guard(self):
        """驗證 force 模式會略過重複推播保護。"""
        with patch("services.morning.pipeline.cache.was_pushed", return_value=True) as pushed, \
             patch("services.morning.pipeline._fetch_candidates", return_value=([], [])), \
             patch("services.morning.pipeline.yahoo.fetch_global_market", return_value={}), \
             patch("services.morning.pipeline.taifex.fetch_tx_night", return_value=None):
            result = await run_morning_pipeline(push=True, force=True)
            self.assertIsNone(result)
            pushed.assert_not_called()


class MorningSubscriberTests(unittest.TestCase):
    def test_subscribe_is_persistent_and_idempotent(self):
        """同一個 LINE user ID 重複訂閱時，白名單只保留一筆。"""
        with tempfile.TemporaryDirectory() as directory:
            whitelist = Path(directory) / "whitelist.json"
            with patch.object(subscribers, "MORNING_ALERT_WHITELIST", whitelist):
                self.assertTrue(subscribers.subscribe_morning_alert("U123"))
                self.assertFalse(subscribers.subscribe_morning_alert("U123"))
                self.assertEqual(subscribers.morning_alert_user_ids(), ["U123"])
                self.assertEqual(json.loads(whitelist.read_text())["user_ids"], ["U123"])

    def test_multicast_skips_empty_whitelist(self):
        """沒有訂閱者時不得呼叫 LINE API。"""
        payload = {
            "type": "bubble",
            "body": {"type": "box", "layout": "vertical", "contents": []},
        }
        with patch("services.morning.line_broadcast.Env.LINE_TOKEN", "token"), \
             patch("services.morning.line_broadcast.morning_alert_user_ids", return_value=[]), \
             patch("services.morning.line_broadcast.ApiClient") as api_client:
            count = multicast_morning_report([payload], ["盤前情報"])
        self.assertEqual(count, 0)
        api_client.assert_not_called()

    def test_multicast_batches_whitelisted_users(self):
        """白名單超過 LINE 單批上限時應拆成多次 multicast。"""
        payload = {
            "type": "bubble",
            "body": {"type": "box", "layout": "vertical", "contents": []},
        }
        recipients = [f"U{index:032d}" for index in range(501)]
        context = MagicMock()
        messaging_api = MagicMock()
        with patch("services.morning.line_broadcast.Env.LINE_TOKEN", "token"), \
             patch("services.morning.line_broadcast.morning_alert_user_ids", return_value=recipients), \
             patch("services.morning.line_broadcast.ApiClient", return_value=context), \
             patch("services.morning.line_broadcast.MessagingApi", return_value=messaging_api):
            count = multicast_morning_report([payload], ["盤前情報"])
        self.assertEqual(count, 501)
        self.assertEqual(messaging_api.multicast.call_count, 2)
        requests = [call.args[0] for call in messaging_api.multicast.call_args_list]
        self.assertEqual(len(requests[0].to), 500)
        self.assertEqual(len(requests[1].to), 1)


class MorningWebhookTests(unittest.IsolatedAsyncioTestCase):
    async def test_on_command_subscribes_and_does_not_call_ai(self):
        """訂閱指令應加入來源帳號、回覆確認，且不進入 AI 對話。"""
        from services.line_api import linebot

        request = AsyncMock()
        request.body.return_value = json.dumps({
            "events": [{
                "replyToken": "reply-token",
                "source": {"userId": "U123"},
                "message": {"text": " /morning-alert-on "},
            }],
        }).encode("utf-8")
        messaging_api = MagicMock()
        with patch("services.line_api.WebhookHandler") as handler, \
             patch("services.line_api.ApiClient"), \
             patch("services.line_api.MessagingApi", return_value=messaging_api), \
             patch("services.line_api.subscribe_morning_alert", return_value=True) as subscribe, \
             patch("services.line_api.send_reply_message") as reply, \
             patch("services.line_api.ask_AI_Agent", new_callable=AsyncMock) as ask_ai:
            result = await linebot(request, "valid-signature")

        self.assertEqual(result, "Morning Alert Enabled!")
        handler.return_value.handle.assert_called_once()
        subscribe.assert_called_once_with("U123")
        reply.assert_called_once_with(
            messaging_api,
            "reply-token",
            "早盤推播已開啟！之後將於交易日早盤收到通知。",
        )
        ask_ai.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
