from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


class FreeImageRenderAgentPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = yaml.safe_load(
            (ROOT / "AI_SKILL_LIBRARY/v4/legion/image_render_policy.yaml").read_text(encoding="utf-8")
        )
        self.agents = yaml.safe_load(
            (ROOT / "AI_SKILL_LIBRARY/v4/legion/agents.yaml").read_text(encoding="utf-8")
        )["agents"]

    def test_image_render_agent_is_non_authoritative_and_free_only(self):
        agent = self.agents["image_render_agent"]
        self.assertFalse(agent["routing_authority"])
        self.assertFalse(agent["reasoning_authority"])
        self.assertEqual(agent["permission_ceiling"], "sandbox_execute")
        self.assertEqual(agent["privacy_classes"], ["PUBLIC"])
        self.assertEqual(agent["tools"], ["image_render"])
        self.assertIn("image_generation", agent["model_capabilities"])
        self.assertTrue(agent["runtime"]["free_only"])
        self.assertFalse(agent["runtime"]["paid_fallback"])

    def test_provider_contract_never_falls_back_to_paid(self):
        self.assertEqual(self.policy["execution_mode"], "async_job")
        self.assertFalse(self.policy["paid_fallback"])
        self.assertFalse(self.policy["auto_purchase"])
        self.assertFalse(self.policy["trial_credit_as_free"])
        self.assertFalse(self.policy["promo_credit_as_free"])
        self.assertEqual(self.policy["provider"]["id"], "ai_horde")
        self.assertEqual(self.policy["provider"]["monetary_cost"], "zero")
        self.assertFalse(self.policy["provider"]["external_availability_guarantee"])
        self.assertTrue(self.policy["constraints"]["paid_route_forbidden"])
        self.assertEqual(self.policy["constraints"]["unknown_cost_action"], "reject")

    def test_volunteer_provider_is_public_data_only(self):
        privacy = self.policy["privacy"]
        self.assertEqual(privacy["allowed_data_classes"], ["PUBLIC"])
        self.assertEqual(set(privacy["denied_data_classes"]), {"INTERNAL", "CONFIDENTIAL", "SECRET"})
        self.assertEqual(privacy["non_public_action"], "fail_closed")
        self.assertEqual(privacy["reference_images_on_volunteer_provider"], "disabled")

    def test_runtime_can_use_anonymous_provider_access_without_new_secret(self):
        runtime = self.policy["runtime"]
        self.assertTrue(runtime["anonymous_without_provider_key"])
        self.assertEqual(runtime["optional_provider_key"], "AI_HORDE_API_KEY")
        self.assertEqual(runtime["execution_token"], "IMAGE_RENDER_EXECUTION_TOKEN")
        self.assertEqual(runtime["token_fallback"], "MODEL_MESH_EXECUTION_TOKEN")


if __name__ == "__main__":
    unittest.main()
