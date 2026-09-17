import hashlib
import tempfile
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.local_runtime.acquisition import (
    AcquisitionRequest,
    AcquisitionStatus,
    TransportError,
    acquire,
    partial_path,
    precondition_refusals,
    resolve_artifact,
    verify_cached_artifact,
)
from AI_SKILL_LIBRARY.v4.local_runtime.lifecycle import ModelState

PAYLOAD = b"weights-" * 512
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


def make_request(root, **kwargs):
    kwargs.setdefault("model_id", "qwen3-8b")
    kwargs.setdefault("revision", "a1b2c3d4")
    kwargs.setdefault("source_uri", "https://example.invalid/qwen3-8b/weights.bin")
    kwargs.setdefault("filename", "weights.bin")
    kwargs.setdefault("sha256", DIGEST)
    kwargs.setdefault("size_bytes", len(PAYLOAD))
    kwargs.setdefault("lifecycle_state", ModelState.AVAILABLE)
    kwargs.setdefault("runtime", "llama.cpp")
    kwargs.setdefault("supported_runtimes", frozenset({"llama.cpp"}))
    kwargs.setdefault("disk_budget_bytes", 10 * len(PAYLOAD))
    # Safety evidence a vetted artifact would already carry. Acquisition
    # consumes these decisions; it never makes them.
    kwargs.setdefault("artifact_format", "gguf")
    kwargs.setdefault("quantization", "Q8_0")
    kwargs.setdefault("license_admission_ref", "governance:license/fixture#1")
    kwargs.setdefault("provenance_ref", "governance:provenance/fixture#1")
    kwargs.setdefault("safe_format_verified", True)
    return AcquisitionRequest(root=Path(root), **kwargs)


def whole_fetcher(chunk=64):
    def fetch(uri, *, offset=0):
        body = PAYLOAD[offset:]
        for start in range(0, len(body), chunk):
            yield body[start:start + chunk]

    return fetch


def truncating_fetcher(stop_after_bytes):
    def fetch(uri, *, offset=0):
        body = PAYLOAD[offset:offset + stop_after_bytes]
        yield body
        raise TransportError("connection reset")

    return fetch


class PreconditionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def test_approved_request_has_no_refusals(self):
        self.assertEqual(precondition_refusals(make_request(self.root)), ())

    def test_unapproved_model_is_refused(self):
        for state in (ModelState.DISCOVERED, ModelState.REGISTERED, ModelState.BLOCKED):
            with self.subTest(state=state):
                refusals = precondition_refusals(make_request(self.root, lifecycle_state=state))
                self.assertTrue(any("state" in r for r in refusals), refusals)

    def test_unpinned_revision_is_refused(self):
        for revision in ("", "main", "latest", "HEAD"):
            with self.subTest(revision=revision):
                refusals = precondition_refusals(make_request(self.root, revision=revision))
                self.assertTrue(any("revision" in r for r in refusals), refusals)

    def test_unknown_size_is_refused(self):
        refusals = precondition_refusals(make_request(self.root, size_bytes=None))
        self.assertTrue(any("size" in r for r in refusals), refusals)

    def test_missing_checksum_is_refused(self):
        refusals = precondition_refusals(make_request(self.root, sha256=None))
        self.assertTrue(any("checksum" in r for r in refusals), refusals)

    def test_disk_budget_shortfall_is_refused(self):
        refusals = precondition_refusals(make_request(self.root, disk_budget_bytes=10))
        self.assertTrue(any("disk" in r for r in refusals), refusals)

    def test_unsupported_runtime_is_refused(self):
        refusals = precondition_refusals(
            make_request(self.root, runtime="vllm", supported_runtimes=frozenset({"llama.cpp"}))
        )
        self.assertTrue(any("runtime" in r for r in refusals), refusals)

    def test_unverified_safe_format_is_refused(self):
        refusals = precondition_refusals(make_request(self.root, safe_format_verified=False))
        self.assertTrue(any("safe artifact format" in r for r in refusals), refusals)

    def test_missing_artifact_format_is_refused(self):
        refusals = precondition_refusals(make_request(self.root, artifact_format=None))
        self.assertTrue(any("artifact_format" in r for r in refusals), refusals)

    def test_missing_quantization_is_refused(self):
        refusals = precondition_refusals(make_request(self.root, quantization=""))
        self.assertTrue(any("quantization" in r for r in refusals), refusals)

    def test_missing_license_admission_reference_is_refused(self):
        refusals = precondition_refusals(make_request(self.root, license_admission_ref=None))
        self.assertTrue(any("license_admission_ref" in r for r in refusals), refusals)

    def test_missing_provenance_reference_is_refused(self):
        refusals = precondition_refusals(make_request(self.root, provenance_ref=None))
        self.assertTrue(any("provenance_ref" in r for r in refusals), refusals)

    def test_egress_with_a_required_sandbox_is_refused(self):
        refusals = precondition_refusals(
            make_request(self.root, egress_allowed=True, sandbox_required=True)
        )
        self.assertTrue(any("egress" in r for r in refusals), refusals)

    def test_safety_evidence_defaults_to_the_refusing_value(self):
        # A request built without safety evidence must not be acquirable.
        bare = AcquisitionRequest(
            root=Path(self.root), model_id="m", revision="a1b2c3d4",
            source_uri="https://example.invalid/w", filename="w.gguf", sha256=DIGEST,
            size_bytes=len(PAYLOAD), lifecycle_state=ModelState.AVAILABLE, runtime="llama.cpp",
            supported_runtimes=frozenset({"llama.cpp"}), disk_budget_bytes=10 * len(PAYLOAD),
        )
        self.assertTrue(precondition_refusals(bare))

    def test_missing_source_uri_is_refused(self):
        refusals = precondition_refusals(make_request(self.root, source_uri=""))
        self.assertTrue(any("source" in r for r in refusals), refusals)

    def test_acquire_refuses_before_touching_the_disk(self):
        request = make_request(self.root, lifecycle_state=ModelState.DISCOVERED)
        result = acquire(request, whole_fetcher())
        self.assertEqual(result.status, AcquisitionStatus.REFUSED)
        self.assertIsNone(result.path)
        self.assertEqual(list(Path(self.root).rglob("*.bin*")), [])


class HappyPathTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def test_download_verifies_and_finalises_atomically(self):
        request = make_request(self.root)
        result = acquire(request, whole_fetcher())
        self.assertEqual(result.status, AcquisitionStatus.COMPLETED)
        self.assertEqual(result.path.read_bytes(), PAYLOAD)
        self.assertEqual(result.bytes_written, len(PAYLOAD))
        self.assertFalse(partial_path(request).exists())

    def test_resolve_returns_the_artifact_only_once_complete(self):
        request = make_request(self.root)
        self.assertIsNone(resolve_artifact(request))
        acquire(request, whole_fetcher())
        self.assertIsNotNone(resolve_artifact(request))

    def test_second_acquire_is_a_no_op(self):
        request = make_request(self.root)
        acquire(request, whole_fetcher())

        def explode(uri, *, offset=0):
            raise AssertionError("must not re-download a verified artifact")

        result = acquire(request, explode)
        self.assertEqual(result.status, AcquisitionStatus.ALREADY_CACHED)

    def test_manifest_records_the_pinned_revision_and_digest(self):
        request = make_request(self.root)
        result = acquire(request, whole_fetcher())
        self.assertEqual(result.manifest["revision"], "a1b2c3d4")
        self.assertEqual(result.manifest["sha256"], DIGEST)
        self.assertEqual(result.manifest["size_bytes"], len(PAYLOAD))


class InterruptionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def test_transport_failure_keeps_the_partial_for_resume(self):
        request = make_request(self.root)
        result = acquire(request, truncating_fetcher(512))
        self.assertEqual(result.status, AcquisitionStatus.FAILED_TRANSPORT)
        self.assertIsNone(result.path)
        self.assertTrue(partial_path(request).exists())
        self.assertEqual(partial_path(request).stat().st_size, 512)

    def test_interrupted_download_resumes_from_the_offset(self):
        request = make_request(self.root)
        acquire(request, truncating_fetcher(512))

        seen_offsets = []

        def resuming(uri, *, offset=0):
            seen_offsets.append(offset)
            yield PAYLOAD[offset:]

        result = acquire(request, resuming)
        self.assertEqual(seen_offsets, [512])
        self.assertEqual(result.status, AcquisitionStatus.COMPLETED)
        self.assertEqual(result.path.read_bytes(), PAYLOAD)

    def test_a_partial_artifact_is_never_resolvable(self):
        request = make_request(self.root)
        acquire(request, truncating_fetcher(512))
        self.assertIsNone(resolve_artifact(request))

    def test_no_internet_is_a_status_not_an_exception(self):
        def offline(uri, *, offset=0):
            raise TransportError("name resolution failed")
            yield b""  # pragma: no cover

        result = acquire(make_request(self.root), offline)
        self.assertEqual(result.status, AcquisitionStatus.FAILED_TRANSPORT)
        self.assertIn("name resolution", result.reason)

    def test_disk_full_mid_write_is_reported_not_raised(self):
        request = make_request(self.root)

        def fetch(uri, *, offset=0):
            yield PAYLOAD[:128]
            raise OSError(28, "No space left on device")

        result = acquire(request, fetch)
        self.assertEqual(result.status, AcquisitionStatus.FAILED_TRANSPORT)
        self.assertIn("space", result.reason.lower())


class CorruptionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def test_checksum_mismatch_fails_and_cleans_up(self):
        request = make_request(self.root)

        def wrong(uri, *, offset=0):
            yield b"x" * len(PAYLOAD)

        result = acquire(request, wrong)
        self.assertEqual(result.status, AcquisitionStatus.FAILED_CHECKSUM)
        self.assertIsNone(result.path)
        # Corrupt bytes are not resumable - resuming them only rebuilds the corruption.
        self.assertFalse(partial_path(request).exists())
        self.assertIsNone(resolve_artifact(request))

    def test_size_mismatch_is_caught_before_the_artifact_is_published(self):
        request = make_request(self.root)

        def short(uri, *, offset=0):
            yield PAYLOAD[:-1]

        result = acquire(request, short)
        self.assertIn(result.status, (AcquisitionStatus.FAILED_CHECKSUM, AcquisitionStatus.FAILED_SIZE))
        self.assertIsNone(resolve_artifact(request))

    def test_corruption_of_a_finalised_artifact_is_detected(self):
        request = make_request(self.root)
        result = acquire(request, whole_fetcher())
        result.path.write_bytes(b"rot" * 100)
        self.assertFalse(verify_cached_artifact(request))
        self.assertIsNone(resolve_artifact(request, verify=True))

    def test_a_corrupt_artifact_can_be_reacquired(self):
        request = make_request(self.root)
        acquire(request, whole_fetcher()).path.write_bytes(b"rot")
        result = acquire(request, whole_fetcher(), verify_cached=True)
        self.assertEqual(result.status, AcquisitionStatus.COMPLETED)
        self.assertEqual(result.path.read_bytes(), PAYLOAD)


if __name__ == "__main__":
    unittest.main()
