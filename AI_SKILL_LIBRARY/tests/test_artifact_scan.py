"""Tests for Task 3 artifact scan evidence and fail-closed admission."""

import json
import unittest

from AI_SKILL_LIBRARY.v4.survival.artifact_scan import (
    AdmissionDecision,
    ScanEvidence,
    ScanEvidenceError,
    admit_artifact,
    parse_scan_evidence,
    trivy_available,
)


SHA = "a" * 64


def clean_payload():
    return {
        "scanner": "trivy",
        "artifact_sha256": SHA,
        "vulnerabilities": [],
        "secrets_found": [],
        "passed": True,
    }


class ScanEvidenceTests(unittest.TestCase):
    def test_parse_clean_evidence(self):
        evidence = parse_scan_evidence(clean_payload())
        self.assertIsInstance(evidence, ScanEvidence)
        self.assertEqual(evidence.artifact_sha256, SHA)
        self.assertTrue(evidence.is_clean)
        self.assertFalse(evidence.has_secrets)

    def test_parse_json_string(self):
        evidence = parse_scan_evidence(json.dumps(clean_payload()))
        self.assertEqual(evidence.scanner, "trivy")

    def test_parse_missing_key_fails_closed(self):
        payload = clean_payload()
        del payload["passed"]
        with self.assertRaises(ScanEvidenceError):
            parse_scan_evidence(payload)

    def test_parse_invalid_json_fails_closed(self):
        with self.assertRaises(ScanEvidenceError):
            parse_scan_evidence("not json")

    def test_parse_non_mapping_fails_closed(self):
        with self.assertRaises(ScanEvidenceError):
            parse_scan_evidence([1, 2, 3])

    def test_parse_bad_findings_fails_closed(self):
        payload = clean_payload()
        payload["vulnerabilities"] = ["CVE-0000"]
        with self.assertRaises(ScanEvidenceError):
            parse_scan_evidence(payload)

    def test_parse_non_bool_passed_fails_closed(self):
        payload = clean_payload()
        payload["passed"] = "yes"
        with self.assertRaises(ScanEvidenceError):
            parse_scan_evidence(payload)

    def test_secrets_mark_not_clean(self):
        payload = clean_payload()
        payload["secrets_found"] = [{"RuleID": "aws-key"}]
        evidence = parse_scan_evidence(payload)
        self.assertTrue(evidence.has_secrets)
        self.assertFalse(evidence.is_clean)

    def test_trivy_available_is_bool(self):
        self.assertIsInstance(trivy_available(), bool)


class AdmissionTests(unittest.TestCase):
    def test_clean_evidence_admitted(self):
        decision = admit_artifact(SHA, parse_scan_evidence(clean_payload()))
        self.assertTrue(decision.admitted)
        self.assertEqual(decision.reasons, ())

    def test_missing_evidence_fails_closed(self):
        decision = admit_artifact(SHA, None)
        self.assertFalse(decision.admitted)
        self.assertIn("scan evidence missing", decision.reasons)

    def test_hash_mismatch_fails_closed(self):
        decision = admit_artifact("b" * 64, parse_scan_evidence(clean_payload()))
        self.assertFalse(decision.admitted)
        self.assertIn("scan evidence hash mismatch", decision.reasons)

    def test_secrets_fail_closed(self):
        payload = clean_payload()
        payload["secrets_found"] = [{"RuleID": "token"}]
        decision = admit_artifact(SHA, parse_scan_evidence(payload))
        self.assertFalse(decision.admitted)
        self.assertIn("scan evidence reports secrets", decision.reasons)

    def test_unpassed_evidence_fails_closed(self):
        payload = clean_payload()
        payload["passed"] = False
        decision = admit_artifact(SHA, parse_scan_evidence(payload))
        self.assertFalse(decision.admitted)
        self.assertIn("scan evidence did not pass", decision.reasons)

    def test_malformed_evidence_fails_closed(self):
        decision = admit_artifact(SHA, {"scanner": "trivy"})
        self.assertFalse(decision.admitted)
        self.assertIn("scan evidence malformed", decision.reasons)

    def test_missing_hash_fails_closed(self):
        decision = admit_artifact("", parse_scan_evidence(clean_payload()))
        self.assertFalse(decision.admitted)
        self.assertIn("artifact hash missing", decision.reasons)

    def test_unprotected_artifact_admitted(self):
        decision = admit_artifact(SHA, None, protected=False)
        self.assertTrue(decision.admitted)

    def test_no_authority_flags(self):
        decision = AdmissionDecision(admitted=True)
        self.assertFalse(decision.routing_authority)
        self.assertFalse(decision.reasoning_authority)
        self.assertFalse(decision.scheduling_authority)
        self.assertFalse(decision.merge_authority)
        self.assertFalse(decision.deployment_authority)
        self.assertFalse(decision.trading_authority)


if __name__ == "__main__":
    unittest.main()
