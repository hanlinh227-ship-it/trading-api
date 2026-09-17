import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.control_plane.federation import (
    compute_routing_metrics, load_specialists, plan_execution, promotion_decision,
)

ROOT = Path(__file__).resolve().parents[2]
GROUPS = {"GENERAL_REASONING", "DEEP_REASONING", "FAST_RESPONSE", "CODING", "DEBUGGING", "CODE_REVIEW", "TESTING", "MATH", "SCIENCE", "VIETNAMESE", "MULTILINGUAL", "LONG_CONTEXT", "RESEARCH", "RERANKING", "EMBEDDING", "VISION", "OCR", "DOCUMENT", "AUDIO", "SPEECH", "TRADING_RESEARCH", "TRADING_CODE", "CREATIVE", "ANIMATION", "VERIFIER", "PLANNING"}


class FederationTests(unittest.TestCase):
    def test_all_specialist_groups_have_required_contract_fields(self):
        rows = load_specialists(ROOT)
        self.assertEqual(set(rows), GROUPS)
        for row in rows.values():
            self.assertTrue(row["capabilities"])
            self.assertTrue(row["evidence_requirements"])
            self.assertTrue(row["fallback_behavior"])
            self.assertTrue(row["verification_strategy"])

    def test_profiles_are_bounded_and_router_remains_authority(self):
        selection = {"primary_model": {"candidate_key": "p"}, "supporting_models": [{"candidate_key": str(i)} for i in range(6)], "verifier": "VERIFIER"}
        fast = plan_execution("FAST", selection, ["CODING"])
        standard = plan_execution("STANDARD", selection, ["CODING", "TESTING"])
        deep = plan_execution("DEEP", selection, ["CODING", "TESTING", "CODE_REVIEW", "DEBUGGING", "PLANNING"])
        self.assertEqual(len(fast["models"]), 1)
        self.assertLessEqual(len(standard["models"]), 2)
        self.assertLessEqual(len(deep["models"]), 4)
        self.assertEqual(deep["routed_by"], "task_router")
        self.assertFalse(deep["routing_authority"])

    def test_challenger_requires_empirical_evidence_and_no_protected_regression(self):
        champion = {"role": "QUALITY_CHAMPION", "quality": .80, "latency": 100, "evidence_refs": ["base:1"], "protected": {"security": 1, "vietnamese": .8}}
        challenger = {"role": "CHALLENGER", "quality": .90, "latency": 90, "evidence_refs": [], "protected": {"security": 1, "vietnamese": .8}}
        self.assertFalse(promotion_decision(champion, challenger)["promote"])
        challenger["evidence_refs"] = ["run:1"]
        self.assertTrue(promotion_decision(champion, challenger)["promote"])
        challenger["protected"]["security"] = .9
        self.assertFalse(promotion_decision(champion, challenger)["promote"])

    def test_routing_learning_metrics_do_not_claim_router_authority(self):
        metrics = compute_routing_metrics([
            {"success": True, "regret": 0.1, "oversized": False, "selection_failed": False, "unnecessary_cold_start": True},
            {"success": False, "regret": 0.4, "oversized": True, "selection_failed": True, "unnecessary_cold_start": False},
        ])
        self.assertEqual(metrics["RoutingSuccessRate"], .5)
        self.assertEqual(metrics["FailedSelectionRate"], .5)
        self.assertFalse(metrics["may_replace_task_router"])


if __name__ == "__main__": unittest.main()
