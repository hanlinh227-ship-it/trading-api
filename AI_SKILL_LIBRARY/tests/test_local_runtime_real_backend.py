"""Real llama.cpp backend tests.

These run against the actual engine, not a stand-in. Where `llama-cpp-python`
is not installed the suite skips rather than substituting a fake - a green run
on a machine without the library must not be mistakable for evidence that the
library works.

The generation test is the activation hook. Point `LOCAL_RUNTIME_TEST_GGUF` at
a real, complete GGUF and it loads it, generates, and asserts on real output
with no code change anywhere. Until such an artifact exists it skips, and says
why.
"""

import os
import tempfile
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.local_runtime.backends.llama_cpp import LlamaCppError
from AI_SKILL_LIBRARY.v4.local_runtime.backends.llama_cpp_python import (
    LlamaCppPythonBackend,
    detect_llama_cpp_python,
)
from AI_SKILL_LIBRARY.v4.local_runtime.evidence import EvidenceRecorder, ExecutionFailureType
from AI_SKILL_LIBRARY.v4.local_runtime.resilience import FailureKind
from AI_SKILL_LIBRARY.v4.local_runtime.runtime import TaskContract

IDENTITY = detect_llama_cpp_python()
REAL_GGUF = os.environ.get("LOCAL_RUNTIME_TEST_GGUF")

requires_engine = unittest.skipIf(IDENTITY is None, "llama-cpp-python is not installed")
requires_model = unittest.skipIf(
    not REAL_GGUF or not Path(REAL_GGUF).is_file(),
    "no real GGUF artifact available; set LOCAL_RUNTIME_TEST_GGUF to a complete model",
)


def contract(model_id="real-model", prompt="The capital of France is", tokens=16):
    return TaskContract(
        task_id="real-run",
        model_id=model_id,
        payload={"prompt": prompt},
        max_output_tokens=tokens,
        timeout_seconds=300.0,
    )


class EngineIdentityTests(unittest.TestCase):
    @requires_engine
    def test_the_engine_reports_a_real_build_identity(self):
        self.assertIsNotNone(IDENTITY.binding_version)
        self.assertIn("llama-cpp-python/", IDENTITY.backend_version)
        self.assertNotIn("unknown", IDENTITY.backend_version)

    @requires_engine
    def test_the_engine_reports_real_cpu_features(self):
        # Compiled-in feature flags come from the real library, not a constant.
        self.assertTrue(IDENTITY.system_info)
        self.assertIn("=", IDENTITY.system_info)

    @requires_engine
    def test_a_present_engine_is_healthy(self):
        backend = LlamaCppPythonBackend(IDENTITY)
        self.assertTrue(backend.healthy())
        self.assertTrue(backend.probe().healthy)
        self.assertEqual(backend.probe().runtime_version, IDENTITY.backend_version)

    def test_an_absent_engine_is_unhealthy_rather_than_faked(self):
        backend = LlamaCppPythonBackend(None)
        self.assertFalse(backend.healthy())
        self.assertFalse(backend.probe().healthy)
        self.assertEqual(backend.probe().runtime_version, "unavailable")

    def test_a_supported_quantization_list_is_not_offered_as_run_evidence(self):
        # The evaluator needs the quantization actually loaded, so the probe
        # deliberately advertises none.
        self.assertEqual(LlamaCppPythonBackend(IDENTITY).probe().quantizations, frozenset())


class ArtifactGuardTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    @requires_engine
    def test_a_non_gguf_file_is_refused_by_magic_bytes(self):
        path = self.root / "not-a-model.gguf"
        path.write_bytes(b"this is not a model" * 10)
        backend = LlamaCppPythonBackend(IDENTITY)
        with self.assertRaises(LlamaCppError) as caught:
            backend.load("m", path)
        self.assertEqual(caught.exception.kind, FailureKind.UNSUPPORTED)
        self.assertIn("magic bytes", str(caught.exception))

    @requires_engine
    def test_a_missing_artifact_is_a_protocol_failure(self):
        backend = LlamaCppPythonBackend(IDENTITY)
        with self.assertRaises(LlamaCppError) as caught:
            backend.load("m", self.root / "absent.gguf")
        self.assertEqual(caught.exception.kind, FailureKind.PROTOCOL)

    @requires_engine
    def test_a_gguf_header_without_tensors_fails_to_load_and_is_normalized(self):
        # Real llama.cpp rejects a vocab-only GGUF. The magic check passes, the
        # loader does not, and the failure has to survive as a typed kind.
        path = self.root / "header-only.gguf"
        path.write_bytes(b"GGUF" + b"\x00" * 256)
        backend = LlamaCppPythonBackend(IDENTITY)
        with self.assertRaises(LlamaCppError) as caught:
            backend.load("m", path)
        self.assertIn(caught.exception.kind, (FailureKind.UNSUPPORTED, FailureKind.OOM))
        evidence_type = {
            FailureKind.UNSUPPORTED: ExecutionFailureType.CAPABILITY_MISMATCH,
            FailureKind.OOM: ExecutionFailureType.OOM,
        }[caught.exception.kind]
        self.assertIsInstance(evidence_type, ExecutionFailureType)

    def test_loading_without_an_engine_is_refused(self):
        path = self.root / "x.gguf"
        path.write_bytes(b"GGUF")
        with self.assertRaises(LlamaCppError) as caught:
            LlamaCppPythonBackend(None).load("m", path)
        self.assertEqual(caught.exception.kind, FailureKind.UNSUPPORTED)

    @requires_engine
    def test_execute_without_a_load_is_refused(self):
        with self.assertRaises(LlamaCppError) as caught:
            LlamaCppPythonBackend(IDENTITY).execute(contract(), LlamaCppPythonBackend(IDENTITY).probe())
        self.assertEqual(caught.exception.kind, FailureKind.PROTOCOL)


class RealGenerationTests(unittest.TestCase):
    """The activation hook: real artifact in, real evidence out."""

    @requires_engine
    @requires_model
    def test_real_load_generation_and_evidence(self):
        backend = LlamaCppPythonBackend(IDENTITY)
        recorder = EvidenceRecorder(admitted_at=None)
        recorder.describe(
            worker_id="local",
            model_id="real-model",
            runtime_id=backend.name,
            runtime_version=IDENTITY.backend_version,
            backend="llama.cpp",
            backend_version=IDENTITY.backend_version,
        )
        recorder.begin(cold_or_warm="COLD", placement_action="LOAD_FROM_CACHE")

        resident = backend.load("real-model", Path(REAL_GGUF), context_limit=512)
        recorder.load_finished()
        self.assertGreater(resident.load_latency_ms, 0.0)
        self.assertTrue(backend.is_loaded("real-model"))

        recorder.inference_started()
        result = backend.execute(contract(), backend.probe())
        evidence = recorder.finish(
            peak_ram_mb=resident.peak_ram_mb,
            tokens_input=result.get("tokens_input"),
            tokens_output=result.get("tokens_output"),
        )

        # Real generated text, not a placeholder.
        self.assertTrue(result["text"].strip())
        self.assertGreater(result["inference_latency_ms"], 0.0)
        self.assertGreater(evidence.total_latency_ms, 0.0)
        self.assertEqual(evidence.failure_type, ExecutionFailureType.NONE)

        # Warm residency is real: the second call skips the load.
        self.assertTrue(backend.is_loaded("real-model"))
        again = backend.execute(contract(), backend.probe())
        self.assertTrue(again["text"].strip())

        self.assertTrue(backend.unload("real-model"))
        self.assertFalse(backend.is_loaded("real-model"))


if __name__ == "__main__":
    unittest.main()
