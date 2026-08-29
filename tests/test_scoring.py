import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import unittest
from engine.scoring import evaluate, _safe, _clamp, _bull_score, _bear_score, _judge_verdict


class TestSafeFunction(unittest.TestCase):
    def test_none_returns_default(self):
        self.assertEqual(_safe(None), 0)
        self.assertEqual(_safe(None, 5), 5)

    def test_valid_number(self):
        self.assertEqual(_safe(42), 42)
        self.assertAlmostEqual(_safe(3.14), 3.14)

    def test_string_number(self):
        self.assertEqual(_safe("42"), 42)

    def test_invalid_string(self):
        self.assertEqual(_safe("abc"), 0)
        self.assertEqual(_safe("abc", -1), -1)


class TestClamp(unittest.TestCase):
    def test_within_range(self):
        self.assertEqual(_clamp(5, 0, 10), 5)

    def test_below_min(self):
        self.assertEqual(_clamp(-5, 0, 10), 0)

    def test_above_max(self):
        self.assertEqual(_clamp(15, 0, 10), 10)


class TestBullScore(unittest.TestCase):
    def test_strong_bull_case(self):
        evidence = {
            "technicals": {"rvol": 2.5, "trend": "up", "price_vs_sma_pct": 5, "day_range_position_pct": 80, "window_return_pct": 12},
            "analyst": {"upside_pct": 25, "buy_pct": 70},
            "news": {"positive": 5, "negative": 1},
            "range_52w": {"position_pct": 85},
        }
        score, reasons = _bull_score(evidence)
        self.assertGreater(score, 50)
        self.assertGreater(len(reasons), 0)

    def test_weak_bull_case(self):
        evidence = {
            "technicals": {"rvol": 0.5, "trend": "down", "price_vs_sma_pct": -5, "day_range_position_pct": 20, "window_return_pct": -10},
            "analyst": {"upside_pct": -5, "buy_pct": 10},
            "news": {"positive": 0, "negative": 5},
            "range_52w": {"position_pct": 10},
        }
        score, reasons = _bull_score(evidence)
        self.assertLess(score, 20)

    def test_empty_evidence(self):
        evidence = {
            "technicals": {},
            "analyst": {},
            "news": {},
            "range_52w": {},
        }
        score, _ = _bull_score(evidence)
        self.assertLessEqual(score, 10)


class TestBearScore(unittest.TestCase):
    def test_strong_bear_case(self):
        evidence = {
            "technicals": {"rvol": 0.4, "trend": "down", "price_vs_sma_pct": -8, "day_range_position_pct": 15, "window_return_pct": -15},
            "analyst": {"upside_pct": -10, "sell_pct": 40},
            "news": {"positive": 0, "negative": 5},
            "range_52w": {"position_pct": 10, "pct_from_high": -30},
        }
        score, reasons = _bear_score(evidence)
        self.assertGreater(score, 50)
        self.assertGreater(len(reasons), 0)

    def test_weak_bear_case(self):
        evidence = {
            "technicals": {"rvol": 2.5, "trend": "up", "price_vs_sma_pct": 5, "day_range_position_pct": 80, "window_return_pct": 10},
            "analyst": {"upside_pct": 25, "sell_pct": 5},
            "news": {"positive": 5, "negative": 0},
            "range_52w": {"position_pct": 90, "pct_from_high": -2},
        }
        score, _ = _bear_score(evidence)
        self.assertLess(score, 20)


class TestJudgeVerdict(unittest.TestCase):
    def test_buy_verdict(self):
        evidence = {
            "range_52w": {"position_pct": 70},
            "technicals": {"rvol": 3.5},
        }
        verdict = _judge_verdict(60, 10, evidence)
        self.assertEqual(verdict["verdict"], "BUY")
        self.assertGreaterEqual(verdict["confidence"], 7)

    def test_avoid_verdict(self):
        evidence = {
            "range_52w": {"position_pct": 20},
            "technicals": {"rvol": 0.5},
        }
        verdict = _judge_verdict(5, 40, evidence)
        self.assertEqual(verdict["verdict"], "AVOID")
        self.assertLessEqual(verdict["confidence"], 6)

    def test_watch_verdict(self):
        evidence = {
            "range_52w": {"position_pct": 50},
            "technicals": {"rvol": 1.0},
        }
        verdict = _judge_verdict(30, 25, evidence)
        self.assertEqual(verdict["verdict"], "WATCH")


class TestConfidenceCalculation(unittest.TestCase):
    def test_confidence_in_range(self):
        evidence = {
            "range_52w": {"position_pct": 50},
            "technicals": {"rvol": 1.0},
        }
        for bull, bear in [(50, 30), (10, 50), (30, 30), (80, 5), (5, 80)]:
            verdict = _judge_verdict(bull, bear, evidence)
            self.assertGreaterEqual(verdict["confidence"], 1)
            self.assertLessEqual(verdict["confidence"], 10)

    def test_buy_confidence_floor(self):
        evidence = {"range_52w": {"position_pct": 70}, "technicals": {"rvol": 3.0}}
        verdict = _judge_verdict(50, 10, evidence)
        if verdict["verdict"] == "BUY":
            self.assertGreaterEqual(verdict["confidence"], 7)


class TestEvaluate(unittest.TestCase):
    def test_returns_correct_structure(self):
        evidence = {
            "technicals": {"rvol": 1.5, "trend": "up", "price_vs_sma_pct": 3, "day_range_position_pct": 60, "window_return_pct": 5},
            "analyst": {"upside_pct": 15, "buy_pct": 60, "consensus": "buy", "num_analysts": 15, "target_mean": 4000, "target_low": 3500, "target_high": 4500, "hold_pct": 30, "sell_pct": 10},
            "news": {"total": 5, "positive": 3, "negative": 1, "neutral": 1, "recent": []},
            "range_52w": {"high": 4500, "low": 3000, "pct_from_high": -10, "position_pct": 67},
            "price": {"live": 4000, "day_open": 3980, "high": 4020, "low": 3960, "prev_close": 3970, "day_change_pct": 0.75, "volume": 2000000},
        }
        result = evaluate(evidence)
        self.assertIn("scores", result)
        self.assertIn("verdict", result)
        self.assertIn("bull", result["scores"])
        self.assertIn("bear", result["scores"])
        self.assertIn("verdict", result["verdict"])
        self.assertIn("confidence", result["verdict"])
        self.assertIn("rationale", result["verdict"])


if __name__ == "__main__":
    unittest.main()
