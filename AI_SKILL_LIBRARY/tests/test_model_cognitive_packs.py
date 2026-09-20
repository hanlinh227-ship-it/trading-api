from __future__ import annotations

import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.tools.compile_model_cognitive_packs import compile_model_cognitive_packs


ROOT = Path(__file__).resolve().parents[2]


class ModelCognitivePackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = compile_model_cognitive_packs(ROOT)

    def test_compiles_all_models_skills_and_role_branches_without_authority(self):
        self.assertGreater(self.doc["model_count"], 0)
        self.assertGreaterEqual(self.doc["canonical_skill_count"], 100)
        self.assertGreaterEqual(self.doc["role_branch_count"], 10)
        self.assertFalse(any(self.doc["authority"].values()))
        for pack in self.doc["models"]:
            self.assertEqual(len(pack["training_units"]), self.doc["canonical_skill_count"])
            self.assertEqual(len(pack["branch_coverage"]), self.doc["role_branch_count"])
            self.assertLessEqual(len(pack["runtime_delta"]["priority_units"]), 6)
            self.assertFalse(pack["runtime_delta"]["full_curriculum_on_prompt"])
            self.assertFalse(pack["runtime_delta"]["hidden_reasoning_persistence"])
            self.assertFalse(pack["weight_training"]["automatic_weight_mutation"])
            self.assertFalse(pack["weight_training"]["automatic_apply"])
            self.assertFalse(any(pack["authority"].values()))

    def test_local_models_may_generate_training_candidates_but_hosted_models_may_not_mutate_weights(self):
        local = [p for p in self.doc["models"] if p["provider_id"] == "local_runtime"]
        hosted = [p for p in self.doc["models"] if p["provider_id"] != "local_runtime"]
        self.assertGreater(len(local), 0)
        self.assertTrue(all(p["weight_training"]["candidate_generation_eligible"] for p in local))
        self.assertTrue(all(not p["weight_training"]["candidate_generation_eligible"] for p in hosted))
        self.assertTrue(all(not p["weight_training"]["automatic_apply"] for p in self.doc["models"]))

    def test_shared_core_is_one_hash_for_every_model(self):
        expected = self.doc["cognitive_core"]["cognitive_core_hash"]
        self.assertTrue(expected)
        self.assertTrue(all(p["cognitive_core_hash"] == expected for p in self.doc["models"]))


if __name__ == "__main__":
    unittest.main()
