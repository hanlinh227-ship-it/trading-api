import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


class CloudOnly24x7FederationTests(unittest.TestCase):
    def test_policy_is_cloud_only_and_never_spills_paid_or_local(self):
        policy = yaml.safe_load((ROOT / "AI_SKILL_LIBRARY/v4/model_mesh/policy.yaml").read_text(encoding="utf-8"))
        cloud = policy["cloud_24x7"]
        self.assertTrue(cloud["enabled"])
        self.assertEqual(cloud["semantics"], "service_continuity_not_all_models_hot")
        self.assertFalse(cloud["personal_pc_required"])
        self.assertFalse(cloud["local_runtime_required"])
        self.assertFalse(cloud["local_fallback_allowed"])
        self.assertFalse(cloud["paid_fallback_allowed"])
        self.assertFalse(cloud["all_models_must_be_hot"])
        self.assertTrue(cloud["provider_managed_residency"])
        self.assertEqual(policy["mode"], "FREE_ONLY")
        self.assertEqual(policy["paid_fallback"], "disabled")
        self.assertFalse(policy["auto_purchase"])

    def test_health_refresh_stays_inside_evidence_ttl(self):
        policy = yaml.safe_load((ROOT / "AI_SKILL_LIBRARY/v4/model_mesh/policy.yaml").read_text(encoding="utf-8"))
        health = policy["cloud_24x7"]["health_refresh"]
        self.assertLess(health["cadence_minutes"], health["live_evidence_ttl_minutes"])
        self.assertEqual(health["authority"], "cloudflare_worker_cron")
        self.assertTrue(health["opportunistic_self_heal"])
        self.assertFalse(health["request_path_probe_blocking"])

        source = (ROOT / "cloudflare-worker/model-mesh/scheduled-health.js").read_text(encoding="utf-8")
        self.assertIn(f"HEALTH_REFRESH_CRON = '*/{health['cadence_minutes']} * * * *'", source)

    def test_active_pool_has_cloud_redundancy_and_enabled_bindings(self):
        policy = yaml.safe_load((ROOT / "AI_SKILL_LIBRARY/v4/model_mesh/policy.yaml").read_text(encoding="utf-8"))
        active = json.loads((ROOT / "AI_SKILL_LIBRARY/v4/model_mesh/active.json").read_text(encoding="utf-8"))
        bindings = json.loads((ROOT / "AI_SKILL_LIBRARY/v4/model_mesh/runtime_bindings.json").read_text(encoding="utf-8"))["bindings"]
        eligible = [m for m in active["models"] if m.get("registry_state") != "NOT_ELIGIBLE"]
        providers = {m["provider_id"] for m in eligible}

        self.assertGreaterEqual(len(eligible), policy["cloud_24x7"]["minimum_active_eligible_models"])
        self.assertGreaterEqual(len(providers), policy["cloud_24x7"]["minimum_independent_provider_paths"])
        self.assertTrue(providers.isdisjoint({"ephemeral-local-0", "github_actions_ubuntu_latest"}))
        for provider in providers:
            self.assertTrue(bindings[provider]["enabled"], provider)

    def test_failover_contract_is_quota_health_and_family_aware(self):
        policy = yaml.safe_load((ROOT / "AI_SKILL_LIBRARY/v4/model_mesh/policy.yaml").read_text(encoding="utf-8"))
        failover = policy["cloud_24x7"]["failover"]
        for key in (
            "quota_aware", "health_aware", "model_family_diversity",
            "rotate_on_429", "rotate_on_5xx",
            "rotate_before_free_quota_exhaustion", "respect_provider_reset",
            "never_open_second_account_to_bypass_quota",
        ):
            self.assertTrue(failover[key], key)
        self.assertTrue(policy["fallback"]["stable_survives_mesh_failure"])
        self.assertTrue(policy["fallback"]["rotate_to_next_verified_zero_cost_candidate"])

    def test_canonical_validator_is_wired_into_ci(self):
        ci = (ROOT / "AI_SKILL_LIBRARY/v4/tools/ci_validate.py").read_text(encoding="utf-8")
        self.assertIn("validate_cloud_24x7.py", ci)

    def test_trading_private_read_outage_cannot_roll_back_brain(self):
        workflow = (ROOT / ".github/workflows/deploy-skill-mandatory-fast-gateway.yml").read_text(encoding="utf-8")
        marker = "Production Bybit private-read readiness canary (advisory, fail-closed)"
        self.assertIn(marker, workflow)
        tail = workflow.split(marker, 1)[1].split("- name: Production Universal Brain adapter canary", 1)[0]
        self.assertIn("continue-on-error: true", tail)
        self.assertIn("BYBIT_PRIVATE_READ_UNAVAILABLE", workflow)


if __name__ == "__main__":
    unittest.main()
