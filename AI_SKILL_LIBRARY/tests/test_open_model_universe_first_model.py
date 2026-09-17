from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, FormatChecker
import yaml


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"
MODEL_SCHEMA = ROOT / "AI_SKILL_LIBRARY/v4/schemas/open_model_universe.schema.json"
INGRESS_SCHEMA = ROOT / "AI_SKILL_LIBRARY/v4/contracts/chatgpt_brain_ingress.schema.json"
RESPONSE_SCHEMA = ROOT / "AI_SKILL_LIBRARY/v4/contracts/brain_response.schema.json"
CONTRACT_VALIDATOR = ROOT / "AI_SKILL_LIBRARY/v4/tools/validate_chatgpt_brain_contracts.py"
CI_VALIDATE = ROOT / "AI_SKILL_LIBRARY/v4/tools/ci_validate.py"

EXPECTED_MODEL_ID = "qwen/qwen2.5-1.5b-instruct-gguf-q4_k_m"
EXPECTED_REVISION = "dd26da440ef0330c47919d1ecae0966d24022222"
EXPECTED_SHA256 = "6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e"
EXPECTED_SIZE = 1117320736


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FirstLocalModelRecordTests(unittest.TestCase):
    def test_registry_contains_exactly_one_first_e2e_model(self):
        data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(len(data["models"]), 1)
        model = data["models"][0]
        self.assertEqual(model["model_id"], EXPECTED_MODEL_ID)
        self.assertEqual(model["upstream_revision"], EXPECTED_REVISION)
        self.assertEqual(model["immutable_revision"], EXPECTED_REVISION)
        self.assertEqual(model["artifact_hash"], f"sha256:{EXPECTED_SHA256}")
        self.assertEqual(model["artifact_size_bytes"], EXPECTED_SIZE)
        self.assertEqual(model["artifact_format"], "GGUF")
        self.assertEqual(model["quantization"], "Q4_K_M")
        self.assertIn("llama_cpp", model["runtime_support"])
        self.assertIs(model["hardware_profile"]["cpu_viable"], True)
        self.assertIs(model["zero_cost_eligible"], True)
        self.assertIs(model["offline_ready"], True)
        self.assertEqual(model["license_name"], "Apache-2.0")
        self.assertEqual(model["license_class"], "permissive")
        self.assertIs(model["license_verified"], True)
        self.assertIs(model["authority"], False)
        self.assertEqual(model["admission_status"], "E2E_CANDIDATE")

    def test_first_model_has_security_and_lineage_evidence(self):
        model = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["models"][0]
        security = model["artifact_security"]
        self.assertIs(security["revision_pinned"], True)
        self.assertIs(security["digest_verified"], True)
        self.assertIs(security["safe_format"], True)
        self.assertIs(security["pickle_risk"], False)
        self.assertIs(security["trust_remote_code_required"], False)
        self.assertIs(security["custom_code_required"], False)
        self.assertIs(security["license_verified"], True)
        self.assertIs(security["provenance_verified"], True)
        self.assertEqual(security["malware_scan_status"], "not_scanned")
        self.assertIs(security["isolated_load_required"], True)
        self.assertIs(security["egress_required"], False)
        self.assertIs(security["rollback_artifact_available"], True)
        self.assertEqual(model["lineage"]["quantization_parent"], "Qwen/Qwen2.5-1.5B-Instruct")

    def test_first_model_projects_required_runtime_identity_without_invention(self):
        model = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["models"][0]
        projection = model["runtime_projection"]
        self.assertEqual(projection["model_id"], model["model_id"])
        self.assertEqual(projection["revision"], model["upstream_revision"])
        self.assertEqual(projection["artifact_hash"], model["artifact_hash"])
        self.assertEqual(projection["artifact_size_bytes"], model["artifact_size_bytes"])
        self.assertEqual(projection["quantization"], model["quantization"])
        self.assertEqual(projection["runtime_support"], model["runtime_support"])
        self.assertEqual(projection["minimum_ram_gb"], model["hardware_profile"]["minimum_ram_gb"])
        self.assertEqual(projection["recommended_ram_gb"], model["hardware_profile"]["recommended_ram_gb"])
        self.assertEqual(projection["minimum_vram_gb"], model["hardware_profile"]["minimum_vram_gb"])
        self.assertEqual(projection["recommended_vram_gb"], model["hardware_profile"]["recommended_vram_gb"])
        self.assertEqual(projection["cpu_viable"], model["hardware_profile"]["cpu_viable"])
        self.assertEqual(projection["privacy_class"], model["privacy_class"])
        self.assertEqual(projection["zero_cost_eligible"], model["zero_cost_eligible"])
        self.assertEqual(projection["admission_status"], model["admission_status"])

    def test_canonical_registry_validates_with_the_real_record(self):
        schema = json.loads(MODEL_SCHEMA.read_text(encoding="utf-8"))
        document = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
        errors = sorted(
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document),
            key=lambda item: list(item.path),
        )
        self.assertEqual(errors, [], [error.message for error in errors])


class ChatGPTBrainContractTests(unittest.TestCase):
    def test_ingress_and_response_schemas_exist_and_are_valid(self):
        for path in (INGRESS_SCHEMA, RESPONSE_SCHEMA):
            self.assertTrue(path.is_file(), path)
            Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))
        self.assertTrue(CONTRACT_VALIDATOR.is_file())

    def test_ingress_requires_router_safe_fields_and_cannot_choose_model(self):
        schema = json.loads(INGRESS_SCHEMA.read_text(encoding="utf-8"))
        required = set(schema["required"])
        self.assertTrue(
            {
                "source",
                "request",
                "project_context",
                "conversation_context",
                "desired_depth",
                "attachments",
                "constraints",
                "privacy_class",
            }.issubset(required)
        )
        properties = schema["properties"]
        for forbidden in ("selected_model_ref", "model_id", "runtime_ref", "permission_override"):
            self.assertNotIn(forbidden, properties)
        self.assertIs(schema["additionalProperties"], False)

    def test_response_contract_contains_no_hidden_reasoning_channel(self):
        schema = json.loads(RESPONSE_SCHEMA.read_text(encoding="utf-8"))
        self.assertTrue(
            {
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
            }.issubset(set(schema["required"]))
        )
        self.assertNotIn("chain_of_thought", schema["properties"])
        self.assertNotIn("hidden_reasoning", schema["properties"])
        self.assertIs(schema["additionalProperties"], False)

    def test_contract_validator_and_ci_are_wired(self):
        module = _load_module(CONTRACT_VALIDATOR)
        self.assertEqual(module.validate_contracts(ROOT), [])
        ci = CI_VALIDATE.read_text(encoding="utf-8")
        self.assertIn("validate_chatgpt_brain_contracts.py", ci)


if __name__ == "__main__":
    unittest.main()
