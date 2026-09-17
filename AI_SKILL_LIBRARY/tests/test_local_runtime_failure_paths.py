"""Failure paths: a refusal must stay a refusal all the way out.

Each gate already has a test asserting it refuses. The property those tests do
not cover is what the gates exist for - that nothing downstream quietly softens
a refusal into a degraded success. These run the real functions against real
bad input and check the refusal survives.
"""

import json
import tempfile
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.local_runtime.resilience import (
    BreakerState,
    CircuitBreaker,
    FailureKind,
    classify_exception,
)
from AI_SKILL_LIBRARY.v4.local_runtime.scanner import ScanStatus, scan_gguf
from AI_SKILL_LIBRARY.v4.tools.local_runtime_failure_paths import (
    breaker_opens_and_recovers,
    failures_are_classified,
    not_a_model_is_refused,
    truncated_artifact_is_refused,
)

ROOT = Path(__file__).resolve().parents[2]
PROOF = ROOT / "CHECKPOINTS/evidence/FAILURE_PATH_PROOF.json"


class ScannerFailurePathTests(unittest.TestCase):
    def test_a_truncated_file_fails_without_raising(self):
        """A scanner that crashes on a hostile file has become the hole."""
        with tempfile.TemporaryDirectory() as tmp:
            result = truncated_artifact_is_refused(Path(tmp))
            self.assertTrue(result["refused"])

    def test_a_non_gguf_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(not_a_model_is_refused(Path(tmp))["refused"])

    def test_an_empty_file_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.gguf"
            path.write_bytes(b"")
            self.assertIsNot(scan_gguf(path).status, ScanStatus.PASS)

    def test_a_structural_pass_never_claims_to_be_a_malware_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.gguf"
            path.write_bytes(b"not gguf")
            self.assertFalse(scan_gguf(path).to_dict()["satisfies_malware_scan_status"])


class BreakerTests(unittest.TestCase):
    def test_it_opens_on_repeated_failure_and_recovers(self):
        self.assertTrue(breaker_opens_and_recovers()["behaves_correctly"])

    def test_a_fatal_failure_opens_it_immediately(self):
        """Some failures should not be retried even once more."""
        from AI_SKILL_LIBRARY.v4.local_runtime.resilience import FATAL_KINDS

        breaker = CircuitBreaker(failure_threshold=99, cooldown_seconds=5.0)
        breaker.record_failure(next(iter(FATAL_KINDS)), now=0.0)
        self.assertIs(breaker.state, BreakerState.OPEN)

    def test_cooldown_grows_with_repeated_opens(self):
        """A runtime that keeps failing should be retried less often, not more."""
        breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=10.0)
        breaker.record_failure(FailureKind.TIMEOUT, now=0.0)
        first = breaker.cooldown_remaining(now=0.0)
        breaker.allow(now=100.0)
        breaker.record_failure(FailureKind.TIMEOUT, now=100.0)
        second = breaker.cooldown_remaining(now=100.0)
        self.assertGreater(second, first)


class ClassificationTests(unittest.TestCase):
    def test_an_unrecognised_failure_is_never_benign(self):
        self.assertTrue(failures_are_classified()["unknown_is_not_benign"])

    def test_out_of_memory_is_recognised(self):
        self.assertIs(classify_exception(MemoryError("oom")), FailureKind.OOM)


class CommittedProofTests(unittest.TestCase):
    def setUp(self):
        if not PROOF.is_file():
            self.skipTest("no failure-path proof committed")
        self.proof = json.loads(PROOF.read_text(encoding="utf-8"))

    def test_every_case_held(self):
        self.assertEqual(self.proof["failure_paths"], "PROVEN")
        self.assertEqual(self.proof["held"], self.proof["cases"])

    def test_a_corrupt_artifact_never_reached_the_cache(self):
        """The refusal that matters most: one flipped bit, past the header, so
        the container still parses and only the digest disagrees."""
        case = next((c for c in self.proof["results"] if c["case"] == "corrupt_artifact"), None)
        if case is None or "skipped" in case:
            self.skipTest("corrupt-artifact case did not run")
        self.assertTrue(case["refused"])
        self.assertEqual(case["status"], "DIGEST_MISMATCH")
        # Not "the cache is empty": intake keeps the failed bytes as evidence.
        # What must hold is that nothing resolvable was cached, so no later
        # lookup can find it.
        self.assertTrue(case["nothing_resolvable_cached"])
        self.assertEqual(case["resolvable_entries"], [])
        self.assertTrue(case["evidence_kept"])
        self.assertNotEqual(case["expected_sha256"], case["recomputed_sha256"])

    def test_quarantined_models_were_actually_checked(self):
        case = next(c for c in self.proof["results"] if c["case"] == "quarantined_not_placeable")
        if not case.get("models"):
            self.skipTest("no quarantined models to check")
        self.assertTrue(case["refused"])
        for row in case["models"]:
            with self.subTest(model_id=row["model_id"]):
                self.assertFalse(row["placeable"])

    def test_the_proof_destroyed_nothing(self):
        self.assertTrue(self.proof["nothing_was_destroyed"])
        self.assertTrue(self.proof["canonical_registry_untouched"])


if __name__ == "__main__":
    unittest.main()
