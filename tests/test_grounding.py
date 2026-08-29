import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import unittest
import json
from engine.verifier import (
    _extract_numbers, _build_evidence_numbers, _build_screening_numbers,
    _check_numbers_against_evidence,
    verify_grounding, verify_scout_grounding, verify_verdict_integrity,
)


class TestNumberExtraction(unittest.TestCase):
    def test_extracts_percentages(self):
        nums = _extract_numbers("Price is up 5.2% today")
        self.assertIn("5.2%", nums)

    def test_extracts_negative_percentages(self):
        nums = _extract_numbers("Stock dropped -3.1%")
        self.assertIn("-3.1%", nums)

    def test_extracts_positive_prefixed(self):
        nums = _extract_numbers("Gained +2.5% this week")
        self.assertIn("+2.5%", nums)

    def test_extracts_rupee_amounts(self):
        nums = _extract_numbers("Target price ₹3,500.00")
        self.assertTrue(any("3" in n for n in nums))

    def test_extracts_score_patterns(self):
        nums = _extract_numbers("Bull score: 65, Bear score: 20")
        self.assertTrue(len(nums) >= 2)

    def test_empty_text(self):
        self.assertEqual(_extract_numbers(""), [])

    def test_none_text(self):
        self.assertEqual(_extract_numbers(None), [])


class TestEvidenceNumbers(unittest.TestCase):
    def test_builds_from_all_sections(self):
        evidence = {
            "price": {"live": 100.5, "day_change_pct": 2.3},
            "range_52w": {"high": 120, "low": 80},
            "technicals": {"rvol": 1.5},
            "analyst": {"buy_pct": 60},
            "news": {"total": 5},
        }
        nums = _build_evidence_numbers(evidence)
        self.assertIn("100.5", nums)
        self.assertIn("2.3", nums)
        self.assertIn("120", nums)
        self.assertIn("1.5", nums)
        self.assertIn("60", nums)

    def test_includes_computed(self):
        evidence = {"_computed": {"net_score": 22}}
        nums = _build_evidence_numbers(evidence)
        self.assertIn("22", nums)
        self.assertIn("+22.00", nums)

    def test_includes_formatted_variants(self):
        evidence = {"price": {"live": 3109.25}}
        nums = _build_evidence_numbers(evidence)
        self.assertIn("3109.25", nums)
        self.assertIn("3109.2", nums)
        self.assertIn("3109", nums)


class TestScreeningNumbers(unittest.TestCase):
    def test_builds_from_shortlist(self):
        shortlist = {
            "large": [
                {"symbol": "TCS.NS", "day_change_pct": -2.78, "price": 3109.25},
                {"symbol": "INFY.NS", "day_change_pct": 1.54, "price": 1480.0},
            ],
            "mid": [
                {"symbol": "TATASTEEL.NS", "day_change_pct": 2.77, "price": 165.5},
            ],
        }
        nums = _build_screening_numbers(shortlist)
        self.assertIn("-2.78", nums)
        self.assertIn("+1.54", nums)
        self.assertIn("2.77", nums)
        self.assertIn("3109.25", nums)
        self.assertIn("165.5", nums)

    def test_empty_shortlist(self):
        self.assertEqual(_build_screening_numbers({}), set())

    def test_none_shortlist(self):
        self.assertEqual(_build_screening_numbers(None), set())

    def test_missing_fields_handled(self):
        shortlist = {"large": [{"symbol": "X"}]}
        nums = _build_screening_numbers(shortlist)
        self.assertIsInstance(nums, set)


class TestNumberCheck(unittest.TestCase):
    def test_known_number_passes(self):
        flagged = _check_numbers_against_evidence("Price is 100.5%", {"100.5", "100"})
        self.assertEqual(flagged, [])

    def test_unknown_number_flagged(self):
        flagged = _check_numbers_against_evidence("Price is 999.9%", {"100.5"})
        self.assertEqual(flagged, ["999.9%"])

    def test_no_numbers_passes(self):
        flagged = _check_numbers_against_evidence("No numbers here", {"100"})
        self.assertEqual(flagged, [])


class TestVerifyGrounding(unittest.TestCase):
    def test_per_agent_results(self):
        agent_outputs = {
            "technician": {"output": {"summary": "Price at 100.5 with rvol 1.5"}},
            "bull": {"output": {"summary": "Buy signal at 60% conviction"}},
        }
        evidence = {
            "price": {"live": 100.5},
            "technicals": {"rvol": 1.5},
            "analyst": {"buy_pct": 60},
        }
        result = verify_grounding(agent_outputs, evidence)
        self.assertTrue(result["valid"])
        self.assertIn("technician", result["per_agent"])
        self.assertIn("bull", result["per_agent"])
        self.assertTrue(result["per_agent"]["technician"]["valid"])
        self.assertTrue(result["per_agent"]["bull"]["valid"])

    def test_agent_with_ungrounded_number(self):
        agent_outputs = {
            "technician": {"output": {"summary": "Price is 999.9%"}},
        }
        evidence = {"price": {"live": 100.0}}
        result = verify_grounding(agent_outputs, evidence)
        self.assertFalse(result["valid"])
        self.assertFalse(result["per_agent"]["technician"]["valid"])
        self.assertIn("999.9%", result["per_agent"]["technician"]["flagged"])

    def test_empty_output(self):
        result = verify_grounding({}, {"price": {}})
        self.assertTrue(result["valid"])

    def test_none_output(self):
        result = verify_grounding(None, {"price": {}})
        self.assertTrue(result["valid"])


class TestScoutGrounding(unittest.TestCase):
    def test_scout_valid_with_screening_numbers(self):
        scout_output = {
            "output": {
                "shortlist": {
                    "large": [
                        {"symbol": "BHARTIARTL.NS", "day_change_pct": -2.78, "price": 1650.0},
                        {"symbol": "TCS.NS", "day_change_pct": 0.5, "price": 3109.25},
                    ],
                    "mid": [
                        {"symbol": "TATASTEEL.NS", "day_change_pct": 2.77, "price": 165.5},
                    ],
                    "small": [
                        {"symbol": "TANLA.NS", "day_change_pct": 1.97, "price": 542.0},
                    ],
                },
                "signals": [
                    "large: top mover BHARTIARTL.NS day change -2.78%",
                    "mid: top mover TATASTEEL.NS day change +2.77%",
                ],
                "summary": "Scanned TCS. Large top mover -2.78%. Mid top mover +2.77%.",
            }
        }
        stock_evidence = {
            "price": {"live": 3109.25},
            "technicals": {"rvol": 3.21},
        }
        screening_data = scout_output["output"]["shortlist"]

        result = verify_scout_grounding(scout_output, stock_evidence, screening_data)
        self.assertTrue(result["valid"], f"Scout should be valid, got flagged: {result['flagged']}")

    def test_scout_valid_with_stock_numbers(self):
        scout_output = {
            "output": {
                "shortlist": {},
                "signals": [],
                "summary": "Coverage 100%. Data gaps 0.",
                "data_coverage": 100,
            }
        }
        stock_evidence = {"price": {"live": 100}, "_computed": {"data_coverage": 100}}
        screening_data = {}

        result = verify_scout_grounding(scout_output, stock_evidence, screening_data)
        self.assertTrue(result["valid"])

    def test_scout_flagged_for_truly_unknown_numbers(self):
        scout_output = {
            "output": {
                "shortlist": {},
                "signals": [],
                "summary": "Random 9999.99% value found.",
            }
        }
        stock_evidence = {"price": {"live": 100}}
        screening_data = {}

        result = verify_scout_grounding(scout_output, stock_evidence, screening_data)
        self.assertFalse(result["valid"])
        self.assertIn("9999.99%", result["flagged"])

    def test_scout_empty_screening(self):
        scout_output = {"output": {"shortlist": {}, "signals": [], "summary": "No screening data."}}
        stock_evidence = {"price": {"live": 100}}
        result = verify_scout_grounding(scout_output, stock_evidence, {})
        self.assertTrue(result["valid"])


class TestOtherAgentsStrictGrounding(unittest.TestCase):
    """Technician, Fundamentalist, Newsdesk, Bull, Bear, Judge must be strictly
    grounded to the selected stock's evidence only."""

    def _make_stock_evidence(self):
        return {
            "price": {"live": 3109.25, "day_change_pct": -0.51, "volume": 5704563},
            "range_52w": {"high": 4149.17, "low": 2404.83, "position_pct": 40.38, "pct_from_high": -25.06},
            "technicals": {"rvol": 3.21, "price_vs_sma_pct": 4.14, "window_return_pct": 7.42, "day_range_position_pct": 47.85, "trend": "up"},
            "analyst": {"buy_pct": 31, "hold_pct": 41, "sell_pct": 28, "upside_pct": 6.53, "num_analysts": 15},
            "news": {"total": 9, "positive": 0, "negative": 0, "neutral": 3},
            "_computed": {"net_score": 22},
        }

    def test_technician_grounded(self):
        from agents.technician import run
        evidence = self._make_stock_evidence()
        agent_out = run(evidence)
        result = verify_grounding({"technician": agent_out}, evidence)
        self.assertTrue(
            result["per_agent"]["technician"]["valid"],
            f"Technician flagged: {result['per_agent']['technician']['flagged']}"
        )

    def test_fundamentalist_grounded(self):
        from agents.fundamentalist import run
        evidence = self._make_stock_evidence()
        agent_out = run(evidence)
        result = verify_grounding({"fundamentalist": agent_out}, evidence)
        self.assertTrue(
            result["per_agent"]["fundamentalist"]["valid"],
            f"Fundamentalist flagged: {result['per_agent']['fundamentalist']['flagged']}"
        )

    def test_newsdesk_grounded(self):
        from agents.newsdesk import run
        evidence = self._make_stock_evidence()
        agent_out = run(evidence)
        result = verify_grounding({"newsdesk": agent_out}, evidence)
        self.assertTrue(
            result["per_agent"]["newsdesk"]["valid"],
            f"Newsdesk flagged: {result['per_agent']['newsdesk']['flagged']}"
        )

    def test_bull_grounded(self):
        from agents.bull import run
        evidence = self._make_stock_evidence()
        agent_out = run(evidence)
        result = verify_grounding({"bull": agent_out}, evidence)
        self.assertTrue(
            result["per_agent"]["bull"]["valid"],
            f"Bull flagged: {result['per_agent']['bull']['flagged']}"
        )

    def test_bear_grounded(self):
        from agents.bear import run
        evidence = self._make_stock_evidence()
        agent_out = run(evidence)
        result = verify_grounding({"bear": agent_out}, evidence)
        self.assertTrue(
            result["per_agent"]["bear"]["valid"],
            f"Bear flagged: {result['per_agent']['bear']['flagged']}"
        )

    def test_judge_grounded(self):
        from agents.judge import run
        from engine.scoring import evaluate
        evidence = self._make_stock_evidence()
        scoring = evaluate(evidence)
        agent_out = run(evidence, scoring)
        result = verify_grounding({"judge": agent_out}, evidence)
        self.assertTrue(
            result["per_agent"]["judge"]["valid"],
            f"Judge flagged: {result['per_agent']['judge']['flagged']}"
        )

    def test_cross_stock_number_rejected_in_stock_agents(self):
        """A stock agent referencing a number NOT in the stock evidence should fail."""
        fake_agent = {
            "output": {
                "summary": "Stock is trading at 7777.77% which is from another stock"
            }
        }
        evidence = self._make_stock_evidence()
        result = verify_grounding({"technician": fake_agent}, evidence)
        self.assertFalse(result["per_agent"]["technician"]["valid"])


class TestPipelineGrounding(unittest.TestCase):
    def test_demo_pipeline_grounding(self):
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        os.environ["SECRET_KEY"] = "test"
        os.environ["DEMO_MODE"] = "true"
        import importlib
        import config as config_mod
        importlib.reload(config_mod)

        from database.db import init_db
        init_db(database_url="sqlite:///:memory:")

        from backend.services.analysis import run_pipeline
        result = run_pipeline("TCS.NS")

        self.assertTrue(
            result["grounding"]["valid"],
            f"Grounding failed: {result['grounding']['flagged']}"
        )

        per_agent = result["grounding"]["per_agent"]
        self.assertIn("scout", per_agent)
        self.assertIn("technician", per_agent)
        self.assertIn("bull", per_agent)
        self.assertIn("bear", per_agent)

        for name, check in per_agent.items():
            self.assertTrue(
                check["valid"],
                f"Agent '{name}' grounding failed: {check['flagged']}"
            )


class TestVerdictIntegrity(unittest.TestCase):
    def test_valid_verdict(self):
        verdict = {
            "winner": "Bull", "verdict": "BUY", "confidence": 8,
            "rationale": "Strong", "key_catalyst": "Volume",
            "bull_score": 60, "bear_score": 15, "net": 45,
        }
        result = verify_verdict_integrity(verdict, {})
        self.assertTrue(result["valid"])

    def test_missing_field(self):
        verdict = {"winner": "Bull"}
        result = verify_verdict_integrity(verdict, {})
        self.assertFalse(result["valid"])

    def test_invalid_verdict_value(self):
        verdict = {
            "winner": "Bull", "verdict": "STRONG_BUY", "confidence": 8,
            "rationale": "Test", "key_catalyst": "Test",
            "bull_score": 60, "bear_score": 15, "net": 45,
        }
        result = verify_verdict_integrity(verdict, {})
        self.assertFalse(result["valid"])

    def test_net_mismatch(self):
        verdict = {
            "winner": "Bull", "verdict": "BUY", "confidence": 8,
            "rationale": "Test", "key_catalyst": "Test",
            "bull_score": 60, "bear_score": 15, "net": 30,
        }
        result = verify_verdict_integrity(verdict, {})
        self.assertFalse(result["valid"])


if __name__ == "__main__":
    unittest.main()
