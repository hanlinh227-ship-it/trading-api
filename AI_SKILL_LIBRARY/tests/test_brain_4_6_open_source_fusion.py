import unittest
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.tools.compile_skill_gateway import compile_snapshot

ROOT = Path(__file__).resolve().parents[2]
SHA = "d" * 40


def load_yaml(rel: str) -> dict:
    return yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))


class Brain46OpenSourceFusionTests(unittest.TestCase):
    def test_skill_count_and_capsules_stay_109(self):
        snapshot = compile_snapshot(ROOT, SHA, generated_at="2026-09-13T00:00:00Z")
        self.assertEqual(len(snapshot["skills"]), 109)
        self.assertEqual(len(snapshot["capsules"]), 109)

    def test_brain_46_candidates_have_zero_authority_and_no_permission_expansion(self):
        record = load_yaml("AI_SKILL_LIBRARY/v4/evergreen/quarantine/brain_4_6_open_source_fusion.yaml")
        self.assertFalse(record["routing_authority"])
        self.assertFalse(record["reasoning_authority"])
        self.assertFalse(record["permission_expansion"])
        self.assertFalse(record["mandatory_runtime_dependency"])
        self.assertTrue(record["zero_local_preserved"])
        for row in record["candidates"]:
            with self.subTest(repository=row["repository"]):
                self.assertEqual(row["decision"], "reference_only")
                self.assertFalse(row["code_reuse"])
                self.assertFalse(row["permission_expansion"])

    def test_fast_and_trading_contracts_remain_closed(self):
        harmonization = load_yaml("AI_SKILL_LIBRARY/v4/stable/harmonization.yaml")
        trading = load_yaml("AI_SKILL_LIBRARY/v4/skills/trading/manifest.yaml")
        self.assertEqual(harmonization["cognitive_execution"]["FAST"]["max_revisions"], 0)
        self.assertFalse(harmonization["cognitive_execution"]["FAST"]["maker_checker"])
        self.assertEqual(trading["permissions"], ["read_only"])
        self.assertTrue(trading["project_authority_required"])
        self.assertFalse(trading["research_may_grant_execution"])
        self.assertEqual(trading["execution_authority"], "external_project_only")

    def test_fusion_map_contains_vetted_46_sources_as_reference_only(self):
        fusion = load_yaml("AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml")
        required = {
            "google/adk-python",
            "openai/openai-agents-python",
            "NVIDIA/garak",
            "langchain-ai/open-swe",
            "nautechsystems/nautilus_trader",
            "KhronosGroup/glTF-Validator",
            "mikedh/trimesh",
            "isl-org/Open3D",
            "stanfordnlp/dspy",
            "figma/code-connect",
        }
        self.assertTrue(required.issubset(fusion["upstream_pattern_map"]))
        for repo in required:
            with self.subTest(repository=repo):
                row = fusion["upstream_pattern_map"][repo]
                self.assertFalse(row.get("routing_authority", False))
                self.assertFalse(row.get("mandatory_runtime_dependency", False))
                self.assertFalse(row.get("code_reuse", False))

    def test_harmonization_requires_upgrade_quality_and_bottleneck_checks(self):
        harmonization = load_yaml("AI_SKILL_LIBRARY/v4/stable/harmonization.yaml")
        required = set(harmonization["candidate_intake"]["require"])
        self.assertTrue(
            {
                "maintenance_status",
                "permission_ceiling",
                "performance_impact",
                "authority_impact",
                "strengthen_existing_skill_first",
            }.issubset(required)
        )
        bottlenecks = harmonization["bottleneck_prevention"]
        self.assertTrue(bottlenecks["required_for_upgrade"])
        self.assertTrue(bottlenecks["checks"]["fast_latency"]["preserve_zero_external_routing_calls"])
        self.assertTrue(bottlenecks["promotion_blocked_on_unresolved_bottleneck"])

    def test_evals_cover_new_fusion_quality_dimensions(self):
        evals = load_yaml("AI_SKILL_LIBRARY/evals.yaml")
        classes = set(evals["benchmark_classes"])
        self.assertTrue(
            {
                "repository_workflow",
                "quant_realism",
                "asset_validation_3d",
                "design_system_validation",
                "prompt_regression",
                "game_runtime_validation",
                "source_license_provenance",
                "duplicate_capability_detection",
            }.issubset(classes)
        )
        self.assertEqual(evals["scoring"]["protected_dimensions"], ["correctness", "verification", "safety", "authority"])

    def test_active_registry_keeps_new_sources_reference_only_and_within_budgets(self):
        registry = load_yaml("AI_SKILL_LIBRARY/sources.yaml")
        rows = registry["sources"]
        by_repo = {row["repo"]: row for row in rows}
        active_refs = {
            "google/adk-python",
            "openai/openai-agents-python",
            "NVIDIA/garak",
            "langchain-ai/open-swe",
            "KhronosGroup/glTF-Validator",
            "mikedh/trimesh",
            "isl-org/Open3D",
            "stanfordnlp/dspy",
            "figma/code-connect",
        }
        for repo in active_refs:
            with self.subTest(repository=repo):
                row = by_repo[repo]
                self.assertEqual(row["usage_tier"], "REFERENCE_ONLY")
                self.assertFalse(row["rag"])
                self.assertFalse(row["training"])
                self.assertEqual(row["tier"], "COLD")
        self.assertNotIn("nautechsystems/nautilus_trader", by_repo)
        self.assertNotIn("langfuse/langfuse", by_repo)
        policy = registry["policy"]
        self.assertLessEqual(len(rows), policy["max_total_sources"])
        categories = {}
        for row in rows:
            categories[row["category"]] = categories.get(row["category"], 0) + 1
        for category, count in categories.items():
            with self.subTest(category=category):
                self.assertLessEqual(count, policy["max_sources_per_category"])

    def test_domain_manifests_add_quality_without_widening_permissions(self):
        engineering = load_yaml("AI_SKILL_LIBRARY/v4/skills/engineering/manifest.yaml")
        trading = load_yaml("AI_SKILL_LIBRARY/v4/skills/trading/manifest.yaml")
        design_2d = load_yaml("AI_SKILL_LIBRARY/v4/skills/design_2d/manifest.yaml")
        design_3d = load_yaml("AI_SKILL_LIBRARY/v4/skills/design_3d/manifest.yaml")
        prompt = load_yaml("AI_SKILL_LIBRARY/v4/skills/prompt_media/manifest.yaml")
        game = load_yaml("AI_SKILL_LIBRARY/v4/skills/game/manifest.yaml")
        self.assertEqual(engineering["permissions"], ["read_only", "reversible_write"])
        self.assertEqual(trading["permissions"], ["read_only"])
        self.assertEqual(design_2d["permissions"], ["read_only"])
        self.assertEqual(design_3d["permissions"], ["read_only"])
        self.assertEqual(prompt["permissions"], ["read_only"])
        self.assertEqual(game["permissions"], ["read_only", "reversible_write"])
        self.assertIn("repository_workflow", engineering["evals"])
        self.assertIn("quant_realism", trading["evals"])
        self.assertIn("design_system_validation", design_2d["evals"])
        self.assertIn("asset_validation_3d", design_3d["evals"])
        self.assertIn("prompt_regression", prompt["evals"])
        self.assertIn("game_runtime_validation", game["evals"])

    def test_plain_language_policy_remains_active(self):
        presentation = load_yaml("AI_SKILL_LIBRARY/v4/stable/presentation.yaml")
        self.assertEqual(presentation["locale"], "vi")
        self.assertEqual(presentation["mode"], "plain")

    def test_47_selective_sources_are_vetted_without_new_authority(self):
        registry = load_yaml("AI_SKILL_LIBRARY/sources.yaml")
        fusion = load_yaml("AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml")
        by_repo = {row["repo"]: row for row in registry["sources"]}
        expected = {
            "modelcontextprotocol/python-sdk": "RAG_ONLY",
            "docling-project/docling": "RAG_ONLY",
            "microsoft/graphrag": "REFERENCE_ONLY",
            "UKGovernmentBEIS/inspect_ai": "RAG_ONLY",
            "ossf/scorecard": "RAG_ONLY",
            "aquasecurity/trivy": "RAG_ONLY",
            "Arize-ai/openinference": "RAG_ONLY",
            "microsoft/playwright": "RAG_ONLY",
        }
        for repo, tier in expected.items():
            with self.subTest(repository=repo):
                self.assertIn(repo, by_repo)
                self.assertEqual(by_repo[repo]["usage_tier"], tier)
                self.assertIn(repo, fusion["upstream_pattern_map"])
                row = fusion["upstream_pattern_map"][repo]
                self.assertFalse(row.get("routing_authority", False))
                self.assertFalse(row.get("mandatory_runtime_dependency", False))
                self.assertFalse(row.get("code_reuse", False))

    def test_47_contracts_cover_mcp_documents_graph_eval_intake_observability_browser(self):
        fusion = load_yaml("AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml")
        retrieval = load_yaml("AI_SKILL_LIBRARY/v4/stable/retrieval.yaml")
        observability = load_yaml("AI_SKILL_LIBRARY/v4/stable/observability.yaml")
        evals = load_yaml("AI_SKILL_LIBRARY/evals.yaml")
        self.assertIn("mcp_interoperability", fusion)
        self.assertTrue(fusion["mcp_interoperability"]["permission_ceiling_required"])
        self.assertIn("document_intelligence", fusion)
        self.assertTrue(fusion["document_intelligence"]["structured_extraction_before_ocr"])
        self.assertIn("graph_retrieval", retrieval)
        self.assertFalse(retrieval["graph_retrieval"]["routing_authority"])
        self.assertEqual(retrieval["graph_retrieval"]["profiles"], ["STANDARD", "DEEP"])
        self.assertIn("ai_semantics", observability)
        self.assertTrue(observability["ai_semantics"]["sensitive_payloads_forbidden"])
        required = {
            "mcp_contract_integrity",
            "document_fidelity",
            "graph_retrieval_safety",
            "oss_intake_security",
            "observability_sanitization",
            "browser_runtime_verification",
        }
        self.assertTrue(required.issubset(set(evals["benchmark_classes"])))

    def test_47_keeps_skill_count_fast_and_trading_invariants(self):
        snapshot = compile_snapshot(ROOT, SHA, generated_at="2026-09-14T00:00:00Z")
        budgets = load_yaml("AI_SKILL_LIBRARY/v4/stable/budgets.yaml")
        trading = load_yaml("AI_SKILL_LIBRARY/v4/skills/trading/manifest.yaml")
        self.assertEqual(len(snapshot["skills"]), 109)
        self.assertEqual(len(snapshot["capsules"]), 109)
        self.assertEqual(budgets["profiles"]["FAST"]["max_external_routing_calls"], 0)
        self.assertEqual(budgets["profiles"]["FAST"]["max_source_candidates"], 0)
        self.assertEqual(trading["permissions"], ["read_only"])
        self.assertFalse(trading["research_may_grant_execution"])


if __name__ == "__main__":
    unittest.main()
