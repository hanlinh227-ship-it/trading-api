"""Multi-model federation: an executor, not a second orchestrator.

Every cap and every selection rule this exercises belongs to a component that
already existed. The tests are mostly about what the executor must *not* do -
re-decide a cap, resolve a disagreement by counting, or claim agreement it did
not measure.
"""

import json
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.control_plane.federation import plan_execution
from AI_SKILL_LIBRARY.v4.local_runtime.multi_model import DECODING, _worker_task

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "CHECKPOINTS/evidence/FEDERATION_V1_EVIDENCE.json"


def selection(supporting=2):
    return {
        "primary_model": {"candidate_key": "local:a", "model_id": "a"},
        "supporting_models": [{"candidate_key": f"local:s{i}", "model_id": f"s{i}"}
                              for i in range(supporting)],
        "verifier": "core_reasoning",
    }


class PlanAuthorityTests(unittest.TestCase):
    """The caps come from plan_execution. The executor must not restate them."""

    def test_fast_plans_one_model_and_no_verifier(self):
        plan = plan_execution("FAST", selection(), ["CORE_REASONING"])
        self.assertEqual(len(plan["models"]), 1)
        self.assertIsNone(plan["verifier"])

    def test_standard_plans_at_most_two(self):
        plan = plan_execution("STANDARD", selection(supporting=5), ["CORE_REASONING"])
        self.assertEqual(plan["max_concurrent_models"], 2)
        self.assertEqual(len(plan["models"]), 2)

    def test_deep_plans_at_most_four(self):
        plan = plan_execution("DEEP", selection(supporting=9), ["CORE_REASONING"])
        self.assertEqual(plan["max_concurrent_models"], 4)
        self.assertEqual(len(plan["models"]), 4)

    def test_the_plan_never_claims_routing_authority(self):
        plan = plan_execution("STANDARD", selection(), ["CORE_REASONING"])
        self.assertFalse(plan["routing_authority"])
        self.assertEqual(plan["routed_by"], "task_router")
        self.assertEqual(plan["model_selection_authority"], "model_mesh")


class WorkerTaskTests(unittest.TestCase):
    def test_permission_is_granted_per_candidate_never_by_default(self):
        """A candidate with no entry is not permitted, which is the right way round."""
        candidates = [{"provider_id": "local_runtime", "model_id": "m"}]
        task = _worker_task("core", "core_reasoning", "STANDARD", candidates)
        self.assertEqual(set(task["permission_allowed"]), {"local_runtime:m"})
        self.assertNotIn("local_runtime:other", task["permission_allowed"])

    def test_reputation_is_the_neutral_default(self):
        """Inventing an operating history would rig the ranking it feeds."""
        candidates = [{"provider_id": "local_runtime", "model_id": "m"}]
        task = _worker_task("core", "core_reasoning", "STANDARD", candidates)
        self.assertEqual(set(task["reputation"].values()), {0.5})


class IsolationTests(unittest.TestCase):
    def test_state_is_reset_between_workers(self):
        """A checker that inherits the maker's context is not independent."""
        self.assertTrue(DECODING["reset_state"])

    def test_decoding_is_deterministic(self):
        self.assertEqual(DECODING["temperature"], 0.0)
        self.assertEqual(DECODING["top_k"], 1)


class FederationEvidenceTests(unittest.TestCase):
    def setUp(self):
        if not EVIDENCE.is_file():
            self.skipTest("no federation evidence committed")
        self.evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))

    def test_nothing_was_resolved_by_vote(self):
        """Two models agreeing is not evidence that either is right."""
        self.assertFalse(self.evidence["resolved_by_vote"])

    def test_substantive_agreement_is_left_unresolved(self):
        """String equality is not agreement, and must not be reported as it.

        Both workers answered Tokyo while differing as text. Calling that
        disagreement would manufacture a conflict signal, and a confidence
        escalation triggered by it would burn a DEEP round on nothing.
        """
        self.assertEqual(self.evidence["substantive_agreement"], "unresolved_here")
        self.assertIn("outputs_identical", self.evidence)

    def test_the_answer_is_the_makers_answer(self):
        maker = next(w for w in self.evidence["workers"] if w["role"] == "maker")
        self.assertEqual(self.evidence["answer"], maker["output"])

    def test_the_round_stayed_within_its_planned_cap(self):
        self.assertLessEqual(len(self.evidence["workers"]),
                             self.evidence["max_concurrent_models"])

    def test_a_checker_round_used_two_different_model_families(self):
        """Same-family replicas are availability redundancy, not independence."""
        if self.evidence["collaboration_mode"] != "MAKER_CHECKER":
            self.skipTest("not a checker round")
        families = {w["model_id"].split("/")[0] for w in self.evidence["workers"]}
        self.assertGreater(len(families), 1, self.evidence["workers"])

    def test_authority_is_attributed_to_the_components_that_hold_it(self):
        self.assertEqual(self.evidence["routing_authority"], "task_router")
        self.assertEqual(self.evidence["model_selection_authority"], "model_mesh")
        self.assertEqual(self.evidence["execution_plan_authority"],
                         "control_plane.plan_execution")


if __name__ == "__main__":
    unittest.main()
