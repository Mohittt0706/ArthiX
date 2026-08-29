import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import unittest


class TestScoutScreening(unittest.TestCase):
    def test_scout_returns_shortlist_per_bucket(self):
        from agents.scout import run

        evidence = {
            "symbol": "TCS.NS",
            "name": "Tata Consultancy Services",
            "sector": "IT",
            "cap_segment": "large",
            "source": "demo",
            "data_gaps": [],
        }
        result = run(evidence)
        self.assertEqual(result["agent"], "Scout")
        self.assertIn("shortlist", result["output"])
        shortlist = result["output"]["shortlist"]
        self.assertIsInstance(shortlist, dict)
        self.assertIn("large", shortlist)
        self.assertIn("mid", shortlist)
        self.assertIn("small", shortlist)

    def test_scout_shortlist_bounded_by_config(self):
        from agents.scout import run
        from config import config

        evidence = {
            "symbol": "RELIANCE.NS",
            "name": "Reliance Industries",
            "sector": "Energy",
            "cap_segment": "large",
            "source": "demo",
            "data_gaps": [],
        }
        result = run(evidence)
        shortlist = result["output"]["shortlist"]
        for bucket, stocks in shortlist.items():
            self.assertLessEqual(
                len(stocks), config.SHORTLIST_PER_BUCKET,
                f"Bucket '{bucket}' has {len(stocks)} stocks, expected <= {config.SHORTLIST_PER_BUCKET}",
            )

    def test_scout_shortlist_sorted_by_abs_day_change(self):
        from agents.scout import run

        evidence = {
            "symbol": "INFY.NS",
            "name": "Infosys",
            "sector": "IT",
            "cap_segment": "large",
            "source": "demo",
            "data_gaps": [],
        }
        result = run(evidence)
        shortlist = result["output"]["shortlist"]
        for bucket, stocks in shortlist.items():
            if len(stocks) < 2:
                continue
            changes = [abs(s["day_change_pct"]) if s["day_change_pct"] is not None else 0 for s in stocks]
            self.assertEqual(
                changes, sorted(changes, reverse=True),
                f"Bucket '{bucket}' not sorted by abs(day_change_pct)",
            )

    def test_scout_signals_include_top_movers(self):
        from agents.scout import run

        evidence = {
            "symbol": "TCS.NS",
            "name": "TCS",
            "sector": "IT",
            "cap_segment": "large",
            "source": "demo",
            "data_gaps": [],
        }
        result = run(evidence)
        signals = result["output"]["signals"]
        self.assertTrue(len(signals) > 0, "Scout should produce screening signals")
        self.assertTrue(
            any("top mover" in s.lower() for s in signals),
            "Signals should mention top movers",
        )


class TestNewsdeskSentiment(unittest.TestCase):
    def test_positive_keywords_classified(self):
        from agents.newsdesk import run

        evidence = {
            "news": {
                "total": 2,
                "positive": 0,
                "negative": 0,
                "neutral": 0,
                "recent": [
                    {"title": "TCS surges 5% on strong quarterly results", "publisher": "ET"},
                    {"title": "Stock rallies to record high on growth", "publisher": "MC"},
                ],
            }
        }
        result = run(evidence)
        output = result["output"]
        self.assertEqual(output["positive"], 2)
        self.assertEqual(output["negative"], 0)
        self.assertEqual(output["sentiment_label"], "positive")

    def test_negative_keywords_classified(self):
        from agents.newsdesk import run

        evidence = {
            "news": {
                "total": 2,
                "positive": 0,
                "negative": 0,
                "neutral": 0,
                "recent": [
                    {"title": "Stock crashes 10% after loss report", "publisher": "ET"},
                    {"title": "Company faces crisis as decline continues", "publisher": "MC"},
                ],
            }
        }
        result = run(evidence)
        output = result["output"]
        self.assertEqual(output["negative"], 2)
        self.assertEqual(output["positive"], 0)
        self.assertEqual(output["sentiment_label"], "negative")

    def test_mixed_headlines_classified(self):
        from agents.newsdesk import run

        evidence = {
            "news": {
                "total": 3,
                "positive": 0,
                "negative": 0,
                "neutral": 0,
                "recent": [
                    {"title": "Stock surges on strong results", "publisher": "ET"},
                    {"title": "Company reports loss, shares drop", "publisher": "MC"},
                    {"title": "Board meeting scheduled for Friday", "publisher": "LT"},
                ],
            }
        }
        result = run(evidence)
        output = result["output"]
        self.assertEqual(output["positive"], 1)
        self.assertEqual(output["negative"], 1)
        self.assertEqual(output["neutral"], 1)
        self.assertIn(output["sentiment_label"], ["neutral", "mildly positive", "mildly negative"])

    def test_neutral_headlines_classified(self):
        from agents.newsdesk import run

        evidence = {
            "news": {
                "total": 2,
                "positive": 0,
                "negative": 0,
                "neutral": 0,
                "recent": [
                    {"title": "Board meeting scheduled for next week", "publisher": "ET"},
                    {"title": "Annual report released on time", "publisher": "MC"},
                ],
            }
        }
        result = run(evidence)
        output = result["output"]
        self.assertEqual(output["neutral"], 2)
        self.assertEqual(output["sentiment_label"], "neutral")

    def test_empty_news(self):
        from agents.newsdesk import run

        evidence = {"news": {"total": 0, "recent": []}}
        result = run(evidence)
        self.assertEqual(result["output"]["sentiment_label"], "no data")

    def test_classified_field_in_output(self):
        from agents.newsdesk import run

        evidence = {
            "news": {
                "total": 1,
                "positive": 0,
                "negative": 0,
                "neutral": 0,
                "recent": [
                    {"title": "Stock surges on upgrade", "publisher": "ET"},
                ],
            }
        }
        result = run(evidence)
        classified = result["output"]["classified"]
        self.assertEqual(len(classified), 1)
        self.assertEqual(classified[0]["sentiment"], "positive")


class TestBullDayRange(unittest.TestCase):
    def test_bull_factors_includes_day_range_above_70(self):
        from agents.bull import run

        evidence = {
            "technicals": {
                "rvol": 1.0,
                "trend": "sideways",
                "price_vs_sma_pct": 0,
                "window_return_pct": 0,
                "day_range_position_pct": 80,
            },
            "analyst": {"upside_pct": 0, "buy_pct": 30},
            "news": {"positive": 0, "negative": 0},
            "range_52w": {"position_pct": 50},
        }
        result = run(evidence)
        args = result["output"]["arguments"]
        self.assertTrue(
            any("day range" in a.lower() or "intraday strength" in a.lower() for a in args),
            f"Bull should mention day_range_position_pct >= 70, got: {args}",
        )

    def test_bull_no_day_range_below_70(self):
        from agents.bull import run

        evidence = {
            "technicals": {
                "rvol": 1.0,
                "trend": "sideways",
                "price_vs_sma_pct": 0,
                "window_return_pct": 0,
                "day_range_position_pct": 50,
            },
            "analyst": {"upside_pct": 0, "buy_pct": 30},
            "news": {"positive": 0, "negative": 0},
            "range_52w": {"position_pct": 50},
        }
        result = run(evidence)
        args = result["output"]["arguments"]
        self.assertFalse(
            any("day range" in a.lower() or "intraday strength" in a.lower() for a in args),
            "Bull should NOT mention day_range when < 70",
        )


class TestBearFixes(unittest.TestCase):
    def test_bear_rvol_threshold_1_0(self):
        from agents.bear import run

        evidence = {
            "technicals": {
                "rvol": 0.9,
                "trend": "sideways",
                "price_vs_sma_pct": 0,
                "window_return_pct": 0,
                "day_range_position_pct": 50,
            },
            "analyst": {"upside_pct": 10, "sell_pct": 5, "buy_pct": 50},
            "news": {"positive": 0, "negative": 0},
            "range_52w": {"position_pct": 50, "pct_from_high": -5},
        }
        result = run(evidence)
        args = result["output"]["arguments"]
        self.assertTrue(
            any("low volume" in a.lower() for a in args),
            f"Bear should flag rvol < 1.0, got: {args}",
        )

    def test_bear_no_rvol_flag_at_1_0(self):
        from agents.bear import run

        evidence = {
            "technicals": {
                "rvol": 1.0,
                "trend": "sideways",
                "price_vs_sma_pct": 0,
                "window_return_pct": 0,
                "day_range_position_pct": 50,
            },
            "analyst": {"upside_pct": 10, "sell_pct": 5, "buy_pct": 50},
            "news": {"positive": 0, "negative": 0},
            "range_52w": {"position_pct": 50, "pct_from_high": -5},
        }
        result = run(evidence)
        args = result["output"]["arguments"]
        self.assertFalse(
            any("low volume" in a.lower() for a in args),
            "Bear should NOT flag rvol at exactly 1.0",
        )

    def test_bear_buy_pct_below_30(self):
        from agents.bear import run

        evidence = {
            "technicals": {
                "rvol": 1.5,
                "trend": "sideways",
                "price_vs_sma_pct": 0,
                "window_return_pct": 0,
                "day_range_position_pct": 50,
            },
            "analyst": {"upside_pct": 10, "sell_pct": 5, "buy_pct": 20},
            "news": {"positive": 0, "negative": 0},
            "range_52w": {"position_pct": 50, "pct_from_high": -5},
        }
        result = run(evidence)
        args = result["output"]["arguments"]
        self.assertTrue(
            any("buy" in a.lower() and "20%" in a for a in args),
            f"Bear should flag buy_pct < 30, got: {args}",
        )

    def test_bear_no_buy_pct_flag_above_30(self):
        from agents.bear import run

        evidence = {
            "technicals": {
                "rvol": 1.5,
                "trend": "sideways",
                "price_vs_sma_pct": 0,
                "window_return_pct": 0,
                "day_range_position_pct": 50,
            },
            "analyst": {"upside_pct": 10, "sell_pct": 5, "buy_pct": 40},
            "news": {"positive": 0, "negative": 0},
            "range_52w": {"position_pct": 50, "pct_from_high": -5},
        }
        result = run(evidence)
        args = result["output"]["arguments"]
        self.assertFalse(
            any("buy" in a.lower() and "analysts" in a.lower() for a in args),
            "Bear should NOT flag buy_pct when >= 30",
        )

    def test_bear_day_range_below_30(self):
        from agents.bear import run

        evidence = {
            "technicals": {
                "rvol": 1.5,
                "trend": "sideways",
                "price_vs_sma_pct": 0,
                "window_return_pct": 0,
                "day_range_position_pct": 20,
            },
            "analyst": {"upside_pct": 10, "sell_pct": 5, "buy_pct": 50},
            "news": {"positive": 0, "negative": 0},
            "range_52w": {"position_pct": 50, "pct_from_high": -5},
        }
        result = run(evidence)
        args = result["output"]["arguments"]
        self.assertTrue(
            any("day range" in a.lower() or "intraday weakness" in a.lower() for a in args),
            f"Bear should flag day_range_position_pct <= 30, got: {args}",
        )

    def test_bear_no_day_range_flag_above_30(self):
        from agents.bear import run

        evidence = {
            "technicals": {
                "rvol": 1.5,
                "trend": "sideways",
                "price_vs_sma_pct": 0,
                "window_return_pct": 0,
                "day_range_position_pct": 60,
            },
            "analyst": {"upside_pct": 10, "sell_pct": 5, "buy_pct": 50},
            "news": {"positive": 0, "negative": 0},
            "range_52w": {"position_pct": 50, "pct_from_high": -5},
        }
        result = run(evidence)
        args = result["output"]["arguments"]
        self.assertFalse(
            any("day range" in a.lower() or "intraday weakness" in a.lower() for a in args),
            "Bear should NOT flag day_range when > 30",
        )


class TestScoutScreenEndpoint(unittest.TestCase):
    def test_screen_endpoint_returns_buckets(self):
        import os
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        os.environ["SECRET_KEY"] = "test-secret-key"
        os.environ["DEMO_MODE"] = "true"

        import importlib
        import config as config_mod
        importlib.reload(config_mod)

        from database.db import reset_db
        reset_db()

        from app import create_app
        app = create_app()
        app.config["TESTING"] = True
        app.config["SESSION_COOKIE_SECURE"] = False
        client = app.test_client()

        client.post("/api/auth/register", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
        })

        res = client.get("/api/screen")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("large", data)
        self.assertIn("mid", data)
        self.assertIn("small", data)

        reset_db()


if __name__ == "__main__":
    unittest.main()
