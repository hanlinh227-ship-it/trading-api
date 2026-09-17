"""AUTO_ACTIVATE_WHEN_VERIFIED eligibility and adapter state machine.

An expansion adapter turns itself on only when every condition it actually
requires is verified. Anything that is FAIL, UNKNOWN, missing or raising leaves
it off, and the stable brain keeps working either way. ALWAYS_ON is not a mode
this system has.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "AI_SKILL_LIBRARY/v4/tools"

RUNTIME_ADAPTERS = ("langfuse", "ragas", "deepeval", "browser_use", "baml")
REFERENCE_ONLY = ("microsoft_agent_framework", "letta", "agno")

STATES = ("reference_only", "sandbox_ready", "eligible", "enabled", "degraded", "disabled", "blocked")


def tool():
    path = TOOLS / "brain_expansion_adapters.py"
    spec = importlib.util.spec_from_file_location("brain_expansion_adapters", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def registry():
    return tool().load_adapter_registry(root=ROOT)


def all_pass(module, candidate_id, record):
    """Build a probe map where every required condition passes."""
    return {name: True for name in module.required_conditions(candidate_id, record)}


class AutoActivationPolicy(unittest.TestCase):
    def test_policy_is_auto_activate_when_verified_never_always_on(self):
        policy = tool().auto_activation_policy()
        self.assertEqual(policy["mode"], "AUTO_ACTIVATE_WHEN_VERIFIED")
        self.assertTrue(policy["auto_activate_when_verified"])
        self.assertFalse(policy["always_on"])
        self.assertTrue(policy["fail_closed"])
        self.assertTrue(policy["unknown_is_failure"])
        self.assertFalse(policy["paid_dependency_auto_install"])
        self.assertFalse(policy["billing_auto_enable"])
        self.assertFalse(policy["fast_path_synchronous_probe"])
        self.assertGreater(int(policy["eligibility_ttl_seconds"]), 0)

    def test_always_on_is_not_a_supported_mode_anywhere(self):
        module = tool()
        for rel in (
            "AI_SKILL_LIBRARY/v4/tools/brain_expansion_adapters.py",
            "AI_SKILL_LIBRARY/v4/integrations/brain_expansion_adapters.yaml",
        ):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("ALWAYS_ON", text, rel)
        self.assertNotIn("ALWAYS_ON", json.dumps(module.auto_activation_policy()))

    def test_condition_set_covers_every_mandated_gate(self):
        expected = {
            "license_verified",
            "dependency_audit",
            "dependency_available",
            "security_policy",
            "credential_present",
            "network_allowed",
            "runtime_health_probe",
            "sandbox_test",
            "no_protected_regression",
            "rollback_verified",
        }
        self.assertEqual(set(tool().AUTO_ACTIVATION_CONDITIONS), expected)


class EligibilityEvaluation(unittest.TestCase):
    def test_all_conditions_pass_auto_enables_the_adapter(self):
        module, reg = tool(), registry()
        for adapter_id in RUNTIME_ADAPTERS:
            with self.subTest(adapter=adapter_id):
                record = reg["candidates"][adapter_id]
                result = module.evaluate_eligibility(adapter_id, record, probes=all_pass(module, adapter_id, record))
                self.assertEqual(result["state"], "enabled", result["reason"])
                self.assertTrue(result["enabled"])

    def test_any_single_failed_condition_keeps_the_adapter_off(self):
        module, reg = tool(), registry()
        for adapter_id in RUNTIME_ADAPTERS:
            record = reg["candidates"][adapter_id]
            for condition in module.required_conditions(adapter_id, record):
                with self.subTest(adapter=adapter_id, condition=condition):
                    probes = all_pass(module, adapter_id, record)
                    probes[condition] = False
                    result = module.evaluate_eligibility(adapter_id, record, probes=probes)
                    self.assertFalse(result["enabled"], f"{adapter_id}: {condition} FAIL must not enable")
                    self.assertIn(result["state"], ("disabled", "degraded", "blocked"))
                    self.assertIn(condition, result["failed"])

    def test_unknown_condition_is_treated_as_failure(self):
        module, reg = tool(), registry()
        for adapter_id in RUNTIME_ADAPTERS:
            record = reg["candidates"][adapter_id]
            for condition in module.required_conditions(adapter_id, record):
                with self.subTest(adapter=adapter_id, condition=condition):
                    probes = all_pass(module, adapter_id, record)
                    probes[condition] = None
                    result = module.evaluate_eligibility(adapter_id, record, probes=probes)
                    self.assertFalse(result["enabled"])
                    self.assertIn(condition, result["unknown"])

    def test_missing_probe_is_unknown_not_optimistic(self):
        module, reg = tool(), registry()
        record = reg["candidates"]["ragas"]
        result = module.evaluate_eligibility("ragas", record, probes={})
        self.assertFalse(result["enabled"])
        self.assertEqual(result["state"], "disabled")
        self.assertTrue(result["unknown"])

    def test_probe_that_raises_never_propagates_and_fails_closed(self):
        module, reg = tool(), registry()

        def exploding_probe(_name):
            raise RuntimeError("probe backend down")

        result = module.evaluate_eligibility("ragas", reg["candidates"]["ragas"], probe_fn=exploding_probe)
        self.assertFalse(result["enabled"])
        self.assertEqual(result["state"], "disabled")
        self.assertTrue(result["unknown"])

    def test_health_failure_after_verification_degrades_rather_than_claiming_enabled(self):
        module, reg = tool(), registry()
        record = reg["candidates"]["langfuse"]
        probes = all_pass(module, "langfuse", record)
        probes["runtime_health_probe"] = False
        result = module.evaluate_eligibility("langfuse", record, probes=probes)
        self.assertEqual(result["state"], "degraded")
        self.assertFalse(result["enabled"])

    def test_license_failure_blocks_rather_than_merely_disables(self):
        module, reg = tool(), registry()
        record = reg["candidates"]["langfuse"]
        probes = all_pass(module, "langfuse", record)
        probes["license_verified"] = False
        result = module.evaluate_eligibility("langfuse", record, probes=probes)
        self.assertEqual(result["state"], "blocked")
        self.assertFalse(result["enabled"])

    def test_security_failure_blocks(self):
        module, reg = tool(), registry()
        record = reg["candidates"]["browser_use"]
        probes = all_pass(module, "browser_use", record)
        probes["security_policy"] = False
        result = module.evaluate_eligibility("browser_use", record, probes=probes)
        self.assertEqual(result["state"], "blocked")
        self.assertFalse(result["enabled"])

    def test_eligible_state_when_policy_is_off_but_conditions_pass(self):
        module, reg = tool(), registry()
        record = reg["candidates"]["baml"]
        result = module.evaluate_eligibility(
            "baml", record, probes=all_pass(module, "baml", record), auto_activate=False
        )
        self.assertEqual(result["state"], "eligible")
        self.assertFalse(result["enabled"])

    def test_every_state_is_in_the_declared_state_machine(self):
        module, reg = tool(), registry()
        self.assertEqual(set(module.ADAPTER_STATES), set(STATES))
        for candidate_id, record in reg["candidates"].items():
            with self.subTest(candidate=candidate_id):
                self.assertIn(module.evaluate_eligibility(candidate_id, record, probes={})["state"], STATES)

    def test_no_result_ever_claims_production_verified_without_runtime_evidence(self):
        module, reg = tool(), registry()
        for candidate_id, record in reg["candidates"].items():
            with self.subTest(candidate=candidate_id):
                result = module.evaluate_eligibility(candidate_id, record, probes=all_pass(module, candidate_id, record))
                self.assertNotEqual(result["state"], "production_verified")
                self.assertNotIn("production_verified", json.dumps(result))


class PerAdapterRequirements(unittest.TestCase):
    def test_offline_eval_adapters_do_not_require_credential_or_network(self):
        module, reg = tool(), registry()
        for adapter_id in ("ragas", "deepeval", "baml"):
            with self.subTest(adapter=adapter_id):
                required = set(module.required_conditions(adapter_id, reg["candidates"][adapter_id]))
                self.assertNotIn("credential_present", required)
                self.assertNotIn("network_allowed", required)
                self.assertIn("dependency_available", required)
                self.assertIn("sandbox_test", required)

    def test_langfuse_requires_the_full_gate_including_credential_and_egress(self):
        module, reg = tool(), registry()
        required = set(module.required_conditions("langfuse", reg["candidates"]["langfuse"]))
        self.assertEqual(required, set(module.AUTO_ACTIVATION_CONDITIONS))

    def test_browser_use_requires_runtime_health_but_not_credential(self):
        module, reg = tool(), registry()
        required = set(module.required_conditions("browser_use", reg["candidates"]["browser_use"]))
        self.assertIn("runtime_health_probe", required)
        self.assertNotIn("credential_present", required)

    def test_browser_use_auto_enables_only_into_read_only_sandbox(self):
        module, reg = tool(), registry()
        record = reg["candidates"]["browser_use"]
        result = module.evaluate_eligibility("browser_use", record, probes=all_pass(module, "browser_use", record))
        self.assertEqual(result["state"], "enabled")
        self.assertEqual(result["activation_mode"], "READ_ONLY_SANDBOX")
        self.assertEqual(result["default_risk_class"], "read_only")

    def test_langfuse_never_activates_against_the_open_core_server_repo(self):
        module, reg = tool(), registry()
        record = reg["candidates"]["langfuse"]
        self.assertEqual(module.activation_upstream("langfuse", record)["repo"], "langfuse/langfuse-python")
        hostile = json.loads(json.dumps(record))
        hostile["activation_path"]["candidate_upstream"] = "langfuse/langfuse"
        result = module.evaluate_eligibility("langfuse", hostile, probes=all_pass(module, "langfuse", record))
        self.assertEqual(result["state"], "blocked")
        self.assertFalse(result["enabled"])

    def test_reference_only_candidates_never_become_eligible(self):
        module, reg = tool(), registry()
        for candidate_id in REFERENCE_ONLY:
            with self.subTest(candidate=candidate_id):
                record = reg["candidates"][candidate_id]
                self.assertEqual(module.required_conditions(candidate_id, record), ())
                result = module.evaluate_eligibility(
                    candidate_id, record, probes={name: True for name in module.AUTO_ACTIVATION_CONDITIONS}
                )
                self.assertEqual(result["state"], "reference_only")
                self.assertFalse(result["enabled"])


class BootEligibilityFlow(unittest.TestCase):
    def test_boot_never_probes_synchronously_on_the_fast_path(self):
        module, reg = tool(), registry()
        calls: list = []

        def counting_probe(name):
            calls.append(name)
            return True

        result = module.boot_eligibility(registry=reg, probe_fn=counting_probe, profile="FAST")
        self.assertEqual(calls, [], "FAST must not add upstream probe latency")
        self.assertFalse(result["probed"])
        for row in result["adapters"].values():
            self.assertFalse(row["enabled"])

    def test_boot_probes_on_standard_and_deep(self):
        module, reg = tool(), registry()
        for profile in ("STANDARD", "DEEP"):
            with self.subTest(profile=profile):
                calls: list = []
                module.boot_eligibility(registry=reg, probe_fn=lambda n: calls.append(n) or True, profile=profile)
                self.assertTrue(calls)

    def test_boot_keeps_the_stable_brain_up_when_every_probe_fails(self):
        module, reg = tool(), registry()
        result = module.boot_eligibility(registry=reg, probe_fn=lambda _n: False, profile="STANDARD")
        self.assertTrue(result["stable_path_ok"])
        self.assertEqual(result["enabled_adapters"], [])
        self.assertEqual(result["router_authority"], "task_router")
        self.assertEqual(result["memory_authority"], "memory_continuity")

    def test_boot_keeps_the_stable_brain_up_when_probing_explodes(self):
        module, reg = tool(), registry()

        def exploding(_name):
            raise OSError("network unreachable")

        result = module.boot_eligibility(registry=reg, probe_fn=exploding, profile="DEEP")
        self.assertTrue(result["stable_path_ok"])
        self.assertEqual(result["enabled_adapters"], [])

    def test_cached_eligibility_is_reused_until_ttl_expires(self):
        module, reg = tool(), registry()
        calls: list = []
        cache: dict = {}

        def probe(name):
            calls.append(name)
            return True

        module.boot_eligibility(registry=reg, probe_fn=probe, profile="STANDARD", cache=cache, now=1000.0)
        first = len(calls)
        self.assertGreater(first, 0)
        module.boot_eligibility(registry=reg, probe_fn=probe, profile="STANDARD", cache=cache, now=1001.0)
        self.assertEqual(len(calls), first, "fresh cache must not re-probe")
        ttl = int(module.auto_activation_policy()["eligibility_ttl_seconds"])
        module.boot_eligibility(registry=reg, probe_fn=probe, profile="STANDARD", cache=cache, now=1000.0 + ttl + 1)
        self.assertGreater(len(calls), first, "expired cache must re-probe")

    def test_boot_result_never_grants_authority(self):
        module, reg = tool(), registry()
        result = module.boot_eligibility(registry=reg, probe_fn=lambda _n: True, profile="STANDARD")
        for row in result["adapters"].values():
            for claim in ("routing_authority", "reasoning_authority", "memory_authority", "model_selection_authority"):
                self.assertFalse(row[claim])


class FailureIsolationMatrix(unittest.TestCase):
    SCENARIOS = (
        ("upstream_down", "runtime_health_probe"),
        ("dependency_missing", "dependency_available"),
        ("credential_absent", "credential_present"),
        ("network_blocked", "network_allowed"),
        ("sandbox_test_failed", "sandbox_test"),
        ("protected_regression", "no_protected_regression"),
        ("rollback_unverified", "rollback_verified"),
    )

    def test_each_failure_mode_degrades_the_adapter_and_spares_the_brain(self):
        module, reg = tool(), registry()
        for scenario, condition in self.SCENARIOS:
            for adapter_id in RUNTIME_ADAPTERS:
                record = reg["candidates"][adapter_id]
                if condition not in module.required_conditions(adapter_id, record):
                    continue
                with self.subTest(scenario=scenario, adapter=adapter_id):
                    probes = all_pass(module, adapter_id, record)
                    probes[condition] = False
                    result = module.evaluate_eligibility(adapter_id, record, probes=probes)
                    self.assertFalse(result["enabled"])
                    self.assertTrue(result["stable_path_ok"])

    def test_http_error_classes_and_timeouts_never_enable(self):
        module, reg = tool(), registry()
        for outcome in ("401", "403", "429", "500", "502", "503", "timeout", "malformed_response"):
            with self.subTest(outcome=outcome):
                verdict = module.classify_probe_outcome(outcome)
                self.assertIn(verdict, (False, None))
                result = module.evaluate_eligibility(
                    "langfuse",
                    reg["candidates"]["langfuse"],
                    probes={**all_pass(module, "langfuse", reg["candidates"]["langfuse"]),
                            "runtime_health_probe": verdict},
                )
                self.assertFalse(result["enabled"])

    def test_auth_failures_never_widen_permissions_or_fall_back_to_paid(self):
        module, reg = tool(), registry()
        record = reg["candidates"]["langfuse"]
        probes = all_pass(module, "langfuse", record)
        probes["credential_present"] = False
        result = module.evaluate_eligibility("langfuse", record, probes=probes)
        self.assertFalse(result["enabled"])
        self.assertFalse(result["permission_widened"])
        self.assertFalse(result["paid_fallback"])

    def test_eligibility_result_leaks_no_secret_material(self):
        module, reg = tool(), registry()
        record = reg["candidates"]["langfuse"]
        probes = all_pass(module, "langfuse", record)
        result = module.evaluate_eligibility(
            "langfuse", record, probes=probes,
            context={"api_key": "s" + "k-live-abcdef0123456789", "token": "Bearer abc123"},
        )
        blob = json.dumps(result)
        self.assertNotIn("sk-live-abcdef0123456789", blob)
        self.assertNotIn("Bearer abc123", blob)


class RegistryPolicyBinding(unittest.TestCase):
    def test_registry_declares_the_auto_activation_policy(self):
        reg = registry()
        policy = reg["auto_activation"]
        self.assertEqual(policy["mode"], "AUTO_ACTIVATE_WHEN_VERIFIED")
        self.assertTrue(policy["auto_activate_when_verified"])
        self.assertFalse(policy["always_on"])
        self.assertTrue(policy["fail_closed"])

    def test_every_runtime_adapter_declares_its_required_conditions(self):
        module, reg = tool(), registry()
        for adapter_id in RUNTIME_ADAPTERS:
            with self.subTest(adapter=adapter_id):
                declared = reg["candidates"][adapter_id]["auto_activation"]["required_conditions"]
                self.assertEqual(tuple(declared), module.required_conditions(adapter_id, reg["candidates"][adapter_id]))
                self.assertTrue(set(declared).issubset(set(module.AUTO_ACTIVATION_CONDITIONS)))

    def test_committed_registry_has_no_adapter_enabled_without_runtime_evidence(self):
        reg = registry()
        for candidate_id, record in reg["candidates"].items():
            with self.subTest(candidate=candidate_id):
                if record["enabled"]:
                    self.assertTrue(record.get("runtime_evidence"), candidate_id)


if __name__ == "__main__":
    unittest.main()
