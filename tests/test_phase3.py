import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import unittest
from unittest.mock import patch, MagicMock
from data.data_sources import (
    load_universe, search_stocks, resolve_symbol,
    fetch_live_evidence, load_demo_evidence, get_evidence,
    screen_universe, DataUnavailableError,
    _classify_headline, _score_news_sentiment,
)
from data.evidence import normalize_evidence


class TestUniverseLoading(unittest.TestCase):
    def test_load_universe_has_all_buckets(self):
        universe = load_universe()
        self.assertIn("large", universe)
        self.assertIn("mid", universe)
        self.assertIn("small", universe)

    def test_load_universe_stocks_have_required_fields(self):
        universe = load_universe()
        for segment, stocks in universe.items():
            for stock in stocks:
                self.assertIn("symbol", stock, f"{segment} stock missing symbol")
                self.assertIn("name", stock, f"{segment} stock missing name")
                self.assertIn("sector", stock, f"{segment} stock missing sector")
                self.assertTrue(stock["symbol"].endswith(".NS"),
                                f"{stock['symbol']} should end with .NS")

    def test_universe_stock_counts(self):
        universe = load_universe()
        self.assertGreater(len(universe["large"]), 0)
        self.assertGreater(len(universe["mid"]), 0)
        self.assertGreater(len(universe["small"]), 0)


class TestSearchStocks(unittest.TestCase):
    def test_search_by_symbol(self):
        results = search_stocks("TCS")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["symbol"], "TCS.NS")

    def test_search_by_name(self):
        results = search_stocks("Infosys")
        self.assertGreater(len(results), 0)
        self.assertTrue(any("Infosys" in r["name"] for r in results))

    def test_search_case_insensitive(self):
        results = search_stocks("tcs")
        self.assertGreater(len(results), 0)

    def test_search_empty_query(self):
        results = search_stocks("")
        self.assertEqual(len(results), 0)

    def test_search_no_match(self):
        results = search_stocks("ZZZZZZ")
        self.assertEqual(len(results), 0)

    def test_search_with_cap_segment_filter(self):
        results = search_stocks("TCS", cap_segment="large")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["cap_segment"], "large")

    def test_search_wrong_segment_returns_empty(self):
        results = search_stocks("TCS", cap_segment="small")
        self.assertEqual(len(results), 0)


class TestResolveSymbol(unittest.TestCase):
    def test_resolve_raw_symbol(self):
        symbol, info = resolve_symbol("TCS")
        self.assertEqual(symbol, "TCS.NS")
        self.assertIsNotNone(info)
        self.assertEqual(info["name"], "Tata Consultancy Services")

    def test_resolve_full_ticker(self):
        symbol, info = resolve_symbol("TCS.NS")
        self.assertEqual(symbol, "TCS.NS")

    def test_resolve_by_name(self):
        symbol, info = resolve_symbol("Infosys")
        self.assertEqual(symbol, "INFY.NS")

    def test_resolve_not_found(self):
        symbol, info = resolve_symbol("ZZZZZZ")
        self.assertIsNone(symbol)
        self.assertIsNone(info)

    def test_resolve_empty(self):
        symbol, info = resolve_symbol("")
        self.assertIsNone(symbol)


class TestDemoEvidence(unittest.TestCase):
    def test_demo_evidence_has_all_sections(self):
        ev = load_demo_evidence("TCS.NS")
        self.assertEqual(ev["symbol"], "TCS.NS")
        self.assertEqual(ev["source"], "demo")
        self.assertIn("price", ev)
        self.assertIn("range_52w", ev)
        self.assertIn("technicals", ev)
        self.assertIn("analyst", ev)
        self.assertIn("news", ev)

    def test_demo_evidence_deterministic(self):
        ev1 = load_demo_evidence("TCS.NS")
        ev2 = load_demo_evidence("TCS.NS")
        self.assertEqual(ev1["price"]["live"], ev2["price"]["live"])
        self.assertEqual(ev1["technicals"]["rvol"], ev2["technicals"]["rvol"])

    def test_demo_evidence_different_stocks(self):
        ev1 = load_demo_evidence("TCS.NS")
        ev2 = load_demo_evidence("INFY.NS")
        self.assertNotEqual(ev1["price"]["live"], ev2["price"]["live"])

    def test_demo_evidence_has_data_gaps(self):
        ev = load_demo_evidence("TCS.NS")
        self.assertIn("data_gaps", ev)
        self.assertIsInstance(ev["data_gaps"], list)


class TestLiveDataSeparation(unittest.TestCase):
    @patch("data.data_sources.fetch_live_evidence")
    def test_get_evidence_demo_mode_returns_demo(self, mock_fetch):
        os.environ["DEMO_MODE"] = "true"
        import importlib
        import config as config_mod
        importlib.reload(config_mod)

        ev = get_evidence("TCS.NS")
        self.assertEqual(ev["source"], "demo")
        mock_fetch.assert_not_called()

    @patch("data.data_sources.fetch_live_evidence")
    def test_get_evidence_live_mode_calls_fetch(self, mock_fetch):
        os.environ["DEMO_MODE"] = "false"
        import importlib
        import config as config_mod
        importlib.reload(config_mod)

        mock_fetch.return_value = {"symbol": "TCS.NS", "source": "live", "price": {}}
        ev = get_evidence("TCS.NS", force_live=True)
        self.assertEqual(ev["source"], "live")
        mock_fetch.assert_called_once_with("TCS.NS")

    @patch("data.data_sources.fetch_live_evidence")
    def test_get_evidence_live_mode_raises_on_failure(self, mock_fetch):
        os.environ["DEMO_MODE"] = "false"
        import importlib
        import config as config_mod
        importlib.reload(config_mod)

        mock_fetch.return_value = None
        with self.assertRaises(DataUnavailableError):
            get_evidence("TCS.NS", force_live=True)

    @patch("data.data_sources.fetch_live_evidence")
    def test_collect_analysis_raises_on_live_failure(self, mock_fetch):
        os.environ["DEMO_MODE"] = "false"
        import importlib
        import config as config_mod
        importlib.reload(config_mod)

        mock_fetch.return_value = None
        from data.data_sources import collect_analysis
        with self.assertRaises(DataUnavailableError):
            collect_analysis("TCS.NS", force_live=True)


class TestScreenUniverse(unittest.TestCase):
    def test_demo_screen_returns_all_buckets(self):
        os.environ["DEMO_MODE"] = "true"
        import importlib
        import config as config_mod
        importlib.reload(config_mod)

        results = screen_universe()
        self.assertIn("large", results)
        self.assertIn("mid", results)
        self.assertIn("small", results)

    def test_demo_screen_respects_per_bucket_limit(self):
        os.environ["DEMO_MODE"] = "true"
        import importlib
        import config as config_mod
        importlib.reload(config_mod)
        from config import config

        results = screen_universe()
        for bucket, stocks in results.items():
            self.assertLessEqual(len(stocks), config.SHORTLIST_PER_BUCKET)

    def test_demo_screen_sorted_by_abs_day_change(self):
        os.environ["DEMO_MODE"] = "true"
        import importlib
        import config as config_mod
        importlib.reload(config_mod)

        results = screen_universe()
        for bucket, stocks in results.items():
            if len(stocks) < 2:
                continue
            changes = [abs(s["day_change_pct"]) if s["day_change_pct"] is not None else 0
                       for s in stocks]
            self.assertEqual(changes, sorted(changes, reverse=True))

    def test_demo_screen_each_stock_has_required_fields(self):
        os.environ["DEMO_MODE"] = "true"
        import importlib
        import config as config_mod
        importlib.reload(config_mod)

        results = screen_universe()
        for bucket, stocks in results.items():
            for stock in stocks:
                self.assertIn("symbol", stock)
                self.assertIn("name", stock)
                self.assertIn("sector", stock)
                self.assertIn("cap_segment", stock)
                self.assertIn("day_change_pct", stock)

    @patch("data.data_sources.fetch_live_evidence")
    def test_strict_live_raises_on_failure(self, mock_fetch):
        os.environ["DEMO_MODE"] = "false"
        import importlib
        import config as config_mod
        importlib.reload(config_mod)

        mock_fetch.return_value = None
        with self.assertRaises(DataUnavailableError):
            screen_universe(strict=True)

    @patch("data.data_sources.fetch_live_evidence")
    def test_non_strict_live_skips_unavailable(self, mock_fetch):
        os.environ["DEMO_MODE"] = "false"
        import importlib
        import config as config_mod
        importlib.reload(config_mod)

        def fake_fetch(symbol):
            if "TCS" in symbol:
                return {"symbol": symbol, "price": {"live": 100, "day_change_pct": 2.0}, "source": "live"}
            return None

        mock_fetch.side_effect = fake_fetch
        results = screen_universe(strict=False)
        self.assertIn("large", results)


class TestNewsdeskSentiment(unittest.TestCase):
    def test_positive_keywords(self):
        from agents.newsdesk import run
        ev = {"news": {"total": 1, "recent": [{"title": "Stock surges on strong results", "publisher": "ET"}]}}
        result = run(ev)
        self.assertEqual(result["output"]["sentiment"], "positive")
        self.assertGreater(result["output"]["conviction"], 50)

    def test_negative_keywords(self):
        from agents.newsdesk import run
        ev = {"news": {"total": 1, "recent": [{"title": "Stock crashes after loss report", "publisher": "ET"}]}}
        result = run(ev)
        self.assertEqual(result["output"]["sentiment"], "negative")
        self.assertLess(result["output"]["conviction"], 50)

    def test_neutral_headlines(self):
        from agents.newsdesk import run
        ev = {"news": {"total": 1, "recent": [{"title": "Board meeting scheduled", "publisher": "ET"}]}}
        result = run(ev)
        self.assertIn(result["output"]["sentiment"], ["neutral", "positive", "negative"])

    def test_empty_news(self):
        from agents.newsdesk import run
        ev = {"news": {"total": 0, "recent": []}}
        result = run(ev)
        self.assertEqual(result["output"]["sentiment"], "no data")


class TestScoutDualMode(unittest.TestCase):
    def test_scout_reports_stock_info(self):
        from agents.scout import run
        ev = {
            "symbol": "TCS.NS", "name": "TCS", "sector": "IT",
            "cap_segment": "large", "source": "demo", "data_gaps": [],
        }
        result = run(ev)
        self.assertEqual(result["agent"], "Scout")
        self.assertEqual(result["output"]["symbol"], "TCS.NS")
        self.assertEqual(result["output"]["data_source"], "demo")

    def test_scout_includes_shortlist_in_demo(self):
        os.environ["DEMO_MODE"] = "true"
        import importlib
        import config as config_mod
        importlib.reload(config_mod)

        from agents.scout import run
        ev = {
            "symbol": "TCS.NS", "name": "TCS", "sector": "IT",
            "cap_segment": "large", "source": "demo", "data_gaps": [],
        }
        result = run(ev)
        self.assertIn("shortlist", result["output"])
        self.assertIn("large", result["output"]["shortlist"])

    @patch("data.data_sources.fetch_live_evidence")
    def test_scout_strict_live_screening_error(self, mock_fetch):
        os.environ["DEMO_MODE"] = "false"
        import importlib
        import config as config_mod
        importlib.reload(config_mod)

        mock_fetch.return_value = None
        from agents.scout import run
        ev = {
            "symbol": "TCS.NS", "name": "TCS", "sector": "IT",
            "cap_segment": "large", "source": "live", "data_gaps": [],
        }
        result = run(ev, strict_live=True)
        self.assertIsNotNone(result["output"]["screening_error"])
        self.assertEqual(result["output"]["shortlist"], {})


class TestPipelineEndToEnd(unittest.TestCase):
    def test_demo_pipeline_complete(self):
        os.environ["DEMO_MODE"] = "true"
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        os.environ["SECRET_KEY"] = "test"
        import importlib
        import config as config_mod
        importlib.reload(config_mod)

        from database.db import init_db
        init_db(database_url="sqlite:///:memory:")

        from backend.services.analysis import run_pipeline
        result = run_pipeline("TCS.NS")

        self.assertIn("evidence", result)
        self.assertIn("agent_outputs", result)
        self.assertIn("scoring", result)
        self.assertIn("verdict", result)
        self.assertIn(result["verdict"]["verdict"], ["BUY", "WATCH", "AVOID"])

        agents = result["agent_outputs"]
        self.assertIn("scout", agents)
        self.assertIn("technician", agents)
        self.assertIn("fundamentalist", agents)
        self.assertIn("newsdesk", agents)
        self.assertIn("bull", agents)
        self.assertIn("bear", agents)
        self.assertIn("judge", agents)

    @patch("data.data_sources.fetch_live_evidence")
    def test_live_pipeline_raises_on_data_failure(self, mock_fetch):
        os.environ["DEMO_MODE"] = "false"
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        os.environ["SECRET_KEY"] = "test"
        import importlib
        import config as config_mod
        importlib.reload(config_mod)

        mock_fetch.return_value = None
        from backend.services.analysis import run_pipeline
        with self.assertRaises(DataUnavailableError):
            run_pipeline("TCS.NS", force_live=True)

    def test_demo_pipeline_all_agents_have_output(self):
        os.environ["DEMO_MODE"] = "true"
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        os.environ["SECRET_KEY"] = "test"
        import importlib
        import config as config_mod
        importlib.reload(config_mod)

        from database.db import init_db
        init_db(database_url="sqlite:///:memory:")

        from backend.services.analysis import run_pipeline
        result = run_pipeline("RELIANCE.NS")

        for agent_name in ["scout", "technician", "fundamentalist", "newsdesk", "bull", "bear", "judge"]:
            agent = result["agent_outputs"][agent_name]
            self.assertEqual(agent["status"], "complete", f"{agent_name} not complete")
            self.assertIn("output", agent)


class TestMissingDataHandling(unittest.TestCase):
    def test_normalize_none_evidence(self):
        result = normalize_evidence(None)
        self.assertEqual(result["symbol"], "UNKNOWN")
        self.assertIn("all_data", result["data_gaps"])

    def test_normalize_empty_evidence(self):
        result = normalize_evidence({})
        self.assertEqual(result["symbol"], "UNKNOWN")

    def test_normalize_partial_evidence(self):
        raw = {"symbol": "TEST", "price": {"live": 100}}
        result = normalize_evidence(raw)
        self.assertEqual(result["price"]["live"], 100)
        self.assertIn("price.day_open", result["data_gaps"])

    def test_evidence_source_preserved(self):
        raw = {"symbol": "TEST", "source": "live", "price": {}, "range_52w": {}, "technicals": {}, "analyst": {}, "news": {}}
        result = normalize_evidence(raw)
        self.assertEqual(result["source"], "live")


class TestAnalyzerEndpoint(unittest.TestCase):
    def _make_app(self):
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        os.environ["SECRET_KEY"] = "test"
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
        return app

    def test_analyze_unknown_symbol_returns_404(self):
        app = self._make_app()
        client = app.test_client()
        client.post("/api/auth/register", json={
            "username": "testuser", "email": "t@t.com", "password": "pass123",
        })
        res = client.post("/api/analyze", json={"symbol": "ZZZZZZ"})
        self.assertEqual(res.status_code, 404)

    def test_analyze_resolves_bare_symbol(self):
        app = self._make_app()
        client = app.test_client()
        client.post("/api/auth/register", json={
            "username": "testuser", "email": "t@t.com", "password": "pass123",
        })
        res = client.post("/api/analyze", json={"symbol": "TCS"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["symbol"], "TCS.NS")

    def test_screen_endpoint_demo(self):
        app = self._make_app()
        client = app.test_client()
        client.post("/api/auth/register", json={
            "username": "testuser", "email": "t@t.com", "password": "pass123",
        })
        res = client.get("/api/screen")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("large", data)
        self.assertIn("mid", data)
        self.assertIn("small", data)

    def test_analyze_requires_auth(self):
        app = self._make_app()
        client = app.test_client()
        res = client.post("/api/analyze", json={"symbol": "TCS"})
        self.assertEqual(res.status_code, 401)


if __name__ == "__main__":
    unittest.main()
