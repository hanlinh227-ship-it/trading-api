from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "AI_SKILL_LIBRARY/v4/tools"
SCHEMAS = ROOT / "AI_SKILL_LIBRARY/v4/schemas"
REGISTRY = ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"


def load_tool(name: str):
    path = TOOLS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WorkB6B5ContractTests(unittest.TestCase):
    def test_governance_lifecycle_excludes_runtime_residency(self):
        universe = load_tool("open_model_universe")
        expected = {
            "DISCOVERED", "QUARANTINED", "QUARANTINED_UPDATE", "REGISTERED",
            "APPROVED", "AVAILABLE", "BLOCKED", "SUPERSEDED", "RETIRED",
        }
        self.assertTrue(hasattr(universe, "GOVERNANCE_STATES"), "governance lifecycle contract missing")
        self.assertEqual(universe.GOVERNANCE_STATES, expected)
        self.assertTrue({"RUNNING", "WARM", "SLEEPING"}.isdisjoint(universe.GOVERNANCE_STATES))

    def test_artifact_and_admission_schemas_exist(self):
        artifact = SCHEMAS / "model_artifact_identity.schema.json"
        admission = SCHEMAS / "model_admission.schema.json"
        self.assertTrue(artifact.is_file(), "artifact identity schema missing")
        self.assertTrue(admission.is_file(), "model admission schema missing")
        artifact_schema = json.loads(artifact.read_text(encoding="utf-8"))
        admission_schema = json.loads(admission.read_text(encoding="utf-8"))
        self.assertEqual(
            set(artifact_schema["required"]),
            {"model_id", "family", "variant", "immutable_revision", "sha256", "size_bytes", "format", "quantization"},
        )
        self.assertEqual(
            set(admission_schema["required"]),
            {
                "license_verified", "provenance_verified", "safe_format_verified", "pickle_safe",
                "trust_remote_code_required", "custom_code_required", "malware_scan_status",
                "isolated_first_load_required", "first_load_egress_allowed", "quarantine_status",
            },
        )

    def test_exactly_one_real_model_record_preserves_identity(self):
        registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(len(registry["models"]), 1)
        model = registry["models"][0]
        identity = model["artifact_identity"]
        self.assertEqual(identity["model_id"], model["model_id"])
        self.assertEqual(identity["family"], model["family"])
        self.assertEqual(identity["variant"], model["variant"])
        self.assertRegex(identity["immutable_revision"], r"^[0-9a-f]{40}$")
        self.assertRegex(identity["sha256"], r"^[0-9a-f]{64}$")
        self.assertGreater(identity["size_bytes"], 0)
        self.assertEqual(identity["format"], "gguf")
        self.assertEqual(identity["quantization"], "Q8_0")

    def test_unknown_critical_security_evidence_blocks_model_mesh_candidate(self):
        universe = load_tool("open_model_universe")
        self.assertTrue(hasattr(universe, "is_model_mesh_local_candidate"), "admission boundary missing")
        registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
        model = registry["models"][0]
        self.assertFalse(universe.is_model_mesh_local_candidate(model))
        self.assertNotEqual(model["admission"]["malware_scan_status"], "pass")

    def test_blocked_and_quarantined_never_activate(self):
        universe = load_tool("open_model_universe")
        registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
        model = registry["models"][0]
        for state in ("BLOCKED", "QUARANTINED", "QUARANTINED_UPDATE"):
            candidate = dict(model)
            candidate["lifecycle_state"] = state
            self.assertFalse(universe.is_model_mesh_local_candidate(candidate), state)

    def test_only_admission_cleared_available_model_can_enter_local_candidate_path(self):
        universe = load_tool("open_model_universe")
        registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
        model = registry["models"][0]
        candidate = dict(model)
        candidate["lifecycle_state"] = "AVAILABLE"
        candidate["admission"] = dict(model["admission"])
        candidate["admission"].update({
            "license_verified": True,
            "provenance_verified": True,
            "safe_format_verified": True,
            "pickle_safe": True,
            "trust_remote_code_required": False,
            "custom_code_required": False,
            "malware_scan_status": "pass",
            "isolated_first_load_required": True,
            "first_load_egress_allowed": False,
            "quarantine_status": "CLEARED",
        })
        self.assertTrue(universe.is_model_mesh_local_candidate(candidate))
        projection = universe.project_runtime_artifact_identity(candidate)
        self.assertEqual(projection, candidate["artifact_identity"])

    def test_registry_membership_does_not_activate_or_hardcode_qwen_at_ingress(self):
        registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
        integration = registry["integration"]
        self.assertFalse(integration["registry_membership_is_activation"])
        self.assertEqual(integration["runtime_residency_owner"], "claude_local_runtime")
        self.assertEqual(integration["model_mesh_local_candidate_rule"], "admission_cleared_only")
        ingress = (ROOT / "AI_SKILL_LIBRARY/v4/universal_entry/policy.yaml").read_text(encoding="utf-8").lower()
        self.assertNotIn("qwen3-0.6b", ingress)


if __name__ == "__main__":
    unittest.main()
