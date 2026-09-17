"""Browser Use isolated runtime: the last Brain Expansion activation blocker.

`browser_use` was the only runtime adapter left at `dependency_available=FAIL`.
The cause was never the adapter contract: `browser-use` pulls Playwright and a
Chromium binary, and installing it into an image whose `PyJWT` came from the
system package manager fails. The fix is a *dedicated interpreter*, not a
forced install: a clean virtualenv that owns its own dependency tree, with the
system Python left exactly as it was.

These tests pin that runtime, the sandbox contract it runs under, and the
evidence merge that lets one activation report speak for two interpreters.
They are deliberately written so they hold in both places: the validator CI
where `browser-use` is absent, and the browser runtime job where it is present.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "AI_SKILL_LIBRARY/v4/tools"
WORKFLOW = ROOT / ".github/workflows/ai-skill-library-ci.yml"
BROWSER_REQUIREMENTS = ROOT / "AI_SKILL_LIBRARY/requirements-brain-expansion-browser.txt"
BASE_REQUIREMENTS = ROOT / "AI_SKILL_LIBRARY/requirements-brain-expansion.txt"


def load(name: str):
    path = TOOLS / f"{name}.py"
    if not path.is_file():
        raise AssertionError(f"missing tool: {path.relative_to(ROOT)}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def registry_record(adapter_id: str = "browser_use") -> dict:
    adapters = load("brain_expansion_adapters")
    return adapters.load_adapter_registry(root=ROOT)["candidates"][adapter_id]


def playwright_available() -> bool:
    try:
        return importlib.util.find_spec("playwright") is not None
    except (ImportError, ValueError):
        return False


# ---------------------------------------------------------------------------
# the isolated runtime itself
# ---------------------------------------------------------------------------


class IsolatedRuntimeDefinition(unittest.TestCase):
    def test_browser_dependencies_are_pinned_in_their_own_requirements_file(self):
        self.assertTrue(BROWSER_REQUIREMENTS.is_file(), f"missing {BROWSER_REQUIREMENTS}")
        text = BROWSER_REQUIREMENTS.read_text(encoding="utf-8")
        pins = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        self.assertTrue(pins, "browser runtime requirements declare no packages")
        for pin in pins:
            self.assertIn("==", pin, f"unpinned browser dependency: {pin!r}")
        joined = " ".join(pins)
        self.assertIn("browser-use==", joined)
        self.assertIn("playwright==", joined)

    def test_the_pinned_version_matches_the_audited_upstream_ref(self):
        record = registry_record()
        tag = str(record["upstream"]["tag"])
        text = BROWSER_REQUIREMENTS.read_text(encoding="utf-8")
        self.assertIn(f"browser-use=={tag}", text,
                      "the installed version must be the version that was licence/dependency audited")

    def test_no_requirements_file_breaks_system_packages(self):
        """`--ignore-installed` would step on Debian-managed packages. Never.

        Only the directive lines count: the files explain in prose *why* those
        flags are forbidden, and that prose must not be what trips the check.
        """
        for path in (BROWSER_REQUIREMENTS, BASE_REQUIREMENTS):
            directives = [
                line.strip()
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
            for directive in directives:
                self.assertNotIn("--ignore-installed", directive, f"{path.name} forces over system packages")
                self.assertNotIn("--break-system-packages", directive, f"{path.name} forces over system packages")

    def test_the_stable_extras_file_does_not_install_the_browser_runtime(self):
        """The ordinary extras install must stay browser-free.

        Installing `browser-use` beside the other extras is what fails; the
        browser runtime is reached through its own file and its own interpreter.
        """
        for line in BASE_REQUIREMENTS.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                continue
            self.assertNotIn("browser-use", stripped)
            self.assertNotIn("playwright", stripped)


class IsolatedRuntimeJob(unittest.TestCase):
    """The CI job is the runtime. Its shape is part of the contract."""

    def setUp(self):
        self.assertTrue(WORKFLOW.is_file())
        self.text = WORKFLOW.read_text(encoding="utf-8")
        # What the job *runs*, with the prose stripped: the workflow explains why
        # the forbidden pip flags are forbidden, and that explanation must not be
        # what trips the check that looks for them.
        self.commands = "\n".join(
            line for line in self.text.splitlines() if not line.lstrip().startswith("#")
        )

    def contains(self, needle: str, why: str):
        """Assert on the workflow without dumping the whole file into the failure."""
        self.assertTrue(needle in self.text, f"{WORKFLOW.name}: {why} (missing {needle!r})")

    def lacks(self, needle: str, why: str):
        self.assertTrue(needle not in self.commands, f"{WORKFLOW.name}: {why} (found {needle!r})")

    def test_a_dedicated_job_exists_for_the_browser_runtime(self):
        self.contains("brain-expansion-browser-runtime:", "no dedicated browser runtime job")

    def test_it_builds_its_own_virtualenv_rather_than_using_the_job_interpreter(self):
        self.contains("python -m venv", "the browser runtime must own its interpreter")
        self.contains("requirements-brain-expansion-browser.txt", "browser pins are not installed")

    def test_it_never_forces_installs_over_system_packages(self):
        self.lacks("--ignore-installed", "forces installs over system packages")
        self.lacks("--break-system-packages", "forces installs over system packages")

    def test_it_installs_a_real_browser_engine(self):
        self.contains("playwright install", "no browser engine is installed")
        self.contains("chromium", "no chromium build is requested")

    def test_it_proves_the_stable_path_with_every_adapter_off_first(self):
        self.contains("--no-env", "no all-adapters-off baseline")
        self.contains("stable_path_ok", "the baseline does not assert the stable path")

    def test_it_requires_browser_use_to_actually_enable(self):
        self.contains("--require browser_use", "the job would pass with browser_use still off")

    def test_it_scans_its_evidence_for_credential_material(self):
        self.contains("BEGIN [A-Z ]*PRIVATE KEY", "no secret-leak scan over the evidence")

    def test_the_merged_evidence_step_asserts_every_runtime_adapter(self):
        self.contains("merge_activation_reports.py", "the two runtimes are never merged into one report")


# ---------------------------------------------------------------------------
# activation gates for browser_use
# ---------------------------------------------------------------------------


class BrowserActivationGates(unittest.TestCase):
    def test_required_gates_match_the_read_only_sandbox_contract(self):
        record = registry_record()
        adapters = load("brain_expansion_adapters")
        required = set(adapters.required_conditions("browser_use", record))
        self.assertEqual(
            required,
            {
                "license_verified",
                "dependency_audit",
                "dependency_available",
                "security_policy",
                "runtime_health_probe",
                "sandbox_test",
                "no_protected_regression",
                "rollback_verified",
            },
        )
        self.assertEqual(record["auto_activation"]["activation_mode"], "READ_ONLY_SANDBOX")
        self.assertEqual(record["auto_activation"]["default_risk_class"], "read_only")

    def test_network_is_not_a_gate_because_the_sandbox_forbids_egress(self):
        """`network_allowed` is absent on purpose, and the registry must say why."""
        record = registry_record()
        contract = record.get("runtime_contract")
        self.assertIsInstance(contract, dict, "browser_use must declare a runtime_contract")
        self.assertNotIn("network_allowed", record["auto_activation"]["required_conditions"])
        self.assertIn("egress", contract)
        self.assertIn("isolation", contract)
        self.assertFalse(record["enabled"], "activation is a boot decision, never a checked-in flag")
        self.assertFalse(record["network_execution_enabled"])

    def test_the_runtime_contract_forbids_persistence_and_financial_execution(self):
        contract = registry_record()["runtime_contract"]
        self.assertIs(contract["credential_persistence"], False)
        self.assertIs(contract["session_persistence"], False)
        self.assertIs(contract["cookie_persistence"], False)
        self.assertIs(contract["financial_execution"], False)
        self.assertIs(contract["destructive_actions"], False)
        self.assertIs(contract["selects_own_objective"], False)
        self.assertEqual(contract["routed_by"], "task_router")

    def test_every_required_gate_has_a_real_probe(self):
        rt, adapters = load("activate_brain_expansion"), load("brain_expansion_adapters")
        record = registry_record()
        probes = rt.build_probes("browser_use", record, root=ROOT)
        for condition in adapters.required_conditions("browser_use", record):
            self.assertIn(condition, probes)
            self.assertTrue(callable(probes[condition]))

    def test_no_adapter_is_hard_coded_on(self):
        for path in (
            TOOLS / "activate_brain_expansion.py",
            TOOLS / "brain_expansion_adapters.py",
            TOOLS / "merge_activation_reports.py",
            ROOT / "AI_SKILL_LIBRARY/v4/integrations/brain_expansion_adapters.yaml",
        ):
            self.assertNotIn("ALWAYS_ON", path.read_text(encoding="utf-8"), f"{path.name} carries an always-on mode")


class BrowserHealthProbe(unittest.TestCase):
    def test_a_missing_engine_is_a_definite_fail_not_a_crash(self):
        rt = load("activate_brain_expansion")
        self.assertIn(rt._browser_runtime_healthy(engine="a_module_that_is_not_installed"), (False,))

    def test_a_hanging_engine_times_out_to_unknown_and_stays_off(self):
        """A probe that never returns must fail closed, not hang the sweep."""
        rt = load("activate_brain_expansion")
        self.assertIsNone(rt._browser_runtime_healthy(launcher=lambda **_: (_ for _ in ()).throw(TimeoutError())))

    def test_a_broken_engine_is_unknown_rather_than_a_false_negative_verdict(self):
        rt = load("activate_brain_expansion")
        def explode(**_kwargs):
            raise RuntimeError("engine crashed")
        self.assertIsNone(rt._browser_runtime_healthy(launcher=explode))

    def test_the_probe_declares_its_timeout(self):
        rt = load("activate_brain_expansion")
        self.assertGreater(rt._BROWSER_PROBE_TIMEOUT_MS, 0)

    @unittest.skipUnless(playwright_available(), "no browser engine in this interpreter")
    def test_a_real_engine_reports_healthy(self):
        rt = load("activate_brain_expansion")
        self.assertIs(rt._browser_runtime_healthy(), True)


class BrowserSandboxTest(unittest.TestCase):
    """The sandbox test is what stands between 'installed' and 'trusted'."""

    def test_it_fails_closed_when_the_dependency_is_absent(self):
        rt = load("activate_brain_expansion")
        record = registry_record()
        probes = rt.build_probes("browser_use", record, root=ROOT)
        if not rt.dependency_available("browser_use"):
            self.assertIs(probes["sandbox_test"](), False)

    def test_financial_execution_is_denied_without_ever_launching_a_browser(self):
        adapters = load("brain_expansion_adapters")

        def runner(_task):
            raise AssertionError("a financial task must never reach the browser runner")

        result = adapters.execute_browser_task(
            {"objective_id": "x", "risk_class": "read_only", "domain": "127.0.0.1", "actions": ["place_order"]},
            permissions={"routed_by": "task_router", "allowed_domains": ["127.0.0.1"]},
            runner=runner,
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["denied_reason"], "financial_execution_forbidden_via_generic_browser_adapter")

    def test_credential_persistence_is_denied_without_ever_launching_a_browser(self):
        adapters = load("brain_expansion_adapters")

        def runner(_task):
            raise AssertionError("a credential task must never reach the browser runner")

        result = adapters.execute_browser_task(
            {"objective_id": "x", "domain": "127.0.0.1", "actions": ["read"], "persist_credentials": True},
            permissions={"routed_by": "task_router", "allowed_domains": ["127.0.0.1"]},
            runner=runner,
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["denied_reason"], "credential_persistence_forbidden")

    def test_a_runner_timeout_fails_closed_rather_than_reporting_success(self):
        adapters = load("brain_expansion_adapters")

        def slow(_task):
            raise TimeoutError("navigation timed out")

        result = adapters.execute_browser_task(
            {"objective_id": "x", "domain": "127.0.0.1", "actions": ["read"]},
            permissions={"routed_by": "task_router", "allowed_domains": ["127.0.0.1"]},
            runner=slow,
        )
        self.assertFalse(result["success"])
        self.assertFalse(result["runtime_verified"])
        self.assertEqual(result["failure"], "runtime")
        self.assertEqual(result["evidence"], {"error": "TimeoutError"})

    def test_a_plan_is_never_accepted_as_a_runtime_result(self):
        adapters = load("brain_expansion_adapters")
        result = adapters.execute_browser_task(
            {"objective_id": "x", "domain": "127.0.0.1", "actions": ["read"]},
            permissions={"routed_by": "task_router", "allowed_domains": ["127.0.0.1"]},
            runner=lambda _t: {"ok": True, "plan": "I would open the page"},
        )
        self.assertFalse(result["success"])
        self.assertFalse(result["runtime_verified"])

    @unittest.skipUnless(playwright_available(), "no browser engine in this interpreter")
    def test_a_real_local_page_load_satisfies_the_sandbox(self):
        rt = load("activate_brain_expansion")
        self.assertIs(rt.browser_sandbox_probe(), True)

    @unittest.skipUnless(playwright_available(), "no browser engine in this interpreter")
    def test_a_real_browser_leaves_no_cookie_or_storage_behind(self):
        rt = load("activate_brain_expansion")
        leftovers = rt.browser_persistence_probe()
        self.assertEqual(leftovers["cookies"], [])
        self.assertEqual(leftovers["origins"], [])


# ---------------------------------------------------------------------------
# lifecycle: disabled -> eligible -> enabled, and back
# ---------------------------------------------------------------------------


class ActivationLifecycle(unittest.TestCase):
    def _evaluate(self, verdicts: dict, *, auto_activate: bool = True) -> dict:
        adapters = load("brain_expansion_adapters")
        record = registry_record()
        conditions = adapters.required_conditions("browser_use", record)
        probes = {name: verdicts.get(name, True) for name in conditions}
        return adapters.evaluate_eligibility("browser_use", record, probes=probes, auto_activate=auto_activate)

    def test_all_gates_pass_and_auto_activation_off_yields_eligible_not_enabled(self):
        row = self._evaluate({}, auto_activate=False)
        self.assertEqual(row["state"], "eligible")
        self.assertFalse(row["enabled"])

    def test_all_gates_pass_and_auto_activation_on_yields_enabled(self):
        row = self._evaluate({})
        self.assertEqual(row["state"], "enabled")
        self.assertTrue(row["enabled"])

    def test_the_current_blocker_keeps_it_disabled(self):
        row = self._evaluate({"dependency_available": False, "sandbox_test": False})
        self.assertEqual(row["state"], "disabled")
        self.assertFalse(row["enabled"])
        self.assertIn("dependency_available", row["failed"])

    def test_a_dead_browser_runtime_degrades_rather_than_blocks(self):
        row = self._evaluate({"runtime_health_probe": False})
        self.assertEqual(row["state"], "degraded")
        self.assertFalse(row["enabled"])

    def test_a_security_failure_blocks(self):
        row = self._evaluate({"security_policy": False})
        self.assertEqual(row["state"], "blocked")

    def test_an_unknown_gate_never_enables(self):
        for condition in ("runtime_health_probe", "sandbox_test", "dependency_available"):
            with self.subTest(condition=condition):
                self.assertFalse(self._evaluate({condition: None})["enabled"])

    def test_recovery_from_degraded_returns_it_to_enabled(self):
        rt = load("activate_brain_expansion")
        recovered = rt.apply_health_transition(
            previous={"state": "degraded", "enabled": False},
            current={"state": "enabled", "enabled": True},
        )
        self.assertTrue(recovered["recovered"])
        self.assertTrue(recovered["enabled"])

    def test_a_blocked_adapter_is_never_resurrected_by_a_health_probe(self):
        rt = load("activate_brain_expansion")
        row = rt.apply_health_transition(
            previous={"state": "blocked", "enabled": False},
            current={"state": "enabled", "enabled": True},
        )
        self.assertEqual(row["state"], "blocked")
        self.assertFalse(row["enabled"])


# ---------------------------------------------------------------------------
# merging evidence across two interpreters
# ---------------------------------------------------------------------------


def _row(adapter_id: str, *, enabled: bool, conditions: dict | None = None) -> dict:
    conditions = conditions or {"dependency_available": "PASS"}
    row = {
        "id": adapter_id,
        "state": "enabled" if enabled else "disabled",
        "enabled": enabled,
        "required": sorted(conditions),
        "conditions": conditions,
        "failed": [name for name, v in conditions.items() if v == "FAIL"],
        "unknown": [name for name, v in conditions.items() if v == "UNKNOWN"],
        "evidence": {"dependency_importable": enabled},
    }
    for claim in ("routing_authority", "reasoning_authority", "memory_authority", "model_selection_authority"):
        row[claim] = False
    return row


def _report(rows: dict, *, stable: bool = True, runtime: str = "validator") -> dict:
    return {
        "schema_version": 1,
        "runtime": runtime,
        "adapters": rows,
        "enabled": sorted(cid for cid, r in rows.items() if r["enabled"]),
        "states": {cid: r["state"] for cid, r in rows.items()},
        "stable_path_ok": stable,
        "router_authority": "task_router",
        "execution_authority": "legion",
        "model_authority": "model_mesh",
        "memory_authority": "memory_continuity",
    }


class EvidenceMerge(unittest.TestCase):
    def merger(self):
        return load("merge_activation_reports")

    def test_an_adapter_enabled_in_either_interpreter_is_enabled_in_the_merge(self):
        merged = self.merger().merge_reports([
            _report({"baml": _row("baml", enabled=True), "browser_use": _row("browser_use", enabled=False)}),
            _report({"browser_use": _row("browser_use", enabled=True)}, runtime="browser"),
        ])
        self.assertEqual(merged["enabled"], ["baml", "browser_use"])
        self.assertEqual(merged["adapters"]["browser_use"]["runtime"], "browser")

    def test_a_row_enabled_without_evidence_is_refused(self):
        row = _row("browser_use", enabled=True)
        row["evidence"] = {}
        with self.assertRaises(ValueError):
            self.merger().merge_reports([_report({"browser_use": row})])

    def test_a_row_claiming_authority_is_refused(self):
        row = _row("browser_use", enabled=True)
        row["routing_authority"] = True
        with self.assertRaises(ValueError):
            self.merger().merge_reports([_report({"browser_use": row})])

    def test_a_row_enabled_with_a_failed_gate_is_refused(self):
        row = _row("browser_use", enabled=True, conditions={"dependency_available": "FAIL"})
        with self.assertRaises(ValueError):
            self.merger().merge_reports([_report({"browser_use": row})])

    def test_a_broken_stable_path_anywhere_breaks_the_merge(self):
        merged = self.merger().merge_reports([
            _report({"baml": _row("baml", enabled=True)}),
            _report({"browser_use": _row("browser_use", enabled=True)}, stable=False, runtime="browser"),
        ])
        self.assertFalse(merged["stable_path_ok"])

    def test_conflicting_authority_between_reports_is_refused(self):
        left = _report({"baml": _row("baml", enabled=True)})
        right = _report({"browser_use": _row("browser_use", enabled=True)}, runtime="browser")
        right["router_authority"] = "browser_use"
        with self.assertRaises(ValueError):
            self.merger().merge_reports([left, right])

    def test_merging_nothing_is_an_error_rather_than_an_empty_pass(self):
        with self.assertRaises(ValueError):
            self.merger().merge_reports([])

    def test_require_reports_the_adapters_that_did_not_enable(self):
        merger = self.merger()
        merged = merger.merge_reports([_report({"browser_use": _row("browser_use", enabled=False)})])
        self.assertEqual(merger.missing(merged, ["browser_use", "baml"]), ["baml", "browser_use"])

    def test_the_merged_report_carries_no_credential_material(self):
        merger = self.merger()
        merged = merger.merge_reports([_report({"baml": _row("baml", enabled=True)})])
        text = json.dumps(merged)
        for pattern in ("sk-", "BEGIN RSA PRIVATE KEY", "Bearer "):
            self.assertNotIn(pattern, text)


if __name__ == "__main__":
    unittest.main()
