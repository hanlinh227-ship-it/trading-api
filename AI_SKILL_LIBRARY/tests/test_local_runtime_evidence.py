import json
import unittest

from AI_SKILL_LIBRARY.v4.local_runtime.admission import ArtifactEvidence, evaluate
from AI_SKILL_LIBRARY.v4.local_runtime.evidence import (
    EvidenceRecorder,
    ExecutionEvidence,
    ExecutionFailureType,
    PeakSampler,
    normalize_failure,
)
from AI_SKILL_LIBRARY.v4.local_runtime.resilience import FailureKind


class FakeClock:
    def __init__(self, start=1000.0):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds
        return self.t


def full_recorder(mono, wall, admitted_at=None):
    recorder = EvidenceRecorder(monotonic=mono, wall=wall, admitted_at=admitted_at)
    recorder.describe(
        worker_id="w-local",
        model_id="m",
        model_revision="abc123",
        artifact_sha256="9" * 64,
        actual_quantization="Q8_0",
        runtime_id="llama.cpp",
        runtime_version="b4200",
        backend="llama.cpp",
        backend_version="b4200",
        placement_action="LOAD_FROM_CACHE",
    )
    return recorder


class FailureNormalizationTests(unittest.TestCase):
    def test_no_failure_is_none_not_unknown(self):
        self.assertEqual(normalize_failure(None), ExecutionFailureType.NONE)

    def test_every_internal_kind_maps_to_a_declared_type(self):
        for kind in FailureKind:
            with self.subTest(kind=kind):
                self.assertIsInstance(normalize_failure(kind), ExecutionFailureType)

    def test_the_evaluator_vocabulary_is_complete(self):
        names = {member.value for member in ExecutionFailureType}
        for required in ("NONE", "OOM", "TIMEOUT", "RUNTIME_CRASH", "LOAD_FAILURE",
                         "DOWNLOAD_FAILURE", "CHECKSUM_FAILURE", "CAPABILITY_MISMATCH",
                         "NETWORK_DEPENDENCY", "WORKER_LOSS", "PROTOCOL", "UNKNOWN"):
            self.assertIn(required, names)

    def test_specific_mappings(self):
        self.assertEqual(normalize_failure(FailureKind.OOM), ExecutionFailureType.OOM)
        self.assertEqual(normalize_failure(FailureKind.TIMEOUT), ExecutionFailureType.TIMEOUT)
        self.assertEqual(normalize_failure(FailureKind.CRASH), ExecutionFailureType.RUNTIME_CRASH)
        self.assertEqual(normalize_failure(FailureKind.WORKER_LOST), ExecutionFailureType.WORKER_LOSS)
        self.assertEqual(
            normalize_failure(FailureKind.UNSUPPORTED), ExecutionFailureType.CAPABILITY_MISMATCH
        )


class TimingTests(unittest.TestCase):
    def test_durations_are_measured_from_the_monotonic_clock(self):
        mono, wall = FakeClock(500.0), FakeClock(1_700_000_000.0)
        recorder = full_recorder(mono, wall, admitted_at=499.5)
        recorder.begin(cold_or_warm="COLD")
        mono.advance(2.0)
        recorder.load_finished()
        recorder.inference_started()
        mono.advance(3.0)
        wall.advance(5.0)
        evidence = recorder.finish(peak_ram_mb=512.0)

        self.assertAlmostEqual(evidence.queue_wait_ms, 500.0, places=1)
        self.assertAlmostEqual(evidence.load_latency_ms, 2000.0, places=1)
        self.assertAlmostEqual(evidence.inference_latency_ms, 3000.0, places=1)
        self.assertAlmostEqual(evidence.total_latency_ms, 5000.0, places=1)

    def test_queue_wait_is_measured_from_admission_not_estimated(self):
        mono, wall = FakeClock(100.0), FakeClock(1_700_000_000.0)
        recorder = full_recorder(mono, wall, admitted_at=99.25)
        recorder.begin(cold_or_warm="WARM")
        evidence = recorder.finish(peak_ram_mb=1.0)
        self.assertAlmostEqual(evidence.queue_wait_ms, 750.0, places=1)

    def test_without_an_admission_time_queue_wait_is_null_not_zero(self):
        mono, wall = FakeClock(), FakeClock(1_700_000_000.0)
        recorder = full_recorder(mono, wall)
        recorder.begin(cold_or_warm="WARM")
        self.assertIsNone(recorder.finish(peak_ram_mb=1.0).queue_wait_ms)

    def test_a_warm_start_has_no_load_phase(self):
        mono, wall = FakeClock(), FakeClock(1_700_000_000.0)
        recorder = full_recorder(mono, wall)
        recorder.begin(cold_or_warm="WARM")
        mono.advance(1.5)
        evidence = recorder.finish(peak_ram_mb=1.0)
        self.assertIsNone(evidence.load_latency_ms)
        self.assertAlmostEqual(evidence.inference_latency_ms, 1500.0, places=1)

    def test_timestamps_are_utc_iso_and_separate_from_durations(self):
        mono, wall = FakeClock(), FakeClock(1_700_000_000.0)
        recorder = full_recorder(mono, wall)
        recorder.begin(cold_or_warm="COLD")
        wall.advance(1.0)
        evidence = recorder.finish(peak_ram_mb=1.0)
        self.assertTrue(evidence.start_time.endswith("+00:00"))
        self.assertTrue(evidence.end_time.endswith("+00:00"))
        self.assertNotEqual(evidence.start_time, evidence.end_time)

    def test_a_wall_clock_step_backwards_cannot_produce_a_negative_duration(self):
        mono, wall = FakeClock(), FakeClock(1_700_000_000.0)
        recorder = full_recorder(mono, wall)
        recorder.begin(cold_or_warm="COLD")
        mono.advance(2.0)
        wall.advance(-30.0)  # NTP correction mid-run
        evidence = recorder.finish(peak_ram_mb=1.0)
        self.assertGreater(evidence.total_latency_ms, 0)


class CompletenessTests(unittest.TestCase):
    def test_a_fully_described_run_is_complete(self):
        mono, wall = FakeClock(), FakeClock(1_700_000_000.0)
        recorder = full_recorder(mono, wall, admitted_at=999.0)
        recorder.begin(cold_or_warm="COLD")
        mono.advance(1.0)
        recorder.load_finished()
        mono.advance(1.0)
        evidence = recorder.finish(peak_ram_mb=900.0, tokens_input=12, tokens_output=30)
        self.assertTrue(evidence.complete, evidence.missing_fields())

    def test_an_undescribed_run_names_what_is_missing(self):
        evidence = ExecutionEvidence()
        self.assertFalse(evidence.complete)
        for field in ("worker_id", "model_id", "artifact_sha256", "actual_quantization",
                      "backend_version", "peak_ram_mb"):
            self.assertIn(field, evidence.missing_fields())

    def test_evidence_is_never_authoritative(self):
        self.assertFalse(ExecutionEvidence().authority)
        self.assertFalse(ExecutionEvidence().to_dict()["execution_evidence"]["authority"])

    def test_unknown_metrics_are_null_and_zero_is_a_measurement(self):
        mono, wall = FakeClock(), FakeClock(1_700_000_000.0)
        recorder = full_recorder(mono, wall)
        recorder.begin(cold_or_warm="WARM")
        evidence = recorder.finish(peak_ram_mb=800.0, peak_vram_mb=0.0)
        payload = evidence.to_dict()["execution_evidence"]["resources"]
        self.assertEqual(payload["peak_vram_mb"], 0.0)  # measured: ran on CPU
        self.assertIsNotNone(payload["peak_ram_mb"])

        unmeasured = recorder.finish(peak_ram_mb=800.0)
        self.assertIsNone(unmeasured.to_dict()["execution_evidence"]["resources"]["peak_vram_mb"])

    def test_the_envelope_has_the_shape_the_evaluator_asked_for(self):
        mono, wall = FakeClock(), FakeClock(1_700_000_000.0)
        recorder = full_recorder(mono, wall)
        recorder.begin(cold_or_warm="COLD", placement_action="ACQUIRE")
        payload = json.loads(json.dumps(recorder.finish(peak_ram_mb=1.0).to_dict()))
        body = payload["execution_evidence"]
        for key in ("worker_id", "model_id", "model_revision", "artifact_sha256",
                    "actual_quantization", "runtime_id", "runtime_version", "backend",
                    "backend_version", "placement_action", "cold_or_warm_start",
                    "timing", "resources", "tokens", "failure", "fallback_used",
                    "attempted_runtimes"):
            self.assertIn(key, body)
        for key in ("queue_wait_ms", "load_latency_ms", "inference_latency_ms",
                    "total_latency_ms", "start_time", "end_time"):
            self.assertIn(key, body["timing"])
        self.assertEqual(set(body["tokens"]), {"input", "output"})
        self.assertEqual(set(body["failure"]), {"kind", "source"})

    def test_fallback_and_attempted_runtimes_are_recorded(self):
        mono, wall = FakeClock(), FakeClock(1_700_000_000.0)
        recorder = full_recorder(mono, wall)
        recorder.begin(cold_or_warm="COLD")
        evidence = recorder.finish(
            peak_ram_mb=1.0, fallback_used=True, attempted_runtimes=("vllm", "llama.cpp")
        )
        self.assertTrue(evidence.fallback_used)
        self.assertEqual(evidence.attempted_runtimes, ("vllm", "llama.cpp"))

    def test_a_failure_carries_its_kind_and_source(self):
        mono, wall = FakeClock(), FakeClock(1_700_000_000.0)
        recorder = full_recorder(mono, wall)
        recorder.begin(cold_or_warm="COLD")
        evidence = recorder.finish(
            peak_ram_mb=1.0, failure=FailureKind.OOM, failure_source="llama.cpp:load"
        )
        body = evidence.to_dict()["execution_evidence"]["failure"]
        self.assertEqual(body["kind"], "OOM")
        self.assertEqual(body["source"], "llama.cpp:load")


class PeakSamplerTests(unittest.TestCase):
    def test_it_measures_this_process(self):
        with PeakSampler(interval=0.01) as sampler:
            blob = [b"x" * 1024 for _ in range(2000)]
            self.assertTrue(blob)
        self.assertIsNotNone(sampler.peak_mb)
        self.assertGreater(sampler.peak_mb, 0)

    def test_an_unreadable_pid_yields_none_rather_than_a_fabricated_figure(self):
        with PeakSampler(pid=999_999_999, interval=0.01) as sampler:
            pass
        self.assertIsNone(sampler.peak_mb)


class SafeAdmissionGateTests(unittest.TestCase):
    def _evidence(self, **overrides):
        base = dict(
            model_id="m", filename="w.gguf", artifact_format="gguf", sha256="9" * 64,
            size_bytes=1000, quantization="Q8_0", revision="abc123", runtime="llama.cpp",
            runtime_support=frozenset({"llama.cpp"}), license_verified=True,
            provenance_verified=True, sandbox_available=True, egress_denied=True,
        )
        base.update(overrides)
        return ArtifactEvidence(**base)

    def test_a_safe_first_load_is_admitted(self):
        result = evaluate(self._evidence())
        self.assertTrue(result.admitted, result.refusals)
        self.assertTrue(result.sandbox_required)
        self.assertTrue(result.egress_required_denied)

    def test_a_first_load_without_a_sandbox_is_refused(self):
        result = evaluate(self._evidence(sandbox_available=False))
        self.assertFalse(result.admitted)
        self.assertTrue(any("sandbox" in r for r in result.refusals))

    def test_a_first_load_with_egress_is_refused(self):
        result = evaluate(self._evidence(egress_denied=False))
        self.assertFalse(result.admitted)
        self.assertTrue(any("egress" in r for r in result.refusals))

    def test_a_previously_loaded_artifact_does_not_need_the_sandbox(self):
        result = evaluate(
            self._evidence(previously_loaded=True, sandbox_available=False, egress_denied=False)
        )
        self.assertTrue(result.admitted, result.refusals)
        self.assertFalse(result.sandbox_required)

    def test_a_pickle_artifact_is_refused_and_quarantined(self):
        result = evaluate(self._evidence(filename="w.pkl", artifact_format="pickle"))
        self.assertFalse(result.admitted)
        self.assertTrue(result.quarantine)
        self.assertTrue(any("executes code" in r for r in result.refusals))

    def test_a_format_that_contradicts_the_filename_is_quarantined(self):
        result = evaluate(self._evidence(filename="w.gguf", artifact_format="pickle"))
        self.assertFalse(result.admitted)
        self.assertTrue(result.quarantine)

    def test_trust_remote_code_is_refused_unless_policy_approved(self):
        refused = evaluate(self._evidence(trust_remote_code=True))
        self.assertFalse(refused.admitted)
        self.assertTrue(refused.quarantine)
        approved = evaluate(self._evidence(trust_remote_code=True, remote_code_allowed=True))
        self.assertTrue(approved.admitted, approved.refusals)

    def test_custom_model_code_is_refused_unless_policy_approved(self):
        self.assertFalse(evaluate(self._evidence(custom_model_code=True)).admitted)
        self.assertTrue(
            evaluate(self._evidence(custom_model_code=True, remote_code_allowed=True)).admitted
        )

    def test_unresolved_license_or_provenance_is_refused(self):
        self.assertTrue(
            any("license" in r for r in evaluate(self._evidence(license_verified=False)).refusals)
        )
        self.assertTrue(
            any("provenance" in r for r in evaluate(self._evidence(provenance_verified=False)).refusals)
        )

    def test_missing_identity_fields_are_refused(self):
        for field in ("sha256", "size_bytes", "revision", "filename", "quantization"):
            with self.subTest(field=field):
                self.assertFalse(evaluate(self._evidence(**{field: None})).admitted)

    def test_a_runtime_the_artifact_does_not_support_is_refused(self):
        result = evaluate(self._evidence(runtime="vllm"))
        self.assertFalse(result.admitted)
        self.assertTrue(any("supported runtimes" in r for r in result.refusals))


if __name__ == "__main__":
    unittest.main()
