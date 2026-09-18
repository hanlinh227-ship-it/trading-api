"""Clearance tests.

The property under test throughout: an absence of evidence never becomes a
positive finding. A structural pass is not a malware clearance, a missing engine
is not a clean result, and an engine error is not a pass.
"""

import struct
import tempfile
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.local_runtime.clearance import (
    SIGNATURE_ENGINES,
    ClearanceStatus,
    apply_clearance,
    evaluate_clearance,
    find_signature_engine,
    run_signature_scan,
)


def build_gguf(tensors=1):
    out = bytearray(b"GGUF") + struct.pack("<I", 3)
    out += struct.pack("<Q", tensors) + struct.pack("<Q", 0)
    for i in range(tensors):
        name = f"t{i}".encode()
        out += struct.pack("<Q", len(name)) + name
        out += struct.pack("<I", 1) + struct.pack("<Q", 4)
        out += struct.pack("<I", 0) + struct.pack("<Q", 0)
    return bytes(out) + b"\x00" * 128


def no_engine(_name):
    return None


def engine_present(name):
    return f"/usr/bin/{name}" if name in SIGNATURE_ENGINES else None


def clean_run(argv, timeout=600.0):
    return 0, "OK"


def infected_run(argv, timeout=600.0):
    return 1, "/model.gguf: Win.Test.EICAR_HDB-1 FOUND"


def broken_run(argv, timeout=600.0):
    return 2, "database load failure"


class NoEngineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "m.gguf"
        self.path.write_bytes(build_gguf())
        self.addCleanup(self._tmp.cleanup)

    def test_a_missing_engine_does_not_clear(self):
        result = evaluate_clearance(self.path, which=no_engine)
        self.assertEqual(result.status, ClearanceStatus.INSUFFICIENT_EVIDENCE)
        self.assertFalse(result.cleared)

    def test_a_structural_pass_alone_never_clears(self):
        result = evaluate_clearance(self.path, which=no_engine)
        structural = next(e for e in result.evidence if e.check == "structural_scan")
        self.assertTrue(structural.passed)          # the container is fine
        self.assertFalse(result.cleared)            # and that is not enough

    def test_the_refusal_says_the_status_stays_not_run(self):
        result = evaluate_clearance(self.path, which=no_engine)
        self.assertIn("not_run", result.reason)

    def test_no_registry_update_is_proposed_without_clearance(self):
        self.assertEqual(evaluate_clearance(self.path, which=no_engine).proposed_registry_update, {})

    def test_the_engines_it_looked_for_are_named(self):
        result = evaluate_clearance(self.path, which=no_engine)
        self.assertEqual(set(result.engines_unavailable), set(SIGNATURE_ENGINES))

    def test_this_host_has_no_signature_engine(self):
        # Records the real state of this machine rather than assuming it.
        self.assertIsNone(find_signature_engine())


class EnginePresentTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "m.gguf"
        self.path.write_bytes(build_gguf())
        self.addCleanup(self._tmp.cleanup)

    def test_a_clean_scan_plus_a_clean_structure_clears(self):
        result = evaluate_clearance(self.path, which=engine_present, run=clean_run)
        self.assertEqual(result.status, ClearanceStatus.CLEARED)
        update = result.proposed_registry_update
        self.assertEqual(update["admission_evidence"]["malware_scan_status"], "pass")
        self.assertEqual(update["admission_evidence"]["quarantine_status"], "clear")
        self.assertEqual(update["lifecycle_state"], "AVAILABLE")
        self.assertTrue(update["model_mesh_local_candidate_eligible"])

    def test_an_infected_result_blocks(self):
        result = evaluate_clearance(self.path, which=engine_present, run=infected_run)
        self.assertEqual(result.status, ClearanceStatus.BLOCKED_INFECTED)
        self.assertIn("FOUND", result.reason)
        self.assertEqual(result.proposed_registry_update, {})

    def test_an_engine_error_is_not_a_pass(self):
        result = evaluate_clearance(self.path, which=engine_present, run=broken_run)
        self.assertEqual(result.status, ClearanceStatus.INSUFFICIENT_EVIDENCE)
        signature = next(e for e in result.evidence if e.check == "signature_scan")
        self.assertFalse(signature.ran)
        self.assertIsNone(signature.passed)

    def test_an_engine_that_raises_is_not_a_pass(self):
        def explodes(argv, timeout=600.0):
            raise OSError("engine crashed")

        result = evaluate_clearance(self.path, which=engine_present, run=explodes)
        self.assertEqual(result.status, ClearanceStatus.INSUFFICIENT_EVIDENCE)

    def test_a_malformed_artifact_blocks_even_with_a_clean_signature_scan(self):
        broken = bytearray(build_gguf())
        struct.pack_into("<Q", broken, 8, 2**40)
        self.path.write_bytes(bytes(broken))
        result = evaluate_clearance(self.path, which=engine_present, run=clean_run)
        self.assertEqual(result.status, ClearanceStatus.BLOCKED_MALFORMED)

    def test_signature_scan_reports_the_engine_it_used(self):
        evidence = run_signature_scan(self.path, which=engine_present, run=clean_run)
        self.assertTrue(evidence.ran)
        self.assertTrue(evidence.passed)
        self.assertIn(evidence.engine, SIGNATURE_ENGINES)


class NoArtifactTests(unittest.TestCase):
    def test_clearance_without_bytes_is_refused(self):
        self.assertEqual(evaluate_clearance(None).status, ClearanceStatus.NO_ARTIFACT)

    def test_a_missing_path_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = evaluate_clearance(Path(tmp) / "absent.gguf")
        self.assertEqual(result.status, ClearanceStatus.NO_ARTIFACT)
        self.assertIn("needs the bytes", result.reason)


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "m.gguf"
        self.path.write_bytes(build_gguf())
        self.addCleanup(self._tmp.cleanup)
        self.record = {
            "model_id": "m",
            "lifecycle_state": "QUARANTINED",
            "model_mesh_local_candidate_eligible": False,
            "admission_evidence": {
                "malware_scan_status": "not_run",
                "quarantine_status": "quarantined",
                "license_verified": True,
                "provenance_verified": True,
                "safe_format_verified": True,
                "pickle_safe": True,
                "trust_remote_code_required": False,
                "custom_code_required": False,
            },
        }

    def test_an_uncleared_result_cannot_be_applied(self):
        result = evaluate_clearance(self.path, which=no_engine)
        with self.assertRaises(ValueError):
            apply_clearance(self.record, result)

    def test_a_cleared_result_updates_only_the_justified_fields(self):
        result = evaluate_clearance(self.path, which=engine_present, run=clean_run)
        updated = apply_clearance(self.record, result)
        self.assertEqual(updated["lifecycle_state"], "AVAILABLE")
        self.assertEqual(updated["admission_evidence"]["malware_scan_status"], "pass")
        self.assertEqual(updated["admission_evidence"]["quarantine_status"], "clear")
        # Untouched evidence survives.
        self.assertTrue(updated["admission_evidence"]["license_verified"])

    def test_apply_does_not_mutate_the_original_record(self):
        result = evaluate_clearance(self.path, which=engine_present, run=clean_run)
        apply_clearance(self.record, result)
        self.assertEqual(self.record["lifecycle_state"], "QUARANTINED")
        self.assertEqual(self.record["admission_evidence"]["malware_scan_status"], "not_run")

    def test_a_cleared_record_then_passes_projection(self):
        from AI_SKILL_LIBRARY.v4.local_runtime.admission_policy import load_admission_policy
        result = evaluate_clearance(self.path, which=engine_present, run=clean_run)
        updated = apply_clearance(self.record, result)
        policy = load_admission_policy(Path(__file__).resolve().parents[2])
        self.assertIsNone(policy.governance_refusal(updated["lifecycle_state"]))
        self.assertEqual(policy.evidence_refusals(updated["admission_evidence"]), ())

    def test_result_is_json_safe_and_states_its_scope(self):
        import json
        payload = evaluate_clearance(self.path, which=no_engine).to_dict()
        decoded = json.loads(json.dumps(payload))
        self.assertFalse(decoded["cleared"])
        self.assertTrue(decoded["structural_scan_is_not_a_malware_scan"])


if __name__ == "__main__":
    unittest.main()
