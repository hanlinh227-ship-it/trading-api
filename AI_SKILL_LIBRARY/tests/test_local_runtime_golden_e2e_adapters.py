"""B3/B4 adapters: the parts that must be able to fail.

The golden gate itself is tested in test_personal_ai_golden_e2e.py. What is
tested here is the half that supplies it: a verifier that cannot fail, or an
`offline` flag that is really a constant, would turn B3 and B4 into ceremony.
Each test below is a way of getting a pass without earning it.
"""

import json
import os
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.local_runtime.golden_e2e import (
    CANONICAL_GOLDEN_REQUEST,
    GoldenE2EError,
    admitted_candidates,
    declared_identities,
    gate_identity,
    ingress,
    make_router,
    make_selector,
    make_verifier,
    observed_offline,
    synthesis,
    verifier,
)

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "CHECKPOINTS/evidence/B3_B4_GOLDEN_E2E_EVIDENCE.json"


def good_execution() -> dict:
    return {
        "output": " Paris.",
        "real_inference": True,
        "load_latency_ms": 2756.3,
        "inference_latency_ms": 766.8,
        "raw_run_ref": "fingerprint:req-1",
        "artifact_identity": {"sha256": "9" * 64},
    }


class VerifierTests(unittest.TestCase):
    def test_a_good_run_passes(self):
        self.assertTrue(verifier("core_reasoning", good_execution())["passed"])

    def test_an_empty_answer_fails(self):
        row = good_execution() | {"output": "   "}
        result = verifier("core_reasoning", row)
        self.assertFalse(result["passed"])
        self.assertIn("empty_output", result["failures"])

    def test_a_run_not_marked_real_fails(self):
        row = good_execution() | {"real_inference": False}
        self.assertIn("not_real_inference", verifier("k", row)["failures"])

    def test_impossible_latencies_fail(self):
        """Zero-latency inference means nothing ran."""
        for field in ("load_latency_ms", "inference_latency_ms"):
            row = good_execution() | {field: 0}
            self.assertIn(f"implausible_{field}", verifier("k", row)["failures"])

    def test_a_run_with_no_raw_reference_fails(self):
        row = good_execution() | {"raw_run_ref": ""}
        self.assertIn("no_raw_run_reference", verifier("k", row)["failures"])

    def test_an_identity_that_is_not_digest_bound_fails(self):
        row = good_execution() | {"artifact_identity": {"sha256": "short"}}
        self.assertIn("artifact_identity_not_digest_bound", verifier("k", row)["failures"])

    def test_canonical_golden_wrong_answer_fails_semantically(self):
        row = good_execution() | {"output": "shogi is a Japanese board game"}
        result = make_verifier("What is the capital city of Japan? Answer briefly.")(
            "core_reasoning", row
        )
        self.assertFalse(result["passed"])
        self.assertIn("semantic_answer_mismatch", result["failures"])

    def test_canonical_golden_correct_answer_passes_semantically(self):
        row = good_execution() | {"output": "Tokyo."}
        result = make_verifier("What is the capital city of Japan? Answer briefly.")(
            "core_reasoning", row
        )
        self.assertTrue(result["passed"], result["failures"])

    def test_arbitrary_request_cannot_earn_golden_semantic_pass(self):
        result = make_verifier("Tell me something interesting.")(
            "core_reasoning", good_execution()
        )
        self.assertFalse(result["passed"])
        self.assertIn("semantic_oracle_unavailable", result["failures"])


class OfflineObservationTests(unittest.TestCase):
    """`offline` must be read from the environment, not asserted."""

    #: All of them, not a sample. The check is "no proxy variable at all", and a
    #: test that cleared two of six would pass while the other four still
    #: pointed at a route out.
    VARS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")

    def setUp(self):
        self.saved = {k: os.environ.get(k) for k in self.VARS}

    def tearDown(self):
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_a_present_proxy_makes_the_run_not_offline(self):
        os.environ["HTTPS_PROXY"] = "http://proxy.invalid:8080"
        self.assertFalse(observed_offline("llama.cpp"))

    def test_a_hosted_runtime_is_never_offline(self):
        for key in self.saved:
            os.environ.pop(key, None)
        self.assertFalse(observed_offline("hosted_api"))
        self.assertFalse(observed_offline("cloud_api"))

    def test_a_local_runtime_with_no_proxy_is_offline(self):
        for key in self.saved:
            os.environ.pop(key, None)
        self.assertTrue(observed_offline("llama.cpp"))


class SelectorTests(unittest.TestCase):
    def test_ingress_never_names_a_model(self):
        route = {"domain": "core", "primary_skill": "core_reasoning"}
        prepared = ingress({"request": "hello"}, route)
        self.assertFalse(prepared["model_named_at_ingress"])
        self.assertNotIn("model_id", json.dumps(prepared))

    def test_the_router_reports_the_canonical_router(self):
        routed = make_router(ROOT)({"request": "The capital of France is"})
        self.assertEqual(routed["routed_by"], "task_router")
        self.assertEqual(routed["domain"], "core")

    def test_selecting_nothing_refuses_rather_than_inventing_a_model(self):
        with self.assertRaises(GoldenE2EError):
            make_selector({})({"domain": "core", "primary_skill": "core_reasoning"}, [])

    def test_a_selected_model_with_no_declared_identity_is_refused(self):
        """An identity index miss must not fall back to the candidate's own claim."""
        pairs = admitted_candidates(ROOT)
        if not pairs:
            self.skipTest("no admitted local candidate")
        candidates = [c for c, _ in pairs]
        with self.assertRaises(GoldenE2EError):
            make_selector({})({"domain": "core", "primary_skill": "core_reasoning"}, candidates)

    def test_the_declared_identity_comes_from_the_canonical_record(self):
        pairs = admitted_candidates(ROOT)
        if not pairs:
            self.skipTest("no admitted local candidate")
        index = declared_identities(pairs)
        self.assertTrue(index)
        for key, identity in index.items():
            self.assertEqual(len(str(identity["sha256"])), 64, key)


class SynthesisTests(unittest.TestCase):
    def test_the_answer_is_the_models_own_output(self):
        execution = good_execution()
        response = synthesis({"request_id": "r"}, execution,
                             {"passed": True, "evidence_refs": ["e"]})
        self.assertEqual(response["answer"], execution["output"])
        self.assertTrue(response["verified"])

    def test_an_unverified_run_is_reported_as_unverified(self):
        response = synthesis({"request_id": "r"}, good_execution(),
                             {"passed": False, "evidence_refs": []})
        self.assertFalse(response["verified"])


class CommittedEvidenceTests(unittest.TestCase):
    """What was committed must be what the gate would accept today."""

    def setUp(self):
        if not EVIDENCE.is_file():
            self.skipTest("no B3/B4 evidence committed")
        self.evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))

    def test_b3_and_b4_are_recorded_as_passing_with_no_failures(self):
        self.assertTrue(self.evidence["B3_pass"])
        self.assertTrue(self.evidence["B4_pass"])
        self.assertEqual(self.evidence["failures"], [])

    def test_the_run_was_offline_with_a_complete_lifecycle(self):
        runtime = self.evidence["runtime_evidence"]
        self.assertTrue(runtime["offline"])
        self.assertEqual(runtime["lifecycle"], {"wake": True, "warm": True, "sleep": True})

    def test_nothing_in_the_run_was_synthetic_or_a_fixture(self):
        runtime = self.evidence["runtime_evidence"]
        self.assertTrue(runtime["real_inference"])
        self.assertFalse(runtime["synthetic"])
        self.assertFalse(runtime["fixture_only"])

    def test_the_verified_bytes_match_what_governance_selected(self):
        """The two identities reach the gate by independent paths."""
        selected = self.evidence["selection"]["primary_model"]["artifact_identity"]
        executed = self.evidence["runtime_evidence"]["artifact_identity"]
        self.assertEqual(selected, executed)

    #: The closed set of ways semantic verification can refuse. Named here so a
    #: test can require "it refused" without pinning which refusal - the two
    #: are different facts about the evidence, not about the verifier, and
    #: which one fires depends on what the committed evidence happens to hold.
    SEMANTIC_REFUSALS = ("semantic_oracle_unavailable", "semantic_answer_mismatch")

    def test_the_committed_evidence_is_rechecked_semantically(self):
        """Never passes. Which refusal fires is the evidence's business.

        This asserted `semantic_answer_mismatch` and was red on the branch it
        arrived from, deterministically and on every host: the committed
        evidence asks "What is the capital of France?", the canonical golden
        request asks about Japan, so the verifier refuses at the earlier gate -
        it will not grade an answer to a question it was not asked. That is the
        stricter behaviour of the two, and pinning the later reason asserted
        the evidence was closer to valid than it is.
        """
        result = make_verifier(self.evidence["request"])(
            "core_reasoning", self.evidence["runtime_evidence"]
        )
        self.assertFalse(result["passed"])
        self.assertTrue(
            set(result["failures"]) & set(self.SEMANTIC_REFUSALS),
            "committed golden evidence must be refused semantically, got %r"
            % (result["failures"],),
        )
        self.assertIsNone(result["semantic_oracle"])

    def test_a_wrong_answer_to_the_canonical_question_is_a_mismatch(self):
        """The check the test above was reaching for, exercised directly.

        With the request the oracle actually knows, a wrong answer has to be
        caught on its content rather than on its question, so `semantic_answer_
        mismatch` gets a deterministic test of its own instead of riding on
        stale evidence that trips a different gate.
        """
        execution = dict(self.evidence["runtime_evidence"])
        execution["output"] = "The capital of France is Paris."
        result = make_verifier(CANONICAL_GOLDEN_REQUEST)("core_reasoning", execution)
        self.assertFalse(result["passed"])
        self.assertIn("semantic_answer_mismatch", result["failures"])
        self.assertIsNotNone(result["semantic_oracle"])

    def test_the_right_answer_to_the_canonical_question_is_not_a_mismatch(self):
        """...and the mismatch check is not simply always on."""
        execution = dict(self.evidence["runtime_evidence"])
        execution["output"] = "Tokyo."
        result = make_verifier(CANONICAL_GOLDEN_REQUEST)("core_reasoning", execution)
        self.assertNotIn("semantic_answer_mismatch", result["failures"])

    def test_resource_use_was_measured_not_left_unknown(self):
        self.assertIsInstance(self.evidence["runtime_evidence"]["peak_ram_mb"], (int, float))


if __name__ == "__main__":
    unittest.main()
