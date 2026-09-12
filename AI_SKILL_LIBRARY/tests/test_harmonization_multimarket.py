from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "AI_SKILL_LIBRARY"


class HarmonizationMultiMarketTests(unittest.TestCase):
    def load_yaml(self, relative_path):
        with (ROOT / relative_path).open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)

    def test_checkpoint_resolves_permanent_harmonization_layer(self):
        checkpoint = self.load_yaml("AI_SKILL_LIBRARY/checkpoint.json")
        path = checkpoint.get("stable_harmonization_path")
        self.assertEqual(path, "AI_SKILL_LIBRARY/v4/stable/harmonization.yaml")
        self.assertTrue((ROOT / path).exists())

    def test_future_upgrades_cannot_create_parallel_authority(self):
        harmonization = self.load_yaml("AI_SKILL_LIBRARY/v4/stable/harmonization.yaml")
        future = harmonization["future_upgrade_contract"]
        self.assertTrue(future["every_new_skill_or_upstream_upgrade_must_pass_harmonization"])
        self.assertTrue(future["checkpoint_resolved_policy_required"])
        self.assertTrue(future["do_not_create_parallel_brain"])
        self.assertTrue(future["do_not_replace_project_authority_silently"])

    def test_multi_market_analysis_is_bound_to_current_trading_authority(self):
        projects = self.load_yaml("AI_SKILL_LIBRARY/projects.yaml")
        trading = next(project for project in projects["projects"] if project["id"] == "trading")
        self.assertEqual(trading["status"], "CURRENT")
        self.assertEqual(trading["authority"], "docs/checkpoints/CURRENT_HANDOFF.md")
        self.assertEqual(trading["routed_by"], "trading_router")
        self.assertIn("multi_market_analysis", trading["load_only_when"])
        self.assertIn("Forex", trading["retired_execution_authorities"])
        self.assertIn("legacy multi-coin Bybit", trading["retired_execution_authorities"])

    def test_multi_market_analysis_is_a_trading_skill_not_a_new_authority(self):
        catalog = self.load_yaml("AI_SKILL_LIBRARY/skills/catalog.yaml")
        skill = next(row for row in catalog["skills"] if row["id"] == "multi_market_analysis")
        self.assertEqual(skill["domain"], "trading")
        self.assertEqual(skill["requires"], ["task_router"])
        self.assertIn("multi_asset_market_data", skill["tools"])
        self.assertNotIn("trade_execution", skill["tools"])
        self.assertNotIn("order_execution", skill["tools"])


if __name__ == "__main__":
    unittest.main()
