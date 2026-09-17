"""An operator decision is history. Superseding it is not deleting it.

A concurrent session found a real contradiction here - the row asserted a
passing scan and, beside it, an acceptance saying no scan had run - and fixed it
by deleting the acceptance. The contradiction was real; the deletion was not the
fix the repository owner asked for. Their instruction on PR #442 was explicit:
"Preserve the prior operator acceptance as historical evidence; a real scan
should supersede the gap, not rewrite history."

These tests pin both halves, so neither can be lost to the next edit: the
contradiction stays refused, and the record stays.
"""

import copy
import unittest
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.tools.validate_open_model_universe import _admission_refusals

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"
ACCEPTED_MODEL = "Qwen/Qwen3-0.6B-GGUF"


def registry():
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))


def accepted_record():
    return next(m for m in registry()["models"] if m["model_id"] == ACCEPTED_MODEL)


class HistoryIsPreservedTests(unittest.TestCase):
    def setUp(self):
        self.record = accepted_record()

    def test_the_operator_decision_is_still_on_the_record(self):
        """Deleting it would erase that a named decision was ever made."""
        acceptance = self.record.get("operator_risk_acceptance")
        self.assertIsNotNone(acceptance, "the operator acceptance must not be deleted")
        self.assertEqual(acceptance["accepted_by"], "hanlinh227-ship-it (repository operator)")
        self.assertEqual(acceptance["accepted_at"], "2026-09-17T05:00:00Z")

    def test_it_is_still_bound_to_the_exact_bytes_it_covered(self):
        acceptance = self.record["operator_risk_acceptance"]
        self.assertEqual(acceptance["artifact_sha256"],
                         self.record["artifact_identity"]["sha256"])
        self.assertEqual(acceptance["scope"], "single_artifact")

    def test_it_still_says_it_was_never_a_scan_result(self):
        self.assertFalse(self.record["operator_risk_acceptance"]["is_a_scan_result"])

    def test_it_is_marked_superseded_rather_than_live(self):
        acceptance = self.record["operator_risk_acceptance"]
        self.assertTrue(acceptance.get("superseded_by", "").strip())
        self.assertTrue(acceptance.get("superseded_at", "").strip())

    def test_what_superseded_it_names_these_bytes(self):
        """A supersession naming nothing checkable is a deletion with extra steps."""
        acceptance = self.record["operator_risk_acceptance"]
        self.assertIn(self.record["artifact_identity"]["sha256"], acceptance["superseded_by"])

    def test_the_model_is_admitted_on_the_scan_not_the_acceptance(self):
        self.assertEqual(self.record["admission_evidence"]["malware_scan_status"], "pass")
        self.assertEqual(self.record["malware_scan_reference"]["artifact_sha256"],
                         self.record["artifact_identity"]["sha256"])

    def test_the_live_record_passes_admission(self):
        self.assertEqual(_admission_refusals(self.record, 0), [])


class ContradictionStaysRefusedTests(unittest.TestCase):
    """The defect the concurrent session found must stay caught."""

    def setUp(self):
        self.record = accepted_record()

    def test_a_live_acceptance_beside_a_passing_scan_is_refused(self):
        record = copy.deepcopy(self.record)
        record["operator_risk_acceptance"].pop("superseded_by", None)
        refusals = _admission_refusals(record, 0)
        self.assertTrue(any("still live" in r for r in refusals), refusals)

    def test_a_supersession_without_a_date_is_refused(self):
        record = copy.deepcopy(self.record)
        record["operator_risk_acceptance"].pop("superseded_at", None)
        refusals = _admission_refusals(record, 0)
        self.assertTrue(any("superseded_at" in r for r in refusals), refusals)

    def test_a_supersession_naming_other_evidence_is_refused(self):
        record = copy.deepcopy(self.record)
        record["operator_risk_acceptance"]["superseded_by"] = "a scan of something else"
        refusals = _admission_refusals(record, 0)
        self.assertTrue(any("does not name this artifact" in r for r in refusals), refusals)

    def test_the_missing_engine_route_is_still_open(self):
        """Superseding one acceptance must not close the path for the next
        model that genuinely cannot be scanned here."""
        record = copy.deepcopy(self.record)
        record["admission_evidence"]["malware_scan_status"] = "not_run"
        record.pop("malware_scan_reference", None)
        acceptance = record["operator_risk_acceptance"]
        acceptance.pop("superseded_by", None)
        acceptance.pop("superseded_at", None)
        self.assertEqual(_admission_refusals(record, 0), [])


class NoStaleClaimsTests(unittest.TestCase):
    def test_no_text_in_the_record_claims_the_scan_did_not_run(self):
        """The original defect: comments and a note asserting not_run above a
        field reading pass. One of them is untrue whichever way it is read."""
        record = accepted_record()
        acceptance = record["operator_risk_acceptance"]
        self.assertEqual(record["admission_evidence"]["malware_scan_status"], "pass")
        for field in ("note", "basis"):
            with self.subTest(field=field):
                self.assertNotIn("remains not_run", acceptance.get(field, ""))
                self.assertNotIn("malware_scan_status remains", acceptance.get(field, ""))

    def test_the_file_carries_no_comment_claiming_not_run(self):
        text = REGISTRY.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") and "not_run" in stripped:
                with self.subTest(line=stripped):
                    self.assertNotIn("still reads not_run", stripped)
                    self.assertNotIn("remains not_run", stripped)


if __name__ == "__main__":
    unittest.main()
