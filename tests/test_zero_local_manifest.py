from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
GATEWAY = ROOT / "crypto-research-gateway"


class ZeroLocalManifestTests(unittest.TestCase):
    def test_railway_config_is_continuous_and_health_checked(self):
        path = GATEWAY / "railway.toml"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn('healthcheckPath = "/health"', text)
        self.assertIn('restartPolicyType = "ON_FAILURE"', text)
        self.assertNotIn("cronSchedule", text)

    def test_gateway_requires_node_22_or_newer(self):
        import json

        package = json.loads((GATEWAY / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["engines"]["node"], ">=22")

    def test_cloud_ci_runs_gateway_and_brain_validators(self):
        text = (ROOT / ".github/workflows/zero-local-cloud-runtime.yml").read_text(encoding="utf-8")
        for required in (
            "node-version: '22'",
            "npm test",
            "npm run typecheck",
            "npm run build",
            "validate_skill_registry.py",
            "validate_brain.py",
            "validate_router.py",
            "validate_v4.py",
            "validate_authority.py",
        ):
            self.assertIn(required, text)

    def test_cloud_runtime_manifest_names_railway_service_root(self):
        manifest = yaml.safe_load((ROOT / "AI_SKILL_LIBRARY/runtime/cloud_runtime.yaml").read_text(encoding="utf-8"))
        self.assertEqual(manifest["runtime"], "railway")
        self.assertEqual(manifest["service_root"], "crypto-research-gateway")
        self.assertEqual(manifest["health_path"], "/health")


if __name__ == "__main__":
    unittest.main()
