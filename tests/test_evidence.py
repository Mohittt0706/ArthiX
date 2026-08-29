import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import unittest
from data.evidence import normalize_evidence


class TestEvidenceNormalization(unittest.TestCase):
    def test_full_evidence(self):
        raw = {
            "symbol": "TCS.NS",
            "name": "Tata Consultancy Services",
            "sector": "IT",
            "cap_segment": "large",
            "price": {"live": 3500, "day_open": 3480, "high": 3520, "low": 3460, "prev_close": 3470, "day_change_pct": 0.86, "volume": 1500000},
            "range_52w": {"high": 4000, "low": 3000, "pct_from_high": -12.5, "position_pct": 50},
            "technicals": {"rvol": 1.5, "price_vs_sma_pct": 2.5, "window_return_pct": 5.0, "swing_high": 3600, "swing_low": 3400, "day_range_position_pct": 60, "trend": "up"},
            "analyst": {"consensus": "buy", "num_analysts": 25, "buy_pct": 70, "hold_pct": 20, "sell_pct": 10, "target_mean": 4000, "target_low": 3500, "target_high": 4500, "upside_pct": 14.3},
            "news": {"total": 5, "positive": 3, "negative": 1, "neutral": 1, "recent": [{"title": "Test"}]},
            "data_gaps": [],
            "source": "demo",
        }
        result = normalize_evidence(raw)
        self.assertEqual(result["symbol"], "TCS.NS")
        self.assertEqual(result["price"]["live"], 3500)
        self.assertEqual(result["technicals"]["trend"], "up")
        self.assertEqual(len(result["data_gaps"]), 0)

    def test_partial_evidence_fills_gaps(self):
        raw = {
            "symbol": "INFY.NS",
            "price": {"live": 1500},
            "technicals": {"trend": "sideways"},
        }
        result = normalize_evidence(raw)
        self.assertIn("price.day_open", result["data_gaps"])
        self.assertIn("technicals.rvol", result["data_gaps"])
        self.assertIn("analyst.consensus", result["data_gaps"])
        self.assertEqual(result["price"]["live"], 1500)

    def test_empty_evidence(self):
        result = normalize_evidence(None)
        self.assertEqual(result["symbol"], "UNKNOWN")
        self.assertIn("all_data", result["data_gaps"])

    def test_missing_fields_added_to_gaps(self):
        raw = {"symbol": "TEST", "price": {"live": 100}}
        result = normalize_evidence(raw)
        self.assertTrue(len(result["data_gaps"]) > 0)


class TestMissingDataHandling(unittest.TestCase):
    def test_none_values_propagated(self):
        raw = {"symbol": "TEST", "price": {}}
        result = normalize_evidence(raw)
        self.assertIsNone(result["price"]["live"])
        self.assertIn("price.live", result["data_gaps"])

    def test_news_defaults(self):
        raw = {"symbol": "TEST"}
        result = normalize_evidence(raw)
        self.assertEqual(result["news"]["total"], 0)
        self.assertEqual(result["news"]["recent"], [])


if __name__ == "__main__":
    unittest.main()
