import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "AI_SKILL_LIBRARY"
V4 = LIB / "v4"


class V4AccelerationContractTests(unittest.TestCase):
    def setUp(self):
        self.checkpoint = json.loads((LIB / "checkpoint.json").read_text(encoding="utf-8"))
        self.router = yaml.safe_load((V4 / "stable/router.yaml").read_text(encoding="utf-8"))
        self.runtime = yaml.safe_load((V4 / "stable/runtime.yaml").read_text(encoding="utf-8"))
        self.context = yaml.safe_load((V4 / "stable/context.yaml").read_text(encoding="utf-8"))
        self.harmonization = yaml.safe_load((V4 / "stable/harmonization.yaml").read_text(encoding="utf-8"))
        self.projects = yaml.safe_load((LIB / "projects.yaml").read_text(encoding="utf-8"))

    def test_checkpoint_resolves_stable_acceleration_policy(self):
        expected = "AI_SKILL_LIBRARY/v4/stable/acceleration.yaml"
        self.assertEqual(self.checkpoint["stable_acceleration_path"], expected)
        self.assertTrue((ROOT / expected).is_file())

    def test_acceleration_cache_is_authority_and_freshness_safe(self):
        acceleration = yaml.safe_load((V4 / "stable/acceleration.yaml").read_text(encoding="utf-8"))
        self.assertIs(acceleration["authority"]["cache_or_index_never_outranks_authority"], True)
        exclusions = set(acceleration["cache"]["final_answer_cache_forbidden_for"])
        self.assertTrue({"live_or_current", "trading", "credentials", "destructive", "deployment", "financial_action"}.issubset(exclusions))
        self.assertIs(acceleration["retrieval"]["semantic_service_required"], False)
        self.assertEqual(acceleration["retrieval"]["fallback"], "lexical_and_canonical_files")

    def test_provider_routing_is_scheduling_not_authority(self):
        acceleration = yaml.safe_load((V4 / "stable/acceleration.yaml").read_text(encoding="utf-8"))
        provider = acceleration["provider_routing"]
        self.assertIs(provider["provider_output_is_authority"], False)
        self.assertIs(provider["majority_vote_for_truth"], False)
        self.assertIn("latency", provider["scheduling_signals"])
        self.assertIn("capability_fit", provider["scheduling_signals"])

    def test_typed_capsules_and_execution_graph_are_bounded(self):
        acceleration = yaml.safe_load((V4 / "stable/acceleration.yaml").read_text(encoding="utf-8"))
        typed = set(acceleration["typed_skill_contracts"]["required_fields"])
        self.assertTrue({"input_contract_id", "output_contract_id", "permission_ceiling", "freshness_requirement", "tools", "sources", "failure_mode"}.issubset(typed))
        graph = acceleration["execution_graph"]
        self.assertLessEqual(graph["max_parallel_tasks"], self.runtime["hard_limits"]["max_parallel_tasks"])
        self.assertLessEqual(graph["max_replans"], self.runtime["hard_limits"]["max_replans"])
        self.assertIs(graph["unbounded_recursion"], False)

    def test_router_places_acceleration_preflight_before_authority_execution(self):
        order = self.router["selection_order"]
        self.assertIn("acceleration_preflight", order)
        self.assertLess(order.index("task_router"), order.index("acceleration_preflight"))
        self.assertLess(order.index("acceleration_preflight"), order.index("project_authority_if_required"))
        self.assertLess(order.index("project_authority_if_required"), order.index("bounded_memory"))

    def test_fast_profile_remains_zero_local_and_external_semantic_free(self):
        fast = self.runtime["profiles"]["FAST"]
        self.assertEqual(fast["durable_memory_items"], 0)
        self.assertEqual(fast["tool_candidates"], 0)
        self.assertIs(fast["external_semantic_lookup"], False)
        self.assertEqual(fast["execution_graph_nodes"], 0)

    def test_harmonization_absorbs_upstreams_into_canonical_capabilities(self):
        upstream = self.harmonization["upstream_absorption"]
        categories = set(upstream["capability_categories"])
        self.assertTrue({"retrieval_index", "memory_context", "orchestration_graph", "provider_routing", "evaluation", "inference_serving", "cache"}.issubset(categories))
        self.assertIs(upstream["create_parallel_router"], False)
        self.assertIs(upstream["create_parallel_reasoning_authority"], False)
        self.assertEqual(upstream["equivalent_capability_action"], "strengthen_canonical_policy")

    def test_trading_authority_is_unchanged(self):
        trading = next(row for row in self.projects["projects"] if row["id"] == "trading")
        self.assertEqual(trading["authority"], "docs/checkpoints/CURRENT_HANDOFF.md")
        self.assertIn("multi_market_analysis", trading["load_only_when"])


if __name__ == "__main__":
    unittest.main()
