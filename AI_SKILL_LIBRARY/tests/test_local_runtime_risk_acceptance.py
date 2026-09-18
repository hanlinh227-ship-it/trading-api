"""Operator risk acceptance.

An operator may accept a named, scoped risk. They may not rewrite a finding.
These tests pin both halves: the acceptance works, and it cannot be stretched
into anything wider than what was accepted.
"""

import copy
import json
import struct
import tempfile
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.local_runtime.admission_policy import load_admission_policy
from AI_SKILL_LIBRARY.v4.local_runtime.clearance import (
    ClearanceStatus,
    apply_clearance,
    build_risk_acceptance,
    evaluate_clearance,
)
from AI_SKILL_LIBRARY.v4.local_runtime.projection import project_record
from AI_SKILL_LIBRARY.v4.local_runtime.scheduler import AdmissionStatus

ROOT = Path(__file__).resolve().parents[2]
SHA = "9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031"


def build_gguf():
    out = bytearray(b"GGUF") + struct.pack("<I", 3)
    out += struct.pack("<Q", 1) + struct.pack("<Q", 0)
    out += struct.pack("<Q", 1) + b"t"
    out += struct.pack("<I", 1) + struct.pack("<Q", 4)
    out += struct.pack("<I", 0) + struct.pack("<Q", 0)
    return bytes(out) + b"\x00" * 64


def acceptance(**overrides):
    base = build_risk_acceptance(
        accepted_by="operator",
        artifact_sha256=SHA,
        basis="verified provenance, immutable revision, exact size, sha256, format and structural scan",
        missing_evidence=["signature_based_malware_scan"],
    )
    return {**base, **overrides}


def no_engine(_name):
    return None


class AcceptanceRecordTests(unittest.TestCase):
    def test_a_built_record_carries_every_required_field(self):
        policy = load_admission_policy(ROOT)
        record = acceptance()
        for field in policy.risk_acceptance_required_fields:
            self.assertTrue(str(record.get(field) or "").strip(), field)

    def test_the_record_says_it_is_not_a_scan_result(self):
        record = acceptance()
        self.assertIs(record["is_a_scan_result"], False)
        self.assertIn("not_run", record["note"])

    def test_an_acceptance_needs_an_accepting_party(self):
        with self.assertRaises(ValueError):
            build_risk_acceptance(accepted_by="  ", artifact_sha256=SHA, basis="b",
                                  missing_evidence=["x"])

    def test_an_acceptance_needs_a_stated_basis(self):
        with self.assertRaises(ValueError):
            build_risk_acceptance(accepted_by="op", artifact_sha256=SHA, basis="",
                                  missing_evidence=["x"])

    def test_an_acceptance_must_record_what_was_not_checked(self):
        with self.assertRaises(ValueError):
            build_risk_acceptance(accepted_by="op", artifact_sha256=SHA, basis="b",
                                  missing_evidence=[])


class PolicyValidationTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_admission_policy(ROOT)

    def test_a_complete_acceptance_validates(self):
        self.assertEqual(
            self.policy.risk_acceptance_refusals(acceptance(), artifact_sha256=SHA), ()
        )

    def test_a_digest_for_different_bytes_is_refused(self):
        refusals = self.policy.risk_acceptance_refusals(acceptance(), artifact_sha256="a" * 64)
        self.assertTrue(any("bound to the exact bytes" in r for r in refusals), refusals)

    def test_a_blanket_scope_is_refused(self):
        refusals = self.policy.risk_acceptance_refusals(
            acceptance(scope="all_models"), artifact_sha256=SHA
        )
        self.assertTrue(any("blanket acceptance is refused" in r for r in refusals), refusals)

    def test_it_can_never_cover_license_or_provenance(self):
        for gate in ("license_verified", "provenance_verified", "safe_format_verified",
                     "pickle_safe", "trust_remote_code_required", "custom_code_required",
                     "structural_scan"):
            with self.subTest(gate=gate):
                refusals = self.policy.risk_acceptance_refusals(
                    acceptance(covers=[gate]), artifact_sha256=SHA
                )
                self.assertTrue(any("never substitute" in r for r in refusals), refusals)

    def test_a_missing_field_invalidates_it(self):
        for field in self.policy.risk_acceptance_required_fields:
            with self.subTest(field=field):
                broken = {k: v for k, v in acceptance().items() if k != field}
                self.assertTrue(
                    self.policy.risk_acceptance_refusals(broken, artifact_sha256=SHA)
                )

    def test_no_acceptance_supplied_is_not_an_acceptance(self):
        self.assertTrue(self.policy.risk_acceptance_refusals(None, artifact_sha256=SHA))

    def test_accepted_gaps_is_empty_for_an_invalid_acceptance(self):
        self.assertEqual(
            self.policy.accepted_gaps(acceptance(scope="everything"), artifact_sha256=SHA),
            frozenset(),
        )

    def test_an_acceptance_covers_not_run_only_never_fail_or_unknown(self):
        """A decision can cover a known absence, not an adverse finding."""
        base = {
            "license_verified": True, "provenance_verified": True,
            "safe_format_verified": True, "pickle_safe": True,
            "trust_remote_code_required": False, "custom_code_required": False,
            "quarantine_status": "clear",
        }
        accepted = frozenset({"malware_scan_status"})

        # not_run: the case the operator actually accepted.
        self.assertEqual(
            self.policy.evidence_refusals(
                {**base, "malware_scan_status": "not_run"}, accepted_gaps=accepted
            ),
            (),
        )
        # Anything else stays blocking, acceptance or not.
        for status in ("fail", "failed", "unknown", "error", ""):
            with self.subTest(status=status):
                refusals = self.policy.evidence_refusals(
                    {**base, "malware_scan_status": status}, accepted_gaps=accepted
                )
                self.assertTrue(
                    any("malware_scan_status" in r for r in refusals), (status, refusals)
                )

    def test_evidence_refusals_only_honour_permitted_gates(self):
        evidence = {
            "license_verified": False, "provenance_verified": True,
            "safe_format_verified": True, "pickle_safe": True,
            "trust_remote_code_required": False, "custom_code_required": False,
            "malware_scan_status": "not_run", "quarantine_status": "clear",
        }
        # Passing a forbidden gate through accepted_gaps must not widen anything.
        refusals = self.policy.evidence_refusals(
            evidence, accepted_gaps=frozenset({"malware_scan_status", "license_verified"})
        )
        self.assertTrue(any("license_verified" in r for r in refusals), refusals)


class ClearanceWithAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "m.gguf"
        self.path.write_bytes(build_gguf())
        self.addCleanup(self._tmp.cleanup)

    def test_acceptance_clears_when_no_engine_exists(self):
        result = evaluate_clearance(self.path, which=no_engine, risk_acceptance=acceptance())
        self.assertEqual(result.status, ClearanceStatus.CLEARED_WITH_ACCEPTED_RISK)
        self.assertTrue(result.cleared)
        self.assertFalse(result.cleared_by_evidence_only)

    def test_the_proposed_update_never_touches_malware_scan_status(self):
        result = evaluate_clearance(self.path, which=no_engine, risk_acceptance=acceptance())
        evidence_update = result.proposed_registry_update["admission_evidence"]
        self.assertNotIn("malware_scan_status", evidence_update)
        self.assertEqual(evidence_update["quarantine_status"], "clear")

    def test_applying_it_leaves_malware_scan_status_at_not_run(self):
        record = {
            "lifecycle_state": "QUARANTINED",
            "model_mesh_local_candidate_eligible": False,
            "admission_evidence": {"malware_scan_status": "not_run",
                                   "quarantine_status": "quarantined"},
        }
        result = evaluate_clearance(self.path, which=no_engine, risk_acceptance=acceptance())
        updated = apply_clearance(record, result)
        self.assertEqual(updated["admission_evidence"]["malware_scan_status"], "not_run")
        self.assertEqual(updated["lifecycle_state"], "AVAILABLE")
        self.assertIn("operator_risk_acceptance", updated)

    def test_a_malformed_artifact_is_not_rescued_by_an_acceptance(self):
        broken = bytearray(build_gguf())
        struct.pack_into("<Q", broken, 8, 2**40)
        self.path.write_bytes(bytes(broken))
        result = evaluate_clearance(self.path, which=no_engine, risk_acceptance=acceptance())
        self.assertEqual(result.status, ClearanceStatus.BLOCKED_MALFORMED)
        self.assertFalse(result.cleared)

    def test_an_infected_result_is_not_rescued_by_an_acceptance(self):
        def infected(argv, timeout=600.0):
            return 1, "EICAR FOUND"

        result = evaluate_clearance(
            self.path, which=lambda n: f"/usr/bin/{n}", run=infected,
            risk_acceptance=acceptance(),
        )
        self.assertEqual(result.status, ClearanceStatus.BLOCKED_INFECTED)
        self.assertFalse(result.cleared)

    def test_a_real_clean_scan_does_not_need_the_acceptance(self):
        def clean(argv, timeout=600.0):
            return 0, "OK"

        result = evaluate_clearance(
            self.path, which=lambda n: f"/usr/bin/{n}", run=clean, risk_acceptance=acceptance()
        )
        self.assertEqual(result.status, ClearanceStatus.CLEARED)
        self.assertTrue(result.cleared_by_evidence_only)
        self.assertEqual(
            result.proposed_registry_update["admission_evidence"]["malware_scan_status"], "pass"
        )

    def test_no_artifact_is_not_rescued_by_an_acceptance(self):
        result = evaluate_clearance(None, risk_acceptance=acceptance())
        self.assertEqual(result.status, ClearanceStatus.NO_ARTIFACT)


class ProjectionWithAcceptanceTests(unittest.TestCase):
    def _record(self, **overrides):
        import yaml
        registry = yaml.safe_load(
            (ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml").read_text()
        )
        record = copy.deepcopy(registry["models"][0])
        # Tests supply their own acceptance; drop any stored on the live row.
        record.pop("operator_risk_acceptance", None)
        # And force the condition these tests are about. The fixture borrowed
        # whatever the live row said, so once that row gained a real signature
        # scan the acceptance stopped being what cleared it, and
        # "without the acceptance it is refused" became false - for a reason
        # that had nothing to do with acceptances.
        record["admission_evidence"]["malware_scan_status"] = "not_run"
        record.pop("malware_scan_reference", None)
        record["lifecycle_state"] = "AVAILABLE"
        record["privacy_class"] = "local_only"
        record["model_mesh_local_candidate_eligible"] = True
        record["admission_evidence"]["quarantine_status"] = "clear"
        record.update(overrides)
        return record

    def test_a_valid_acceptance_lets_a_not_run_scan_through(self):
        record = self._record(operator_risk_acceptance=acceptance())
        result = project_record(record, available_runtimes=["llama.cpp"])
        self.assertEqual(result.admission_status, AdmissionStatus.ADMITTED)
        self.assertEqual(result.risk_accepted_gaps, ("malware_scan_status",))
        self.assertIsNotNone(result.risk_acceptance)

    def test_without_the_acceptance_the_same_record_is_refused(self):
        result = project_record(self._record(), available_runtimes=["llama.cpp"])
        self.assertEqual(result.admission_status, AdmissionStatus.INELIGIBLE)
        self.assertTrue(any("malware_scan_status" in r for r in result.exclusion_reasons))

    def test_an_invalid_acceptance_is_named_not_ignored(self):
        record = self._record(operator_risk_acceptance=acceptance(scope="all_models"))
        result = project_record(record, available_runtimes=["llama.cpp"])
        self.assertEqual(result.admission_status, AdmissionStatus.INELIGIBLE)
        self.assertTrue(any("blanket" in r for r in result.exclusion_reasons))

    def test_an_acceptance_for_other_bytes_does_not_apply(self):
        record = self._record(operator_risk_acceptance=acceptance(artifact_sha256="b" * 64))
        result = project_record(record, available_runtimes=["llama.cpp"])
        self.assertEqual(result.admission_status, AdmissionStatus.INELIGIBLE)

    def test_the_result_states_it_was_not_cleared_by_evidence_alone(self):
        record = self._record(operator_risk_acceptance=acceptance())
        payload = project_record(record, available_runtimes=["llama.cpp"]).to_dict()
        decoded = json.loads(json.dumps(payload))
        self.assertFalse(decoded["cleared_by_evidence_only"])
        self.assertEqual(decoded["risk_accepted_gaps"], ["malware_scan_status"])

    def test_an_acceptance_cannot_rescue_a_quarantined_state(self):
        record = self._record(lifecycle_state="QUARANTINED",
                              operator_risk_acceptance=acceptance())
        result = project_record(record, available_runtimes=["llama.cpp"])
        self.assertEqual(result.admission_status, AdmissionStatus.INELIGIBLE)
        self.assertTrue(any("QUARANTINED" in r for r in result.exclusion_reasons))


if __name__ == "__main__":
    unittest.main()
