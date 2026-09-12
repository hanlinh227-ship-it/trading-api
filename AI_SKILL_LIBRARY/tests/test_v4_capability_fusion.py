from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "AI_SKILL_LIBRARY"


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


class V4CapabilityFusionTests(unittest.TestCase):
    def test_checkpoint_discovers_canonical_capability_fusion(self):
        checkpoint = load_json(LIB / "checkpoint.json")
        expected = "AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml"
        self.assertEqual(checkpoint.get("stable_capability_fusion_path"), expected)
        self.assertTrue((ROOT / expected).is_file())

    def test_fusion_preserves_single_authority_and_zero_local_runtime(self):
        fusion = load_yaml(LIB / "v4/stable/capability_fusion.yaml")
        policy = fusion["policy"]
        self.assertTrue(policy["single_authority_chain"])
        self.assertTrue(policy["upstream_is_reference_not_authority"])
        self.assertTrue(policy["mandatory_external_runtime_dependency"] is False)
        self.assertTrue(policy["zero_local_cloud_runtime_preserved"])

    def test_fast_knowledge_plane_is_safe_and_freshness_closed(self):
        fusion = load_yaml(LIB / "v4/stable/capability_fusion.yaml")
        fast = fusion["fast_knowledge_plane"]
        self.assertTrue(fast["exact_cache"])
        self.assertTrue(fast["semantic_cache"])
        self.assertGreaterEqual(float(fast["semantic_similarity_min"]), 0.90)
        forbidden = set(fast["cache_forbidden_for"])
        required = {
            "live_or_current_state",
            "trading_entry_or_execution",
            "credentials_or_secrets",
            "destructive_action",
            "private_connected_source_content",
            "deployment_or_runtime_claim",
        }
        self.assertTrue(required.issubset(forbidden))
        self.assertIn("authority_revision", fast["compatibility_fingerprint"])
        self.assertIn("primary_skill", fast["compatibility_fingerprint"])

        runtime = load_yaml(LIB / "v4/stable/runtime.yaml")
        profile = runtime["profiles"]["FAST"]
        self.assertEqual(profile["durable_memory_items"], 0)
        self.assertEqual(profile["tool_candidates"], 0)
        self.assertEqual(profile["max_bridge_nodes"], 0)
        self.assertFalse(profile["preload_trading"])
        self.assertIn("fast_knowledge_plane", profile["stages"])

    def test_retrieval_and_index_are_optional_and_authority_filtered(self):
        fusion = load_yaml(LIB / "v4/stable/capability_fusion.yaml")
        retrieval = fusion["retrieval_plane"]
        self.assertEqual(retrieval["index_backend"], "pluggable_optional")
        self.assertEqual(retrieval["on_index_unavailable"], "fallback_to_canonical_retrieval")
        self.assertIn("authority_filter", retrieval["stages"])
        self.assertIn("freshness_filter", retrieval["stages"])
        self.assertIn("rerank", retrieval["stages"])
        self.assertIn("dedupe", retrieval["stages"])

        context = load_yaml(LIB / "v4/stable/context.yaml")
        self.assertTrue(context["semantic_index"]["optional"])
        self.assertFalse(context["semantic_index"]["routing_authority"])
        self.assertTrue(context["semantic_index"]["authority_filter_required"])

    def test_execution_graph_and_typed_contracts_are_bounded(self):
        fusion = load_yaml(LIB / "v4/stable/capability_fusion.yaml")
        graph = fusion["execution_graph"]
        self.assertTrue(graph["bounded"])
        self.assertLessEqual(graph["max_nodes_deep"], 12)
        self.assertLessEqual(graph["max_parallel_deep"], 4)
        self.assertLessEqual(graph["max_resume_attempts"], 2)
        self.assertFalse(graph["persist_hidden_reasoning"])

        typed = fusion["typed_capability_contracts"]
        self.assertTrue(typed["input_schema_required"])
        self.assertTrue(typed["output_contract_required"])
        self.assertTrue(typed["permission_ceiling_required"])
        self.assertEqual(typed["on_schema_failure"], "fail_closed")
        self.assertEqual(typed["on_permission_expansion"], "fail_closed")

    def test_memory_remains_selective_private_and_authority_subordinate(self):
        memory = load_yaml(LIB / "v4/stable/memory.yaml")
        policy = memory["policy"]
        self.assertTrue(policy["current_authority_precedes_memory"])
        self.assertTrue(policy["retrieve_before_write"])
        self.assertTrue(memory["semantic_index_adapter"]["optional"])
        self.assertFalse(memory["semantic_index_adapter"]["authority"])
        self.assertEqual(memory["consolidation"]["conflict_action"], "reverify_or_supersede")
        self.assertIn("secrets", memory["privacy"]["durable_exclusions"])

    def test_evals_cover_retrieval_cache_adversarial_and_latency(self):
        evals = load_yaml(LIB / "evals.yaml")
        classes = set(evals["benchmark_classes"])
        required = {
            "routing",
            "retrieval_relevance",
            "cache_safety",
            "authority_preservation",
            "adversarial_prompt_resistance",
            "provider_fallback",
            "latency",
            "answer_quality",
        }
        self.assertTrue(required.issubset(classes))
        protected = set(evals["scoring"]["protected_dimensions"])
        self.assertTrue({"correctness", "verification", "safety", "authority"}.issubset(protected))

    def test_harmonization_absorbs_patterns_without_parallel_framework_authority(self):
        harmonization = load_yaml(LIB / "v4/stable/harmonization.yaml")
        future = harmonization["future_upgrade_contract"]
        self.assertTrue(future["every_new_capability_pattern_must_pass_harmonization"])
        self.assertTrue(future["prefer_native_contract_over_framework_dependency"])
        self.assertTrue(future["do_not_create_parallel_brain"])

    def test_approved_upstream_references_are_registered_without_training(self):
        sources = load_yaml(LIB / "sources.yaml")
        rows = {row.get("repo"): row for row in sources.get("sources", []) if isinstance(row, dict)}
        expected = {
            "langchain-ai/langgraph",
            "pydantic/pydantic-ai",
            "deepset-ai/haystack",
            "qdrant/qdrant",
            "mem0ai/mem0",
            "promptfoo/promptfoo",
            "sgl-project/sglang",
            "zilliztech/GPTCache",
        }
        self.assertTrue(expected.issubset(rows))
        for repo in expected:
            self.assertFalse(rows[repo]["training"], repo)
            self.assertIn(rows[repo]["usage_tier"], {"RAG_ONLY", "REFERENCE_ONLY"}, repo)


if __name__ == "__main__":
    unittest.main()
