"""Wave 3 selection: the ways a model could get acquired without earning it.

The gap map, the resource preflight, the candidate-state resolver and the
coverage proof together decide what Wave 3 acquires and what it may claim
afterwards. These are the specific routes by which that could go wrong: a
capability reported as covered because nothing measures it, a saturated suite
read as a ranking, a documentation score entering the map, a candidate acquired
on an estimate, or a non-AVAILABLE candidate counted as coverage.
"""

import copy
import json
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.tools import (
    capability_gap_map,
    wave3_candidate_states,
    wave3_coverage_proof,
    wave3_resource_preflight,
)

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "CHECKPOINTS/evidence"


class GapMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.map = capability_gap_map.build(ROOT)

    def test_the_whole_admitted_fleet_is_measured(self):
        """A gap map over two models is a gap map about two models."""
        self.assertGreaterEqual(self.map["fleet_size"], 7)

    def test_a_capability_nothing_measures_is_not_covered(self):
        """The failure this file exists to prevent: inferring coverage from a
        neighbouring score because the models are generally decent."""
        for name in ("long_context", "tool_calling", "multilingual_reasoning"):
            with self.subTest(capability=name):
                row = self.map["capabilities"][name]
                self.assertEqual(row["state"], "NOT_MEASURED")
                self.assertIs(row["capability_gap"], True)
                self.assertTrue(row["reason"])

    def test_a_saturated_capability_is_not_presented_as_a_ranking(self):
        for name in self.map["saturated_capabilities"]:
            with self.subTest(capability=name):
                row = self.map["capabilities"][name]
                self.assertEqual(row["state"], "COVERED_BUT_SATURATED")
                self.assertTrue(row["saturation_note"])
                self.assertTrue(row["tied_with"])

    def test_ties_break_on_a_measurement_not_on_a_name(self):
        """Breaking on model_id alone named a 9-of-12 model the fleet's best at
        deep reasoning, because it sorts first."""
        row = self.map["capabilities"]["deep_reasoning"]
        best = next(m for m in self.map["fleet"]
                    if m["model_id"] == row["current_best_model"])
        for other_id in row["tied_with"]:
            other = next(m for m in self.map["fleet"] if m["model_id"] == other_id)
            with self.subTest(other=other_id):
                self.assertGreaterEqual(best["wave0"]["passed"], other["wave0"]["passed"])

    def test_every_capability_score_is_bound_to_an_artifact_digest(self):
        for name, row in self.map["capabilities"].items():
            if row["state"] == "NOT_MEASURED":
                continue
            with self.subTest(capability=name):
                self.assertEqual(len(str(row["artifact_digest"])), 64)

    def test_no_documentation_url_reaches_the_map(self):
        self.assertIs(self.map["no_documentation_scores"], True)
        self.assertNotIn("http", json.dumps(self.map["capabilities"]))

    def test_it_claims_no_routing_or_admission_authority(self):
        self.assertIs(self.map["routing_authority"], False)
        self.assertIs(self.map["admission_authority"], False)

    def test_a_deeper_measurement_only_replaces_a_shallower_one_for_the_same_bytes(self):
        """A deeper score measured on different weights is not a deeper score
        of these weights."""
        rows = [{"category": "CODING", "verifier_passed": True},
                {"category": "CODING", "verifier_passed": True}]
        engineering = {
            "suite": "local_engineering_judgment@1.0.0",
            "artifact_sha256": "b" * 64,
            "per_skill": {"coding": {"score": 0.1, "passed": 1, "attempted": 6}},
        }
        merged = capability_gap_map._merge_capabilities(rows, engineering, "a" * 64)
        self.assertEqual(merged["coding"]["measured_by"], "wave0")
        self.assertEqual(merged["coding"]["score"], 1.0)

        same = capability_gap_map._merge_capabilities(rows, engineering, "b" * 64)
        self.assertEqual(same["coding"]["score"], 0.1)
        self.assertEqual(same["coding"]["attempted"], 6)


class ResourcePreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pre = wave3_resource_preflight.build(ROOT)
        cls.rows = {row["candidate_id"]: row for row in cls.pre["candidates"]}

    def test_it_classifies_every_manifest_candidate(self):
        self.assertEqual(self.pre["manifest_candidates_not_classified"], [])
        self.assertEqual(self.pre["candidates_not_in_manifest"], [])

    def test_it_acquires_nothing_and_accepts_no_licence(self):
        self.assertIs(self.pre["acquires_nothing"], True)
        self.assertIs(self.pre["admits_nothing"], True)
        self.assertIs(self.pre["accepts_no_licence"], True)

    def test_the_licence_gated_candidate_is_never_feasible(self):
        """No resource profile makes a candidate acquirable when a person has
        to accept terms first."""
        row = self.rows["gemma-3-4b-it"]
        self.assertEqual(row["state"], "HUMAN_LICENSE_GATE_REQUIRED")
        self.assertEqual(row["deferred_to_wave"], 4)

    def test_every_row_says_its_sizes_are_estimates(self):
        """An estimate is enough to refuse something; it is never enough to
        admit anything."""
        for name, row in self.rows.items():
            with self.subTest(candidate=name):
                self.assertIs(row["sizes_are_estimates"], True)
                self.assertTrue(row["estimate_basis"])
                self.assertIn("digest", row["admission_binds_to"])

    def test_runtime_ram_is_more_than_the_artifact(self):
        """llama.cpp maps the weights and then needs a KV cache and a compute
        buffer, so a 5 GB artifact does not run in 5 GB."""
        for name, row in self.rows.items():
            with self.subTest(candidate=name):
                self.assertGreater(row["estimated_runtime_ram_mb"],
                                   row["estimated_artifact_mb"])

    def test_a_model_larger_than_the_disk_is_refused(self):
        host = self.pre["host"]
        oversized = {
            "upstream": "test/oversized", "upstream_format": "gguf",
            "target_quantization": "Q4_K_M",
            "artifact_mb": host["disk_free_mb"] + 5000,
            "artifact_mb_basis": "test", "roles": ["coding"],
        }
        row = wave3_resource_preflight.classify("oversized", oversized, host, {})
        self.assertEqual(row["state"], "RESOURCE_INFEASIBLE")

    def test_redundancy_needs_coverage_that_is_neither_thin_nor_saturated(self):
        """A capability five models tie at 1.000 on is not evidence a sixth
        adds nothing; it is evidence the suite cannot tell."""
        host = self.pre["host"]
        spec = {
            "upstream": "test/small", "upstream_format": "gguf",
            "target_quantization": "Q4_K_M", "artifact_mb": 100,
            "artifact_mb_basis": "test", "roles": ["coding"],
        }
        saturated = {"coding": {"state": "COVERED_MEASURED", "saturated": True,
                                "thin_evidence": True, "current_best_model": "x",
                                "measured_score": 1.0, "measurement_depth": "2 task(s)"}}
        self.assertEqual(
            wave3_resource_preflight.classify("small", spec, host, saturated)["state"],
            "RESOURCE_FEASIBLE")

        solid = {"coding": {"state": "COVERED_MEASURED", "saturated": False,
                            "thin_evidence": False, "current_best_model": "x",
                            "measured_score": 0.9, "measurement_depth": "20 task(s)"}}
        self.assertEqual(
            wave3_resource_preflight.classify("small", spec, host, solid)["state"],
            "ROLE_REDUNDANT")


class CandidateStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.states = wave3_candidate_states.build(ROOT)
        cls.rows = {row["candidate_id"]: row for row in cls.states["candidates"]}

    def test_gemma_is_gated_and_deferred_and_never_acquired(self):
        row = self.rows["gemma-3-4b-it"]
        self.assertEqual(row["state"], "HUMAN_LICENSE_GATE_REQUIRED")
        self.assertIsNone(row["upstream_artifact"])
        self.assertIs(self.states["accepts_no_licence"], True)

    def test_a_candidate_blocked_two_ways_records_both(self):
        """Qwen3-Coder has no author GGUF and does not fit the disk; reporting
        whichever check ran last would lose one of them."""
        row = self.rows["qwen3-coder-30b-a3b-instruct"]
        self.assertEqual(row["state"], "RESOURCE_INFEASIBLE")
        self.assertGreaterEqual(len(row["findings"]), 2)
        self.assertTrue(any("disk" in f for f in row["findings"]))
        self.assertTrue(any("author" in f for f in row["findings"]))

    def test_a_candidate_with_no_author_artifact_gets_an_actionable_gap(self):
        for name in ("phi-4-mini-instruct", "deepseek-r1-distill-qwen-7b"):
            with self.subTest(candidate=name):
                row = self.rows[name]
                self.assertEqual(row["state"], "QUARANTINED_WITH_ACTIONABLE_GAP")
                self.assertTrue(row["actionable_gap"])

    def test_the_actionable_gap_does_not_leak_between_candidates(self):
        """It was read out of locals() and survived into the next iteration."""
        for name, row in self.rows.items():
            if row["state"] != "QUARANTINED_WITH_ACTIONABLE_GAP":
                with self.subTest(candidate=name):
                    self.assertIsNone(row["actionable_gap"])

    def test_it_admits_nothing(self):
        self.assertIs(self.states["admits_nothing"], True)


class CoverageProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof = wave3_coverage_proof.build(ROOT)

    def test_an_unavailable_candidate_contributes_no_coverage(self):
        """A model the runtime cannot load is not coverage, however good its
        role hypothesis was."""
        blocked = {row["candidate_id"] for row in self.proof["candidates_contributing_nothing"]}
        self.assertIn("qwen3-coder-30b-a3b-instruct", blocked)
        self.assertIn("gemma-3-4b-it", blocked)
        best = {row.get("current_best_model")
                for row in self.proof["core_targets"] + self.proof["reported_targets"]}
        self.assertFalse(best & {"Qwen/Qwen3-Coder-30B-A3B-Instruct", "google/gemma-3-4b-it"})

    def test_no_documentation_claim_is_used(self):
        self.assertIs(self.proof["sources"]["documentation_claims_used"], False)

    def test_a_deferral_carries_its_reason(self):
        for row in self.proof["deferred_targets"]:
            with self.subTest(target=row["target"]):
                self.assertEqual(row["state"], "INTENTIONALLY_DEFERRED")
                self.assertTrue(row["reason"])

    def test_every_covered_target_names_the_digest_it_was_measured_on(self):
        for row in self.proof["core_targets"] + self.proof["reported_targets"]:
            if row["state"] != "COVERED_MEASURED":
                continue
            with self.subTest(target=row["target"]):
                self.assertEqual(len(str(row["artifact_digest"])), 64)
                self.assertIsNotNone(row["measured_score"])

    def test_it_says_an_observer_gap_count_is_not_coverage(self):
        self.assertIs(self.proof["observer_gap_count_is_not_coverage"], True)

    def test_a_target_below_the_floor_is_not_covered(self):
        self.assertIsNotNone(self.proof["coverage_floor"])
        for row in self.proof["core_targets"]:
            if row["state"] == "COVERED_MEASURED":
                with self.subTest(target=row["target"]):
                    self.assertGreaterEqual(row["measured_score"],
                                            self.proof["coverage_floor"])


if __name__ == "__main__":
    unittest.main()
