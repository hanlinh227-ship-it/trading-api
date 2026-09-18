from __future__ import annotations

import unittest

from AI_SKILL_LIBRARY.v4.tools.intake_experience import (
    merge_experiences,
    normalize_experience,
)


class ExperienceLearningTests(unittest.TestCase):
    BASE = {
        "experience_id": "exp-1",
        "timestamp": "2026-09-18T00:00:00Z",
        "request_class": "coding",
        "role_id": "CODING_BRANCH",
        "skill_ids": ["debugging"],
        "model_id": "Qwen/Qwen3-8B-GGUF",
        "latency_ms": 1200,
        "success": True,
        "verifier_passed": True,
        "retry_count": 0,
        "evidence_ref": "CHECKPOINTS/evidence/exp-1.json",
    }

    def test_private_or_unknown_fields_are_rejected(self):
        for forbidden in (
            "raw_prompt", "raw_private_chat", "hidden_reasoning",
            "chain_of_thought", "secret", "credentials", "anything_else",
        ):
            with self.subTest(forbidden=forbidden):
                row = dict(self.BASE)
                row[forbidden] = "forbidden"
                with self.assertRaises(ValueError):
                    normalize_experience(row)

    def test_duplicate_id_must_be_byte_equivalent_after_normalization(self):
        row = normalize_experience(self.BASE)
        seed = {
            "version": 1, "ledger_id": "EXPERIENCE_LEDGER",
            "authority": False, "stable_write": False,
            "authority_flags": {}, "experiences": [],
        }
        merged = merge_experiences(seed, [row, row])
        self.assertEqual(len(merged["experiences"]), 1)
        conflict = dict(row)
        conflict["success"] = False
        with self.assertRaises(ValueError):
            merge_experiences(merged, [conflict])

    def test_merge_is_deterministic_and_non_authoritative(self):
        row_a = dict(self.BASE, experience_id="exp-b")
        row_b = dict(self.BASE, experience_id="exp-a")
        seed = {"experiences": []}
        merged = merge_experiences(seed, [row_a, row_b])
        self.assertEqual([x["experience_id"] for x in merged["experiences"]], ["exp-a", "exp-b"])
        self.assertIs(merged["authority"], False)
        self.assertIs(merged["stable_write"], False)
        self.assertTrue(all(v is False for v in merged["authority_flags"].values()))


if __name__ == "__main__":
    unittest.main()
