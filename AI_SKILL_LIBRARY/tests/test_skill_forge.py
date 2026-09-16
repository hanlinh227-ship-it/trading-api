from __future__ import annotations

import unittest

from AI_SKILL_LIBRARY.v4.tools.skill_forge import promotion_decision, triage_gap


class SkillForgeTests(unittest.TestCase):
    def test_strengthen_existing_skill_first(self) -> None:
        out = triage_gap(
            {"gap_id": "g1", "domain": "engineering", "recommended_capability": "debugging", "risk_class": "A"},
            [{"id": "debugging", "domain": "engineering", "capabilities": ["debugging"]}],
        )
        self.assertEqual(out["action"], "improve")
        self.assertEqual(out["target_skill_id"], "debugging")

    def test_distinct_candidate_created_only_when_material(self) -> None:
        out = triage_gap(
            {"gap_id": "g2", "domain": "engineering", "recommended_capability": "novel_contract_eval", "risk_class": "A", "distinct_contract": True},
            [{"id": "debugging", "domain": "engineering", "capabilities": ["debugging"]}],
        )
        self.assertEqual(out["action"], "create")
        self.assertEqual(out["promotion_class"], "A")

    def test_non_distinct_gap_is_held_not_skill_growth(self) -> None:
        out = triage_gap(
            {"gap_id": "g3", "domain": "engineering", "recommended_capability": "maybe_duplicate", "risk_class": "A", "distinct_contract": False},
            [],
        )
        self.assertEqual(out["action"], "discard")

    def test_class_a_and_b_can_auto_promote_only_with_all_gates(self) -> None:
        candidate = {"promotion_class": "A", "permission_unchanged": True}
        eval_result = {"all_gates_pass": True, "frozen_replay": True, "protected_regressions": 0, "critical_conflicts": 0, "measured_gain": 0.02}
        out = promotion_decision(candidate, eval_result)
        self.assertTrue(out["eligible"])
        self.assertTrue(out["automatic"])

        candidate = {"promotion_class": "B", "permission_unchanged": True, "sandbox_pass": True}
        out = promotion_decision(candidate, eval_result)
        self.assertTrue(out["automatic"])

    def test_class_c_and_d_never_auto_promote(self) -> None:
        eval_result = {"all_gates_pass": True, "frozen_replay": True, "protected_regressions": 0, "critical_conflicts": 0, "measured_gain": 1.0}
        for klass in ("C", "D"):
            out = promotion_decision({"promotion_class": klass, "permission_unchanged": True, "sandbox_pass": True}, eval_result)
            self.assertTrue(out["eligible"])
            self.assertFalse(out["automatic"])
            self.assertTrue(out["explicit_authorization_required"])

    def test_replay_regression_conflict_or_permission_change_blocks(self) -> None:
        base = {"promotion_class": "A", "permission_unchanged": True}
        good = {"all_gates_pass": True, "frozen_replay": True, "protected_regressions": 0, "critical_conflicts": 0, "measured_gain": 0.02}
        cases = [
            dict(good, frozen_replay=False),
            dict(good, protected_regressions=1),
            dict(good, critical_conflicts=1),
            dict(good, all_gates_pass=False),
        ]
        for case in cases:
            self.assertFalse(promotion_decision(base, case)["eligible"])
        self.assertFalse(promotion_decision({"promotion_class": "A", "permission_unchanged": False}, good)["eligible"])


if __name__ == "__main__":
    unittest.main()
