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
                "source_license_provenance",
                "duplicate_capability_detection",
            }.issubset(classes)
        )
        self.assertEqual(evals["scoring"]["protected_dimensions"], ["correctness", "verification", "safety", "authority"])

    def test_plain_language_policy_remains_active(self):
        presentation = load_yaml("AI_SKILL_LIBRARY/v4/stable/presentation.yaml")
        self.assertEqual(presentation["locale"], "vi")
        self.assertEqual(presentation["mode"], "plain")


if __name__ == "__main__":
    unittest.main()
