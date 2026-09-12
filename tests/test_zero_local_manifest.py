from pathlib import Path
import json
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

    def test_railway_production_region_is_southeast_asia_only(self):
        text = (GATEWAY / "railway.toml").read_text(encoding="utf-8")
        self.assertIn('[deploy.multiRegionConfig."asia-southeast1-eqsg3a"]', text)
        self.assertIn('numReplicas = 1', text)
        self.assertNotIn('[deploy.multiRegionConfig."us-', text)

    def test_gateway_requires_node_22_or_newer(self):
        package = json.loads((GATEWAY / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["engines"]["node"], ">=22")

    def test_cloud_ci_runs_gateway_and_brain_validators(self):
        text = (ROOT / ".github/workflows/zero-local-cloud-runtime.yml").read_text(encoding="utf-8")
        for required in (
            "node-version: '22'",
            "npm test",
            "npm run typecheck",
            "npm run build",
            "AI_SKILL_LIBRARY/v4/tools/ci_validate.py",
        ):
            self.assertIn(required, text)
        # The single entrypoint must still run every Brain validator exactly once.
        entrypoint = (ROOT / "AI_SKILL_LIBRARY/v4/tools/ci_validate.py").read_text(encoding="utf-8")
        for required in (
            "validate_skill_registry.py",
            "validate_brain.py",
            "validate_router.py",
            "validate_v4.py",
            "validate_authority.py",
        ):
            self.assertEqual(entrypoint.count(f'"AI_SKILL_LIBRARY/{required}"'), 1, required)

    def test_ci_smokes_venue_bound_execution_quotes(self):
        text = (ROOT / ".github/workflows/zero-local-cloud-runtime.yml").read_text(encoding="utf-8")
        for required in (
            "action",
            "execution_quote",
            "executionVenue",
            "binance",
            "side",
            "LONG",
            "executionVerified",
            "quoteAgeMs",
            "spreadBps",
            "bid",
            "ask",
            "region_restricted_bybit_cloud_region",
            "region_restricted_binance_futures_cloud_region",
        ):
            self.assertIn(required, text)

    def test_main_ci_verifies_exact_connector_managed_source_sha_and_both_execution_venues(self):
        text = (ROOT / ".github/workflows/zero-local-cloud-runtime.yml").read_text(encoding="utf-8")
        for required in (
            "crypto-research-gateway-prod-production.up.railway.app",
            "deploymentCommitSha",
            "GITHUB_SHA",
            "bybit LONG BTCUSDT ask",
            "binance LONG BTCUSDT ask",
            "Production venue-bound execution smoke",
        ):
            self.assertIn(required, text)

    def test_cloud_runtime_manifest_names_railway_service_root(self):
        manifest = yaml.safe_load((ROOT / "AI_SKILL_LIBRARY/runtime/cloud_runtime.yaml").read_text(encoding="utf-8"))
        self.assertEqual(manifest["runtime"], "railway")
        self.assertEqual(manifest["service_root"], "crypto-research-gateway")
        self.assertEqual(manifest["health_path"], "/health")

    def test_cloud_runtime_uses_connector_managed_exact_commit_releases(self):
        manifest = yaml.safe_load((ROOT / "AI_SKILL_LIBRARY/runtime/cloud_runtime.yaml").read_text(encoding="utf-8"))
        source = manifest["production_source"]
        self.assertEqual(source["provider"], "github")
        self.assertEqual(source["repository"], "hanlinh227-ship-it/trading-api")
        self.assertEqual(source["branch"], "main")
        self.assertEqual(source["deployment_trigger"], "railway_connector_exact_commit")
        self.assertFalse(source["auto_deploy_on_push"])
        self.assertFalse(source["github_app_required"])
        self.assertFalse(source["user_local_action_required"])
        self.assertTrue(source["deployment_commit_pin_required"])
        verification = manifest["production_verification"]
        self.assertEqual(verification["release_marker"], "live-price-execution-v1")
        self.assertTrue(verification["railway_success_required"])
        self.assertEqual(verification["required_execution_venues"], ["bybit", "binance"])
        self.assertTrue(verification["live_execution_smoke_required"])

    def test_global_checkpoint_is_resolved_for_every_new_work_cycle(self):
        checkpoint = json.loads((ROOT / "AI_SKILL_LIBRARY/checkpoint.json").read_text(encoding="utf-8"))
        self.assertEqual(checkpoint["global_checkpoint_path"], "AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md")
        global_checkpoint = ROOT / checkpoint["global_checkpoint_path"]
        self.assertTrue(global_checkpoint.is_file())
        text = global_checkpoint.read_text(encoding="utf-8")
        for required in (
            "ZERO_LOCAL_CLOUD_RUNTIME_V1",
            "crypto-research-gateway-prod",
            "live-price-execution-v1",
            "railway_connector_exact_commit",
            "HIGH_RISK",
        ):
            self.assertIn(required, text)
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md", agents)


if __name__ == "__main__":
    unittest.main()
