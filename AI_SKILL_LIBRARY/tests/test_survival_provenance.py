"""Tests for Task 4 artifact provenance validation and fail-closed admission."""

import json
import unittest

from AI_SKILL_LIBRARY.v4.survival.provenance import (
    ArtifactProvenance,
    ProvenanceDecision,
    ProvenanceError,
    admit_with_provenance,
    parse_provenance,
    validate_provenance,
)


SHA = "c" * 64
REV = "git:abc123"
SIGNER = "cosign:keyless:builder@example.com"
SBOM = "cyclonedx:sha256:deadbeef"


def valid_payload():
    return {
        "sha256": SHA,
        "source_revision": REV,
        "signer_ref": SIGNER,
        "sbom_ref": SBOM,
        "verified": True,
    }


class ParseProvenanceTests(unittest.TestCase):
    def test_parse_valid(self):
        prov = parse_provenance(valid_payload())
        self.assertIsInstance(prov, ArtifactProvenance)
        self.assertEqual(prov.sha256, SHA)
        self.assertTrue(prov.verified)

    def test_parse_json_string(self):
        prov = parse_provenance(json.dumps(valid_payload()))
        self.assertEqual(prov.sbom_ref, SBOM)

    def test_parse_missing_key_fails_closed(self):
        payload = valid_payload()
        del payload["sbom_ref"]
        with self.assertRaises(ProvenanceError):
            parse_provenance(payload)

    def test_parse_invalid_json_fails_closed(self):
        with self.assertRaises(ProvenanceError):
            parse_provenance("<xml/>")

    def test_parse_non_mapping_fails_closed(self):
        with self.assertRaises(ProvenanceError):
            parse_provenance(42)

    def test_parse_empty_string_fails_closed(self):
        payload = valid_payload()
        payload["signer_ref"] = "   "
        with self.assertRaises(ProvenanceError):
            parse_provenance(payload)

    def test_parse_non_bool_verified_fails_closed(self):
        payload = valid_payload()
        payload["verified"] = 1
        with self.assertRaises(ProvenanceError):
            parse_provenance(payload)


class ValidateProvenanceTests(unittest.TestCase):
    def test_valid_provenance_has_no_reasons(self):
        prov = parse_provenance(valid_payload())
        self.assertEqual(validate_provenance(SHA, prov), ())

    def test_missing_provenance_fails_closed(self):
        reasons = validate_provenance(SHA, None)
        self.assertIn("provenance missing", reasons)

    def test_hash_mismatch_fails_closed(self):
        prov = parse_provenance(valid_payload())
        reasons = validate_provenance("d" * 64, prov)
        self.assertIn("provenance hash mismatch", reasons)

    def test_unverified_fails_closed(self):
        payload = valid_payload()
        payload["verified"] = False
        reasons = validate_provenance(SHA, parse_provenance(payload))
        self.assertIn("provenance unverified", reasons)

    def test_source_revision_mismatch_fails_closed(self):
        prov = parse_provenance(valid_payload())
        reasons = validate_provenance(SHA, prov, expected_source_revision="git:other")
        self.assertIn("source revision mismatch", reasons)

    def test_signer_mismatch_fails_closed(self):
        prov = parse_provenance(valid_payload())
        reasons = validate_provenance(SHA, prov, expected_signer_ref="cosign:other")
        self.assertIn("signer reference mismatch", reasons)

    def test_sbom_mismatch_fails_closed(self):
        prov = parse_provenance(valid_payload())
        reasons = validate_provenance(SHA, prov, expected_sbom_ref="spdx:other")
        self.assertIn("sbom reference mismatch", reasons)

    def test_missing_artifact_hash_fails_closed(self):
        prov = parse_provenance(valid_payload())
        reasons = validate_provenance("", prov)
        self.assertIn("artifact hash missing", reasons)

    def test_malformed_provenance_fails_closed(self):
        reasons = validate_provenance(SHA, {"sha256": SHA})
        self.assertIn("provenance malformed", reasons)


class ProvenanceAdmissionTests(unittest.TestCase):
    def test_valid_provenance_admitted(self):
        decision = admit_with_provenance(SHA, parse_provenance(valid_payload()))
        self.assertTrue(decision.admitted)
        self.assertEqual(decision.reasons, ())

    def test_missing_provenance_fails_closed(self):
        decision = admit_with_provenance(SHA, None)
        self.assertFalse(decision.admitted)
        self.assertIn("provenance missing", decision.reasons)

    def test_unverified_fails_closed(self):
        payload = valid_payload()
        payload["verified"] = False
        decision = admit_with_provenance(SHA, parse_provenance(payload))
        self.assertFalse(decision.admitted)
        self.assertIn("provenance unverified", decision.reasons)

    def test_expected_revision_enforced(self):
        decision = admit_with_provenance(
            SHA,
            parse_provenance(valid_payload()),
            expected_source_revision="git:different",
        )
        self.assertFalse(decision.admitted)
        self.assertIn("source revision mismatch", decision.reasons)

    def test_unprotected_artifact_admitted(self):
        decision = admit_with_provenance(SHA, None, protected=False)
        self.assertTrue(decision.admitted)

    def test_no_authority_flags(self):
        decision = ProvenanceDecision(admitted=True)
        self.assertFalse(decision.routing_authority)
        self.assertFalse(decision.reasoning_authority)
        self.assertFalse(decision.scheduling_authority)
        self.assertFalse(decision.merge_authority)
        self.assertFalse(decision.deployment_authority)
        self.assertFalse(decision.trading_authority)


if __name__ == "__main__":
    unittest.main()
