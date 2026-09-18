"""Runtime Fabric V2: capacity that cannot become authority, and cannot lie.

Most of these tests DAMAGE something and require a refusal. Tests that assert a
good state pass just as happily when the thing they guard has been removed - the
bugs found in this repository were caught by the damaging kind, never by the
reassuring kind, so that is what this file is made of.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
FABRIC_DIR = ROOT / "AI_SKILL_LIBRARY/v4/runtime_fabric"
REGISTRY_PATH = FABRIC_DIR / "registry.yaml"

_spec = importlib.util.spec_from_file_location("runtime_fabric", FABRIC_DIR / "fabric.py")
fabric = importlib.util.module_from_spec(_spec)
sys.modules["runtime_fabric"] = fabric
_spec.loader.exec_module(fabric)


def registry():
    return yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))


def entry(runtime_id):
    return registry()["runtimes"][runtime_id]


def verified_entry(**overrides):
    """A fully eligible runtime, so a test can damage exactly one thing."""
    base = {
        "class": "edge_serverless",
        "tier": "primary",
        "http": True,
        "capabilities": ["http_api", "research_market"],
        "lifecycle": "STABLE",
        "verification": {axis: True for axis in fabric.VERIFICATION_AXES},
    }
    base.update(overrides)
    return base


class RegistryShapeTests(unittest.TestCase):
    def test_every_required_runtime_is_registered(self):
        runtimes = registry()["runtimes"]
        for required in ("cloudflare_workers", "deno_deploy", "netlify_functions",
                         "github_actions", "koyeb_free", "render_free"):
            self.assertIn(required, runtimes, required)

    def test_tiers_are_as_specified(self):
        runtimes = registry()["runtimes"]
        self.assertEqual(runtimes["cloudflare_workers"]["tier"], "primary")
        self.assertEqual(runtimes["deno_deploy"]["tier"], "secondary")
        self.assertEqual(runtimes["netlify_functions"]["tier"], "tertiary")
        self.assertEqual(runtimes["github_actions"]["tier"], "batch_recovery")
        self.assertEqual(runtimes["koyeb_free"]["tier"], "emergency")
        self.assertEqual(runtimes["render_free"]["tier"], "emergency")

    def test_every_runtime_records_all_verification_axes_separately(self):
        for runtime_id, row in registry()["runtimes"].items():
            verification = row["verification"]
            for axis in fabric.VERIFICATION_AXES:
                self.assertIn(axis, verification, f"{runtime_id}:{axis}")
                self.assertIsInstance(verification[axis], bool, f"{runtime_id}:{axis}")

    def test_no_entry_declares_production_eligible(self):
        """It is derived. A stored copy could disagree with the facts it
        summarises, which is this repository's most-repeated defect."""
        text = REGISTRY_PATH.read_text(encoding="utf-8")
        for runtime_id, row in registry()["runtimes"].items():
            self.assertNotIn("production_eligible", row, runtime_id)
            self.assertNotIn("production_eligible", row.get("verification", {}), runtime_id)
        # Only the comment explaining the absence may mention it.
        self.assertLessEqual(text.count("production_eligible"), 3)

    def test_every_lifecycle_value_is_a_known_lifecycle(self):
        allowed = set(fabric.LIFECYCLE) | {fabric.QUARANTINED_LIFECYCLE}
        for runtime_id, row in registry()["runtimes"].items():
            self.assertIn(row["lifecycle"], allowed, runtime_id)

    def test_tier_order_covers_every_tier_actually_used(self):
        reg = registry()
        used = {row["tier"] for row in reg["runtimes"].values()}
        self.assertTrue(used.issubset(set(reg["tier_order"])),
                        f"tiers not in tier_order: {used - set(reg['tier_order'])}")


class AuthorityTests(unittest.TestCase):
    def test_the_fabric_holds_none_of_the_six_authorities(self):
        report = fabric.RuntimeFabric().authority_report()
        self.assertTrue(report)
        for name, value in report.items():
            self.assertIs(value, False, name)

    def test_offering_an_authority_raises_rather_than_being_ignored(self):
        """Silently ignoring it would let a caller believe it had been granted."""
        for name in fabric.RuntimeFabric._AUTHORITIES:
            with self.subTest(name=name):
                with self.assertRaises(fabric.AuthorityViolation):
                    fabric.RuntimeFabric(**{name: True})

    def test_the_registry_declares_the_fabric_authority_free(self):
        for key, value in registry()["fabric_authority"].items():
            self.assertIs(value, False, key)

    def test_there_is_no_duplicate_brain_router_or_model_authority(self):
        text = (FABRIC_DIR / "fabric.py").read_text(encoding="utf-8")
        for forbidden in ("def route(", "def select_model(", "def admit("):
            self.assertNotIn(forbidden, text, forbidden)


class EligibilityTests(unittest.TestCase):
    def test_a_fully_verified_stable_runtime_is_eligible(self):
        ok, reasons = fabric.eligibility(verified_entry(), capability="http_api")
        self.assertTrue(ok, reasons)
        self.assertEqual(reasons, [])

    def test_each_verification_axis_alone_blocks_eligibility(self):
        """Damages one axis at a time, so no axis can quietly stop mattering."""
        for axis in fabric.VERIFICATION_AXES:
            with self.subTest(axis=axis):
                row = verified_entry()
                row["verification"][axis] = False
                ok, reasons = fabric.eligibility(row, capability="http_api")
                self.assertFalse(ok)
                self.assertIn("not_%s" % axis, reasons)

    def test_the_refusal_names_every_failing_reason_not_just_the_first(self):
        row = verified_entry()
        row["verification"]["deployed"] = False
        row["verification"]["health_verified"] = False
        ok, reasons = fabric.eligibility(row, capability="http_api")
        self.assertFalse(ok)
        self.assertIn("not_deployed", reasons)
        self.assertIn("not_health_verified", reasons)

    def test_a_non_stable_lifecycle_is_never_eligible(self):
        for lifecycle in fabric.LIFECYCLE:
            if lifecycle == fabric.STABLE_LIFECYCLE:
                continue
            with self.subTest(lifecycle=lifecycle):
                row = verified_entry(lifecycle=lifecycle)
                ok, reasons = fabric.eligibility(row, capability="http_api")
                self.assertFalse(ok)

    def test_a_quarantined_runtime_is_never_eligible(self):
        row = verified_entry(lifecycle=fabric.QUARANTINED_LIFECYCLE)
        ok, reasons = fabric.eligibility(row, capability="http_api")
        self.assertFalse(ok)
        self.assertIn("quarantined", reasons)

    def test_a_capability_the_runtime_lacks_is_refused(self):
        ok, reasons = fabric.eligibility(verified_entry(), capability="container_only")
        self.assertFalse(ok)
        self.assertIn("capability_unsupported:container_only", reasons)

    def test_github_actions_can_never_serve_http_however_healthy(self):
        """An ephemeral runner holds no endpoint. Health cannot change that."""
        row = verified_entry(http=False, capabilities=["http_api", "batch"])
        ok, reasons = fabric.eligibility(row, capability="http_api")
        self.assertFalse(ok)
        self.assertIn("not_an_http_runtime", reasons)

    def test_only_selectable_states_are_eligible(self):
        for state in fabric.STATE_VALUES:
            with self.subTest(state=state):
                ok, _ = fabric.eligibility(verified_entry(), capability="http_api",
                                           state=state)
                self.assertEqual(ok, state in fabric.SELECTABLE_STATES)

    def test_production_eligible_agrees_with_eligibility(self):
        """Two ways to ask one question must not be able to disagree."""
        row = verified_entry()
        self.assertEqual(fabric.production_eligible(row, capability="http_api"),
                         fabric.eligibility(row, capability="http_api")[0])
        row["verification"]["deployed"] = False
        self.assertEqual(fabric.production_eligible(row, capability="http_api"),
                         fabric.eligibility(row, capability="http_api")[0])


class ZeroCostGuardTests(unittest.TestCase):
    def test_a_free_verified_runtime_passes(self):
        ok, reasons = fabric.zero_cost_guard(verified_entry())
        self.assertTrue(ok, reasons)

    def test_mandatory_billing_is_refused(self):
        ok, reasons = fabric.zero_cost_guard(verified_entry(), billing_required=True)
        self.assertFalse(ok)
        self.assertIn("billing_required", reasons)

    def test_unverified_free_tier_is_refused_rather_than_assumed(self):
        """A provider having a free plan is not evidence anyone checked."""
        row = verified_entry()
        row["verification"]["free_tier_verified"] = False
        ok, reasons = fabric.zero_cost_guard(row)
        self.assertFalse(ok)
        self.assertIn("free_tier_unverified", reasons)

    def test_exhausted_quota_never_escalates_to_a_paid_path(self):
        ok, reasons = fabric.zero_cost_guard(verified_entry(),
                                             quota_state="QUOTA_EXHAUSTED")
        self.assertFalse(ok)
        self.assertIn("free_quota_exhausted", reasons)

    def test_the_registry_forbids_paid_and_railway_fallback(self):
        reg = registry()
        self.assertIs(reg["paid_fallback_allowed"], False)
        self.assertIs(reg["railway_fallback_allowed"], False)


class CircuitBreakerTests(unittest.TestCase):
    def test_one_failure_does_not_open_the_circuit(self):
        """Failing over on a single transient error causes runtime ping-pong."""
        breaker = fabric.CircuitBreaker(failure_threshold=3)
        self.assertEqual(breaker.record_failure(), "DEGRADED")
        self.assertEqual(breaker.state, "DEGRADED")

    def test_the_threshold_opens_the_circuit(self):
        breaker = fabric.CircuitBreaker(failure_threshold=3)
        breaker.record_failure()
        breaker.record_failure()
        self.assertEqual(breaker.record_failure(), "CIRCUIT_OPEN")

    def test_success_clears_accumulated_failures(self):
        breaker = fabric.CircuitBreaker(failure_threshold=3)
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_success()
        self.assertEqual(breaker.record_failure(), "DEGRADED")

    def test_cooldown_moves_an_open_circuit_to_half_open(self):
        now = [0.0]
        breaker = fabric.CircuitBreaker(failure_threshold=1, cooldown_seconds=30,
                                        clock=lambda: now[0])
        breaker.record_failure()
        self.assertEqual(breaker.state, "CIRCUIT_OPEN")
        now[0] = 29.0
        self.assertEqual(breaker.state, "CIRCUIT_OPEN")
        now[0] = 30.0
        self.assertEqual(breaker.state, "HALF_OPEN")

    def test_a_passing_probe_in_half_open_restores_health(self):
        now = [0.0]
        breaker = fabric.CircuitBreaker(failure_threshold=1, cooldown_seconds=10,
                                        clock=lambda: now[0])
        breaker.record_failure()
        now[0] = 10.0
        self.assertEqual(breaker.state, "HALF_OPEN")
        self.assertEqual(breaker.record_success(), "HEALTHY")

    def test_a_failing_probe_in_half_open_reopens_immediately(self):
        """Half-open is one chance, not a fresh threshold's worth."""
        now = [0.0]
        breaker = fabric.CircuitBreaker(failure_threshold=3, cooldown_seconds=10,
                                        clock=lambda: now[0])
        for _ in range(3):
            breaker.record_failure()
        now[0] = 10.0
        self.assertEqual(breaker.state, "HALF_OPEN")
        self.assertEqual(breaker.record_failure(), "CIRCUIT_OPEN")

    def test_a_zero_threshold_is_refused(self):
        with self.assertRaises(ValueError):
            fabric.CircuitBreaker(failure_threshold=0)


class SelectionTests(unittest.TestCase):
    def _reg(self, **verification_overrides):
        reg = registry()
        for runtime_id, axes in verification_overrides.items():
            reg["runtimes"][runtime_id]["verification"].update(axes)
            reg["runtimes"][runtime_id]["lifecycle"] = "STABLE"
        return reg

    def test_no_eligible_runtime_fails_closed_with_the_named_refusal(self):
        reg = registry()
        states = {
            "cloudflare_workers": "CIRCUIT_OPEN",
            "deno_deploy": "CIRCUIT_OPEN",
            "netlify_functions": "DISABLED",
            "koyeb_free": "DISABLED",
            "render_free": "DISABLED",
        }
        chosen, detail = fabric.select_runtime(reg, capability="http_api", states=states)
        self.assertIsNone(chosen)
        self.assertEqual(detail["refusal"], fabric.NO_ELIGIBLE_RUNTIME)
        self.assertTrue(detail["rejected"])

    def test_cloudflare_is_selected_once_fully_verified(self):
        reg = self._reg(cloudflare_workers={"exact_sha_verified": True})
        chosen, detail = fabric.select_runtime(reg, capability="http_api")
        self.assertEqual(chosen, "cloudflare_workers")
        self.assertEqual(detail["tier"], "primary")

    def test_deno_is_selected_when_the_primary_is_excluded(self):
        reg = self._reg(
            cloudflare_workers={"exact_sha_verified": True},
            deno_deploy={"configured": True, "deployed": True,
                         "health_verified": True, "exact_sha_verified": True},
        )
        chosen, _ = fabric.select_runtime(
            reg, capability="http_api",
            states={"cloudflare_workers": "CIRCUIT_OPEN"})
        self.assertEqual(chosen, "deno_deploy")

    def test_netlify_is_selected_when_primary_and_secondary_are_excluded(self):
        reg = self._reg(
            cloudflare_workers={"exact_sha_verified": True},
            deno_deploy={"configured": True, "deployed": True,
                         "health_verified": True, "exact_sha_verified": True},
            netlify_functions={"configured": True, "deployed": True,
                               "health_verified": True, "exact_sha_verified": True},
        )
        chosen, _ = fabric.select_runtime(
            reg, capability="http_api",
            states={"cloudflare_workers": "QUOTA_EXHAUSTED",
                    "deno_deploy": "CIRCUIT_OPEN"})
        self.assertEqual(chosen, "netlify_functions")

    def test_tier_order_is_respected_not_alphabetical_or_brand_order(self):
        reg = self._reg(
            cloudflare_workers={"exact_sha_verified": True},
            deno_deploy={"configured": True, "deployed": True,
                         "health_verified": True, "exact_sha_verified": True},
        )
        chosen, _ = fabric.select_runtime(reg, capability="http_api")
        # "deno_deploy" sorts before "cloudflare_workers"? No - but both are
        # eligible, and primary must win regardless of name ordering.
        self.assertEqual(chosen, "cloudflare_workers")

    def test_batch_work_routes_to_github_actions(self):
        chosen, _ = fabric.select_runtime(registry(), capability="batch")
        self.assertEqual(chosen, "github_actions")

    def test_github_actions_is_never_chosen_for_http(self):
        reg = self._reg(
            cloudflare_workers={"exact_sha_verified": True},
        )
        chosen, _ = fabric.select_runtime(
            reg, capability="http_api",
            states={"cloudflare_workers": "CIRCUIT_OPEN"})
        self.assertNotEqual(chosen, "github_actions")

    def test_a_container_only_workload_does_not_land_on_an_edge_runtime(self):
        chosen, detail = fabric.select_runtime(registry(), capability="container_only")
        self.assertNotIn(chosen, ("cloudflare_workers", "deno_deploy",
                                  "netlify_functions"))

    def test_exhausted_quota_excludes_a_runtime_from_selection(self):
        reg = self._reg(cloudflare_workers={"exact_sha_verified": True})
        chosen, _ = fabric.select_runtime(
            reg, capability="http_api",
            quota={"cloudflare_workers": "QUOTA_EXHAUSTED"})
        self.assertNotEqual(chosen, "cloudflare_workers")

    def test_mandatory_billing_excludes_a_runtime_from_selection(self):
        reg = self._reg(cloudflare_workers={"exact_sha_verified": True})
        chosen, detail = fabric.select_runtime(
            reg, capability="http_api",
            billing_required={"cloudflare_workers": True})
        self.assertNotEqual(chosen, "cloudflare_workers")

    def test_a_development_runtime_never_receives_stable_traffic(self):
        """Every non-STABLE runtime must be rejected even if fully verified."""
        reg = registry()
        for runtime_id, row in reg["runtimes"].items():
            if row["lifecycle"] == "STABLE":
                continue
            row["verification"].update({axis: True for axis in fabric.VERIFICATION_AXES})
        chosen, detail = fabric.select_runtime(reg, capability="http_api")
        self.assertNotIn(chosen, ("deno_deploy", "netlify_functions",
                                  "koyeb_free", "render_free"))


class EvidenceTests(unittest.TestCase):
    def test_operational_fields_are_accepted(self):
        record = fabric.build_evidence(
            request_id="r1", trace_id="t1", source_sha="a" * 40,
            runtime_id="cloudflare_workers", runtime_revision="b" * 40,
            capability="http_api", health_state_at_selection="HEALTHY",
            quota_state="HEALTHY", latency_ms=12, verifier_result="PASS",
            fallback_used=False)
        self.assertEqual(record["runtime_id"], "cloudflare_workers")

    def test_a_secret_shaped_field_is_refused_not_dropped(self):
        """Dropping it silently would leave a caller believing it was recorded
        and redacted, when it was neither."""
        for bad in ("api_token", "authorization", "chain_of_thought",
                    "reasoning", "password"):
            with self.subTest(field=bad):
                with self.assertRaises(ValueError):
                    fabric.build_evidence(request_id="r1", **{bad: "x"})

    def test_the_allowlist_is_exactly_the_specified_fields(self):
        self.assertEqual(set(fabric.EVIDENCE_FIELDS), {
            "request_id", "trace_id", "source_sha", "runtime_id",
            "runtime_revision", "capability", "health_state_at_selection",
            "quota_state", "latency_ms", "verifier_result", "fallback_used"})


class AntiRailwayRegressionTests(unittest.TestCase):
    def test_railway_is_not_a_registered_runtime(self):
        self.assertNotIn("railway", " ".join(registry()["runtimes"]).lower())

    def test_no_railway_endpoint_appears_in_the_fabric(self):
        for path in (REGISTRY_PATH, FABRIC_DIR / "fabric.py"):
            self.assertNotIn("railway.app", path.read_text(encoding="utf-8"), str(path))

    def test_railway_cannot_be_selected_even_when_added_fully_verified(self):
        """Config is the cheapest way back in, so this adds a PERFECT Railway
        entry - every axis true, STABLE, primary tier - and requires refusal."""
        reg = registry()
        reg["runtimes"]["railway"] = {
            "class": "container", "tier": "primary", "http": True,
            "capabilities": ["http_api"], "lifecycle": "STABLE",
            "verification": {axis: True for axis in fabric.VERIFICATION_AXES},
        }
        chosen, detail = fabric.select_runtime(
            reg, capability="http_api",
            states={"cloudflare_workers": "CIRCUIT_OPEN", "deno_deploy": "CIRCUIT_OPEN"})
        self.assertNotEqual(chosen, "railway")
        self.assertIn("retired_provider:railway", detail["rejected"]["railway"])

    def test_railway_cannot_return_under_a_different_runtime_name(self):
        """Renaming the entry must not launder the endpoint."""
        reg = registry()
        reg["runtimes"]["legacy_gateway"] = {
            "class": "container", "tier": "primary", "http": True,
            "capabilities": ["http_api"], "lifecycle": "STABLE",
            "base_url": "https://crypto-research-gateway-prod-production.up.railway.app",
            "verification": {axis: True for axis in fabric.VERIFICATION_AXES},
        }
        chosen, detail = fabric.select_runtime(
            reg, capability="http_api",
            states={"cloudflare_workers": "CIRCUIT_OPEN", "deno_deploy": "CIRCUIT_OPEN"})
        self.assertNotEqual(chosen, "legacy_gateway")
        self.assertIn("retired_provider:railway",
                      detail["rejected"]["legacy_gateway"])

    def test_a_non_retired_provider_is_not_caught_by_the_guard(self):
        """The guard must refuse Railway, not everything."""
        self.assertEqual(
            fabric.retired_provider_reasons(
                "deno_deploy", {"base_url": "https://x.deno.dev"}), [])


class AdapterArtifactTests(unittest.TestCase):
    """A registry entry that points at nothing is a promise, not a runtime."""

    def test_every_declared_deploy_authority_exists(self):
        for runtime_id, row in registry()["runtimes"].items():
            authority = row.get("deploy_authority")
            if not authority:
                continue
            self.assertTrue((ROOT / authority).is_file(),
                            f"{runtime_id} -> {authority}")

    def test_every_declared_entrypoint_exists(self):
        for runtime_id, row in registry()["runtimes"].items():
            entrypoint = row.get("entrypoint")
            if not entrypoint:
                continue
            self.assertTrue((ROOT / entrypoint).is_file(),
                            f"{runtime_id} -> {entrypoint}")

    def test_every_declared_container_manifest_exists(self):
        for runtime_id, row in registry()["runtimes"].items():
            manifest = row.get("manifest")
            if not manifest:
                continue
            self.assertTrue((ROOT / manifest).is_file(),
                            f"{runtime_id} -> {manifest}")

    def test_the_netlify_adapter_wraps_the_shared_handler(self):
        """It must not reimplement admission. A tertiary that admits what the
        primary rejects is a hole shaped like a failover."""
        text = (ROOT / "netlify/functions/research-gateway.mts").read_text(encoding="utf-8")
        self.assertIn("from '../../deno-secondary/main.ts'", text)
        for forbidden in ("const parseMarketInput", "const ALLOWED_KEYS",
                          "const EXECUTION_VENUES"):
            self.assertNotIn(forbidden, text, forbidden)

    def test_the_netlify_adapter_declares_no_authority(self):
        text = (ROOT / "netlify/functions/research-gateway.mts").read_text(encoding="utf-8")
        for flag in ("ROUTING_AUTHORITY = false", "REASONING_AUTHORITY = false",
                     "MODEL_SELECTION_AUTHORITY = false"):
            self.assertIn("const " + flag, text, flag)

    def test_one_portable_lane_checks_both_portable_runtimes(self):
        text = (ROOT / ".github/workflows/deploy-portable-runtimes.yml").read_text(encoding="utf-8")
        self.assertIn("deno-secondary/main.ts", text)
        self.assertIn("netlify/functions/research-gateway.mts", text)
        # The lane must never claim an unprobed runtime is live.
        self.assertIn("NETLIFY_STATE=ADAPTER_READY", text)
        self.assertIn("NETLIFY_HEALTH=NOT_PROBED", text)
        self.assertIn("DENO_HEALTH=NOT_PROBED", text)


class TruthfulStateTests(unittest.TestCase):
    """Nothing may claim to be live that has not been probed."""

    def test_no_unprobed_runtime_claims_health(self):
        for runtime_id, row in registry()["runtimes"].items():
            verification = row["verification"]
            if verification["health_verified"]:
                self.assertTrue(verification["deployed"],
                                f"{runtime_id} claims health without deployment")

    def test_no_undeployed_runtime_claims_exact_sha(self):
        for runtime_id, row in registry()["runtimes"].items():
            verification = row["verification"]
            if verification["exact_sha_verified"] and row.get("http") is True:
                self.assertTrue(verification["deployed"],
                                f"{runtime_id} claims exact SHA without deployment")

    def test_deno_records_the_live_probe_truthfully(self):
        """A real Deno deployment, exact-SHA probe and research smoke have succeeded."""
        row = entry("deno_deploy")
        verification = row["verification"]
        self.assertEqual(row["lifecycle"], "STABLE")
        self.assertIs(verification["configured"], True)
        self.assertIs(verification["deployed"], True)
        self.assertIs(verification["health_verified"], True)
        self.assertIs(verification["exact_sha_verified"], True)
        self.assertTrue(fabric.production_eligible(row, capability="http_api"))

    def test_netlify_is_adapter_ready_not_verified(self):
        row = entry("netlify_functions")
        self.assertEqual(row["lifecycle"], "ADAPTER_READY")
        self.assertIs(row["verification"]["deployed"], False)
        self.assertIs(row["verification"]["health_verified"], False)

    def test_container_emergency_runtimes_do_not_assume_a_free_tier(self):
        for runtime_id in ("koyeb_free", "render_free"):
            self.assertIs(entry(runtime_id)["verification"]["free_tier_verified"],
                          False, runtime_id)

    def test_cloudflare_records_the_current_exact_revision_honestly(self):
        """Primary has passed health and exact-main deployment verification."""
        verification = entry("cloudflare_workers")["verification"]
        self.assertIs(verification["health_verified"], True)
        self.assertIs(verification["exact_sha_verified"], True)
        self.assertTrue(fabric.production_eligible(
            entry("cloudflare_workers"), capability="http_api"))


class HardInvariantTests(unittest.TestCase):
    def test_canonical_contract_keeps_the_hard_invariants(self):
        manifest = yaml.safe_load(
            (ROOT / "AI_SKILL_LIBRARY/runtime/cloud_runtime.yaml").read_text(encoding="utf-8"))
        self.assertIs(manifest["railway_required"], False)
        self.assertIs(manifest["personal_pc_required"], False)
        self.assertIs(manifest["paid_fallback_allowed"], False)

    def test_states_tuple_is_derived_from_the_state_table(self):
        self.assertEqual(fabric.STATE_VALUES, tuple(fabric.RUNTIME_STATES))

    def test_every_required_state_exists(self):
        for required in ("UNVERIFIED", "PROBING", "HEALTHY", "DEGRADED",
                         "RATE_LIMITED", "QUOTA_LOW", "QUOTA_EXHAUSTED",
                         "CIRCUIT_OPEN", "HALF_OPEN", "COOLDOWN", "DISABLED",
                         "QUARANTINED"):
            self.assertIn(required, fabric.STATE_VALUES, required)


if __name__ == "__main__":
    unittest.main()
