import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "v4", "survival"))

from policy_adapter import Decision, evaluate_policy, load_policy  # noqa: E402


class TestSurvivalPolicy(unittest.TestCase):
    def test_local_only_allowed(self):
        decision = evaluate_policy(
            {"placement": "LOCAL_ONLY", "provider": "local", "action": "read"}
        )
        self.assertIsInstance(decision, Decision)
        self.assertTrue(decision.allow)
        self.assertEqual(decision.reasons, [])

    def test_remote_placement_fails_closed(self):
        decision = evaluate_policy(
            {"placement": "REMOTE", "provider": "local", "action": "read"}
        )
        self.assertFalse(decision.allow)
        self.assertIn("placement_not_local_only", decision.reasons)

    def test_missing_placement_fails_closed(self):
        decision = evaluate_policy({"provider": "local", "action": "read"})
        self.assertFalse(decision.allow)
        self.assertIn("missing_placement", decision.reasons)

    def test_paid_path_fails_closed(self):
        decision = evaluate_policy(
            {"placement": "LOCAL_ONLY", "provider": "local", "path": "/billing/invoice"}
        )
        self.assertFalse(decision.allow)
        self.assertIn("paid_path_denied", decision.reasons)

    def test_unverified_provider_fails_closed(self):
        decision = evaluate_policy(
            {"placement": "LOCAL_ONLY", "provider": "cloud_llm", "action": "read"}
        )
        self.assertFalse(decision.allow)
        self.assertIn("unverified_provider", decision.reasons)

    def test_missing_provider_fails_closed(self):
        decision = evaluate_policy({"placement": "LOCAL_ONLY", "action": "read"})
        self.assertFalse(decision.allow)
        self.assertIn("missing_provider", decision.reasons)

    def test_invalid_input_fails_closed(self):
        decision = evaluate_policy("not-a-document")
        self.assertFalse(decision.allow)
        self.assertIn("invalid_input_document", decision.reasons)

    def test_authority_flags_are_false(self):
        policy = load_policy()
        authority = policy.get("authority", {})
        for key in ("routing", "reasoning", "scheduling", "merge", "deployment", "trading"):
            self.assertFalse(authority.get(key, False))

    def test_authority_escalation_fails_closed(self):
        policy = load_policy()
        policy = dict(policy)
        policy["authority"] = dict(policy.get("authority", {}))
        policy["authority"]["trading"] = True
        decision = evaluate_policy(
            {"placement": "LOCAL_ONLY", "provider": "local"}, policy=policy
        )
        self.assertFalse(decision.allow)
        self.assertIn("authority_escalation_trading", decision.reasons)


if __name__ == "__main__":
    unittest.main()
