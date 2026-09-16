"""Zero-cost admission: FREE_ONLY means free at execution time, not free forever.

The previous policy admitted only `recurring` and `account_specific`. That kept
paid usage out, but it also kept out models that genuinely cost nothing right
now, and it decided eligibility per provider -- so one paid model, or one
retired model id, wrote off a whole catalog. These tests pin the replacement:
eligibility is per model, proven by current price and quota evidence.
"""
import json
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.tools.model_mesh import (
    eligible_free_candidate,
    normalize_candidate,
    zero_cost_rejection,
)

ROOT = Path(__file__).resolve().parents[2]
POLICY = json.loads((ROOT / "AI_SKILL_LIBRARY/v4/model_mesh/free_only_policy.json").read_text(encoding="utf-8"))
ACTIVE = json.loads((ROOT / "AI_SKILL_LIBRARY/v4/model_mesh/active.json").read_text(encoding="utf-8"))
NOW = "2026-09-16T12:00:00Z"


def candidate(provider="zen", **overrides):
    raw = {
        "model_id": "free-model",
        "model_family": "free-model",
        "model_variant": "hosted",
        "provider_class": "F2",
        "endpoint_family": "openai_compatible",
        "free_status": "recurring",
        "free_verified_at": "2026-09-16T00:00:00Z",
        "quota_scope": "account",
        "quota_dimensions": ["rpm"],
        "reset_semantics": "rolling",
        "capabilities": {"text_reasoning": {"supported": True, "score": 0.8, "evidence": ["bench"], "verified_at": NOW}},
        "context_window": 131072,
        "privacy_class": "public_safe",
        "data_training_allowed_by_provider": False,
        "retention_policy": "documented",
        "usage_terms": "production_allowed",
        "health": "healthy",
        "latency_ema_ms": 100.0,
        "success_rate_ema": 0.99,
        "quality_scores": {"core": 0.7},
        "last_benchmark_at": NOW,
        "source_evidence": ["https://example.test/pricing"],
        "zero_cost": {
            "price_model": "recurring_free",
            "input_price_per_million": 0.0,
            "output_price_per_million": 0.0,
            "price_verified_at": "2026-09-16T11:00:00Z",
            "price_revalidate_after_hours": 24,
            "quota_model": "unknown",
            "hard_stop_verified": False,
            "quota_headroom_ratio": None,
            "evidence": ["https://example.test/pricing"],
        },
    }
    zero_cost = overrides.pop("zero_cost", None)
    raw.update(overrides)
    if zero_cost:
        raw["zero_cost"] = {**raw["zero_cost"], **zero_cost}
    return normalize_candidate(provider, raw, observed_at=NOW)


class ZeroCostPolicyTests(unittest.TestCase):
    def test_policy_admits_the_four_zero_cost_classes_and_no_billable_one(self):
        self.assertEqual(POLICY["schema_version"], 2)
        self.assertEqual(
            sorted(POLICY["eligible_statuses"]),
            ["account_specific", "free_quota_hard_stop", "recurring", "temporary_zero_price"],
        )
        for billable in ("paid", "trial_credit", "limited_time", "expired", "unknown"):
            self.assertNotIn(billable, POLICY["eligible_statuses"])
            self.assertIn(billable, POLICY["default_ineligible_statuses"])
        self.assertTrue(POLICY["requirements"]["auto_purchase_forbidden"])
        self.assertTrue(POLICY["requirements"]["paid_fallback_forbidden"])
        self.assertTrue(POLICY["requirements"]["hard_stop_required_for_finite_free_quota"])

    def test_failure_policy_replaces_stale_models_instead_of_writing_off_providers(self):
        self.assertEqual(POLICY["failure_policy"]["402"], "quarantine_model_and_failover")
        self.assertEqual(POLICY["failure_policy"]["404"], "discover_probe_replacement")
        self.assertEqual(POLICY["failure_policy"]["410"], "discover_probe_replacement")
        self.assertEqual(POLICY["failure_policy"]["429"], "cooldown_and_failover")
        self.assertEqual(POLICY["failure_policy"]["5xx"], "degrade_and_failover")
        self.assertFalse(POLICY["model_level_eligibility"]["provider_blacklist_on_single_model_failure"])


class ZeroCostGateTests(unittest.TestCase):
    def test_recorded_price_above_zero_vetoes_any_class(self):
        self.assertIsNone(zero_cost_rejection(candidate(), now=NOW))
        self.assertEqual(zero_cost_rejection(candidate(zero_cost={"input_price_per_million": 0.4}), now=NOW), "nonzero_price")
        self.assertEqual(zero_cost_rejection(candidate(zero_cost={"price_model": "paid"}), now=NOW), "price_model_not_zero_cost")

    def test_temporary_zero_price_must_reprove_its_price_on_a_timer(self):
        fresh = candidate(free_status="temporary_zero_price", zero_cost={"price_model": "temporary_zero_price", "price_verified_at": "2026-09-16T06:00:00Z"})
        stale = candidate(free_status="temporary_zero_price", zero_cost={"price_model": "temporary_zero_price", "price_verified_at": "2026-09-14T06:00:00Z"})
        missing = candidate(free_status="temporary_zero_price", zero_cost={"price_model": "temporary_zero_price", "price_verified_at": None})
        self.assertIsNone(zero_cost_rejection(fresh, now=NOW))
        self.assertEqual(zero_cost_rejection(stale, now=NOW), "price_evidence_stale")
        self.assertEqual(zero_cost_rejection(missing, now=NOW), "price_evidence_missing")
        self.assertFalse(eligible_free_candidate(stale, data_class="PUBLIC", now=NOW))

    def test_finite_free_quota_needs_a_hard_stop_headroom_and_an_unexpired_window(self):
        def finite(**zero_cost):
            return candidate(
                free_status="free_quota_hard_stop",
                zero_cost={"price_model": "finite_free_quota", "quota_model": "finite", "hard_stop_verified": True, **zero_cost},
            )

        self.assertIsNone(zero_cost_rejection(finite(), now=NOW))
        self.assertEqual(zero_cost_rejection(finite(hard_stop_verified=False), now=NOW), "finite_free_quota_without_hard_stop")
        self.assertEqual(zero_cost_rejection(finite(quota_headroom_ratio=0.05), now=NOW), "free_quota_below_safety_reserve")
        # An unknown headroom is unknown, not exhausted.
        self.assertIsNone(zero_cost_rejection(finite(quota_headroom_ratio=None), now=NOW))
        dated = finite(free_quota_expires_at="2026-11-21T00:00:00Z")
        self.assertIsNone(zero_cost_rejection(dated, now=NOW))
        self.assertEqual(zero_cost_rejection(dated, now="2026-12-01T00:00:00Z"), "free_quota_expired")

    def test_a_finite_quota_filed_under_another_class_gets_the_same_gate(self):
        row = candidate(free_status="account_specific", zero_cost={"quota_model": "finite", "hard_stop_verified": False})
        self.assertEqual(zero_cost_rejection(row, now=NOW), "finite_free_quota_without_hard_stop")

    def test_trial_credit_and_paid_never_become_autonomous(self):
        for status in ("trial_credit", "limited_time", "paid", "expired", "unknown"):
            self.assertEqual(zero_cost_rejection(candidate(free_status=status), now=NOW), "status_not_eligible", status)


class ZeroCostRegistryTests(unittest.TestCase):
    def _row(self, provider_id):
        return next(row for row in ACTIVE["models"] if row["provider_id"] == provider_id)

    def test_every_registered_model_carries_zero_price_evidence(self):
        for row in ACTIVE["models"]:
            zero_cost = row.get("zero_cost")
            self.assertIsInstance(zero_cost, dict, row["provider_id"])
            self.assertTrue(zero_cost.get("evidence"), row["provider_id"])
            for field in ("input_price_per_million", "output_price_per_million"):
                price = zero_cost.get(field)
                if isinstance(price, (int, float)) and not isinstance(price, bool):
                    self.assertEqual(price, 0.0, f"{row['provider_id']} is not zero-price")

    def test_alibaba_is_a_hard_stopped_finite_quota_with_a_recorded_expiry(self):
        row = self._row("alibaba_model_studio")
        self.assertEqual(row["free_status"], "free_quota_hard_stop")
        zero_cost = row["zero_cost"]
        self.assertEqual(zero_cost["quota_model"], "finite")
        self.assertTrue(zero_cost["hard_stop_verified"])
        self.assertTrue(zero_cost["hard_stop_evidence"])
        self.assertEqual(zero_cost["free_quota_expires_at"], "2026-11-21T00:00:00Z")

    def test_zen_stays_out_until_its_live_price_is_verified(self):
        row = self._row("opencode_zen")
        self.assertEqual(row["free_status"], "temporary_zero_price")
        self.assertEqual(row["registry_state"], "NOT_ELIGIBLE")
        self.assertIsNone(row["zero_cost"]["price_verified_at"])

    def test_trial_providers_remain_discovery_only(self):
        for provider_id in ("cohere", "huggingface_inference_providers"):
            row = self._row(provider_id)
            self.assertEqual(row["registry_state"], "NOT_ELIGIBLE", provider_id)
            self.assertEqual(row["zero_cost"]["price_model"], "trial_credit", provider_id)

    def test_no_credential_material_leaks_into_the_registry(self):
        serialized = json.dumps(ACTIVE).lower()
        for forbidden in ("api_key", "authorization", "bearer ", "secret_value", "sk-"):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
