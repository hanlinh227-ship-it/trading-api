from pathlib import Path
import unittest

from AI_SKILL_LIBRARY.v4.tools.evaluate_model_mesh import detect_conflicts


class AdaptiveFreeModelMeshConflictTests(unittest.TestCase):
    def test_duplicate_family_hosts_do_not_count_as_independent_truth(self):
        outputs = [
            {"worker_id": "a", "model_family": "same-family", "claims": [{"claim_id": "c1", "value": "yes"}]},
            {"worker_id": "b", "model_family": "same-family", "claims": [{"claim_id": "c1", "value": "yes"}]},
        ]
        failures = detect_conflicts(outputs)
        self.assertIn("duplicate_model_family_truth_vote", failures)

    def test_same_resource_mutation_conflict_is_blocked(self):
        outputs = [
            {"worker_id": "a", "model_family": "f1", "writes": [{"resource_id": "file:x", "operation": "replace"}]},
            {"worker_id": "b", "model_family": "f2", "writes": [{"resource_id": "file:x", "operation": "replace"}]},
        ]
        failures = detect_conflicts(outputs)
        self.assertIn("same_resource_mutation_conflict", failures)

    def test_contradictory_worker_outputs_require_verifier(self):
        outputs = [
            {"worker_id": "a", "model_family": "f1", "claims": [{"claim_id": "c1", "value": "yes"}]},
            {"worker_id": "b", "model_family": "f2", "claims": [{"claim_id": "c1", "value": "no"}]},
        ]
        failures = detect_conflicts(outputs)
        self.assertIn("unresolved_contradictory_claim", failures)

    def test_verifier_can_resolve_contradiction_without_majority_vote(self):
        outputs = [
            {"worker_id": "a", "model_family": "f1", "claims": [{"claim_id": "c1", "value": "yes"}]},
            {"worker_id": "b", "model_family": "f2", "claims": [{"claim_id": "c1", "value": "no"}]},
            {"worker_id": "v", "role": "verifier", "model_family": "f3", "resolutions": [{"claim_id": "c1", "selected_value": "no", "evidence_refs": ["official:1"]}]},
        ]
        failures = detect_conflicts(outputs)
        self.assertNotIn("unresolved_contradictory_claim", failures)


if __name__ == "__main__":
    unittest.main()
