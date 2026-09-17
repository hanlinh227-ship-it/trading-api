import unittest

from AI_SKILL_LIBRARY.v4.control_plane.e2e import run_golden_e2e


IDENTITY = {"model_id": "m", "family": "f", "variant": "v", "immutable_revision": "a" * 40, "sha256": "b" * 64, "size_bytes": 10, "format": "gguf", "quantization": "Q8_0"}


def ingress(_envelope, _route): return {"request_id": "r", "request": "x", "selection_request": {}}
def router(_envelope): return {"routed_by": "task_router", "domain": "MATH", "profile": "STANDARD", "primary_skill": "math"}
def selector(_request, _candidates): return {"primary_model": {"candidate_key": "local:x", "artifact_identity": IDENTITY}, "supporting_models": [], "verifier": "MATH", "fallback_chain": [], "evidence_refs": [], "resource_plan": {}}
def verifier(_kind, _output): return {"passed": True, "failures": [], "evidence_refs": ["verify:1"]}
def synthesis(_prepared, runtime, _verification): return {"answer": runtime["output"]}


def real_runtime(_selection, _prepared):
    return {
        "real_inference": True, "synthetic": False, "fixture_only": False,
        "artifact_identity": IDENTITY, "runtime": "llama.cpp", "runtime_version": "1",
        "offline": True,
        "started_at": "2026-09-17T00:00:00Z", "ended_at": "2026-09-17T00:00:01Z",
        "load_latency_ms": 10, "inference_latency_ms": 20, "peak_ram_mb": 100,
        "output": "4", "raw_run_ref": "run:1", "lifecycle": {"wake": True, "warm": True, "sleep": True},
    }


class GoldenE2ETests(unittest.TestCase):
    def _run_case(self, runtime=real_runtime, verify=verifier):
        return run_golden_e2e({}, [], ingress=ingress, router=router, selector=selector, runtime=runtime, verifier=verify, synthesis=synthesis)

    def test_exact_trace_and_real_runtime_pass(self):
        result = self._run_case()
        self.assertEqual(result["trace"], ["ingress", "task_router", "task_decomposition", "model_mesh", "runtime_scheduler", "wake_load", "real_inference", "verifier", "brain_synthesis", "response", "warm_sleep"])
        self.assertTrue(result["B2_pass"])
        self.assertTrue(result["B3_pass"])
        self.assertTrue(result["B4_pass"])

    def test_fake_or_fixture_runtime_cannot_pass(self):
        def fake(selection, prepared):
            row = real_runtime(selection, prepared); row["synthetic"] = True
            return row
        result = self._run_case(fake)
        self.assertFalse(result["B2_pass"])
        self.assertFalse(result["B3_pass"])

    def test_artifact_identity_mismatch_fails_closed(self):
        def mismatch(selection, prepared):
            row = real_runtime(selection, prepared); row["artifact_identity"] = {**IDENTITY, "sha256": "c" * 64}
            return row
        self.assertIn("artifact_identity_mismatch", self._run_case(mismatch)["failures"])

    def test_verifier_failure_blocks_b3_and_b4(self):
        failed = lambda _kind, _output: {"passed": False, "failures": ["wrong"], "evidence_refs": []}
        result = self._run_case(verify=failed)
        self.assertTrue(result["B2_pass"])
        self.assertFalse(result["B3_pass"])
        self.assertFalse(result["B4_pass"])

    def test_offline_evidence_is_required_for_b4(self):
        def online(selection, prepared):
            row = real_runtime(selection, prepared); row["offline"] = False
            return row
        result = self._run_case(online)
        self.assertTrue(result["B2_pass"])
        self.assertTrue(result["B3_pass"])
        self.assertFalse(result["B4_pass"])


if __name__ == "__main__": unittest.main()
