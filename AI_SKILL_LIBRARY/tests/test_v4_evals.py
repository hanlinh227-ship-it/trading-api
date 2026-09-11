import unittest

from AI_SKILL_LIBRARY.v4.tools.evaluate import compare_candidate
from AI_SKILL_LIBRARY.v4.tools.reputation import update_reputation


class V4EvalTests(unittest.TestCase):
    def test_protected_regression_blocks_candidate(self):
        stable = {"correctness": 0.95, "authority": 1.0, "security": 1.0, "verification": 0.96, "latency_efficiency": 0.75}
        candidate = {"correctness": 0.94, "authority": 1.0, "security": 1.0, "verification": 0.96, "latency_efficiency": 0.90}
        result = compare_candidate(stable, candidate)
        self.assertFalse(result["promotable"])
        self.assertIn("correctness", result["protected_regressions"])

    def test_unprotected_gain_can_pass_without_protected_regression(self):
        stable = {"correctness": 0.95, "authority": 1.0, "security": 1.0, "verification": 0.96, "latency_efficiency": 0.75}
        candidate = {"correctness": 0.95, "authority": 1.0, "security": 1.0, "verification": 0.96, "latency_efficiency": 0.82}
        result = compare_candidate(stable, candidate)
        self.assertTrue(result["promotable"])

    def test_reputation_is_bounded(self):
        record = {"score": 0.95, "observations": 10}
        result = update_reputation(record, success=True, verification=True, latency_score=1.0)
        self.assertGreaterEqual(result["score"], 0.0)
        self.assertLessEqual(result["score"], 1.0)
        self.assertEqual(result["observations"], 11)


if __name__ == "__main__":
    unittest.main()
