"""The failover harness and acceptance matrix must not be able to lie.

Every test here tries to make them claim something unproven.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
FABRIC_DIR = ROOT / "AI_SKILL_LIBRARY/v4/runtime_fabric"

sys.path.insert(0, str(FABRIC_DIR))
_fs = importlib.util.spec_from_file_location("fabric", FABRIC_DIR / "fabric.py")
fabric = importlib.util.module_from_spec(_fs)
sys.modules["fabric"] = fabric
_fs.loader.exec_module(fabric)

_as = importlib.util.spec_from_file_location("acceptance", FABRIC_DIR / "acceptance.py")
acceptance = importlib.util.module_from_spec(_as)
sys.modules["acceptance"] = acceptance
_as.loader.exec_module(acceptance)


def registry():
    return yaml.safe_load((FABRIC_DIR / "registry.yaml").read_text(encoding="utf-8"))


def all_axes_true():
    return {axis: True for axis in fabric.VERIFICATION_AXES}


class FailoverProofTests(unittest.TestCase):
    def test_an_undeployed_secondary_is_never_reported_as_proof(self):
        """The whole point: selection working is not traffic being served."""
        result = acceptance.failover_proof(registry())
        self.assertNotEqual(result["status"], acceptance.PASS)

    def test_a_selected_but_undeployed_runtime_reads_simulated_only(self):
        """SIMULATED_ONLY is unreachable today - eligibility() already requires
        `deployed` and `health_verified`, so anything it selects is live. This
        is defence in depth against that ever being loosened, so the test
        reaches it the only way it could happen: selection returning a runtime
        that is not actually there.
        """
        reg = registry()
        reg["runtimes"]["deno_deploy"]["verification"] = dict(
            all_axes_true(), deployed=False, health_verified=False)
        original = acceptance.select_runtime
        acceptance.select_runtime = lambda *a, **k: ("deno_deploy", {"tier": "secondary"})
        try:
            result = acceptance.failover_proof(reg)
        finally:
            acceptance.select_runtime = original
        self.assertEqual(result["status"], acceptance.SIMULATED_ONLY)
        self.assertIn("not deployed", result["reason"])

    def test_eligibility_today_makes_an_undeployed_selection_impossible(self):
        """Documents WHY the guard above is unreachable, so a later change that
        removes `deployed` from the axes fails this test loudly."""
        self.assertIn("deployed", fabric.VERIFICATION_AXES)
        self.assertIn("health_verified", fabric.VERIFICATION_AXES)
        reg = registry()
        reg["runtimes"]["deno_deploy"]["lifecycle"] = "STABLE"
        reg["runtimes"]["deno_deploy"]["verification"] = dict(
            all_axes_true(), deployed=False)
        ok, reasons = fabric.eligibility(
            reg["runtimes"]["deno_deploy"], capability="http_api")
        self.assertFalse(ok)
        self.assertIn("not_deployed", reasons)

    def test_simulated_only_is_not_spelled_pass(self):
        """A reader skimming for PASS must not find one."""
        self.assertNotIn("PASS", acceptance.SIMULATED_ONLY)

    def test_a_genuinely_live_secondary_passes_and_emits_evidence(self):
        reg = registry()
        reg["runtimes"]["deno_deploy"]["lifecycle"] = "STABLE"
        reg["runtimes"]["deno_deploy"]["verification"] = all_axes_true()
        result = acceptance.failover_proof(reg)
        self.assertEqual(result["status"], acceptance.PASS)
        self.assertEqual(result["selected"], "deno_deploy")
        self.assertIs(result["evidence"]["fallback_used"], True)

    def test_nothing_selectable_is_unverified_not_pass(self):
        reg = registry()
        for row in reg["runtimes"].values():
            row["lifecycle"] = "DISCOVERED"
        result = acceptance.failover_proof(reg)
        self.assertEqual(result["status"], acceptance.UNVERIFIED)

    def test_the_excluded_primary_is_never_the_answer(self):
        reg = registry()
        reg["runtimes"]["cloudflare_workers"]["verification"] = all_axes_true()
        reg["runtimes"]["deno_deploy"]["lifecycle"] = "STABLE"
        reg["runtimes"]["deno_deploy"]["verification"] = all_axes_true()
        result = acceptance.failover_proof(reg)
        self.assertNotEqual(result["selected"], "cloudflare_workers")

    def test_liveness_needs_both_deployed_and_health_verified(self):
        for deployed, health, live in ((True, True, True), (True, False, False),
                                       (False, True, False), (False, False, False)):
            with self.subTest(deployed=deployed, health=health):
                entry = {"verification": {"deployed": deployed,
                                          "health_verified": health}}
                self.assertEqual(acceptance.runtime_is_live(entry), live)


class AcceptanceMatrixTests(unittest.TestCase):
    def test_unobserved_gates_are_not_passing(self):
        matrix = acceptance.acceptance_matrix(registry())
        self.assertEqual(matrix["PRIMARY_DEPLOY"], "NOT_OBSERVED")
        self.assertIs(matrix["FULL_ACTIVE"], False)

    def test_full_active_has_no_independent_setter(self):
        """It is a conjunction. There must be no way to switch it on alone."""
        text = (FABRIC_DIR / "acceptance.py").read_text(encoding="utf-8")
        self.assertNotIn('matrix["FULL_ACTIVE"] = True', text)
        self.assertIn('matrix["FULL_ACTIVE"] = (', text)

    def test_every_gate_alone_blocks_full_active(self):
        gates = {"CLOUDFLARE_DEPLOY": True, "CLOUDFLARE_HEALTH": True,
                 "CLOUDFLARE_SHA_MATCH": True, "LIVE_RESEARCH_SMOKE": True}
        reg = registry()
        self.assertIs(acceptance.acceptance_matrix(reg, cloudflare_gates=gates)["FULL_ACTIVE"], True)
        for name in gates:
            with self.subTest(gate=name):
                damaged = dict(gates, **{name: False})
                matrix = acceptance.acceptance_matrix(reg, cloudflare_gates=damaged)
                self.assertIs(matrix["FULL_ACTIVE"], False)
                self.assertIn(name, matrix["BLOCKERS"])

    def test_paid_fallback_true_blocks_full_active(self):
        reg = registry()
        reg["paid_fallback_allowed"] = True
        gates = {"CLOUDFLARE_DEPLOY": True, "CLOUDFLARE_HEALTH": True,
                 "CLOUDFLARE_SHA_MATCH": True, "LIVE_RESEARCH_SMOKE": True}
        matrix = acceptance.acceptance_matrix(reg, cloudflare_gates=gates)
        self.assertIs(matrix["PAID_FALLBACK"], True)
        self.assertIs(matrix["FULL_ACTIVE"], False)

    def test_the_matrix_reports_the_hard_invariants(self):
        matrix = acceptance.acceptance_matrix(registry())
        self.assertIs(matrix["RAILWAY_REQUIRED"], False)
        self.assertIs(matrix["PERSONAL_PC_REQUIRED"], False)
        self.assertIs(matrix["PAID_FALLBACK"], False)
        self.assertEqual(matrix["ZERO_COST_GUARD"], "ENFORCED")

    def test_secondary_flags_track_the_registry_not_wishes(self):
        matrix = acceptance.acceptance_matrix(registry())
        self.assertIs(matrix["SECONDARY_DEPLOYED"], False)
        self.assertIs(matrix["SECONDARY_HEALTH_VERIFIED"], False)

    def test_runtime_portable_requires_more_than_one_real_adapter(self):
        matrix = acceptance.acceptance_matrix(registry())
        self.assertIs(matrix["RUNTIME_PORTABLE"], True)
        reg = registry()
        for row in reg["runtimes"].values():
            row.pop("entrypoint", None)
            row.pop("manifest", None)
            row.pop("worker", None)
        self.assertIs(acceptance.acceptance_matrix(reg)["RUNTIME_PORTABLE"], False)

    def test_github_actions_compute_readiness_is_derived(self):
        matrix = acceptance.acceptance_matrix(registry())
        self.assertIs(matrix["GITHUB_ACTIONS_COMPUTE_READY"], True)
        reg = registry()
        reg["runtimes"]["github_actions"]["verification"]["health_verified"] = False
        self.assertIs(
            acceptance.acceptance_matrix(reg)["GITHUB_ACTIONS_COMPUTE_READY"], False)

    def test_render_matrix_never_prints_a_bare_pass_for_failover(self):
        text = acceptance.render_matrix(acceptance.acceptance_matrix(registry()))
        self.assertIn("FAILOVER_PROOF=", text)
        self.assertNotIn("FAILOVER_PROOF=PASS", text)


if __name__ == "__main__":
    unittest.main()
