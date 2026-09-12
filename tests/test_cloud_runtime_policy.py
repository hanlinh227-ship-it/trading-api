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


if __name__ == "__main__":
    unittest.main()
