import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "AI_SKILL_LIBRARY"


class MultiCoinScannerPolicyTests(unittest.TestCase):
    def test_checkpoint_resolves_research_only_scanner_policy(self):
        checkpoint = json.loads((LIB / "checkpoint.json").read_text(encoding="utf-8"))
        self.assertEqual(
            checkpoint["multi_coin_scanner_policy_path"],
            "AI_SKILL_LIBRARY/skills/registry/multi_coin_scanner_policy.yaml",
        )
        policy_path = ROOT / checkpoint["multi_coin_scanner_policy_path"]
        self.assertTrue(policy_path.is_file())
        policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
        self.assertEqual(policy["authority_token"], "MULTI-COIN-USDT-PERP-A-PLUS-SCANNER-1.0")
        self.assertIs(policy["research_only"], True)
        self.assertIs(policy["production_execution_authority"], False)
        self.assertEqual(policy["venues"], ["bybit", "binance", "okx"])
        self.assertEqual(policy["instrument"], "perpetual")
        self.assertEqual(policy["quote_currency"], "USDT")
        self.assertEqual(policy["eligibility"]["min_venue_coverage"], 2)
        self.assertNotIn("preferred_symbol", policy)
        self.assertNotIn("btc_bonus", policy)

    def test_scanner_thresholds_are_configured_and_live_price_semantics_are_reused(self):
        checkpoint = json.loads((LIB / "checkpoint.json").read_text(encoding="utf-8"))
        policy = yaml.safe_load((ROOT / checkpoint["multi_coin_scanner_policy_path"]).read_text(encoding="utf-8"))
        thresholds = policy["thresholds"]
        for key in (
            "broad_candidate_limit",
            "deep_candidate_limit",
            "min_quote_volume_usd",
            "max_spread_bps",
            "min_near_touch_depth_usd",
            "min_candle_history",
            "min_reward_risk",
            "tie_tolerance_score",
        ):
            self.assertGreater(thresholds[key], 0, key)
        self.assertEqual(
            policy["live_price_policy_path"],
            "AI_SKILL_LIBRARY/skills/registry/live_price_policy.yaml",
        )
        self.assertTrue(policy["safety"]["fail_closed"])
        self.assertFalse(policy["safety"]["allow_scan_to_execution_promotion"])

    def test_cloud_runtime_exposes_policy_pointer_without_execution_widening(self):
        runtime = yaml.safe_load((LIB / "runtime/cloud_runtime.yaml").read_text(encoding="utf-8"))
        self.assertEqual(
            runtime["multi_coin_scanner_policy_path"],
            "AI_SKILL_LIBRARY/skills/registry/multi_coin_scanner_policy.yaml",
        )
        self.assertIs(runtime["high_risk_cloud_execution"], False)
        self.assertEqual(runtime["default_execution_mode"], "research_safe_only")


if __name__ == "__main__":
    unittest.main()
