from pathlib import Path
import json
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
GATEWAY = ROOT / "crypto-research-gateway"
WORKFLOW_PATH = ROOT / ".github/workflows/zero-local-cloud-runtime.yml"
MANIFEST_PATH = ROOT / "AI_SKILL_LIBRARY/runtime/cloud_runtime.yaml"
WORKER_PATH = ROOT / "cloudflare-worker/research-gateway.js"

#: The retired provider, named once. Every assertion below that must not find it
#: reads this, so re-admitting it cannot be done by editing one forgotten string.
RETIRED_PRODUCTION_HOST = "railway.app"


class ZeroLocalManifestTests(unittest.TestCase):
    def test_gateway_requires_node_22_or_newer(self):
        package = json.loads((GATEWAY / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["engines"]["node"], ">=22")

    def test_cloud_ci_runs_gateway_and_brain_validators(self):
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
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
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
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
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        validate = text.split("  production-smoke:", 1)[0]
        self.assertNotIn("required_unrestricted - healthy", validate)
        self.assertNotIn("public provider probes failed: {missing}", validate)
        self.assertIn("research_sources = {'binance', 'okx', 'gate', 'kucoin'}", validate)
        self.assertIn("if len(healthy_research) < 2:", validate)
        self.assertIn("public research redundancy insufficient", validate)

    def test_production_smoke_does_not_promote_research_only_symbols_or_optional_venues(self):
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        production = text.split("  production-smoke:", 1)[1]
        self.assertIn("'bybit LONG BTCUSDT ask'", production)
        self.assertIn("'bybit SHORT BTCUSDT bid'", production)
        self.assertNotIn("'bybit SHORT SOLUSDT bid'", production)
        self.assertNotIn("'binance LONG BTCUSDT ask'", production)
        self.assertNotIn("'binance SHORT SOLUSDT bid'", production)
        manifest_text = MANIFEST_PATH.read_text(encoding="utf-8")
        self.assertNotIn("required_execution_venues:\n    - bybit\n    - binance", manifest_text)

    def test_global_checkpoint_is_resolved_for_every_new_work_cycle(self):
        checkpoint = json.loads((ROOT / "AI_SKILL_LIBRARY/checkpoint.json").read_text(encoding="utf-8"))
        self.assertEqual(checkpoint["global_checkpoint_path"], "AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md")
        global_checkpoint = ROOT / checkpoint["global_checkpoint_path"]
        self.assertTrue(global_checkpoint.is_file())
        text = global_checkpoint.read_text(encoding="utf-8")
        for required in (
            "ZERO_LOCAL_CLOUD_RUNTIME_V1",
            "live-price-execution-v1",
            "HIGH_RISK",
            "PRIMARY_RUNTIME = CLOUDFLARE_WORKERS",
        ):
            self.assertIn(required, text)
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md", agents)


class CanonicalRuntimeContractTests(unittest.TestCase):
    """The canonical contract names Cloudflare as production authority."""

    def setUp(self):
        self.manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_primary_runtime_is_cloudflare_workers(self):
        self.assertEqual(self.manifest["runtime"], "cloudflare_workers")
        self.assertEqual(self.manifest["service_root"], "crypto-research-gateway")
        self.assertEqual(self.manifest["health_path"], "/health")

    def test_the_contract_declares_railway_and_personal_pc_not_required(self):
        self.assertIs(self.manifest["railway_required"], False)
        self.assertIs(self.manifest["personal_pc_required"], False)
        self.assertIs(self.manifest["paid_fallback_allowed"], False)

    def test_production_source_auto_deploys_from_main_without_local_action(self):
        source = self.manifest["production_source"]
        self.assertEqual(source["provider"], "github")
        self.assertEqual(source["repository"], "hanlinh227-ship-it/trading-api")
        self.assertEqual(source["branch"], "main")
        self.assertIs(source["auto_deploy_on_push"], True)
        self.assertIs(source["user_local_action_required"], False)
        self.assertNotIn("railway", str(source).lower())

    def test_production_verification_requires_cloudflare_sha_and_health(self):
        verification = self.manifest["production_verification"]
        self.assertEqual(verification["primary_runtime"], "cloudflare_workers")
        self.assertIs(verification["railway_success_required"], False)
        self.assertIs(verification["exact_source_sha_required"], True)
        self.assertIs(verification["primary_health_required"], True)
        self.assertIs(verification["live_execution_smoke_required"], True)
        self.assertEqual(verification["required_execution_venues"], ["bybit"])

    def test_the_contract_no_longer_requires_a_railway_deployment(self):
        text = MANIFEST_PATH.read_text(encoding="utf-8")
        for forbidden in (
            "railway_connector_exact_commit",
            "railway_deployment_metadata_must_match_source_sha",
            RETIRED_PRODUCTION_HOST,
        ):
            self.assertNotIn(forbidden, text, forbidden)
        self.assertNotEqual(self.manifest["runtime"], "railway")


class SecondaryRuntimeContractTests(unittest.TestCase):
    """The secondary is capacity, never authority, and never claimed live early."""

    def setUp(self):
        self.scheduler = yaml.safe_load(
            MANIFEST_PATH.read_text(encoding="utf-8"))["runtime_scheduler"]

    def test_the_primary_is_the_cloudflare_worker(self):
        self.assertEqual(self.scheduler["primary"]["id"], "cloudflare_workers")
        self.assertEqual(self.scheduler["primary"]["cost_tier"], "free")

    def test_the_secondary_holds_no_routing_or_reasoning_authority(self):
        secondary = self.scheduler["secondary"]
        self.assertIs(secondary["routing_authority"], False)
        self.assertIs(secondary["reasoning_authority"], False)
        self.assertIs(secondary["model_selection_authority"], False)

    def test_the_secondary_is_not_claimed_deployed_until_health_probed(self):
        """Deno has not been deployed or probed. Nothing may say otherwise, and
        the cutover must not wait on it either."""
        secondary = self.scheduler["secondary"]
        self.assertIs(secondary["deployed"], False)
        self.assertIs(secondary["health_verified"], False)
        self.assertIs(secondary["required_for_primary_cutover"], False)

    def test_no_verified_secondary_fails_closed_rather_than_escalating(self):
        self.assertEqual(
            self.scheduler["no_verified_secondary_behaviour"],
            "CAPABILITY_TEMPORARILY_UNAVAILABLE",
        )
        self.assertIs(self.scheduler["paid_fallback_allowed"], False)
        self.assertIs(self.scheduler["railway_fallback_allowed"], False)

    def test_both_declared_runtimes_are_zero_cost(self):
        self.assertEqual(self.scheduler["primary"]["cost_tier"], "free")
        self.assertEqual(self.scheduler["secondary"]["cost_tier"], "free")


class RailwayExitTests(unittest.TestCase):
    """Railway must be gone, and must not be able to return quietly."""

    def setUp(self):
        self.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.worker = WORKER_PATH.read_text(encoding="utf-8")

    def test_no_hardcoded_railway_production_url_anywhere_in_the_runtime_path(self):
        for label, text in (
            ("workflow", self.workflow),
            ("worker", self.worker),
            ("manifest", MANIFEST_PATH.read_text(encoding="utf-8")),
        ):
            self.assertNotIn(
                "crypto-research-gateway-prod-production.up." + RETIRED_PRODUCTION_HOST,
                text,
                label,
            )

    def test_the_worker_carries_no_railway_identifier_at_all(self):
        self.assertNotIn("railway-safety-fallback", self.worker)
        self.assertNotIn("upstreamFallback:'railway'", self.worker)
        # The only permitted occurrence is the guard that keeps it OUT.
        occurrences = self.worker.lower().count("railway")
        self.assertLessEqual(
            occurrences, 2,
            "railway should survive only inside the retired-host guard")

    def test_there_is_no_railway_deploy_job_or_mutation(self):
        for forbidden in (
            "deploy-latest",
            "railway_deploy_latest.py",
            "serviceInstanceDeployV2",
            "RAILWAY_TOKEN",
            "RAILWAY_SERVICE_ID",
            "RAILWAY_ENVIRONMENT_ID",
            "deploymentCommitSha",
            "x-railway-upstream-zone",
        ):
            self.assertNotIn(forbidden, self.workflow, forbidden)

    def test_the_railway_deploy_script_is_gone(self):
        self.assertFalse((ROOT / ".github/scripts/railway_deploy_latest.py").exists())

    def test_railway_cannot_re_enter_as_the_secondary_gateway(self):
        """A URL is the easiest way for a retired provider to come back, so the
        refusal is in the Worker, not only in this test."""
        self.assertIn("RETIRED_SECONDARY_HOST_PATTERN", self.worker)
        self.assertIn("resolveSecondaryGatewayUrl", self.worker)


class CloudflareProductionGateTests(unittest.TestCase):
    """The production gate verifies the exact Cloudflare revision that is live.

    This replaces the Railway gate, which could only compare gateway SOURCE
    TREES because Railway's connector never carried the repository commit. The
    Worker is deployed at an exact revision, so this compares the commit itself
    - a stricter check than the one it replaces, not a looser one.
    """

    def setUp(self):
        self.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.production = self.workflow.split("  production-smoke:", 1)[1]

    def test_the_gate_requires_the_exact_main_sha(self):
        self.assertIn("deploymentSourceSha", self.production)
        self.assertIn("GITHUB_SHA", self.production)
        self.assertIn("CLOUDFLARE_SHA_MATCH=PASS", self.production)

    def test_the_gate_requires_cloudflare_health(self):
        self.assertIn("/health", self.production)
        self.assertIn("CLOUDFLARE_HEALTH=PASS", self.production)
        self.assertIn("runtimeProvider", self.production)
        self.assertIn("cloudflare-workers", self.production)

    def test_the_gate_requires_a_live_research_smoke(self):
        self.assertIn("/research/market", self.production)
        self.assertIn("/capabilities", self.production)
        self.assertIn("LIVE_RESEARCH_SMOKE=PASS", self.production)
        self.assertIn("'bybit LONG BTCUSDT ask'", self.production)

    def test_the_gate_still_fails_closed(self):
        self.assertIn("CLOUDFLARE_HEALTH=FAIL", self.production)
        self.assertIn("exit 1", self.production)
        self.assertNotIn("exit 0  # always pass", self.production)
        self.assertNotIn("|| true\n            exit 0", self.production)

    def test_the_gate_asserts_zero_local_and_no_personal_pc(self):
        self.assertIn("localInstallRequired", self.production)
        self.assertIn("ZERO_LOCAL=PASS", self.production)
        self.assertIn("PERSONAL_PC_REQUIRED=false", self.production)
        self.assertIn("RAILWAY_REQUIRED=false", self.production)

    def test_the_gate_runs_on_a_hosted_runner_not_a_personal_machine(self):
        workflow = yaml.safe_load(self.workflow)
        for name, job in workflow["jobs"].items():
            self.assertEqual(job["runs-on"], "ubuntu-latest", name)

    def test_the_gate_does_not_touch_trading_execution_authority(self):
        for forbidden in ("BYBIT_AUTO_LIVE", "BYBIT_BTC_LIVE_ACK", "BYBIT_AUTO_ENABLED"):
            self.assertNotIn(forbidden, self.workflow)
        self.assertIn("write/high-risk tool exposed in production", self.workflow)


class SingleAuthorityTests(unittest.TestCase):
    """One Brain, one router, one Model Mesh. Migration must not fork them."""

    def test_the_migration_introduces_no_duplicate_brain_router_or_mesh(self):
        workspace = yaml.safe_load(
            (ROOT / "AI_SKILL_LIBRARY/v4/index/workspace_map.yaml").read_text(encoding="utf-8"))
        self.assertEqual(workspace["single_brain"], "GITHUB_BRAIN_V4")
        self.assertEqual(workspace["single_router"], "AI_SKILL_LIBRARY/v4/stable/router.yaml")

    def test_the_secondary_runtime_is_not_a_second_router(self):
        scheduler = yaml.safe_load(
            MANIFEST_PATH.read_text(encoding="utf-8"))["runtime_scheduler"]
        self.assertIs(scheduler["secondary"]["routing_authority"], False)

    def test_there_is_exactly_one_cloudflare_deploy_authority(self):
        scheduler = yaml.safe_load(
            MANIFEST_PATH.read_text(encoding="utf-8"))["runtime_scheduler"]
        authority = scheduler["primary"]["deploy_authority"]
        self.assertEqual(
            authority, ".github/workflows/deploy-skill-mandatory-fast-gateway.yml")
        self.assertTrue((ROOT / authority).is_file())
        # The verification lane must not also deploy.
        self.assertNotIn("wrangler deploy", WORKFLOW_PATH.read_text(encoding="utf-8"))


# Guard at the END of the module. It previously sat mid-file, above the
# production-gate class, so running this file directly defined and ran only the
# tests above it and silently skipped the rest; only `unittest discover` ever
# executed them.
if __name__ == "__main__":
    unittest.main()
