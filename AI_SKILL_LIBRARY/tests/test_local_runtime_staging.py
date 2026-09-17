"""Staged-artifact intake tests, driven by the real canonical record."""

import copy
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.local_runtime.staging import (
    IntakeStatus,
    cached_artifact_path,
    intake_staged_artifact,
    manifest_path,
    quarantine_dir,
    resolve_cached,
    sha256_file,
)

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"


def canonical_record():
    return copy.deepcopy(yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["models"][0])


def build_gguf(tensors=1, payload=b"\x00" * 128):
    """A small well-formed GGUF, used as a stand-in staged file."""
    out = bytearray(b"GGUF")
    out += struct.pack("<I", 3)
    out += struct.pack("<Q", tensors)
    out += struct.pack("<Q", 0)
    for index in range(tensors):
        name = f"t{index}".encode()
        out += struct.pack("<Q", len(name)) + name
        out += struct.pack("<I", 1) + struct.pack("<Q", 4)
        out += struct.pack("<I", 0) + struct.pack("<Q", 0)
    return bytes(out) + payload


class StagedIntakeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "cache"
        self.staged_dir = Path(self._tmp.name) / "staged"
        self.staged_dir.mkdir(parents=True)
        self.addCleanup(self._tmp.cleanup)

        self.blob = build_gguf()
        self.digest = hashlib.sha256(self.blob).hexdigest()
        # A record describing exactly these bytes.
        self.record = canonical_record()
        self.record["artifact_identity"] = {
            **self.record["artifact_identity"],
            "sha256": self.digest,
            "size_bytes": len(self.blob),
        }

    def stage(self, data=None, name="Qwen3-0.6B-Q8_0.gguf"):
        path = self.staged_dir / name
        path.write_bytes(self.blob if data is None else data)
        return path

    # -- happy path --------------------------------------------------------

    def test_a_matching_staged_artifact_is_verified_and_cached(self):
        result = intake_staged_artifact(self.stage(), self.record, root=self.root)
        self.assertEqual(result.status, IntakeStatus.VERIFIED, result.reason)
        self.assertTrue(result.verified)
        self.assertTrue(result.digest_match)
        self.assertTrue(Path(result.cached_path).is_file())

    def test_the_digest_is_recomputed_from_the_bytes_on_disk(self):
        result = intake_staged_artifact(self.stage(), self.record, root=self.root)
        self.assertEqual(result.recomputed_sha256, self.digest)
        self.assertEqual(result.expected_sha256, self.digest)
        self.assertEqual(result.recomputed_sha256, sha256_file(Path(result.cached_path)))

    def test_a_manifest_records_the_verification(self):
        result = intake_staged_artifact(self.stage(), self.record, root=self.root)
        identity = result.identity
        payload = json.loads(manifest_path(self.root, identity).read_text(encoding="utf-8"))
        self.assertEqual(payload["verified_sha256"], self.digest)
        self.assertEqual(payload["immutable_revision"], identity.immutable_revision)
        self.assertIs(payload["clears_governance"], False)

    def test_copy_leaves_the_staged_file_in_place(self):
        staged = self.stage()
        intake_staged_artifact(staged, self.record, root=self.root)
        self.assertTrue(staged.is_file())

    def test_move_consumes_the_staged_file(self):
        staged = self.stage()
        intake_staged_artifact(staged, self.record, root=self.root, move=True)
        self.assertFalse(staged.is_file())

    def test_a_second_intake_is_already_cached(self):
        intake_staged_artifact(self.stage(), self.record, root=self.root)
        again = intake_staged_artifact(self.stage(), self.record, root=self.root)
        self.assertEqual(again.status, IntakeStatus.ALREADY_CACHED)
        self.assertTrue(again.verified)

    def test_a_corrupt_staged_file_is_reported_even_when_the_cache_is_good(self):
        """A populated cache must not silently accept bad staged input."""
        intake_staged_artifact(self.stage(), self.record, root=self.root)
        corrupt = bytearray(self.blob)
        corrupt[-1] ^= 0xFF
        result = intake_staged_artifact(self.stage(bytes(corrupt)), self.record, root=self.root)
        self.assertEqual(result.status, IntakeStatus.DIGEST_MISMATCH)
        self.assertIsNotNone(result.quarantined_path)
        # The good cached artifact is untouched by the bad submission.
        self.assertIsNotNone(resolve_cached(self.root, self.record))

    def test_a_wrong_size_staged_file_is_reported_over_a_good_cache(self):
        intake_staged_artifact(self.stage(), self.record, root=self.root)
        result = intake_staged_artifact(self.stage(self.blob + b"x"), self.record, root=self.root)
        self.assertEqual(result.status, IntakeStatus.SIZE_MISMATCH)

    def test_already_cached_with_no_staged_file_is_still_reported(self):
        intake_staged_artifact(self.stage(), self.record, root=self.root, move=True)
        result = intake_staged_artifact(self.staged_dir / "gone.gguf", self.record, root=self.root)
        self.assertEqual(result.status, IntakeStatus.ALREADY_CACHED)
        self.assertTrue(result.verified)

    def test_resolve_cached_returns_the_verified_artifact(self):
        self.assertIsNone(resolve_cached(self.root, self.record))
        intake_staged_artifact(self.stage(), self.record, root=self.root)
        self.assertIsNotNone(resolve_cached(self.root, self.record))

    def test_the_cache_key_is_identity_not_model_id(self):
        result = intake_staged_artifact(self.stage(), self.record, root=self.root)
        parts = Path(result.cached_path).parts
        self.assertTrue(any(result.identity.fingerprint[:12] in part for part in parts))
        self.assertTrue(any("Q8_0" in part for part in parts))

    def test_a_different_quantization_caches_separately(self):
        first = intake_staged_artifact(self.stage(), self.record, root=self.root)
        other = copy.deepcopy(self.record)
        other["artifact_identity"] = {**other["artifact_identity"], "quantization": "Q4_K_M"}
        self.assertNotEqual(
            cached_artifact_path(self.root, first.identity),
            cached_artifact_path(self.root, __import__(
                "AI_SKILL_LIBRARY.v4.local_runtime.identity", fromlist=["from_record"]
            ).from_record(other)[0]),
        )

    # -- rejection ---------------------------------------------------------

    def test_a_size_mismatch_is_refused_and_quarantined(self):
        result = intake_staged_artifact(self.stage(self.blob + b"extra"), self.record, root=self.root)
        self.assertEqual(result.status, IntakeStatus.SIZE_MISMATCH)
        self.assertFalse(result.verified)
        self.assertTrue(Path(result.quarantined_path).is_file())

    def test_a_digest_mismatch_is_refused_and_quarantined(self):
        corrupt = bytearray(self.blob)
        corrupt[-1] ^= 0xFF                       # same length, different bytes
        result = intake_staged_artifact(self.stage(bytes(corrupt)), self.record, root=self.root)
        self.assertEqual(result.status, IntakeStatus.DIGEST_MISMATCH)
        self.assertFalse(result.digest_match)
        self.assertNotEqual(result.recomputed_sha256, result.expected_sha256)
        self.assertTrue(Path(result.quarantined_path).is_file())

    def test_a_rejected_artifact_is_never_cached(self):
        result = intake_staged_artifact(self.stage(self.blob + b"x"), self.record, root=self.root)
        self.assertIsNone(result.cached_path)
        self.assertIsNone(resolve_cached(self.root, self.record))

    def test_a_quarantined_file_is_kept_as_evidence_not_deleted(self):
        result = intake_staged_artifact(self.stage(self.blob + b"x"), self.record, root=self.root)
        self.assertTrue(quarantine_dir(self.root).is_dir())
        self.assertGreater(Path(result.quarantined_path).stat().st_size, 0)

    def test_a_non_gguf_payload_with_a_matching_digest_is_still_refused(self):
        # The digest proves the bytes are the expected ones; it says nothing
        # about whether they are a loadable artifact.
        blob = b"this is not a gguf file at all"
        record = copy.deepcopy(self.record)
        record["artifact_identity"] = {
            **record["artifact_identity"],
            "sha256": hashlib.sha256(blob).hexdigest(),
            "size_bytes": len(blob),
        }
        result = intake_staged_artifact(self.stage(blob), record, root=self.root)
        self.assertEqual(result.status, IntakeStatus.FORMAT_REJECTED)
        self.assertTrue(result.digest_match)
        self.assertIsNotNone(result.quarantined_path)

    def test_a_structurally_broken_gguf_is_refused(self):
        broken = bytearray(build_gguf())
        struct.pack_into("<Q", broken, 8, 2**40)   # absurd tensor count
        blob = bytes(broken)
        record = copy.deepcopy(self.record)
        record["artifact_identity"] = {
            **record["artifact_identity"],
            "sha256": hashlib.sha256(blob).hexdigest(),
            "size_bytes": len(blob),
        }
        result = intake_staged_artifact(self.stage(blob), record, root=self.root)
        self.assertEqual(result.status, IntakeStatus.FORMAT_REJECTED)

    def test_a_missing_staged_file_is_reported(self):
        result = intake_staged_artifact(self.staged_dir / "absent.gguf", self.record, root=self.root)
        self.assertEqual(result.status, IntakeStatus.MISSING)

    def test_a_record_without_identity_is_refused(self):
        result = intake_staged_artifact(self.stage(), {"model_id": "x"}, root=self.root)
        self.assertEqual(result.status, IntakeStatus.IDENTITY_INCOMPLETE)

    def test_a_corrupted_cache_entry_is_quarantined_and_replaced(self):
        first = intake_staged_artifact(self.stage(), self.record, root=self.root)
        Path(first.cached_path).write_bytes(b"rot")
        again = intake_staged_artifact(self.stage(), self.record, root=self.root)
        self.assertEqual(again.status, IntakeStatus.VERIFIED)
        self.assertEqual(sha256_file(Path(again.cached_path)), self.digest)

    # -- governance boundary ----------------------------------------------

    def test_intake_never_claims_to_clear_governance(self):
        payload = intake_staged_artifact(self.stage(), self.record, root=self.root).to_dict()
        self.assertIs(payload["clears_governance"], False)
        self.assertIs(payload["clears_quarantine"], False)

    def test_intake_does_not_mutate_the_record(self):
        before = copy.deepcopy(self.record)
        intake_staged_artifact(self.stage(), self.record, root=self.root)
        self.assertEqual(self.record, before)

    def test_a_verified_artifact_of_a_quarantined_model_stays_unplaceable(self):
        """The bytes being right does not make the model runnable."""
        from AI_SKILL_LIBRARY.v4.local_runtime.projection import project_record
        result = intake_staged_artifact(self.stage(), self.record, root=self.root)
        self.assertTrue(result.verified)
        self.assertEqual(self.record["lifecycle_state"], "QUARANTINED")
        projected = project_record(self.record)
        self.assertFalse(projected.placeable)

    def test_result_is_json_safe(self):
        payload = intake_staged_artifact(self.stage(), self.record, root=self.root).to_dict()
        self.assertEqual(json.loads(json.dumps(payload))["status"], "VERIFIED")


if __name__ == "__main__":
    unittest.main()
