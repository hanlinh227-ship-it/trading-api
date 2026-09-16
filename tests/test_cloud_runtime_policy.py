import json
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "AI_SKILL_LIBRARY"


class ZeroLocalCloudRuntimePolicyTests(unittest.TestCase):
    def test_checkpoint_resolves_zero_local_runtime_files(self):
        checkpoint = json.loads((LIB / "checkpoint.json").read_text(encoding="utf-8"))
        for key in ("cloud_runtime_policy_path", "cloud_runtime_manifest_path"):
            self.assertIn(key, checkpoint)
            self.assertTrue((ROOT / checkpoint[key]).is_file(), key)

    def test_runtime_manifest_forbids_local_dependency(self):
        data = yaml.safe_load((LIB / "runtime/cloud_runtime.yaml").read_text(encoding="utf-8"))
        self.assertFalse(data["local_install_required"])
        self.assertFalse(data["local_cli_execution"])
        self.assertFalse(data["local_mcp_server_required"])
        self.assertTrue(data["cloud_runtime_required_for_provider_execution"])
        self.assertFalse(data["high_risk_cloud_execution"])
        self.assertFalse(data["auth_read_only_default_enabled"])
        self.assertEqual(data["runtime"], "railway")
        self.assertEqual(data["node_major"], 22)

    def test_runtime_policy_has_no_local_install_fallback(self):
        data = yaml.safe_load((LIB / "skills/registry/runtime_policy.yaml").read_text(encoding="utf-8"))
        self.assertFalse(data["policy"]["allow_local_install_fallback"])
        self.assertEqual(
            data["execution_preference"],
            [
                "connected_cloud_tool",
                "public_first_party_https",
                "approved_remote_read_only_mcp",
                "degraded_failure",
            ],
        )

    def test_high_risk_capabilities_cannot_execute_in_cloud(self):
        registry = yaml.safe_load((LIB / "skills/providers/crypto_agents.yaml").read_text(encoding="utf-8"))
        capabilities = registry["capabilities"]
        high_risk = [row for row in capabilities if row["mode"] == "HIGH_RISK"]
        self.assertGreater(len(high_risk), 0)
        for row in high_risk:
            self.assertFalse(row.get("cloud_execution", False), row["id"])
            self.assertEqual(row.get("runtime_target", "none"), "none", row["id"])

    def test_executable_provider_capabilities_are_research_safe_only(self):
        registry = yaml.safe_load((LIB / "skills/providers/crypto_agents.yaml").read_text(encoding="utf-8"))
        for row in registry["capabilities"]:
            if row.get("cloud_execution"):
                self.assertEqual(row["mode"], "RESEARCH_SAFE", row["id"])
                self.assertEqual(row.get("runtime_target"), "cloud_gateway", row["id"])

    def test_zero_local_observer_cannot_block_sole_gated_worker_deploy(self):
        zero_local = yaml.safe_load((ROOT / ".github/workflows/deploy-cloudflare-worker.yml").read_text(encoding="utf-8"))
        gated = yaml.safe_load((ROOT / ".github/workflows/deploy-skill-mandatory-fast-gateway.yml").read_text(encoding="utf-8"))
        zero_group = zero_local.get("concurrency", {}).get("group")
        deploy_job = gated["jobs"]["deploy-exact-main"]
        refresh_job = gated["jobs"]["refresh-model-mesh-health"]
        gated_group = deploy_job.get("concurrency", {}).get("group")
        self.assertEqual(gated_group, "cloudflare-zero-local-runtime-production")
        self.assertIs(deploy_job["concurrency"].get("cancel-in-progress"), False)
        self.assertIsInstance(zero_group, str)
        self.assertTrue(zero_group)
        self.assertNotEqual(
            zero_group,
            gated_group,
            "the non-mutating Zero-Local Worker observer must not hold the sole production deploy lock while waiting for that deploy",
        )
        # The scheduled health refresh must not share the deploy lock: GitHub cancels
        # the older pending run in a group, so a 20-minute cron in the same group
        # could evict a queued production deploy.
        self.assertNotIn("concurrency", gated, "concurrency must be declared per job")
        refresh_group = refresh_job.get("concurrency", {}).get("group")
        self.assertIsInstance(refresh_group, str)
        self.assertNotEqual(refresh_group, gated_group)
        self.assertIs(refresh_job["concurrency"].get("cancel-in-progress"), False)

    def test_pr_ci_runs_repository_policy_tests_for_deploy_workflow_changes(self):
        """A change to the deploy workflow or the Worker must run this module in PR CI,
        not only post-merge inside the deploy job."""
        ci = (ROOT / ".github/workflows/skill-mandatory-fast-gateway-ci.yml").read_text(encoding="utf-8")
        self.assertIn("deploy-skill-mandatory-fast-gateway.yml", ci)
        self.assertIn("unittest discover -s tests", ci)


if __name__ == "__main__":
    unittest.main()
