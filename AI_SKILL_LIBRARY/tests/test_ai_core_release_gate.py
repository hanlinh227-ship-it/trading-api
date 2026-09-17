"""The AI CORE release gate.

A gate that only ever reports PASS is a decoration. Half of these tests take the
live evidence, break one thing in it, and require the gate to notice - once per
check, so no check can quietly become unreachable.
"""

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.tools.ai_core_release_gate import CANONICAL_TRACE, gate

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = "CHECKPOINTS/evidence"
REGISTRY = "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"


def _sandbox(tmp: Path) -> Path:
    """A copy of the evidence and registry the gate reads, safe to damage."""
    (tmp / EVIDENCE).mkdir(parents=True, exist_ok=True)
    for path in (ROOT / EVIDENCE).glob("*.json"):
        shutil.copy2(path, tmp / EVIDENCE / path.name)
    (tmp / REGISTRY).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / REGISTRY, tmp / REGISTRY)
    return tmp


def _edit(tmp: Path, name: str, mutate) -> None:
    path = tmp / EVIDENCE / name
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")


class LiveGateTests(unittest.TestCase):
    """What the gate says about the evidence actually in the repository."""

    @classmethod
    def setUpClass(cls):
        cls.result = gate(ROOT)

    def test_the_gate_passes_on_the_committed_evidence(self):
        self.assertEqual(self.result["verdict"], "PASS", self.result["failed_checks"])

    def test_every_check_ran(self):
        self.assertEqual(self.result["checks_passed"], self.result["checks_run"])
        self.assertEqual(self.result["failed_checks"], [])

    def test_each_check_states_what_it_required(self):
        """A check whose requirement is unreadable cannot be reviewed."""
        for check in self.result["checks"]:
            with self.subTest(check=check["check"]):
                self.assertTrue(check["requirement"].strip())

    def test_the_gate_grants_nothing(self):
        self.assertIs(self.result["grants_nothing"], True)
        self.assertIs(self.result["release_authority"], False)
        self.assertIs(self.result["routing_authority"], False)


class TheGateActuallyRefusesTests(unittest.TestCase):
    """One deliberate break per check. A check that cannot fail is not a check."""

    def _gate_after(self, damage) -> dict:
        with tempfile.TemporaryDirectory() as raw:
            tmp = _sandbox(Path(raw))
            damage(tmp)
            return gate(tmp)

    def _assert_fails(self, check_name: str, damage) -> None:
        result = self._gate_after(damage)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn(check_name, result["failed_checks"])

    def test_a_missing_evidence_file_is_not_a_pass(self):
        """Absent evidence blocks exactly like failed evidence."""
        self._assert_fails(
            "real_local_runtime",
            lambda tmp: (tmp / EVIDENCE / "B1_REAL_INFERENCE_EVIDENCE.json").unlink(),
        )

    def test_an_unreadable_evidence_file_is_not_a_pass(self):
        self._assert_fails(
            "golden_e2e",
            lambda tmp: (tmp / EVIDENCE / "AI_CORE_E2E_EVIDENCE.json").write_text(
                "{not json", encoding="utf-8"),
        )

    def test_a_run_with_egress_open_is_refused(self):
        self._assert_fails(
            "real_local_runtime",
            lambda tmp: _edit(tmp, "B1_REAL_INFERENCE_EVIDENCE.json",
                              lambda d: d["egress"].__setitem__("denied", False)),
        )

    def test_a_trace_missing_a_stage_is_refused(self):
        def damage(tmp):
            shortened = [s for s in CANONICAL_TRACE if s != "ai_legion"]
            _edit(tmp, "AI_CORE_E2E_EVIDENCE.json",
                  lambda d: d.__setitem__("trace", shortened))

        self._assert_fails("golden_e2e", damage)

    def test_a_specialist_assigned_after_model_selection_is_refused(self):
        """Order is the claim: a role applied to a decision already taken is a label."""
        def damage(tmp):
            reordered = [s for s in CANONICAL_TRACE if s != "ai_legion"]
            reordered.insert(reordered.index("model_mesh") + 1, "ai_legion")
            _edit(tmp, "AI_CORE_E2E_EVIDENCE.json",
                  lambda d: d.__setitem__("trace", reordered))

        self._assert_fails("golden_e2e", damage)

    def test_a_resume_inside_the_same_process_is_refused(self):
        """Otherwise it proves only that a dictionary is still in memory."""
        def damage(tmp):
            e2e = json.loads((tmp / EVIDENCE / "AI_CORE_E2E_EVIDENCE.json").read_text())
            _edit(tmp, "AI_CORE_RESUME_EVIDENCE.json",
                  lambda d: d.__setitem__("process_id", e2e["process_id"]))

        self._assert_fails("memory_continuity", damage)

    def test_resuming_a_different_checkpoint_is_refused(self):
        self._assert_fails(
            "memory_continuity",
            lambda tmp: _edit(tmp, "AI_CORE_RESUME_EVIDENCE.json",
                              lambda d: d.__setitem__("checkpoint_id", "some-other-run")),
        )

    def test_a_failure_case_that_did_not_hold_is_refused(self):
        self._assert_fails(
            "failure_paths",
            lambda tmp: _edit(tmp, "FAILURE_PATH_PROOF.json",
                              lambda d: d.__setitem__("held", d["cases"] - 1)),
        )

    def test_a_self_approved_run_is_refused(self):
        self._assert_fails(
            "self_development",
            lambda tmp: _edit(tmp, "SELFDEV_CYCLE_EVIDENCE.json",
                              lambda d: d["accepted_run"].__setitem__(
                                  "self_approval_refused", False)),
        )

    def test_a_rejected_run_that_could_still_propose_is_refused(self):
        self._assert_fails(
            "self_development",
            lambda tmp: _edit(tmp, "SELFDEV_CYCLE_EVIDENCE.json",
                              lambda d: d["rejected_run"].__setitem__(
                                  "rejected_run_can_still_propose", True)),
        )

    def test_an_outstanding_gap_is_refused(self):
        self._assert_fails(
            "no_open_gaps",
            lambda tmp: _edit(tmp, "SELFDEV_OBSERVED_GAPS.json",
                              lambda d: d.__setitem__("gap_count", 1)),
        )

    def test_a_row_holding_both_a_scan_and_an_acceptance_is_refused(self):
        def damage(tmp):
            path = tmp / REGISTRY
            registry = yaml.safe_load(path.read_text(encoding="utf-8"))
            row = registry["models"][0]
            row["admission_evidence"]["malware_scan_status"] = "pass"
            row["operator_risk_acceptance"] = {
                "accepted_by": "operator",
                "artifact_sha256": row["artifact_identity"]["sha256"],
                "covers": ["malware_scan_status"],
                "scope": "single_artifact",
                "is_a_scan_result": False,
            }
            path.write_text(yaml.safe_dump(registry), encoding="utf-8")

        self._assert_fails("model_admission", damage)

    def test_a_scan_reference_naming_other_bytes_is_refused(self):
        def damage(tmp):
            path = tmp / REGISTRY
            registry = yaml.safe_load(path.read_text(encoding="utf-8"))
            for row in registry["models"]:
                if isinstance(row.get("malware_scan_reference"), dict):
                    row["malware_scan_reference"]["artifact_sha256"] = "b" * 64
                    break
            path.write_text(yaml.safe_dump(registry), encoding="utf-8")

        self._assert_fails("model_admission", damage)

    def test_a_run_on_bytes_the_registry_does_not_track_is_refused(self):
        def damage(tmp):
            _edit(tmp, "B1_REAL_INFERENCE_EVIDENCE.json",
                  lambda d: d["artifact_identity"].__setitem__("artifact_sha256", "c" * 64))

        self._assert_fails("runs_used_admitted_artifacts", damage)

    def test_a_run_claiming_authority_is_refused(self):
        self._assert_fails(
            "authority_ceilings",
            lambda tmp: _edit(tmp, "AI_CORE_E2E_EVIDENCE.json",
                              lambda d: d["checkpoint"].__setitem__("memory_authority", True)),
        )

    def test_a_run_recording_an_approver_is_refused(self):
        """Approval is outside the automation, so a recorded one is a ceiling breach."""
        self._assert_fails(
            "authority_ceilings",
            lambda tmp: _edit(tmp, "SELFDEV_CYCLE_EVIDENCE.json",
                              lambda d: d["accepted_run"]["run"].__setitem__(
                                  "approved_by", "auto_dev")),
        )

    def test_every_check_can_be_made_to_fail_by_something(self):
        """No check may be structurally unreachable.

        Checked by removing the whole evidence directory: if a check still
        passes with nothing to read, it is not reading anything.
        """
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            (tmp / EVIDENCE).mkdir(parents=True)
            (tmp / REGISTRY).parent.mkdir(parents=True, exist_ok=True)
            (tmp / REGISTRY).write_text("models: []\n", encoding="utf-8")
            result = gate(tmp)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertEqual(
            sorted(result["failed_checks"]),
            sorted(check["check"] for check in result["checks"]),
        )


if __name__ == "__main__":
    unittest.main()
