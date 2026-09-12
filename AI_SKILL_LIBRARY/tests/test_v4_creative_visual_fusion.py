from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "AI_SKILL_LIBRARY"


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


class V4CreativeVisualFusionTests(unittest.TestCase):
    def test_checkpoint_discovers_canonical_creative_visual_fusion(self):
        cp = load_json(LIB / "checkpoint.json")
        expected = "AI_SKILL_LIBRARY/v4/stable/creative_visual_fusion.yaml"
        self.assertEqual(cp.get("stable_creative_visual_fusion_path"), expected)
        self.assertTrue((ROOT / expected).is_file())

    def test_creative_fusion_is_subordinate_and_not_parallel_authority(self):
        creative = load_yaml(LIB / "v4/stable/creative_visual_fusion.yaml")
        policy = creative["policy"]
        self.assertTrue(policy["single_authority_chain"])
        self.assertFalse(policy["routing_authority"])
        self.assertFalse(policy["reasoning_authority"])
        self.assertTrue(policy["canonical_skill_first"])
        self.assertTrue(policy["zero_local_cloud_runtime_preserved"])
        self.assertTrue(policy["project_authority_precedes_creative_patterns"])
        self.assertTrue(policy["stable_security_precedes_creative_patterns"])

        fusion = load_yaml(LIB / "v4/stable/capability_fusion.yaml")
        self.assertEqual(
            fusion["creative_visual_fusion"]["policy_path"],
            "AI_SKILL_LIBRARY/v4/stable/creative_visual_fusion.yaml",
        )
        self.assertFalse(fusion["creative_visual_fusion"]["routing_authority"])

    def test_six_native_modules_exist_and_are_bounded(self):
        creative = load_yaml(LIB / "v4/stable/creative_visual_fusion.yaml")
        required = {
            "creative_direction",
            "script_to_shots",
            "visual_prompt_compiler",
            "continuity_engine",
            "visual_edit_reasoning",
            "render_quality_critic",
        }
        self.assertTrue(required.issubset(creative["modules"]))
        continuity = creative["continuity"]
        self.assertLessEqual(continuity["max_state_items_standard"], 12)
        self.assertLessEqual(continuity["max_state_items_deep"], 32)
        self.assertFalse(continuity["authority"])
        self.assertFalse(continuity["persist_hidden_reasoning"])

    def test_existing_canonical_skills_remain_the_route_surface(self):
        catalog = load_yaml(LIB / "skills/catalog.yaml")
        ids = {row["id"] for row in catalog["skills"]}
        expected = {
            "image_prompt",
            "video_prompt",
            "negative_constraints",
            "prompt_debugging",
            "character_consistency",
            "scene_continuity",
            "camera_direction",
            "storyboard",
            "graphic_design",
            "layout",
            "photoshop",
            "premiere_pro",
            "scriptwriting",
            "storytelling",
        }
        self.assertTrue(expected.issubset(ids))
        forbidden_duplicates = {
            "creative_brain",
            "creative_router",
            "super_image_prompt",
            "identity_lock_engine",
            "cinematic_prompt_master",
        }
        self.assertTrue(ids.isdisjoint(forbidden_duplicates))

    def test_visual_edit_reasoning_is_target_preserving_and_fail_closed(self):
        creative = load_yaml(LIB / "v4/stable/creative_visual_fusion.yaml")
        edit = creative["visual_edit_reasoning"]
        self.assertTrue(edit["smallest_necessary_scope"])
        self.assertTrue(edit["preserve_non_target_content"])
        self.assertEqual(edit["missing_target_action"], "fail_closed")
        self.assertEqual(edit["missing_reference_action"], "fail_closed_when_reference_required")
        self.assertFalse(edit["may_silently_add_or_remove_subjects"])

    def test_fast_profile_has_no_external_creative_runtime_dependency(self):
        creative = load_yaml(LIB / "v4/stable/creative_visual_fusion.yaml")
        fast = creative["profiles"]["FAST"]
        self.assertFalse(fast["external_framework_required"])
        self.assertEqual(fast["continuity_preload_items"], 0)
        self.assertFalse(fast["maker_checker"])
        self.assertFalse(fast["independent_grader"])

    def test_upstream_creative_sources_are_reference_only_or_rag_and_never_training(self):
        sources = load_yaml(LIB / "sources.yaml")
        rows = {row.get("repo"): row for row in sources.get("sources", []) if isinstance(row, dict)}
        expected = {
            "lllyasviel/ControlNet",
            "tencent-ailab/IP-Adapter",
            "facebookresearch/segment-anything",
            "IDEA-Research/GroundingDINO",
            "xinntao/Real-ESRGAN",
            "comfyanonymous/ComfyUI",
        }
        self.assertTrue(expected.issubset(rows))
        for repo in expected:
            self.assertFalse(rows[repo]["training"], repo)
            self.assertIn(rows[repo]["usage_tier"], {"RAG_ONLY", "REFERENCE_ONLY"}, repo)

    def test_harmonization_requires_creative_overlap_and_conflict_gates(self):
        harmonization = load_yaml(LIB / "v4/stable/harmonization.yaml")
        future = harmonization["future_upgrade_contract"]
        self.assertTrue(future["every_new_creative_pattern_must_pass_harmonization"])
        self.assertTrue(future["creative_overlap_must_strengthen_canonical_skill_first"])
        self.assertTrue(future["creative_visual_fusion_policy_required"])
        self.assertTrue(future["do_not_create_parallel_brain"])


if __name__ == "__main__":
    unittest.main()
