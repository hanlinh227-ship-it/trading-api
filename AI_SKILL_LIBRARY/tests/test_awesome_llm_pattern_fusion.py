import unittest
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.tools.legion import execution_pattern


ROOT = Path(__file__).resolve().parents[2]


class AwesomeLLMPatternFusionTests(unittest.TestCase):
    def test_pattern_policy_is_reference_only(self):
        payload = yaml.safe_load((ROOT / "AI_SKILL_LIBRARY/v4/legion/pattern_fusion.yaml").read_text(encoding="utf-8"))
        self.assertEqual(payload["canonical_source"], "Shubhamsaboo/awesome-llm-apps")
        self.assertEqual(payload["license"], "Apache-2.0")
        self.assertFalse(payload["code_reuse"])
        self.assertFalse(payload["routing_authority"])
        self.assertFalse(payload["reasoning_authority"])
        self.assertFalse(payload["mandatory_runtime_dependency"])
        self.assertNotIn("broadcast_all_models", payload["allowed_patterns"])

    def test_single_specialist_for_simple_bounded_task(self):
        self.assertEqual(execution_pattern({
            "complexity": "low",
            "independent_subtasks": 1,
            "needs_retrieval": False,
            "needs_tools": False,
            "has_image": False,
            "needs_checker": False,
        }), "single_specialist")

    def test_parallel_specialists_for_independent_multidomain_work(self):
        self.assertEqual(execution_pattern({
            "complexity": "high",
            "independent_subtasks": 3,
            "needs_retrieval": False,
            "needs_tools": False,
            "has_image": False,
            "needs_checker": False,
        }), "parallel_specialists")

    def test_maker_checker_for_material_change(self):
        self.assertEqual(execution_pattern({
            "complexity": "medium",
            "independent_subtasks": 1,
            "needs_retrieval": False,
            "needs_tools": False,
            "has_image": False,
            "needs_checker": True,
        }), "maker_checker")

    def test_corrective_rag_when_retrieval_needs_validation(self):
        self.assertEqual(execution_pattern({
            "complexity": "medium",
            "independent_subtasks": 1,
            "needs_retrieval": True,
            "retrieval_quality_uncertain": True,
            "needs_tools": False,
            "has_image": False,
            "needs_checker": False,
        }), "corrective_rag")

    def test_agentic_rag_for_multistep_retrieval(self):
        self.assertEqual(execution_pattern({
            "complexity": "high",
            "independent_subtasks": 1,
            "needs_retrieval": True,
            "retrieval_quality_uncertain": False,
            "retrieval_requires_iteration": True,
            "needs_tools": False,
            "has_image": False,
            "needs_checker": False,
        }), "agentic_rag")

    def test_mcp_router_for_specialized_tool_task(self):
        self.assertEqual(execution_pattern({
            "complexity": "medium",
            "independent_subtasks": 1,
            "needs_retrieval": False,
            "needs_tools": True,
            "mcp_specialist_required": True,
            "has_image": False,
            "needs_checker": False,
        }), "mcp_specialist_router")

    def test_multimodal_team_for_image_plus_cross_domain(self):
        self.assertEqual(execution_pattern({
            "complexity": "high",
            "independent_subtasks": 2,
            "needs_retrieval": False,
            "needs_tools": False,
            "has_image": True,
            "cross_domain_visual": True,
            "needs_checker": False,
        }), "multimodal_team")


if __name__ == "__main__":
    unittest.main()
