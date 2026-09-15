import copy
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.tools.legion import eligible_agents, load_agent_registry, validate_agent_contract


ROOT = Path(__file__).resolve().parents[2]


class LegionAgentRegistryTests(unittest.TestCase):
    def setUp(self):
        self.agents = load_agent_registry(ROOT)

    def test_required_specialists_exist(self):
        required = {
            "engineering_builder",
            "security_reviewer",
            "research_scout",
            "data_rag_analyst",
            "creative_prompt_specialist",
            "uxui_reviewer",
            "asset_3d_validator",
            "automation_integrator",
            "deployment_verifier",
            "quant_researcher",
            "business_analyst",
            "game_system_designer",
            "academic_researcher",
            "independent_checker",
        }
        self.assertTrue(required.issubset(self.agents))

    def test_every_agent_contract_is_typed_and_non_authoritative(self):
        for agent_id, agent in self.agents.items():
            self.assertEqual(validate_agent_contract(agent), [], agent_id)
            self.assertEqual(agent["agent_id"], agent_id)
            self.assertFalse(agent["routing_authority"])
            self.assertFalse(agent["reasoning_authority"])
            self.assertGreaterEqual(agent["max_retries"], 0)
            self.assertLessEqual(agent["max_retries"], 3)

    def test_quant_agent_cannot_execute_live_financial_actions(self):
        agent = self.agents["quant_researcher"]
        self.assertTrue(agent["research_only"])
        self.assertFalse(agent["live_financial_execution"])
        self.assertNotIn("financial_execution", agent["tools"])

    def test_eligibility_filters_domain_permission_risk_tools_and_privacy(self):
        task = {
            "domain": "engineering",
            "mode": "patch",
            "required_tools": ["repo_edit"],
            "required_model_capabilities": ["coding"],
            "permission_ceiling": "bounded_write",
            "risk_ceiling": "B",
            "data_class": "PUBLIC",
        }
        eligible = eligible_agents(task, self.agents)
        ids = {item["agent_id"] for item in eligible}
        self.assertIn("engineering_builder", ids)
        self.assertNotIn("research_scout", ids)

        hostile = copy.deepcopy(task)
        hostile["required_tools"] = ["financial_execution"]
        self.assertEqual(eligible_agents(hostile, self.agents), [])

    def test_invalid_contract_is_rejected(self):
        broken = copy.deepcopy(self.agents["engineering_builder"])
        broken.pop("permission_ceiling")
        errors = validate_agent_contract(broken)
        self.assertTrue(any("permission_ceiling" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
