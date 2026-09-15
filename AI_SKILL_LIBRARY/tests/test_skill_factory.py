import unittest

from AI_SKILL_LIBRARY.v4.tools.skill_factory import (
    create_skill_candidate,
    merge_skill_candidate,
    triage_experience,
    validate_skill_lineage,
)


class SkillFactoryTests(unittest.TestCase):
    def test_triage_actions_are_bounded(self):
        existing = [{"skill_id": "coding-review", "domain": "engineering", "signature": "review-code"}]
        self.assertEqual(triage_experience({"reusable": False}, existing), "discard")
        self.assertEqual(triage_experience({"reusable": True, "skill_id": "coding-review", "is_correction": True}, existing), "improve")
        self.assertEqual(triage_experience({"reusable": True, "domain": "engineering", "signature": "review-code", "skill_id": "other"}, existing), "merge")
        self.assertEqual(triage_experience({"reusable": True, "domain": "design_3d", "signature": "new-pattern"}, existing), "create")

    def test_candidate_is_incubating_and_preserves_peer_layers(self):
        candidate = create_skill_candidate([
            {"claim_id": "a1", "learning_layer": "experience", "content": "observed fix"},
            {"claim_id": "b1", "learning_layer": "curated", "content": "official pattern"},
            {"claim_id": "c1", "learning_layer": "exploration", "content": "new hypothesis"},
        ], "engineering")
        self.assertEqual(candidate["status"], "incubating")
        self.assertEqual(candidate["domain"], "engineering")
        self.assertEqual(candidate["learning_layers"], ["curated", "experience", "exploration"])
        self.assertEqual(candidate["source_claims"], ["a1", "b1", "c1"])
        self.assertFalse(candidate["stable_write_allowed"])
        self.assertEqual(candidate["permission_ceiling"], "read_only")
        self.assertEqual(candidate["risk_class"], "A")
        self.assertEqual(validate_skill_lineage(candidate), [])

    def test_candidate_creation_is_deterministic_for_same_inputs(self):
        items = [{"claim_id": "a1", "learning_layer": "experience", "content": "same"}]
        one = create_skill_candidate(items, "engineering")
        two = create_skill_candidate(items, "engineering")
        self.assertEqual(one["candidate_id"], two["candidate_id"])
        self.assertEqual(one["lineage_id"], two["lineage_id"])

    def test_merge_never_widens_permission_or_lowers_risk(self):
        base = create_skill_candidate([
            {"claim_id": "a1", "learning_layer": "experience", "content": "base"}
        ], "engineering")
        base["permission_ceiling"] = "read_only"
        base["risk_class"] = "B"
        challenger = create_skill_candidate([
            {"claim_id": "c1", "learning_layer": "exploration", "content": "change"}
        ], "engineering")
        challenger["permission_ceiling"] = "sandbox_execute"
        challenger["risk_class"] = "A"
        merged = merge_skill_candidate(base, challenger)
        self.assertEqual(merged["permission_ceiling"], "read_only")
        self.assertEqual(merged["risk_class"], "B")
        self.assertEqual(set(merged["source_claims"]), {"a1", "c1"})
        self.assertFalse(merged["stable_write_allowed"])

    def test_lineage_rejects_promoted_or_missing_provenance_candidate(self):
        candidate = create_skill_candidate([
            {"claim_id": "a1", "learning_layer": "experience", "content": "base"}
        ], "engineering")
        candidate["status"] = "promoted"
        candidate["source_claims"] = []
        errors = validate_skill_lineage(candidate)
        self.assertTrue(any("status" in error for error in errors))
        self.assertTrue(any("source_claims" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
