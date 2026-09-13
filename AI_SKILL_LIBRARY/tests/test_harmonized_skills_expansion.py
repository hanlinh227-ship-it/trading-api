import unittest
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.tools.compile_skill_gateway import compile_snapshot

ROOT = Path(__file__).resolve().parents[2]
SHA = "b" * 40


def load_yaml(relative: str) -> dict:
    with (ROOT / relative).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise AssertionError(f"expected mapping in {relative}")
    return data


class HarmonizedSkillsExpansionTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_yaml("AI_SKILL_LIBRARY/skills/catalog.yaml")
        self.router = load_yaml("AI_SKILL_LIBRARY/v4/stable/router.yaml")
        self.engineering = load_yaml("AI_SKILL_LIBRARY/v4/skills/engineering/manifest.yaml")
        self.trading = load_yaml("AI_SKILL_LIBRARY/v4/skills/trading/manifest.yaml")
        self.design_3d = load_yaml("AI_SKILL_LIBRARY/v4/skills/design_3d/manifest.yaml")
        self.by_id = {row["id"]: row for row in self.catalog["skills"]}

    def test_new_canonical_skills_have_one_domain_owner(self):
        expected = {
            "skill_engineering": "engineering",
            "eval_engineering": "engineering",
            "quant_validation": "trading",
            "asset_validation_3d": "design_3d",
        }
        domain_routes = self.router["domain_routes"]
        manifests = {
            "engineering": self.engineering,
            "trading": self.trading,
            "design_3d": self.design_3d,
        }
        for skill_id, domain in expected.items():
            self.assertIn(skill_id, self.by_id)
            self.assertNotIn("alias_of", self.by_id[skill_id])
            owners = [name for name, skill_ids in domain_routes.items() if skill_id in skill_ids]
            self.assertEqual(owners, [domain])
            self.assertIn(skill_id, manifests[domain]["skills"])

    def test_compiled_snapshot_contains_capsules_for_all_new_skills(self):
        snapshot = compile_snapshot(ROOT, SHA, generated_at="2026-09-13T00:00:00Z")
        for skill_id in (
            "skill_engineering",
            "eval_engineering",
            "quant_validation",
            "asset_validation_3d",
        ):
            self.assertIn(skill_id, snapshot["skills"])
            self.assertIn(skill_id, snapshot["capsules"])
            self.assertEqual(snapshot["capsules"][skill_id]["skill_id"], skill_id)
            self.assertTrue(snapshot["capsules"][skill_id]["capsule_hash"])

    def test_quant_validation_is_analysis_only_and_does_not_steal_backtest_build_intent(self):
        quant_validation = self.by_id["quant_validation"]
        quant_backtesting = self.by_id["quant_backtesting"]
        self.assertIn("validate this backtest", quant_validation["triggers"])
        self.assertNotIn("validate this backtest", quant_backtesting["triggers"])
        self.assertEqual(self.trading["permissions"], ["read_only"])
        self.assertTrue(self.trading["project_authority_required"])
        self.assertFalse(self.trading["research_may_grant_execution"])
        self.assertIn("quant_validation", self.trading["analysis_only_skills"])

    def test_blender_creation_and_asset_validation_have_distinct_owners(self):
        self.assertIn("blender", self.by_id["blender"]["triggers"])
        validation = self.by_id["asset_validation_3d"]
        self.assertIn("validate export", validation["triggers"])
        self.assertNotIn("blender", validation["triggers"])

    def test_existing_skills_absorb_equivalent_upstream_intents(self):
        self.assertIn("repository threat model", self.by_id["security"]["triggers"])
        self.assertIn("github actions failure", self.by_id["debugging"]["triggers"])
        self.assertIn("design system", self.by_id["ux_ui"]["triggers"])
        self.assertIn("design to code", self.by_id["product_design"]["triggers"])

    def test_vetted_upstreams_are_reference_patterns_not_reasoning_authority(self):
        fusion = load_yaml("AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml")
        upstreams = fusion["upstream_pattern_map"]
        expected = {
            "openai/skills",
            "agentskills/agentskills",
            "ml4t/skills",
            "ifBars/blender-agent-studio",
        }
        self.assertTrue(expected.issubset(upstreams))
        for repo in expected:
            row = upstreams[repo]
            self.assertIn(row["status"], {"approved_reference", "approved_reference_optional"})
            self.assertFalse(row.get("routing_authority", False))
            self.assertFalse(row.get("mandatory_runtime_dependency", False))

    def test_provenance_quarantine_record_exists_without_permission_expansion(self):
        path = ROOT / "AI_SKILL_LIBRARY/v4/evergreen/quarantine/harmonized_skills_expansion.yaml"
        self.assertTrue(path.is_file())
        record = load_yaml("AI_SKILL_LIBRARY/v4/evergreen/quarantine/harmonized_skills_expansion.yaml")
        self.assertEqual(record["routing_authority"], False)
        self.assertEqual(record["permission_expansion"], False)
        candidates = {row["repository"]: row for row in record["candidates"]}
        for repo in (
            "openai/skills",
            "agentskills/agentskills",
            "ml4t/skills",
            "ifBars/blender-agent-studio",
        ):
            self.assertIn(repo, candidates)
            self.assertTrue(candidates[repo]["license"])
            self.assertEqual(candidates[repo]["decision"], "reference_only")


if __name__ == "__main__":
    unittest.main()
