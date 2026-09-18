from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.tools.compile_skill_curriculum import compile_curriculum
from AI_SKILL_LIBRARY.v4.tools.skill_forge import triage_gap
from AI_SKILL_LIBRARY.v4.tools.validate_learning_fabric import validate


ROOT = Path(__file__).resolve().parents[2]


class LearningFabricOperationalTests(unittest.TestCase):
    def test_full_repository_learning_contract_validates(self):
        self.assertEqual(validate(ROOT), [])

    def test_compiler_discovers_all_109_canonical_skills(self):
        doc = compile_curriculum(ROOT)
        self.assertEqual(len(doc["curricula"]), 109)
        self.assertEqual(len({row["skill_id"] for row in doc["curricula"]}), 109)

    def test_trading_curricula_are_never_lower_than_class_d(self):
        rows = [x for x in compile_curriculum(ROOT)["curricula"] if x["domain"] == "trading"]
        self.assertTrue(rows)
        self.assertTrue(all(row["risk_class"] == "D" for row in rows))
        self.assertTrue(all(row["promotion_class"] == "D" for row in rows))

    def test_competency_gap_without_evidence_is_discarded(self):
        out = triage_gap(
            {
                "gap_id": "cg-1",
                "domain": "engineering",
                "recommended_capability": "coding",
                "source_kind": "competency_gap",
                "evidence_refs": [],
            },
            [{"id": "coding", "domain": "engineering", "capabilities": ["coding"]}],
        )
        self.assertEqual(out["action"], "discard")
        self.assertEqual(out["reason"], "competency_gap_missing_evidence")

    def test_competency_gap_with_evidence_can_only_become_candidate_input(self):
        out = triage_gap(
            {
                "gap_id": "cg-2",
                "domain": "engineering",
                "recommended_capability": "coding",
                "source_kind": "competency_gap",
                "evidence_refs": ["CHECKPOINTS/evidence/example.json"],
            },
            [{"id": "coding", "domain": "engineering", "capabilities": ["coding"]}],
        )
        self.assertEqual(out["action"], "improve")
        self.assertIs(out["stable_write"], False)
        self.assertIs(out["routing_authority"], False)

    def test_development_lab_isolated_from_stable(self):
        stable = yaml.safe_load(
            (ROOT / "AI_SKILL_LIBRARY/v4/stable/continuous_intelligence.yaml").read_text(encoding="utf-8")
        )
        learning = stable["continuous_skill_learning"]
        self.assertEqual(learning["plane"], "development_lab_only")
        self.assertIs(learning["stable_request_dependency"], False)
        self.assertIs(learning["lanes"]["development_lab"]["may_mutate_stable"], False)
        self.assertIs(learning["lanes"]["development_lab"]["may_self_merge"], False)
        self.assertIs(learning["lanes"]["stable_runtime"]["accepts_unpromoted_candidates"], False)


if __name__ == "__main__":
    unittest.main()
