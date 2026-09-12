import json
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "AI_SKILL_LIBRARY"


class LivePricePolicyTests(unittest.TestCase):
    def test_checkpoint_resolves_live_price_policy(self):
        checkpoint = json.loads((LIB / "checkpoint.json").read_text(encoding="utf-8"))
        self.assertIn("live_price_policy_path", checkpoint)
        path = ROOT / checkpoint["live_price_policy_path"]
        self.assertTrue(path.is_file())

    def test_live_price_policy_is_fail_closed_and_venue_bound(self):
        checkpoint = json.loads((LIB / "checkpoint.json").read_text(encoding="utf-8"))
        policy = yaml.safe_load((ROOT / checkpoint["live_price_policy_path"]).read_text(encoding="utf-8"))
        execution = policy["execution"]
        freshness = policy["freshness"]
        cross_venue = policy["cross_venue"]

        self.assertEqual(execution["default_production_venue"], "bybit")
        self.assertEqual(execution["default_production_instrument"], "perpetual")
        self.assertEqual(freshness["executable_target_ms"], 2000)
        self.assertEqual(freshness["executable_hard_stale_ms"], 5000)
        self.assertEqual(freshness["contextual_max_age_ms"], 10000)
        self.assertEqual(cross_venue["divergence_bps"], 30)
        self.assertTrue(policy["safety"]["fail_closed"])
        self.assertFalse(policy["safety"]["allow_cross_venue_execution_substitution"])
        self.assertTrue(policy["safety"]["require_source_timestamp"])

    def test_cloud_runtime_declares_live_price_policy_pointer(self):
        manifest = yaml.safe_load((LIB / "runtime/cloud_runtime.yaml").read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["live_price_policy_path"],
            "AI_SKILL_LIBRARY/skills/registry/live_price_policy.yaml",
        )


if __name__ == "__main__":
    unittest.main()
