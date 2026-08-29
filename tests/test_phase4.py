import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test")

from agents.base import (
    _safe, _clamp, validate_schema, build_evidence_text, parse_llm_json, SCHEMAS,
)
from engine.llm import call_llm, call_llm_structured, is_available


class TestSafeAndClamp(unittest.TestCase):
    def test_safe_none(self):
        self.assertEqual(_safe(None), 0)

    def test_safe_valid(self):
        self.assertEqual(_safe("42.5"), 42.5)

    def test_safe_invalid(self):
        self.assertEqual(_safe("abc", 99), 99)

    def test_clamp_within(self):
        self.assertEqual(_clamp(5, 0, 10), 5)

    def test_clamp_below(self):
        self.assertEqual(_clamp(-5, 0, 10), 0)

    def test_clamp_above(self):
        self.assertEqual(_clamp(15, 0, 10), 10)


class TestSchemaValidation(unittest.TestCase):
    def test_valid_technician(self):
        data = {
            "agent": "technician",
            "conviction": 65,
            "bullish_signals": ["uptrend"],
            "bearish_signals": [],
            "reasoning": "Test",
            "evidence_used": ["technicals.trend"],
        }
        valid, errors = validate_schema("technician", data)
        self.assertTrue(valid)
        self.assertEqual(errors, [])

    def test_missing_field(self):
        data = {"agent": "technician", "conviction": 65}
        valid, errors = validate_schema("technician", data)
        self.assertFalse(valid)
        self.assertTrue(any("Missing" in e for e in errors))

    def test_conviction_out_of_range(self):
        data = {
            "agent": "technician",
            "conviction": 150,
            "bullish_signals": [],
            "bearish_signals": [],
            "reasoning": "Test",
            "evidence_used": [],
        }
        valid, errors = validate_schema("technician", data)
        self.assertFalse(valid)
        self.assertTrue(any("Conviction" in e for e in errors))

    def test_invalid_sentiment(self):
        data = {
            "agent": "newsdesk",
            "sentiment": "very_positive",
            "conviction": 50,
            "catalysts": [],
            "risks": [],
            "reasoning": "Test",
            "evidence_used": [],
        }
        valid, errors = validate_schema("newsdesk", data)
        self.assertFalse(valid)
        self.assertTrue(any("sentiment" in e for e in errors))

    def test_invalid_winner(self):
        data = {
            "agent": "judge",
            "winner": "nobody",
            "assessment": "Test",
            "key_catalyst": "Test",
            "key_risk": "Test",
            "confidence": 5,
            "recommended_verdict": "WATCH",
            "evidence_used": [],
        }
        valid, errors = validate_schema("judge", data)
        self.assertFalse(valid)
        self.assertTrue(any("winner" in e for e in errors))

    def test_all_schemas_defined(self):
        for agent in ("technician", "fundamentalist", "newsdesk", "bull", "bear", "judge"):
            self.assertIn(agent, SCHEMAS)
            self.assertIn("required", SCHEMAS[agent])


class TestParseLlmJson(unittest.TestCase):
    def test_valid_json(self):
        result = parse_llm_json('{"key": "value"}')
        self.assertEqual(result, {"key": "value"})

    def test_json_in_markdown(self):
        result = parse_llm_json('```json\n{"key": "value"}\n```')
        self.assertEqual(result, {"key": "value"})

    def test_json_with_surrounding_text(self):
        result = parse_llm_json('Here is the analysis: {"key": "value"} done.')
        self.assertEqual(result, {"key": "value"})

    def test_invalid_json(self):
        result = parse_llm_json("not json at all")
        self.assertIsNone(result)

    def test_empty_string(self):
        result = parse_llm_json("")
        self.assertIsNone(result)

    def test_none(self):
        result = parse_llm_json(None)
        self.assertIsNone(result)


class TestBuildEvidenceText(unittest.TestCase):
    def test_includes_sections(self):
        evidence = {
            "price": {"live": 100, "day_change_pct": 2.5},
            "technicals": {"rvol": 1.5, "trend": "up"},
        }
        text = build_evidence_text(evidence)
        self.assertIn("price", text)
        self.assertIn("technicals", text)

    def test_excludes_none_values(self):
        evidence = {"price": {"live": 100, "high": None}}
        text = build_evidence_text(evidence)
        self.assertIn("live", text)
        self.assertNotIn("high", text)

    def test_includes_headlines(self):
        evidence = {
            "news": {
                "recent": [{"title": "Test headline", "publisher": "ET"}],
            }
        }
        text = build_evidence_text(evidence)
        self.assertIn("Test headline", text)

    def test_includes_data_gaps(self):
        evidence = {"data_gaps": ["technicals.rvol"]}
        text = build_evidence_text(evidence)
        self.assertIn("technicals.rvol", text)


class TestTechnicianAgent(unittest.TestCase):
    def _make_evidence(self, **overrides):
        base = {
            "technicals": {
                "rvol": 1.5, "trend": "up", "price_vs_sma_pct": 3.0,
                "window_return_pct": 5.0, "day_range_position_pct": 70.0,
                "swing_high": 100, "swing_low": 90,
            },
            "price": {"live": 95.0},
            "range_52w": {"position_pct": 75.0, "pct_from_high": -5.0},
        }
        for k, v in overrides.items():
            if k in ("technicals", "price", "range_52w"):
                base[k].update(v)
        return base

    def test_deterministic_bullish(self):
        from agents.technician import _deterministic
        ev = self._make_evidence()
        result = _deterministic(ev)
        self.assertIn("technician", result["agent"])
        self.assertGreater(result["conviction"], 50)
        self.assertTrue(result["bullish_signals"])
        self.assertIn("technicals.trend", result["evidence_used"])

    def test_deterministic_bearish(self):
        from agents.technician import _deterministic
        ev = self._make_evidence(
            technicals={"rvol": 0.5, "trend": "down", "price_vs_sma_pct": -5.0,
                        "window_return_pct": -8.0, "day_range_position_pct": 20.0},
            range_52w={"position_pct": 15.0, "pct_from_high": -30.0},
        )
        result = _deterministic(ev)
        self.assertLess(result["conviction"], 50)
        self.assertTrue(result["bearish_signals"])

    def test_run_returns_correct_structure(self):
        from agents.technician import run
        ev = self._make_evidence()
        result = run(ev)
        self.assertEqual(result["agent"], "Technician")
        self.assertEqual(result["status"], "complete")
        self.assertIn("output", result)
        self.assertIn("llm_powered", result)
        self.assertFalse(result["llm_powered"])

    def test_run_schema_valid(self):
        from agents.technician import run
        ev = self._make_evidence()
        result = run(ev)
        valid, errors = validate_schema("technician", result["output"])
        self.assertTrue(valid, f"Schema errors: {errors}")


class TestFundamentalistAgent(unittest.TestCase):
    def _make_evidence(self, **overrides):
        base = {
            "analyst": {
                "consensus": "buy", "num_analysts": 20,
                "buy_pct": 65, "hold_pct": 25, "sell_pct": 10,
                "target_mean": 120.0, "upside_pct": 20.0,
            },
            "price": {"live": 100.0},
        }
        for k, v in overrides.items():
            if k in ("analyst", "price"):
                base[k].update(v)
        return base

    def test_deterministic_bullish(self):
        from agents.fundamentalist import _deterministic
        ev = self._make_evidence()
        result = _deterministic(ev)
        self.assertGreater(result["conviction"], 50)
        self.assertTrue(result["bullish_points"])

    def test_deterministic_bearish(self):
        from agents.fundamentalist import _deterministic
        ev = self._make_evidence(
            analyst={"consensus": "sell", "num_analysts": 3,
                     "buy_pct": 10, "hold_pct": 30, "sell_pct": 60,
                     "target_mean": 80.0, "upside_pct": -20.0},
        )
        result = _deterministic(ev)
        self.assertLess(result["conviction"], 50)
        self.assertTrue(result["bearish_points"])

    def test_data_gaps(self):
        from agents.fundamentalist import _deterministic
        ev = {"analyst": {}, "price": {"live": 100}}
        result = _deterministic(ev)
        self.assertTrue(result["data_gaps"])

    def test_run_schema_valid(self):
        from agents.fundamentalist import run
        ev = self._make_evidence()
        result = run(ev)
        valid, errors = validate_schema("fundamentalist", result["output"])
        self.assertTrue(valid, f"Schema errors: {errors}")


class TestNewsdeskAgent(unittest.TestCase):
    def test_deterministic_positive(self):
        from agents.newsdesk import _deterministic
        ev = {
            "news": {
                "total": 2, "positive": 0, "negative": 0, "neutral": 0,
                "recent": [
                    {"title": "Stock surges on strong results", "publisher": "ET"},
                    {"title": "Company rallies to new high", "publisher": "MC"},
                ],
            }
        }
        result = _deterministic(ev)
        self.assertEqual(result["sentiment"], "positive")
        self.assertGreater(result["conviction"], 50)

    def test_deterministic_negative(self):
        from agents.newsdesk import _deterministic
        ev = {
            "news": {
                "total": 2, "positive": 0, "negative": 0, "neutral": 0,
                "recent": [
                    {"title": "Stock crashes after loss", "publisher": "ET"},
                    {"title": "Company faces crisis", "publisher": "MC"},
                ],
            }
        }
        result = _deterministic(ev)
        self.assertEqual(result["sentiment"], "negative")

    def test_empty_news(self):
        from agents.newsdesk import _deterministic
        ev = {"news": {"total": 0, "recent": []}}
        result = _deterministic(ev)
        self.assertEqual(result["sentiment"], "no data")

    def test_run_schema_valid(self):
        from agents.newsdesk import run
        ev = {"news": {"total": 1, "recent": [{"title": "Test", "publisher": "ET"}]}}
        result = run(ev)
        valid, errors = validate_schema("newsdesk", result["output"])
        self.assertTrue(valid, f"Schema errors: {errors}")


class TestBullAgent(unittest.TestCase):
    def _make_evidence(self):
        return {
            "technicals": {"rvol": 2.0, "trend": "up", "window_return_pct": 5.0, "day_range_position_pct": 75.0},
            "analyst": {"upside_pct": 15.0, "buy_pct": 60.0},
            "news": {"positive": 3, "negative": 1},
            "range_52w": {"position_pct": 70.0, "pct_from_high": -5.0},
        }

    def test_deterministic_bullish(self):
        from agents.bull import _deterministic
        ev = self._make_evidence()
        result = _deterministic(ev)
        self.assertGreater(result["conviction"], 50)
        self.assertTrue(result["arguments"])
        self.assertIn("technicals.rvol", result["supporting_evidence"])

    def test_risks_acknowledged(self):
        from agents.bull import _deterministic
        ev = self._make_evidence()
        ev["technicals"]["trend"] = "down"
        result = _deterministic(ev)
        self.assertTrue(result["risks_acknowledged"])

    def test_run_schema_valid(self):
        from agents.bull import run
        result = run(self._make_evidence())
        valid, errors = validate_schema("bull", result["output"])
        self.assertTrue(valid, f"Schema errors: {errors}")


class TestBearAgent(unittest.TestCase):
    def _make_evidence(self):
        return {
            "technicals": {"rvol": 0.5, "trend": "down", "window_return_pct": -8.0, "day_range_position_pct": 20.0},
            "analyst": {"upside_pct": 2.0, "buy_pct": 15.0, "sell_pct": 35.0},
            "news": {"positive": 1, "negative": 3},
            "range_52w": {"position_pct": 20.0, "pct_from_high": -25.0},
        }

    def test_deterministic_bearish(self):
        from agents.bear import _deterministic
        ev = self._make_evidence()
        result = _deterministic(ev)
        self.assertGreater(result["conviction"], 50)
        self.assertTrue(result["arguments"])

    def test_bullish_risks_acknowledged(self):
        from agents.bear import _deterministic
        ev = self._make_evidence()
        ev["technicals"]["trend"] = "up"
        result = _deterministic(ev)
        self.assertTrue(result["bullish_risks_acknowledged"])

    def test_run_schema_valid(self):
        from agents.bear import run
        result = run(self._make_evidence())
        valid, errors = validate_schema("bear", result["output"])
        self.assertTrue(valid, f"Schema errors: {errors}")


class TestJudgeAgent(unittest.TestCase):
    def test_deterministic_with_scoring(self):
        from agents.judge import _deterministic
        from engine.scoring import evaluate
        ev = {
            "technicals": {"rvol": 2.0, "trend": "up", "price_vs_sma_pct": 3.0,
                           "window_return_pct": 5.0, "day_range_position_pct": 70.0},
            "analyst": {"upside_pct": 15.0, "buy_pct": 60.0, "sell_pct": 5.0},
            "news": {"positive": 3, "negative": 1, "neutral": 2, "total": 6},
            "range_52w": {"position_pct": 70.0, "pct_from_high": -5.0, "high": 120, "low": 80},
            "price": {"live": 100.0},
        }
        scoring = evaluate(ev)
        result = _deterministic(ev, scoring)
        self.assertIn("winner", result)
        self.assertIn("verdict", result)
        self.assertIn("confidence", result)
        self.assertEqual(result["bull_score"], scoring["verdict"]["bull_score"])

    def test_run_schema_valid(self):
        from agents.judge import run
        from engine.scoring import evaluate
        ev = {
            "technicals": {"rvol": 1.5, "trend": "up", "price_vs_sma_pct": 2.0,
                           "window_return_pct": 3.0, "day_range_position_pct": 60.0},
            "analyst": {"upside_pct": 10.0, "buy_pct": 50.0, "sell_pct": 10.0},
            "news": {"positive": 2, "negative": 1, "neutral": 1, "total": 4},
            "range_52w": {"position_pct": 60.0, "pct_from_high": -10.0, "high": 120, "low": 80},
            "price": {"live": 100.0},
        }
        scoring = evaluate(ev)
        result = run(ev, scoring_result=scoring)
        self.assertEqual(result["agent"], "Judge")
        self.assertIn("verdict", result["output"])


class TestLLMProviderSystem(unittest.TestCase):
    @patch("engine.llm._detect_claude_cli", return_value=False)
    def test_is_available_no_providers(self, mock_cli):
        os.environ["LLM_PROVIDER"] = "auto"
        os.environ["ANTHROPIC_API_KEY"] = ""
        os.environ["OPENAI_API_KEY"] = ""
        self.assertFalse(is_available())

    def test_is_available_deterministic_mode(self):
        os.environ["LLM_PROVIDER"] = "deterministic"
        self.assertFalse(is_available())

    @patch("engine.llm._detect_claude_cli", return_value=True)
    def test_is_available_claude_cli(self, mock_cli):
        os.environ["LLM_PROVIDER"] = "auto"
        self.assertTrue(is_available())

    @patch("engine.llm._detect_claude_cli", return_value=False)
    def test_is_available_anthropic_key(self, mock_cli):
        os.environ["LLM_PROVIDER"] = "auto"
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        os.environ["OPENAI_API_KEY"] = ""
        self.assertTrue(is_available())
        os.environ["ANTHROPIC_API_KEY"] = ""

    @patch("engine.llm._detect_claude_cli", return_value=False)
    def test_is_available_respects_provider_setting(self, mock_cli):
        os.environ["LLM_PROVIDER"] = "anthropic"
        os.environ["ANTHROPIC_API_KEY"] = ""
        os.environ["OPENAI_API_KEY"] = ""
        self.assertFalse(is_available())

    @patch("engine.llm._detect_claude_cli", return_value=False)
    def test_call_llm_returns_none_without_providers(self, mock_cli):
        os.environ["LLM_PROVIDER"] = "auto"
        os.environ["ANTHROPIC_API_KEY"] = ""
        os.environ["OPENAI_API_KEY"] = ""
        result = call_llm("test prompt")
        self.assertIsNone(result)

    @patch("engine.llm._detect_claude_cli", return_value=False)
    def test_call_llm_structured_returns_error_without_providers(self, mock_cli):
        os.environ["LLM_PROVIDER"] = "auto"
        os.environ["ANTHROPIC_API_KEY"] = ""
        os.environ["OPENAI_API_KEY"] = ""
        result, error = call_llm_structured("test prompt", "technician")
        self.assertIsNone(result)
        self.assertIsNotNone(error)


class TestPipelineChaining(unittest.TestCase):
    def test_demo_pipeline_produces_correct_output(self):
        import importlib
        import config as config_mod
        os.environ["DEMO_MODE"] = "true"
        importlib.reload(config_mod)

        from database.db import init_db
        init_db(database_url="sqlite:///:memory:")

        from backend.services.analysis import run_pipeline
        result = run_pipeline("TCS.NS")

        self.assertIn("evidence", result)
        self.assertIn("agent_outputs", result)
        self.assertIn("verdict", result)
        self.assertIn("grounding", result)
        self.assertIn("llm_used", result)

        self.assertEqual(result["llm_used"], False)

        agents = result["agent_outputs"]
        self.assertIn("scout", agents)
        self.assertIn("technician", agents)
        self.assertIn("fundamentalist", agents)
        self.assertIn("newsdesk", agents)
        self.assertIn("bull", agents)
        self.assertIn("bear", agents)
        self.assertIn("judge", agents)

    def test_technician_feeds_bull_bear(self):
        import importlib
        import config as config_mod
        os.environ["DEMO_MODE"] = "true"
        importlib.reload(config_mod)

        from database.db import init_db
        init_db(database_url="sqlite:///:memory:")

        from backend.services.analysis import run_pipeline
        result = run_pipeline("TCS.NS")

        tech = result["agent_outputs"]["technician"]["output"]
        self.assertIn("conviction", tech)
        self.assertIn("bullish_signals", tech)
        self.assertIn("bearish_signals", tech)

    def test_bull_bear_receive_previous_outputs(self):
        import importlib
        import config as config_mod
        os.environ["DEMO_MODE"] = "true"
        importlib.reload(config_mod)

        from database.db import init_db
        init_db(database_url="sqlite:///:memory:")

        from backend.services.analysis import run_pipeline
        result = run_pipeline("TCS.NS")

        bull = result["agent_outputs"]["bull"]["output"]
        bear = result["agent_outputs"]["bear"]["output"]
        self.assertIn("arguments", bull)
        self.assertIn("supporting_evidence", bull)
        self.assertIn("risks_acknowledged", bull)
        self.assertIn("arguments", bear)
        self.assertIn("supporting_evidence", bear)
        self.assertIn("bullish_risks_acknowledged", bear)

    def test_judge_receives_all_inputs(self):
        import importlib
        import config as config_mod
        os.environ["DEMO_MODE"] = "true"
        importlib.reload(config_mod)

        from database.db import init_db
        init_db(database_url="sqlite:///:memory:")

        from backend.services.analysis import run_pipeline
        result = run_pipeline("TCS.NS")

        judge = result["agent_outputs"]["judge"]["output"]
        self.assertIn("verdict", judge)
        self.assertIn("winner", judge)
        self.assertIn("confidence", judge)
        self.assertIn("bull_score", judge)
        self.assertIn("bear_score", judge)


class TestGroundingWithNewSchemas(unittest.TestCase):
    def test_all_agents_ground_in_demo(self):
        import importlib
        import config as config_mod
        os.environ["DEMO_MODE"] = "true"
        importlib.reload(config_mod)

        from database.db import init_db
        init_db(database_url="sqlite:///:memory:")

        from backend.services.analysis import run_pipeline
        result = run_pipeline("TCS.NS")

        self.assertTrue(result["grounding"]["valid"], f"Flagged: {result['grounding']['flagged']}")

    def test_verdict_integrity(self):
        import importlib
        import config as config_mod
        os.environ["DEMO_MODE"] = "true"
        importlib.reload(config_mod)

        from database.db import init_db
        init_db(database_url="sqlite:///:memory:")

        from backend.services.analysis import run_pipeline
        result = run_pipeline("TCS.NS")

        self.assertTrue(result["verdict_integrity"]["valid"], f"Issues: {result['verdict_integrity']['issues']}")


if __name__ == "__main__":
    unittest.main()
