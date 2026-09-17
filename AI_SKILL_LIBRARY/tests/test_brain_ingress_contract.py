from __future__ import annotations

import json
from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "AI_SKILL_LIBRARY/v4/control_plane/chatgpt_brain_contract.yaml"
SCHEMA = ROOT / "AI_SKILL_LIBRARY/v4/schemas/chatgpt_brain_contract.schema.json"


class ChatGPTBrainIngressContractTests(unittest.TestCase):
    def test_contract_and_schema_exist(self):
        self.assertTrue(CONTRACT.is_file())
        self.assertTrue(SCHEMA.is_file())

    def test_ingress_cannot_bypass_task_router_or_choose_model(self):
        data = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
        ingress = data["ingress"]
        self.assertEqual(ingress["mandatory_next_hop"], "task_router")
        self.assertIs(ingress["may_choose_model"], False)
        self.assertIs(ingress["may_bypass_task_router"], False)
        self.assertIs(ingress["may_widen_permissions"], False)
        self.assertEqual(
            ingress["required_fields"],
            [
                "source",
                "request",
                "project_context",
                "conversation_context",
                "desired_depth",
                "attachments",
                "constraints",
                "privacy_class",
            ],
        )

    def test_brain_flow_preserves_canonical_authority(self):
        data = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(
            data["brain_flow"],
            [
                "ingress",
                "task_router",
                "project_domain_resolution",
                "memory",
                "skills",
                "model_mesh",
                "runtime_scheduler",
                "verifier",
                "synthesis",
                "response",
            ],
        )
        self.assertIs(data["authority"]["routing"], False)
        self.assertIs(data["authority"]["reasoning"], False)
        self.assertIs(data["authority"]["permission"], False)
        self.assertIs(data["authority"]["memory"], False)
        self.assertIs(data["authority"]["project_truth"], False)
        self.assertIs(data["authority"]["final_answer"], False)

    def test_response_contract_has_no_hidden_reasoning(self):
        data = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
        response = data["response"]
        self.assertEqual(
            response["required_fields"],
            [
                "request_id",
                "task_id",
                "route",
                "selected_model_ref",
                "runtime_ref",
                "verification_status",
                "result",
                "evidence_refs",
                "limitations",
                "runtime_metrics_ref",
            ],
        )
        self.assertIs(response["hidden_reasoning_allowed"], False)

    def test_privacy_policy_is_fail_closed_for_secret_and_confidential(self):
        data = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
        privacy = data["privacy"]
        self.assertEqual(privacy["classes"], ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "SECRET"])
        self.assertEqual(privacy["SECRET"]["default_route"], "local_only")
        self.assertEqual(privacy["CONFIDENTIAL"]["default_route"], "local_preferred")
        self.assertIs(privacy["CONFIDENTIAL"]["external_requires_verified_policy"], True)
        self.assertIs(privacy["free_external_sensitive_default"], False)

    def test_schema_requires_core_contract_sections(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(
            set(schema["required"]),
            {"version", "contract_id", "authority", "ingress", "brain_flow", "response", "privacy"},
        )
        self.assertFalse(schema["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
