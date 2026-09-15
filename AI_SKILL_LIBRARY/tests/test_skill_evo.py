import unittest

from AI_SKILL_LIBRARY.v4.tools.skill_evo import (
    compile_eval_rules,
    freeze_replay,
    generate_mutations,
    score_mutation,
    select_champion,
)


class SkillEvoTests(unittest.TestCase):
    def _champion(self):
        return {
            "candidate_id": "champion-1",
            "lineage_id": "lineage-1",
            "permission_ceiling": "read_only",
            "risk_class": "A",
            "content_digest": "abc",
            "status": "benchmarked",
        }

    def test_replay_is_deterministic_and_frozen(self):
        samples_a = [
            {"sample_id": "2", "input": "b", "expected": "B"},
            {"sample_id": "1", "input": "a", "expected": "A"},
        ]
        samples_b = list(reversed(samples_a))
        one = freeze_replay(samples_a, "lineage-1")
        two = freeze_replay(samples_b, "lineage-1")
        self.assertEqual(one, two)
        self.assertTrue(one["frozen"])
        self.assertEqual([row["sample_id"] for row in one["samples"]], ["1", "2"])
        self.assertEqual(len(one["replay_digest"]), 64)

    def test_compile_eval_rules_includes_protected_gates(self):
        replay = freeze_replay([{"sample_id": "1", "input": "a", "expected": "A"}], "lineage-1")
        rules = compile_eval_rules(self._champion(), replay)
        ids = {rule["rule_id"] for rule in rules}
        self.assertTrue({"replay_accuracy", "protected_regression", "permission_unchanged", "critical_conflicts"}.issubset(ids))
        self.assertTrue(all(rule["binary"] for rule in rules))

    def test_mutation_budget_is_bounded(self):
        mutations = generate_mutations(self._champion(), budget=100)
        self.assertGreater(len(mutations), 0)
        self.assertLessEqual(len(mutations), 6)
        self.assertEqual(len({m["mutation_id"] for m in mutations}), len(mutations))
        self.assertTrue(all(m["lineage_id"] == "lineage-1" for m in mutations))

    def test_score_mutation_uses_measured_results_not_judge_only(self):
        mutation = generate_mutations(self._champion(), budget=1)[0]
        weak = score_mutation(mutation, {"judge_preference": True})
        strong = score_mutation(mutation, {
            "eval_pass": True,
            "regression_pass": True,
            "permission_unchanged": True,
            "critical_conflicts": 0,
            "replay_accuracy": 0.95,
        })
        self.assertGreater(strong, weak)

    def test_llm_judge_alone_cannot_promote(self):
        current = self._champion()
        challenger = generate_mutations(current, budget=1)[0]
        result = select_champion(current, [challenger], {
            challenger["mutation_id"]: {
                "judge_preference": True,
                "score_delta": 1.0,
            }
        })
        self.assertEqual(result["candidate_id"], current["candidate_id"])

    def test_protected_regression_and_permission_are_required(self):
        current = self._champion()
        challenger = generate_mutations(current, budget=1)[0]
        base = {
            "eval_pass": True,
            "regression_pass": True,
            "permission_unchanged": True,
            "critical_conflicts": 0,
            "score_delta": 0.1,
            "canary_required": False,
        }
        for field, bad in (("eval_pass", False), ("regression_pass", False), ("permission_unchanged", False), ("critical_conflicts", 1)):
            outcome = dict(base)
            outcome[field] = bad
            result = select_champion(current, [challenger], {challenger["mutation_id"]: outcome})
            self.assertEqual(result["candidate_id"], current["candidate_id"], field)

    def test_valid_challenger_becomes_champion_candidate(self):
        current = self._champion()
        challenger = generate_mutations(current, budget=1)[0]
        result = select_champion(current, [challenger], {
            challenger["mutation_id"]: {
                "eval_pass": True,
                "regression_pass": True,
                "permission_unchanged": True,
                "critical_conflicts": 0,
                "score_delta": 0.2,
                "canary_required": True,
                "canary_pass": True,
            }
        })
        self.assertEqual(result["mutation_id"], challenger["mutation_id"])
        self.assertEqual(result["status"], "champion_candidate")
        self.assertFalse(result["stable_write_allowed"])


if __name__ == "__main__":
    unittest.main()
