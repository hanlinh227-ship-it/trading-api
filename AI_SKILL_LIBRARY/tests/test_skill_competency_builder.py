from __future__ import annotations

import unittest

from AI_SKILL_LIBRARY.v4.tools.build_skill_competency import build_competency_matrix


class SkillCompetencyTests(unittest.TestCase):
    CURRICULUM = {
        "curricula": [{
            "skill_id": "reasoning",
            "roles": ["REASONING_BRANCH"],
            "capabilities": ["text_reasoning"],
            "authority": {"model_selection_authority": False},
        }]
    }
    ROLES = {
        "branches": [{
            "role_id": "REASONING_BRANCH",
            "required_capabilities": ["text_reasoning"],
        }]
    }

    def test_unmeasured_input_emits_no_fabricated_competency(self):
        out = build_competency_matrix(self.CURRICULUM, {"records": []}, {"experiences": []}, self.ROLES)
        self.assertEqual(out["rows"], [])
        self.assertIs(out["authority"], False)

    def test_measured_capability_reaches_measured_not_primary(self):
        evidence = {"records": [{
            "evidence_id": "e-1",
            "model_id": "m1",
            "capability": "text_reasoning",
            "score": 0.9,
            "passed": True,
            "measured_at": "2026-09-18T00:00:00Z",
            "provenance": {"reference": "CHECKPOINTS/evidence/e-1.json"},
        }]}
        out = build_competency_matrix(self.CURRICULUM, evidence, {"experiences": []}, self.ROLES)
        self.assertEqual(len(out["rows"]), 1)
        row = out["rows"][0]
        self.assertEqual(row["state"], "MEASURED")
        self.assertEqual(row["measured_score"], 0.9)
        self.assertEqual(row["evidence_refs"], ["CHECKPOINTS/evidence/e-1.json"])
        self.assertEqual(row["protected_regression_status"], "NOT_RUN")
        self.assertNotIn(row["state"], {"PRIMARY", "FALLBACK", "PROFICIENT"})

    def test_experience_can_add_verifier_rate_but_not_self_promote(self):
        evidence = {"records": [{
            "model_id": "m1", "capability": "text_reasoning", "score": 1.0,
            "measured_at": "2026-09-18T00:00:00Z",
            "provenance": {"reference": "CHECKPOINTS/evidence/e-1.json"},
        }]}
        ledger = {"experiences": [{
            "model_id": "m1",
            "role_id": "REASONING_BRANCH",
            "skill_ids": ["reasoning"],
            "verifier_passed": True,
            "timestamp": "2026-09-18T00:01:00Z",
            "evidence_ref": "CHECKPOINTS/evidence/exp-1.json",
        }]}
        row = build_competency_matrix(self.CURRICULUM, evidence, ledger, self.ROLES)["rows"][0]
        self.assertEqual(row["verifier_pass_rate"], 1.0)
        self.assertEqual(row["state"], "MEASURED")
        self.assertEqual(row["promotion_state"], "NONE")


if __name__ == "__main__":
    unittest.main()
