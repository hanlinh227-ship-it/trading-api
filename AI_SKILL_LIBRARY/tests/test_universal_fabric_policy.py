from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load(rel: str) -> dict:
    return yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))


class UniversalFabricPolicyTests(unittest.TestCase):
    def test_initial_user_adapters_and_internal_evergreen_are_non_authoritative(self):
        rows = load("AI_SKILL_LIBRARY/v4/adapters/registry.yaml")["adapters"]
        users = {r["id"] for r in rows if r.get("principal_type", "user") == "user"}
        internal = {r["id"] for r in rows if r.get("principal_type") == "internal"}
        self.assertEqual(users, {"chatgpt", "claude", "gemini"})
        self.assertEqual(internal, {"evergreen"})
        self.assertTrue(all(r["routing_authority"] is False for r in rows))
        self.assertTrue(all(r["reasoning_authority"] is False for r in rows))
        self.assertEqual(len({r["token_binding"] for r in rows}), len(rows))
        evergreen = next(r for r in rows if r["id"] == "evergreen")
        self.assertNotIn("brain.route", evergreen["scopes"])
        self.assertIn("brain.review_candidate_memory", evergreen["scopes"])

    def test_fast_is_zero_rtt_and_high_risk_never_degrades(self):
        policy = load("AI_SKILL_LIBRARY/v4/stable/universal_fabric.yaml")
        self.assertEqual(policy["authority"], "GITHUB_BRAIN_V4")
        self.assertIs(policy["routing"]["FAST"]["online_brain_required"], False)
        self.assertEqual(policy["routing"]["FAST"]["external_routing_calls"], 0)
        self.assertIs(policy["routing"]["FAST"]["synchronous_shared_state"], False)
        self.assertGreaterEqual(
            set(policy["degraded"]["fail_closed_classes"]),
            {
                "live_or_trading",
                "deployment_or_runtime_claim",
                "credential_sensitive",
                "financial",
                "destructive",
                "permission_change",
            },
        )

    def test_learning_is_candidate_first_and_permission_bounded(self):
        policy = load("AI_SKILL_LIBRARY/v4/stable/universal_fabric.yaml")
        learning = policy["learning"]
        self.assertIs(learning["candidate_first"], True)
        self.assertEqual(set(learning["autonomous_promotion_classes"]), {"A", "B"})
        self.assertGreaterEqual(set(learning["approval_required_classes"]), {"C", "D"})
        self.assertIs(learning["permission_widening"], False)

    def test_future_adapter_defaults_disabled(self):
        contract = load("AI_SKILL_LIBRARY/v4/adapters/registry.yaml")["future_adapter_contract"]
        self.assertIs(contract["brain_core_change_required"], False)
        self.assertEqual(contract["default_state"], "disabled")
        self.assertEqual(contract["default_scopes"], ["brain.route"])


if __name__ == "__main__":
    unittest.main()
