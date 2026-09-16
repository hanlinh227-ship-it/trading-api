from pathlib import Path
import unittest

from AI_SKILL_LIBRARY.v4.tools.compile_skill_gateway import compile_snapshot


ROOT = Path(__file__).resolve().parents[2]
AUTONOMOUS_TRIGGERS = {
    "quét market",
    "tìm entry",
    "quét thị trường",
    "tìm lệnh",
    "tìm lệnh tốt nhất",
    "tìm lệnh tốt nhất hiện tại",
    "quét đa thị trường",
    "quét toàn bộ thị trường",
    "có setup nào không",
    "có lệnh nào không",
    "find best trade",
    "scan markets",
    "best setup",
}


class AutonomousMarketRoutingTests(unittest.TestCase):
    def test_multi_market_analysis_owns_one_command_autopilot_intents(self):
        snapshot = compile_snapshot(ROOT, "0" * 40, generated_at="2026-09-16T00:00:00Z")
        multi_market = snapshot["skills"]["multi_market_analysis"]
        triggers = set(multi_market["triggers"])

        self.assertTrue(AUTONOMOUS_TRIGGERS.issubset(triggers))
        self.assertIn("TOP_SETUP", multi_market["output_contract"])
        self.assertIn("NO_TRADE", multi_market["output_contract"])
        self.assertIn("research", multi_market["output_contract"].lower())

    def test_v3_output_contract_exposes_autonomous_acquisition_and_research_levels(self):
        snapshot = compile_snapshot(ROOT, "0" * 40, generated_at="2026-09-16T00:00:00Z")
        contract = snapshot["skills"]["multi_market_analysis"]["output_contract"]
        normalized = contract.lower()

        self.assertIn("capabilityversion 3", normalized)
        self.assertIn("dataacquisitionplan", normalized)
        self.assertIn("live / context_only / gap", normalized)
        self.assertIn("entry/sl/tp", normalized)
        self.assertIn("research-only", normalized)
        self.assertIn("btc", normalized)

    def test_legacy_trading_router_aliases_yield_to_canonical_trigger_owner(self):
        snapshot = compile_snapshot(ROOT, "0" * 40, generated_at="2026-09-16T00:00:00Z")
        trading_router_aliases = set(snapshot["routing_aliases"].get("trading_router", []))
        multi_market_triggers = set(snapshot["skills"]["multi_market_analysis"]["triggers"])

        for phrase in {"quét market", "tìm entry", "quét thị trường", "quét đa thị trường"}:
            self.assertIn(phrase, multi_market_triggers)
            self.assertNotIn(phrase, trading_router_aliases)

    def test_canonical_skill_count_is_unchanged(self):
        snapshot = compile_snapshot(ROOT, "0" * 40, generated_at="2026-09-16T00:00:00Z")
        self.assertEqual(len(snapshot["skills"]), 109)
        self.assertEqual(len(snapshot["capsules"]), 109)


if __name__ == "__main__":
    unittest.main()
