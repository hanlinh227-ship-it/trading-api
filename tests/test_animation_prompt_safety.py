from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "AI_SKILL_LIBRARY/skills/catalog.yaml"
MANIFEST = ROOT / "AI_SKILL_LIBRARY/v4/skills/prompt_media/manifest.yaml"


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


if __name__ == "__main__":
    unittest.main()
