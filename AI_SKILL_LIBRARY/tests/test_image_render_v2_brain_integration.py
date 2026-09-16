from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "AI_SKILL_LIBRARY/v4/legion/image_render_policy.yaml"
AGENTS_PATH = ROOT / "AI_SKILL_LIBRARY/v4/legion/agents.yaml"
CREATIVE_PATH = ROOT / "AI_SKILL_LIBRARY/v4/stable/creative_visual_fusion.yaml"


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class ImageRenderV2BrainIntegrationTests(unittest.TestCase):
    def test_policy_v2_keeps_free_public_fail_closed_boundary(self):
        policy = load_yaml(POLICY_PATH)
        self.assertEqual(policy["version"], 2)
        self.assertFalse(policy["routing_authority"])
        self.assertFalse(policy["reasoning_authority"])
        self.assertFalse(policy["paid_fallback"])
        self.assertFalse(policy["auto_purchase"])
        self.assertEqual(policy["privacy"]["allowed_data_classes"], ["PUBLIC"])
        self.assertEqual(policy["privacy"]["non_public_action"], "fail_closed")
        self.assertFalse(policy["privacy"]["reference_images_on_volunteer_provider"])
        self.assertTrue(policy["constraints"]["paid_route_forbidden"])
        self.assertEqual(policy["constraints"]["unknown_cost_action"], "reject")

    def test_policy_v2_declares_batch_quality_and_isolates_trading_state(self):
        policy = load_yaml(POLICY_PATH)
        batch = policy["batch"]
        self.assertTrue(batch["enabled"])
        self.assertEqual(batch["max_scenes"], 100)
        self.assertEqual(batch["concurrency"], {"default": 4, "maximum": 8, "minimum": 1})
        self.assertEqual(batch["max_attempts_per_scene"], 3)
        self.assertEqual(batch["state_binding"], "IMAGE_RENDER_BATCH")
        self.assertEqual(batch["state_class"], "ImageRenderBatchState")
        self.assertTrue(batch["trading_state_forbidden"])
        self.assertTrue(policy["quality"]["never_fake_verified"])
        self.assertEqual(
            policy["quality"]["strict"]["missing_visual_critic_action"],
            "complete_unverified",
        )

    def test_legion_agent_advertises_v2_runtime_without_widening_authority(self):
        agents = load_yaml(AGENTS_PATH)["agents"]
        agent = agents["image_render_agent"]
        self.assertEqual(agent["privacy_classes"], ["PUBLIC"])
        self.assertFalse(agent["routing_authority"])
        self.assertFalse(agent["reasoning_authority"])
        runtime = agent["runtime"]
        self.assertEqual(runtime["contract_version"], "image_render_v2")
        self.assertEqual(runtime["batch_submit_path"], "/brain/image/batch")
        self.assertEqual(runtime["batch_status_path"], "/brain/image/batch/status")
        self.assertEqual(runtime["batch_retry_path"], "/brain/image/retry")
        self.assertEqual(runtime["models_path"], "/brain/image/models")
        self.assertEqual(runtime["state_binding"], "IMAGE_RENDER_BATCH")
        self.assertTrue(runtime["free_only"])
        self.assertTrue(runtime["public_only"])
        self.assertFalse(runtime["reference_images_on_provider"])
        self.assertFalse(runtime["paid_fallback"])

    def test_creative_fusion_points_to_canonical_v2_runtime_only(self):
        creative = load_yaml(CREATIVE_PATH)
        runtime = creative["image_render_runtime"]
        self.assertEqual(runtime["policy_path"], "AI_SKILL_LIBRARY/v4/legion/image_render_policy.yaml")
        self.assertEqual(runtime["contract_version"], "image_render_v2")
        self.assertTrue(runtime["batch_enabled"])
        self.assertTrue(runtime["free_only"])
        self.assertTrue(runtime["public_only"])
        self.assertFalse(runtime["reference_provider_upload"])
        self.assertEqual(runtime["quality_profiles"], ["STRUCTURAL", "STRICT"])
        self.assertEqual(runtime["strict_without_visual_critic"], "complete_unverified")
        self.assertFalse(runtime["routing_authority"])
        self.assertFalse(runtime["reasoning_authority"])


if __name__ == "__main__":
    unittest.main()
