from __future__ import annotations

import unittest

from AI_SKILL_LIBRARY.v4.tools.run_learning_cycle import run_learning_cycle


class LearningCycleTests(unittest.TestCase):
    def _eval(self):
        return {
            "all_gates_pass": True,
            "frozen_replay": True,
            "protected_regressions": 0,
            "critical_conflicts": 0,
            "measured_gain": 0.1,
            "evidence_ref": "CHECKPOINTS/evidence/eval-1.json",
        }

    def test_missing_or_unfrozen_replay_blocks_cycle(self):
        with self.assertRaises(ValueError):
            run_learning_cycle(
                {"cycle_id": "c1", "replay_ref": ""},
                curriculum={"curricula": []}, competency={"rows": []},
                candidate={"candidate_id": "x", "promotion_class": "A", "permission_unchanged": True},
                eval_result=self._eval(),
            )
        bad = self._eval(); bad["frozen_replay"] = False
        with self.assertRaises(ValueError):
            run_learning_cycle(
                {"cycle_id": "c1", "replay_ref": "artifact://replay/c1"},
                curriculum={"curricula": []}, competency={"rows": []},
                candidate={"candidate_id": "x", "promotion_class": "A", "permission_unchanged": True},
                eval_result=bad,
            )

    def test_class_c_never_self_promotes(self):
        result = run_learning_cycle(
            {"cycle_id": "c2", "replay_ref": "artifact://replay/c2"},
            curriculum={"curricula": []}, competency={"rows": []},
            candidate={
                "candidate_id": "x", "promotion_class": "C",
                "permission_unchanged": True, "sandbox_pass": True,
                "evidence_refs": ["CHECKPOINTS/evidence/candidate-x.json"],
            },
            eval_result=self._eval(),
        )
        self.assertEqual(result["state"], "HUMAN_GATE")
        self.assertIs(result["stable_write"], False)
        self.assertIs(result["routing_authority"], False)
        self.assertIs(result["model_selection_authority"], False)
        self.assertIs(result["merge_authority"], False)

    def test_class_a_can_only_become_a_promotion_candidate(self):
        result = run_learning_cycle(
            {"cycle_id": "c3", "replay_ref": "artifact://replay/c3"},
            curriculum={"curricula": []}, competency={"rows": []},
            candidate={"candidate_id": "x", "promotion_class": "A", "permission_unchanged": True},
            eval_result=self._eval(),
        )
        self.assertEqual(result["state"], "PROMOTION_CANDIDATE")
        self.assertTrue(result["automatic"])
        self.assertIs(result["stable_write"], False)

    def test_protected_regression_rejects_without_touching_stable(self):
        ev = self._eval(); ev["protected_regressions"] = 1
        result = run_learning_cycle(
            {"cycle_id": "c4", "replay_ref": "artifact://replay/c4"},
            curriculum={"curricula": []}, competency={"rows": []},
            candidate={"candidate_id": "x", "promotion_class": "A", "permission_unchanged": True},
            eval_result=ev,
        )
        self.assertEqual(result["state"], "REJECTED")
        self.assertIn("protected_regression", result["reasons"])
        self.assertIs(result["stable_write"], False)


if __name__ == "__main__":
    unittest.main()
