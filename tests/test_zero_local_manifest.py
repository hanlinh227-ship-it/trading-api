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

    def test_research_provider_smoke_tolerates_one_degraded_optional_source(self):
        text = (ROOT / ".github/workflows/zero-local-cloud-runtime.yml").read_text(encoding="utf-8")
        validate = text.split("  production-smoke:", 1)[0]
        self.assertNotIn("required_unrestricted - healthy", validate)
        self.assertNotIn("public provider probes failed: {missing}", validate)
        self.assertIn("research_sources = {'binance', 'okx', 'gate', 'kucoin'}", validate)
        self.assertIn("if len(healthy_research) < 2:", validate)
        self.assertIn("public research redundancy insufficient", validate)

    def test_main_ci_verifies_exact_connector_managed_source_sha_and_authoritative_execution_venue(self):
        text = (ROOT / ".github/workflows/zero-local-cloud-runtime.yml").read_text(encoding="utf-8")
        production = text.split("  production-smoke:", 1)[1]
        for required in (
            "crypto-research-gateway-prod-production.up.railway.app",
            "deploymentCommitSha",
            "GITHUB_SHA",
            "bybit LONG BTCUSDT ask",
            "bybit SHORT BTCUSDT bid",
            "Production venue-bound execution smoke",
        ):
            self.assertIn(required, text)
        self.assertNotIn("binance LONG BTCUSDT ask", production)
        self.assertNotIn("binance SHORT SOLUSDT bid", production)
        self.assertNotIn("bybit SHORT SOLUSDT bid", production)

    def test_production_smoke_does_not_promote_research_only_symbols_or_optional_venues(self):
        text = (ROOT / ".github/workflows/zero-local-cloud-runtime.yml").read_text(encoding="utf-8")
        production = text.split("  production-smoke:", 1)[1]
        self.assertIn("'bybit LONG BTCUSDT ask'", production)
        self.assertIn("'bybit SHORT BTCUSDT bid'", production)
        self.assertNotIn("'bybit SHORT SOLUSDT bid'", production)
        self.assertNotIn("'binance LONG BTCUSDT ask'", production)
        self.assertNotIn("'binance SHORT SOLUSDT bid'", production)
        manifest_text = (ROOT / "AI_SKILL_LIBRARY/runtime/cloud_runtime.yaml").read_text(encoding="utf-8")
        self.assertNotIn("required_execution_venues:\n    - bybit\n    - binance", manifest_text)

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
        self.assertEqual(verification["required_execution_venues"], ["bybit"])
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


class RailwayProductionGateTests(unittest.TestCase):
    """The production gate must verify the exact gateway revision that is actually running.

    Railway only redeploys when its own service source changes, so comparing the deployed
    commit to the repository HEAD fails on every main commit that does not touch
    ``crypto-research-gateway/``. The gate must compare against the gateway source instead,
    without ever becoming a gate that always passes.
    """

    WORKFLOW = ROOT / ".github/workflows/zero-local-cloud-runtime.yml"

    def setUp(self):
        self.workflow = self.WORKFLOW.read_text(encoding="utf-8")

    def test_gate_does_not_compare_deployment_to_global_repo_head(self):
        self.assertNotIn(
            'if [ "$DEPLOYED_SHA" = "$GITHUB_SHA" ]',
            self.workflow,
            "the deployed gateway must not be compared to the repository HEAD",
        )
        self.assertNotIn(
            "data.get('deploymentCommitSha') != os.environ['GITHUB_SHA']",
            self.workflow,
            "the deployed gateway must not be compared to the repository HEAD",
        )

    def test_gate_compares_against_the_gateway_source_revision(self):
        # The gate resolves what the gateway source actually is, rather than assuming the
        # whole repository redeploys on every push.
        self.assertIn("crypto-research-gateway", self.workflow)
        self.assertIn("GATEWAY_TREE", self.workflow)
        # It needs repository history available to resolve that revision.
        self.assertIn("fetch-depth: 0", self.workflow)

    def test_gate_still_fails_closed(self):
        # Exact verification is preserved: an unknown or mismatched deployment still fails.
        self.assertIn("production gateway source mismatch", self.workflow)
        self.assertIn("exit 1", self.workflow)
        # The gate must never be reduced to an unconditional pass.
        self.assertNotIn("exit 0  # always pass", self.workflow)

    def test_gate_keeps_region_and_local_install_assertions(self):
        self.assertIn("x-railway-upstream-zone", self.workflow)
        self.assertIn("localInstallRequired", self.workflow)

    def test_gate_does_not_touch_trading_execution_authority(self):
        # The workflow legitimately names write verbs inside a negative assertion that
        # production must not expose them, so absence of the words is the wrong check.
        # What matters is that the gate never enables live execution.
        for forbidden in ("BYBIT_AUTO_LIVE", "BYBIT_BTC_LIVE_ACK", "BYBIT_AUTO_ENABLED"):
            self.assertNotIn(forbidden, self.workflow)
        # The existing guard that production exposes no write/high-risk tool stays.
        self.assertIn("write/high-risk tool exposed in production", self.workflow)
