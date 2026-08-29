import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import unittest
from engine.verifier import verify_grounding, verify_verdict_integrity, _extract_numbers


class TestNumberExtraction(unittest.TestCase):
    def test_percentages(self):
        nums = _extract_numbers("Price is up 5.2% today")
        self.assertIn("5.2%", nums)

    def test_scores(self):
        nums = _extract_numbers("Confidence: 8/10, Bull score: 65")
        self.assertTrue(len(nums) > 0)

    def test_empty(self):
        nums = _extract_numbers("")
        self.assertEqual(nums, [])

    def test_none(self):
        nums = _extract_numbers(None)
        self.assertEqual(nums, [])


class TestGroundingVerification(unittest.TestCase):
    def test_valid_output(self):
        evidence = {
            "price": {"live": 3500},
            "technicals": {"rvol": 1.5},
        }
        output = "Current price is 3500, volume is normal at 1.5x"
        result = verify_grounding(output, evidence)
        self.assertTrue(result["valid"])

    def test_empty_output(self):
        result = verify_grounding("", {"price": {}})
        self.assertTrue(result["valid"])

    def test_none_output(self):
        result = verify_grounding(None, {"price": {}})
        self.assertTrue(result["valid"])


class TestVerdictIntegrity(unittest.TestCase):
    def test_valid_verdict(self):
        verdict = {
            "winner": "Bull",
            "verdict": "BUY",
            "confidence": 8,
            "rationale": "Strong signals",
            "key_catalyst": "Volume spike",
            "bull_score": 60,
            "bear_score": 15,
            "net": 45,
        }
        result = verify_verdict_integrity(verdict, {})
        self.assertTrue(result["valid"])

    def test_missing_fields(self):
        verdict = {"winner": "Bull"}
        result = verify_verdict_integrity(verdict, {})
        self.assertFalse(result["valid"])
        self.assertTrue(len(result["issues"]) > 0)

    def test_invalid_verdict_value(self):
        verdict = {
            "winner": "Bull",
            "verdict": "STRONG_BUY",
            "confidence": 8,
            "rationale": "Test",
            "key_catalyst": "Test",
            "bull_score": 60,
            "bear_score": 15,
            "net": 45,
        }
        result = verify_verdict_integrity(verdict, {})
        self.assertFalse(result["valid"])

    def test_net_mismatch(self):
        verdict = {
            "winner": "Bull",
            "verdict": "BUY",
            "confidence": 8,
            "rationale": "Test",
            "key_catalyst": "Test",
            "bull_score": 60,
            "bear_score": 15,
            "net": 30,
        }
        result = verify_verdict_integrity(verdict, {})
        self.assertFalse(result["valid"])


if __name__ == "__main__":
    unittest.main()
