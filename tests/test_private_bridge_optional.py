"""The private VPC bridge must not be a dependency of the canonical primary.

Requiring it made a public runtime fail on a private resource: Cloudflare
returned 10196 ("credentials are not authorized for requested VPC resource")
and the entire primary deploy died, including the public research path that
needs no VPC at all.

These tests damage that arrangement in each direction and require the right
refusal, rather than asserting a happy shape.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "cloudflare-worker"
PREPARE = WORKER / "prepare-wrangler.mjs"
DEPLOY_WF = ROOT / ".github/workflows/deploy-skill-mandatory-fast-gateway.yml"

KV_ID = "a" * 32
SERVICE_ID = "12345678-1234-4123-8abc-123456789abc"
SHA = "deadbeef" * 5


def run_prepare(**env_overrides):
    """Generate a config in a scratch copy, so the repo tree is never mutated."""
    env = dict(os.environ)
    env.pop("PRIVATE_BRIDGE_ENABLED", None)
    env.pop("AI_BRIDGE_SERVICE_ID", None)
    env.pop("V11_AI_BRIDGE_SERVICE_ID", None)
    env.update({"TRADING_KV_NAMESPACE_ID": KV_ID, "GITHUB_SHA": SHA})
    env.update({k: v for k, v in env_overrides.items() if v is not None})
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [sys.executable and "node", str(PREPARE)],
            cwd=tmp, env=env, capture_output=True, text=True, timeout=120)
        config_path = Path(tmp) / "wrangler.jsonc"
        config = None
        if config_path.is_file():
            text = re.sub(r"^\s*//.*$", "", config_path.read_text(), flags=re.M)
            config = json.loads(text)
        return result, config


class PrimaryBuildsWithoutVpcTests(unittest.TestCase):
    """A. and B."""

    def test_the_primary_config_builds_with_no_bridge_credentials_at_all(self):
        result, config = run_prepare()
        self.assertEqual(result.returncode, 0, result.stderr[-600:])
        self.assertIsNotNone(config)
        self.assertEqual(config["name"], "trading-v77-scanner")

    def test_no_vpc_services_generated_when_the_bridge_is_disabled(self):
        _, config = run_prepare()
        self.assertNotIn("vpc_services", config)

    def test_a_stray_service_id_alone_does_not_re_enable_vpc(self):
        """The flag decides, not the presence of a leftover secret - otherwise
        the dependency returns the moment an old secret is still configured."""
        _, config = run_prepare(AI_BRIDGE_SERVICE_ID=SERVICE_ID)
        self.assertNotIn("vpc_services", config)

    def test_the_public_runtime_still_has_everything_it_needs(self):
        _, config = run_prepare()
        self.assertTrue(config["keep_vars"])
        self.assertEqual([b["binding"] for b in config["kv_namespaces"]][0], "TRADING_STATE")
        self.assertEqual(config["ai"]["binding"], "AI")
        self.assertEqual(config["vars"]["RUNTIME_REVISION"], SHA)
        self.assertTrue(config["durable_objects"]["bindings"])

    def test_the_log_states_which_mode_was_built(self):
        result, _ = run_prepare()
        self.assertIn("PRIVATE_BRIDGE=DISABLED_PUBLIC_RUNTIME_ONLY", result.stdout)


class EnablingTheBridgeStillWorksTests(unittest.TestCase):
    """D. Opting in must still produce a real binding."""

    def test_enabled_with_a_valid_service_generates_the_vpc_binding(self):
        result, config = run_prepare(
            PRIVATE_BRIDGE_ENABLED="true", AI_BRIDGE_SERVICE_ID=SERVICE_ID)
        self.assertEqual(result.returncode, 0, result.stderr[-600:])
        self.assertEqual(config["vpc_services"],
                         [{"binding": "AI_BRIDGE", "service_id": SERVICE_ID, "remote": True}])
        self.assertIn("PRIVATE_BRIDGE=ENABLED", result.stdout)

    def test_the_v11_service_id_is_still_accepted(self):
        _, config = run_prepare(
            PRIVATE_BRIDGE_ENABLED="true", V11_AI_BRIDGE_SERVICE_ID=SERVICE_ID)
        self.assertEqual(config["vpc_services"][0]["service_id"], SERVICE_ID)

    def test_enabled_without_a_resolvable_service_fails_closed(self):
        """An operator who asked for the bridge and cannot have it must be told,
        not quietly handed a public runtime they did not ask for."""
        result, config = run_prepare(PRIVATE_BRIDGE_ENABLED="true")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PRIVATE_BRIDGE_ENABLED is set but no VPC service", result.stderr)
        self.assertIsNone(config)

    def test_an_invalid_service_id_is_not_accepted_as_a_binding(self):
        result, _ = run_prepare(
            PRIVATE_BRIDGE_ENABLED="true", AI_BRIDGE_SERVICE_ID="not-a-uuid")
        self.assertNotEqual(result.returncode, 0)


class WorkflowRequirementTests(unittest.TestCase):
    """F./§6. The deploy must not demand bridge credentials by default."""

    def setUp(self):
        self.text = DEPLOY_WF.read_text(encoding="utf-8")
        self.workflow = yaml.safe_load(self.text)

    def test_bridge_credentials_are_only_required_when_the_flag_is_true(self):
        self.assertIn('if [ "${PRIVATE_BRIDGE_ENABLED:-false}" = "true" ]', self.text)
        # The old unconditional requirement must be gone.
        self.assertNotIn(
            'if [ -z "${AI_BRIDGE_SERVICE_ID:-}" ] && [ -z "${V11_AI_BRIDGE_SERVICE_ID:-}" ]; then exit 1; fi',
            self.text)

    def test_bybit_private_fallback_explicitly_enables_bridge(self):
        self.assertIn("PRIVATE_BRIDGE_ENABLED: 'true'", self.text)

    def test_every_config_building_step_receives_the_flag(self):
        steps = self.workflow["jobs"]["deploy-exact-main"]["steps"]
        for step in steps:
            env = step.get("env") or {}
            if "V11_AI_BRIDGE_SERVICE_ID" in env:
                self.assertIn("PRIVATE_BRIDGE_ENABLED", env, step.get("name"))


class VerificationLaneCoverageTests(unittest.TestCase):
    """The lane that verifies the Worker must run when the Worker changes."""

    ZERO_LOCAL = ROOT / ".github/workflows/zero-local-cloud-runtime.yml"

    def setUp(self):
        workflow = yaml.safe_load(self.ZERO_LOCAL.read_text(encoding="utf-8"))
        self.on = workflow.get(True) or workflow.get("on")

    def test_the_lane_triggers_on_worker_changes(self):
        """c8a1dc8d changed the Worker, deployed, and this lane never ran - so
        the health and smoke gates went unobserved on the commit that most
        needed them."""
        self.assertIn("cloudflare-worker/**", self.on["push"]["paths"])
        self.assertIn("cloudflare-worker/**", self.on["pull_request"]["paths"])

    def test_push_and_pull_request_watch_exactly_the_same_paths(self):
        """A lane that checks a path pre-merge but not post-merge, or the
        reverse, is a gate with a hole in one direction."""
        self.assertEqual(self.on["push"]["paths"], self.on["pull_request"]["paths"])

    def test_the_private_bridge_test_is_watched(self):
        self.assertIn("tests/test_private_bridge_optional.py", self.on["push"]["paths"])


class CapabilityFailsClosedTests(unittest.TestCase):
    """C. A capability that needs the bridge must refuse, never emulate."""

    def setUp(self):
        self.text = (WORKER / "private-bridge.js").read_text(encoding="utf-8")

    def test_an_explicit_unavailable_state_exists(self):
        self.assertIn("PRIVATE_BRIDGE_UNAVAILABLE", self.text)
        self.assertIn("CAPABILITY_TEMPORARILY_UNAVAILABLE", self.text)

    def test_the_refusal_is_not_a_success_shape(self):
        self.assertIn("ok: false", self.text)
        self.assertIn("degraded: true", self.text)

    def test_the_bridge_is_never_emulated(self):
        self.assertIn("is not emulated", self.text)

    def test_legacy_consumers_still_fail_closed_on_a_missing_binding(self):
        """E./§5: the legacy bridge code stays, and stays strict."""
        for name in ("research-bybit-transport.js", "bybit-v5-client.js"):
            text = (WORKER / name).read_text(encoding="utf-8")
            self.assertIn("BYBIT_VPS_BRIDGE_BINDING_MISSING", text, name)

    def test_health_reports_the_bridge_state_rather_than_assuming_it(self):
        gateway = (WORKER / "research-gateway.js").read_text(encoding="utf-8")
        self.assertIn("privateBridgeState(env)", gateway)
        self.assertIn("bybitTransportPriority(env)", gateway)
        # The hard-coded priority that named a transport it might not have is gone.
        self.assertNotIn("['cloudflare-vpc-bridge','secondary-research-gateway']", gateway)


class LegacyPreservedTests(unittest.TestCase):
    """E. Optional does not mean deleted."""

    def test_the_legacy_bridge_modules_still_exist(self):
        for name in ("research-bybit-transport.js", "bybit-v5-client.js",
                     "bybit-btc-microstructure-client.js", "bybit-android-monitor.js"):
            self.assertTrue((WORKER / name).is_file(), name)

    def test_the_vpc_service_names_are_still_known(self):
        self.assertIn("unified-3ai-bridge", PREPARE.read_text(encoding="utf-8"))
        self.assertIn("v11-ai-bridge", PREPARE.read_text(encoding="utf-8"))


class HardInvariantsUnchangedTests(unittest.TestCase):
    """G./H./I. This change must not disturb the settled invariants."""

    def setUp(self):
        self.manifest = yaml.safe_load(
            (ROOT / "AI_SKILL_LIBRARY/runtime/cloud_runtime.yaml").read_text(encoding="utf-8"))

    def test_railway_remains_absent(self):
        self.assertIs(self.manifest["railway_required"], False)
        for path in (PREPARE, WORKER / "private-bridge.js"):
            self.assertNotIn("railway.app", path.read_text(encoding="utf-8"), str(path))

    def test_paid_fallback_remains_false(self):
        self.assertIs(self.manifest["paid_fallback_allowed"], False)

    def test_personal_pc_remains_not_required(self):
        self.assertIs(self.manifest["personal_pc_required"], False)

    def test_no_duplicate_brain_router_or_model_authority_introduced(self):
        text = (WORKER / "private-bridge.js").read_text(encoding="utf-8")
        for forbidden in ("task_router", "select_model", "routing_authority = true"):
            self.assertNotIn(forbidden, text, forbidden)


if __name__ == "__main__":
    unittest.main()
