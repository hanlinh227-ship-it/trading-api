from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "AI_SKILL_LIBRARY/skills/catalog.yaml"
MANIFEST = ROOT / "AI_SKILL_LIBRARY/v4/skills/prompt_media/manifest.yaml"
FUSION = ROOT / "AI_SKILL_LIBRARY/v4/stable/creative_visual_fusion.yaml"
QUARANTINE = ROOT / "AI_SKILL_LIBRARY/v4/evergreen/quarantine/animation_prompt_reference_fusion.yaml"


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AssertionError(f"expected mapping: {path}")
    return data


class AnimationPromptSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_yaml(CATALOG)
        cls.manifest = load_yaml(MANIFEST)
        cls.fusion = load_yaml(FUSION)
        cls.quarantine = load_yaml(QUARANTINE)
        cls.skills = {
            row["id"]: row
            for row in cls.catalog.get("skills", [])
            if isinstance(row, dict) and isinstance(row.get("id"), str)
        }

    def test_specific_animation_prompt_intents_route_to_video_prompt_without_stealing_generic_animation(self):
        video = self.skills["video_prompt"]
        animation = self.skills["animation"]
        self.assertTrue(
            {"animation prompt", "image to video prompt", "i2v prompt"}.issubset(
                set(video.get("triggers", []))
            )
        )
        self.assertEqual(animation.get("triggers"), ["animation"])
        self.assertNotIn("animation", video.get("triggers", []))

    def test_video_prompt_contract_contains_animation_safety_invariants(self):
        contract = self.skills["video_prompt"].get("output_contract", "").casefold()
        required = (
            "start/end state",
            "action owner",
            "contact",
            "trajectory",
            "screen direction",
            "camera ownership",
            "motion budget",
            "object permanence",
            "body mechanics",
            "image-to-video",
            "positive operational wording",
            "stochastic",
        )
        for phrase in required:
            self.assertIn(phrase, contract, phrase)

    def test_prompt_media_manifest_declares_animation_safety_quality_gates(self):
        quality = self.manifest.get("quality_requirements", {})
        required_true = (
            "animation_start_end_state_lock",
            "animation_action_owner_unambiguous",
            "animation_contact_continuity",
            "animation_trajectory_consistency",
            "animation_screen_direction_consistency",
            "animation_camera_ownership_explicit",
            "animation_motion_budget_checked",
            "animation_object_permanence",
            "animation_body_mechanics",
            "animation_provider_wording_adapted",
            "animation_i2v_reference_is_authority",
        )
        for key in required_true:
            self.assertIs(quality.get(key), True, key)

    def test_harmonization_declares_one_compiler_and_canonical_shared_logic_owners(self):
        harmonization = self.manifest.get("harmonization", {})
        self.assertEqual(harmonization.get("compiler_skill"), "video_prompt")
        self.assertIs(harmonization.get("parallel_primary_skills"), False)
        self.assertIs(harmonization.get("supporting_skills_material_only"), True)
        self.assertLessEqual(harmonization.get("max_supporting_skills", 99), 2)
        self.assertEqual(harmonization.get("generic_animation_owner"), "animation")
        self.assertEqual(harmonization.get("specialist_animation_prompt_owner"), "video_prompt")

        owners = harmonization.get("shared_logic_owner", {})
        stable_owners = self.fusion.get("shared_logic_owner", {})
        for key in (
            "identity_preservation",
            "scene_continuity",
            "object_counts",
            "camera_variation",
            "reference_preservation",
            "negative_constraints",
        ):
            self.assertEqual(owners.get(key), stable_owners.get(key), key)

        expected_animation_owners = {
            "start_end_state": "scene_continuity",
            "contact_continuity": "scene_continuity",
            "trajectory": "scene_continuity",
            "screen_direction": "camera_direction",
            "camera_ownership": "camera_direction",
            "motion_budget": "video_prompt",
            "temporal_action_order": "video_prompt",
            "body_mechanics": "video_prompt",
            "provider_wording": "video_prompt",
        }
        for key, expected in expected_animation_owners.items():
            self.assertEqual(owners.get(key), expected, key)

    def test_reference_fusion_is_normalized_into_existing_prompt_media_skills_only(self):
        q = self.quarantine
        self.assertEqual(q.get("state"), "evaluated_reference_only")
        self.assertIs(q.get("routing_authority"), False)
        self.assertIs(q.get("reasoning_authority"), False)
        self.assertIs(q.get("permission_expansion"), False)
        self.assertEqual(q.get("promotion_target"), "strengthen_existing_prompt_media_skills_only")
        self.assertEqual(q.get("max_new_primary_skills"), 0)

        prompt_skills = set(self.manifest.get("skills", []))
        absorption = q.get("normalized_absorption", {})
        self.assertTrue(absorption)
        self.assertTrue(set(absorption.values()).issubset(prompt_skills))
        self.assertIn("video_prompt", set(absorption.values()))
        self.assertIn("scene_continuity", set(absorption.values()))
        self.assertIn("camera_direction", set(absorption.values()))


if __name__ == "__main__":
    unittest.main()
