import unittest

from AI_SKILL_LIBRARY.v4.control_plane.e2e import run_golden_e2e


IDENTITY = {"model_id": "m", "family": "f", "variant": "v", "immutable_revision": "a" * 40, "sha256": "b" * 64, "size_bytes": 10, "format": "gguf", "quantization": "Q8_0"}


def ingress(_envelope, _route): return {"request_id": "r", "request": "x", "selection_request": {}}
def router(_envelope): return {"routed_by": "task_router", "domain": "MATH", "profile": "STANDARD", "primary_skill": "math"}
def selector(_request, _candidates): return {"primary_model": {"candidate_key": "local:x", "artifact_identity": IDENTITY}, "supporting_models": [], "verifier": "MATH", "fallback_chain": [], "evidence_refs": [], "resource_plan": {}}
def verifier(_kind, _output): return {"passed": True, "failures": [], "evidence_refs": ["verify:1"]}
def legion(_route, _prepared): return {"specialist_group": "MATH", "orchestration_authority": False}
def memory(_prepared, _response, _verification): return {"checkpoint_id": "c1", "resumable": True, "memory_authority": False}
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
        return run_golden_e2e({}, [], ingress=ingress, router=router, legion=legion, selector=selector, runtime=runtime, verifier=verify, synthesis=synthesis, memory=memory)

    def test_exact_trace_and_real_runtime_pass(self):
        result = self._run_case()
        # The trace gained ai_legion, memory_update and checkpoint. Without
        # them a golden run proved a model answered without proving a
        # specialist was involved, and ended without proving the work survived
        # the session that did it.
        self.assertEqual(result["trace"], ["ingress", "task_router", "task_decomposition", "ai_legion", "model_mesh", "runtime_scheduler", "wake_load", "real_inference", "verifier", "brain_synthesis", "response", "memory_update", "checkpoint", "warm_sleep"])
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


class LegionAndContinuityGateTests(unittest.TestCase):
    """The two stages the Definition of Done added, and what they must refuse."""

    def _run(self, **override):
        kwargs = dict(ingress=ingress, router=router, legion=legion, selector=selector,
                      runtime=real_runtime, verifier=verifier, synthesis=synthesis,
                      memory=memory)
        kwargs.update(override)
        return run_golden_e2e({}, [], **kwargs)

    def test_a_run_without_a_specialist_is_refused(self):
        with self.assertRaises(ValueError):
            self._run(legion=lambda _r, _p: {"specialist_group": "", "orchestration_authority": False})

    def test_legion_may_not_claim_orchestration_authority(self):
        """Legion orchestrates specialists; it does not route or select models."""
        with self.assertRaises(ValueError):
            self._run(legion=lambda _r, _p: {"specialist_group": "MATH",
                                             "orchestration_authority": True})

    def test_the_specialist_assignment_is_carried_into_the_result(self):
        self.assertEqual(self._run()["legion"]["specialist_group"], "MATH")

    def test_a_missing_checkpoint_fails_continuity_without_failing_inference(self):
        """Losing the work is not the same as getting it wrong."""
        result = self._run(memory=lambda _p, _r, _v: None)
        self.assertTrue(result["B2_pass"])
        self.assertFalse(result["continuity_pass"])
        self.assertIn("checkpoint_not_written", result["failures"])

    def test_an_unresumable_checkpoint_fails_continuity(self):
        """A checkpoint that cannot be picked up is worse than none: it looks
        like continuity."""
        result = self._run(memory=lambda _p, _r, _v: {"checkpoint_id": "c",
                                                      "resumable": False,
                                                      "memory_authority": False})
        self.assertIn("checkpoint_not_resumable", result["failures"])

    def test_memory_claiming_authority_fails_the_run(self):
        result = self._run(memory=lambda _p, _r, _v: {"checkpoint_id": "c", "resumable": True,
                                                      "memory_authority": True})
        self.assertIn("memory_claimed_authority", result["failures"])

    def test_no_checkpoint_is_written_for_a_run_with_no_answer(self):
        """A resumable record of a failed run is a resumable record of nothing."""
        failed = lambda _kind, _out: {"passed": False, "failures": ["wrong"], "evidence_refs": []}
        result = self._run(verify=failed) if False else self._run(verifier=failed)
        self.assertIsNone(result["response"])
        self.assertIsNone(result["checkpoint"])
        self.assertFalse(result["continuity_pass"])
