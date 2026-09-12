from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "AI_SKILL_LIBRARY"
POLICY = LIB / "v4/stable/cognitive_harmonization.yaml"


class CognitiveHarmonizationContractTests(unittest.TestCase):
    def load_policy(self) -> dict:
        self.assertTrue(POLICY.is_file(), "cognitive harmonization policy must exist")
        data = yaml.safe_load(POLICY.read_text(encoding="utf-8"))
        self.assertIsInstance(data, dict)
        return data

    def test_policy_preserves_single_authority_and_fail_closed_conflicts(self):
        policy = self.load_policy()
        authority = policy["authority"]
        self.assertFalse(authority["external_framework_is_reasoning_authority"])
        self.assertFalse(authority["provider_consensus_is_authorization"])
        self.assertTrue(authority["current_project_authority_precedes_external_methods"])
        self.assertEqual(
            policy["harmonization"]["unresolved_material_conflict"],
            "disclose_and_block_high_consequence_dependent_conclusion",
        )

    def test_agent_loop_is_bounded_and_cannot_expand_permissions(self):
        policy = self.load_policy()
        loop = policy["agent_loop"]
        self.assertTrue(loop["enabled"])
        self.assertLessEqual(loop["max_iterations"], 3)
        self.assertFalse(loop["may_expand_permissions"])
        self.assertFalse(loop["may_bypass_security_or_authority"])
        self.assertFalse(loop["financial_execution_allowed"])

    def test_maker_checker_grader_are_profile_bounded(self):
        policy = self.load_policy()
        profiles = policy["profiles"]
        self.assertEqual(profiles["FAST"]["mode"], "disabled")
        self.assertIn(profiles["STANDARD"]["mode"], {"checker_on_demand", "disabled"})
        self.assertEqual(profiles["DEEP"]["mode"], "maker_checker_with_independent_grader")
        self.assertTrue(policy["grader"]["independent_from_maker_when_available"])

    def test_artifact_pyramid_does_not_change_truth_or_authority(self):
        policy = self.load_policy()
        pyramid = policy["artifact_pyramid"]
        self.assertEqual(pyramid["layers"], ["summary", "analysis", "evidence_dossier"])
        self.assertFalse(pyramid["may_override_verification"])
        self.assertFalse(pyramid["may_override_authority"])

    def test_checkpoint_discovers_policy(self):
        checkpoint = json.loads((LIB / "checkpoint.json").read_text(encoding="utf-8"))
        self.assertEqual(
            checkpoint["cognitive_harmonization_path"],
            "AI_SKILL_LIBRARY/v4/stable/cognitive_harmonization.yaml",
        )


if __name__ == "__main__":
    unittest.main()
