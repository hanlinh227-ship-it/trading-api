from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.tools.evaluate_skill_candidate import evaluate_candidate
from AI_SKILL_LIBRARY.v4.tools.intake_failure import merge_failures, normalize_failure


class FailureDrivenLearningTests(unittest.TestCase):
    def test_failure_intake_rejects_private_or_secret_fields(self) -> None:
        base = {
            "failure_id": "f-1",
            "domain": "coding",
            "failure_class": "verification",
            "observable_symptom": "validator returned non-zero",
            "expected_outcome": "validator passes",
            "evidence_ref": "artifact://ci/run/1",
            "timestamp": "2026-09-16T00:00:00Z",
        }
        for forbidden in (
            "raw_prompt",
            "raw_private_chat",
            "secret",
            "credentials",
            "hidden_reasoning",
            "private_tool_payload",
        ):
            row = dict(base)
            row[forbidden] = "must-not-persist"
            with self.assertRaises(ValueError):
                normalize_failure(row)

    def test_failure_merge_is_deterministic_and_conflict_safe(self) -> None:
        row = normalize_failure({
            "failure_id": "f-2",
            "domain": "core",
            "failure_class": "routing",
            "observable_symptom": "wrong primary skill",
            "expected_outcome": "canonical primary skill selected",
            "evidence_ref": "artifact://eval/f-2",
            "timestamp": "2026-09-16T00:01:00Z",
            "client_id": "chatgpt",
        })
        merged = merge_failures({"version": 1, "failures": []}, [row, row])
        self.assertEqual([x["failure_id"] for x in merged["failures"]], ["f-2"])
        conflicting = dict(row)
        conflicting["observable_symptom"] = "different symptom"
        with self.assertRaises(ValueError):
            merge_failures(merged, [conflicting])

    def test_ab_can_auto_promote_but_cd_require_authorization(self) -> None:
        eval_result = {
            "all_gates_pass": True,
            "frozen_replay": True,
            "protected_regressions": 0,
            "critical_conflicts": 0,
            "measured_gain": 0.1,
        }
        for klass, automatic, approval in (
            ("A", True, False),
            ("B", True, False),
            ("C", False, True),
            ("D", False, True),
        ):
            candidate = {
                "candidate_id": f"skill-{klass}",
                "promotion_class": klass,
                "permission_unchanged": True,
                "sandbox_pass": True,
            }
            result = evaluate_candidate(candidate, eval_result, replay_ref="artifact://replay/frozen-1")
            self.assertEqual(result["automatic"], automatic)
            self.assertEqual(result["explicit_authorization_required"], approval)
            self.assertEqual(result["immutable_replay_ref"], "artifact://replay/frozen-1")
            self.assertFalse(result["stable_write"])

    def test_permission_change_blocks_automatic_promotion(self) -> None:
        candidate = {
            "candidate_id": "skill-A",
            "promotion_class": "A",
            "permission_unchanged": False,
            "sandbox_pass": True,
        }
        eval_result = {
            "all_gates_pass": True,
            "frozen_replay": True,
            "protected_regressions": 0,
            "critical_conflicts": 0,
            "measured_gain": 1.0,
        }
        result = evaluate_candidate(candidate, eval_result, replay_ref="artifact://replay/frozen-2")
        self.assertFalse(result["eligible"])
        self.assertIn("permission_changed", result["reasons"])


if __name__ == "__main__":
    unittest.main()
