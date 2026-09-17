from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.control_plane.artifact_delivery import (
    DeliveryError,
    build_delivery_candidate,
    verify_staged_artifact,
)


class ArtifactDeliveryContractTests(unittest.TestCase):
    def _record(self) -> dict:
        payload = b"GGUF" + b"safe-model-bytes"
        return {
            "model_id": "org/model-gguf",
            "family": "Family",
            "variant": "Variant-Q8_0-GGUF",
            "weights_source": "https://example.invalid/org/model/resolve/0123456789abcdef0123456789abcdef01234567/model.gguf",
            "upstream_revision": "0123456789abcdef0123456789abcdef01234567",
            "local_runtime_possible": True,
            "self_hostable": True,
            "lifecycle_state": "QUARANTINED",
            "authority": False,
            "artifact_identity": {
                "model_id": "org/model-gguf",
                "family": "Family",
                "variant": "Variant-Q8_0-GGUF",
                "immutable_revision": "0123456789abcdef0123456789abcdef01234567",
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
                "format": "gguf",
                "quantization": "Q8_0",
            },
            "admission_evidence": {
                "license_verified": True,
                "provenance_verified": True,
                "safe_format_verified": True,
                "pickle_safe": True,
                "trust_remote_code_required": False,
                "custom_code_required": False,
                "malware_scan_status": "not_run",
                "isolated_first_load_required": True,
                "first_load_egress_allowed": False,
                "quarantine_status": "quarantined",
            },
            "model_mesh_local_candidate_eligible": False,
        }

    def test_candidate_reads_nested_canonical_identity_without_hardcoding(self):
        candidate = build_delivery_candidate(self._record())
        self.assertEqual(candidate.model_id, "org/model-gguf")
        self.assertEqual(candidate.family, "Family")
        self.assertEqual(candidate.variant, "Variant-Q8_0-GGUF")
        self.assertEqual(candidate.quantization, "Q8_0")
        self.assertEqual(candidate.lifecycle_state, "QUARANTINED")
        self.assertFalse(candidate.activation_permitted)

    def test_candidate_fails_closed_when_source_is_not_pinned_to_identity_revision(self):
        record = self._record()
        record["weights_source"] = "https://example.invalid/org/model/resolve/main/model.gguf"
        with self.assertRaisesRegex(DeliveryError, "immutable revision"):
            build_delivery_candidate(record)

    def test_candidate_fails_closed_when_required_identity_field_is_missing(self):
        record = self._record()
        del record["artifact_identity"]["size_bytes"]
        with self.assertRaisesRegex(DeliveryError, "size_bytes"):
            build_delivery_candidate(record)

    def test_verified_bytes_emit_bounded_manifest_without_activating_model(self):
        record = self._record()
        candidate = build_delivery_candidate(record)
        payload = b"GGUF" + b"safe-model-bytes"
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "model.gguf"
            artifact.write_bytes(payload)
            manifest = verify_staged_artifact(
                candidate,
                artifact,
                retrieval_method="github_actions_download",
                malware_scan_status="pass",
                verifier_version="artifact-delivery-v1",
                verified_at="2026-09-17T06:30:00Z",
            )

        self.assertEqual(manifest["artifact"]["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(manifest["artifact"]["size_bytes"], len(payload))
        self.assertEqual(manifest["security"]["malware_scan_status"], "pass")
        self.assertEqual(manifest["quarantine"]["state"], "quarantined")
        self.assertTrue(manifest["runtime_handoff"]["permitted"])
        self.assertEqual(manifest["runtime_handoff"]["purpose"], "isolated_security_first_load_only")
        self.assertFalse(manifest["activation"]["permitted"])
        self.assertFalse(manifest["model_mesh"]["candidate_eligible"])

    def test_size_or_digest_mismatch_fails_closed(self):
        candidate = build_delivery_candidate(self._record())
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "model.gguf"
            artifact.write_bytes(b"GGUF" + b"tampered")
            with self.assertRaisesRegex(DeliveryError, "size|sha256"):
                verify_staged_artifact(
                    candidate,
                    artifact,
                    retrieval_method="external_stage",
                    malware_scan_status="pass",
                )

    def test_nonpassing_malware_status_never_permits_runtime_handoff(self):
        candidate = build_delivery_candidate(self._record())
        payload = b"GGUF" + b"safe-model-bytes"
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "model.gguf"
            artifact.write_bytes(payload)
            manifest = verify_staged_artifact(
                candidate,
                artifact,
                retrieval_method="external_stage",
                malware_scan_status="unknown",
            )
        self.assertFalse(manifest["runtime_handoff"]["permitted"])
        self.assertFalse(manifest["activation"]["permitted"])


if __name__ == "__main__":
    unittest.main()
