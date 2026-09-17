from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "AI_SKILL_LIBRARY/v4/tools"
CONTRACT = ROOT / "AI_SKILL_LIBRARY/v4/control_plane/chatgpt_brain_contract.yaml"
SCHEMA = ROOT / "AI_SKILL_LIBRARY/v4/schemas/chatgpt_brain_contract.schema.json"
CI_VALIDATE = TOOLS / "ci_validate.py"


def load_tool(name: str):
    path = TOOLS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ChatGPTBrainIngressContractTests(unittest.TestCase):
    def test_contract_schema_and_validator_exist(self):
        self.assertTrue(CONTRACT.is_file())
        self.assertTrue(SCHEMA.is_file())
        self.assertTrue((TOOLS / "validate_brain_ingress_contract.py").is_file())

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
        self.assertTrue(all(value is False for value in data["authority"].values()))

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

    def test_validator_accepts_checked_in_contract(self):
        validator = load_tool("validate_brain_ingress_contract")
        self.assertEqual(validator.validate_contract(CONTRACT, SCHEMA), [])

    def test_canonical_ci_runs_ingress_validator(self):
        text = CI_VALIDATE.read_text(encoding="utf-8")
        self.assertIn("AI_SKILL_LIBRARY/v4/tools/validate_brain_ingress_contract.py", text)


if __name__ == "__main__":
    unittest.main()
