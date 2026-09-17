"""Production activation runtime for Brain Expansion adapters.

The runtime probes each adapter for real: is the dependency importable, is the
credential present, is the egress reachable, does the upstream answer, does the
adapter's own sandbox test pass. Anything it cannot prove leaves the adapter off.

These tests pin the contract of the probe runner itself: it must never enable on
an unproven condition, never carry a secret value into its report, never let a
probe failure escape, and never claim an adapter is LIVE without evidence.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "AI_SKILL_LIBRARY/v4/tools"

RUNTIME_ADAPTERS = ("langfuse", "ragas", "deepeval", "browser_use", "baml")


def load(name: str):
    path = TOOLS / f"{name}.py"
    if not path.is_file():
        raise AssertionError(f"missing tool: {path.relative_to(ROOT)}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def runtime():
    return load("activate_brain_expansion")


class ProbeRegistry(unittest.TestCase):
    def test_every_runtime_adapter_has_a_real_probe_for_each_required_condition(self):
        rt, adapters = runtime(), load("brain_expansion_adapters")
        reg = adapters.load_adapter_registry(root=ROOT)
        for adapter_id in RUNTIME_ADAPTERS:
            with self.subTest(adapter=adapter_id):
                record = reg["candidates"][adapter_id]
                probes = rt.build_probes(adapter_id, record, root=ROOT)
                for condition in adapters.required_conditions(adapter_id, record):
                    self.assertIn(condition, probes, f"{adapter_id}: {condition} has no probe")
                    self.assertTrue(callable(probes[condition]))

    def test_dependency_probe_reflects_real_import_state(self):
        """The probe must agree with the interpreter, in either direction.

        Asserting that a particular optional package *is* installed would make
        this a test of the image rather than of the probe: the validator CI
        deliberately does not install the extras, so the adapters are absent
        there and present in an activation run. Compare against ground truth
        instead, so the test holds in both.
        """
        rt = runtime()
        for adapter_id, module in rt.ADAPTER_MODULES.items():
            with self.subTest(adapter=adapter_id):
                expected = importlib.util.find_spec(module) is not None
                self.assertIs(rt.dependency_available(adapter_id), expected)
        self.assertFalse(rt.dependency_available("definitely_not_a_real_adapter"))

    def test_dependency_probe_is_false_for_an_unmapped_or_missing_module(self):
        rt = runtime()
        original = rt.ADAPTER_MODULES.get("baml")
        rt.ADAPTER_MODULES["baml"] = "a_module_that_is_not_installed_anywhere"
        try:
            self.assertFalse(rt.dependency_available("baml"))
        finally:
            if original is not None:
                rt.ADAPTER_MODULES["baml"] = original

    def test_credential_probe_reports_names_never_values(self):
        rt = runtime()
        result = rt.credential_status("langfuse", env={"LANGFUSE_PUBLIC_KEY": "pk-secret-value",
                                                       "LANGFUSE_SECRET_KEY": "s" + "k-secret-value"})
        self.assertTrue(result["present"])
        self.assertEqual(sorted(result["required"]), ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"])
        blob = json.dumps(result)
        self.assertNotIn("pk-secret-value", blob)
        self.assertNotIn("sk-secret-value", blob)

    def test_missing_credential_is_a_definite_failure_not_unknown(self):
        rt = runtime()
        self.assertFalse(rt.credential_status("langfuse", env={})["present"])

    def test_adapters_without_credentials_report_not_required(self):
        rt = runtime()
        for adapter_id in ("ragas", "deepeval", "baml"):
            with self.subTest(adapter=adapter_id):
                self.assertEqual(rt.credential_status(adapter_id, env={})["required"], [])


class ActivationSweep(unittest.TestCase):
    def test_sweep_produces_a_state_for_every_candidate(self):
        rt, adapters = runtime(), load("brain_expansion_adapters")
        report = rt.activation_sweep(root=ROOT, env={})
        reg = adapters.load_adapter_registry(root=ROOT)
        self.assertEqual(set(report["adapters"]), set(reg["candidates"]))
        for row in report["adapters"].values():
            self.assertIn(row["state"], adapters.ADAPTER_STATES)

    def test_sweep_never_enables_an_adapter_whose_dependency_is_absent(self):
        rt = runtime()
        report = rt.activation_sweep(root=ROOT, env={})
        for adapter_id, row in report["adapters"].items():
            if row["conditions"].get("dependency_available") == "FAIL":
                with self.subTest(adapter=adapter_id):
                    self.assertFalse(row["enabled"])

    def test_sweep_never_enables_langfuse_without_credentials(self):
        rt = runtime()
        report = rt.activation_sweep(root=ROOT, env={})
        langfuse = report["adapters"]["langfuse"]
        self.assertFalse(langfuse["enabled"])
        self.assertIn(langfuse["conditions"]["credential_present"], ("FAIL", "UNKNOWN"))

    def test_sweep_report_carries_no_secret_material(self):
        rt = runtime()
        report = rt.activation_sweep(
            root=ROOT,
            env={"LANGFUSE_PUBLIC_KEY": "pk-live-should-never-appear",
                 "LANGFUSE_SECRET_KEY": "s" + "k-live-should-never-appear"},
        )
        blob = json.dumps(report)
        self.assertNotIn("pk-live-should-never-appear", blob)
        self.assertNotIn("sk-live-should-never-appear", blob)

    def test_sweep_keeps_the_stable_brain_up(self):
        rt = runtime()
        report = rt.activation_sweep(root=ROOT, env={})
        self.assertTrue(report["stable_path_ok"])
        self.assertEqual(report["router_authority"], "task_router")
        self.assertEqual(report["memory_authority"], "memory_continuity")

    def test_sweep_records_evidence_for_each_enabled_adapter(self):
        rt = runtime()
        report = rt.activation_sweep(root=ROOT, env={})
        for adapter_id, row in report["adapters"].items():
            if row["enabled"]:
                with self.subTest(adapter=adapter_id):
                    self.assertTrue(row["evidence"], f"{adapter_id}: enabled without recorded evidence")

    def test_sweep_survives_a_probe_that_raises(self):
        rt = runtime()

        def exploding(_adapter_id, _record, **_kwargs):
            raise RuntimeError("probe backend exploded")

        report = rt.activation_sweep(root=ROOT, env={}, probe_builder=exploding)
        self.assertTrue(report["stable_path_ok"])
        self.assertEqual(report["enabled"], [])

    def test_report_is_json_serialisable_and_declares_no_authority(self):
        rt = runtime()
        report = rt.activation_sweep(root=ROOT, env={})
        json.dumps(report)
        for row in report["adapters"].values():
            for claim in ("routing_authority", "reasoning_authority", "memory_authority", "model_selection_authority"):
                self.assertFalse(row[claim])


class RevalidationAndRecovery(unittest.TestCase):
    def test_fresh_entries_are_not_reprobed_before_ttl(self):
        rt = runtime()
        cache: dict = {}
        first = rt.revalidate(root=ROOT, env={}, cache=cache, now=1000.0)
        self.assertTrue(first["probed"])
        second = rt.revalidate(root=ROOT, env={}, cache=cache, now=1010.0)
        self.assertFalse(second["probed"], "fresh cache must not re-probe")

    def test_expired_entries_are_reprobed(self):
        rt, adapters = runtime(), load("brain_expansion_adapters")
        ttl = int(adapters.auto_activation_policy()["eligibility_ttl_seconds"])
        cache: dict = {}
        rt.revalidate(root=ROOT, env={}, cache=cache, now=1000.0)
        later = rt.revalidate(root=ROOT, env={}, cache=cache, now=1000.0 + ttl + 1)
        self.assertTrue(later["probed"])

    def test_degraded_adapter_recovers_when_health_returns(self):
        rt = runtime()
        recovered = rt.apply_health_transition(
            previous={"state": "degraded", "enabled": False},
            current={"state": "enabled", "enabled": True},
        )
        self.assertEqual(recovered["state"], "enabled")
        self.assertTrue(recovered["enabled"])
        self.assertTrue(recovered["recovered"])

    def test_enabled_adapter_degrades_when_health_drops(self):
        rt = runtime()
        dropped = rt.apply_health_transition(
            previous={"state": "enabled", "enabled": True},
            current={"state": "degraded", "enabled": False},
        )
        self.assertEqual(dropped["state"], "degraded")
        self.assertFalse(dropped["enabled"])
        self.assertFalse(dropped["recovered"])

    def test_recovery_never_resurrects_a_blocked_adapter(self):
        rt = runtime()
        still_blocked = rt.apply_health_transition(
            previous={"state": "blocked", "enabled": False},
            current={"state": "enabled", "enabled": True},
        )
        self.assertEqual(still_blocked["state"], "blocked")
        self.assertFalse(still_blocked["enabled"])


class ActivationReportArtifact(unittest.TestCase):
    def test_write_report_is_deterministic_and_secret_free(self, ):
        rt = runtime()
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "activation.json"
            report = rt.activation_sweep(root=ROOT, env={})
            rt.write_report(report, out)
            written = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(written["adapters"].keys(), report["adapters"].keys())
            for token in ("sk-", "Bearer ", "BEGIN PRIVATE KEY"):
                self.assertNotIn(token, out.read_text(encoding="utf-8"))

    def test_cli_exits_zero_even_when_every_adapter_is_off(self):
        rt = runtime()
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            code = rt.main(["--root", str(ROOT), "--output", str(Path(tmp) / "a.json"), "--no-env"])
            self.assertEqual(code, 0, "adapters being off is a normal outcome, not a build failure")


if __name__ == "__main__":
    unittest.main()
