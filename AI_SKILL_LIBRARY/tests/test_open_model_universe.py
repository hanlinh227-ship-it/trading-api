from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "AI_SKILL_LIBRARY/v4/tools"
SCHEMA = ROOT / "AI_SKILL_LIBRARY/v4/schemas/open_model_universe.schema.json"
REGISTRY = ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"
CI_VALIDATE = TOOLS / "ci_validate.py"


def load_tool(name: str):
    path = TOOLS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def model_record(index: int) -> dict:
    return {
        "model_id": f"example/model-{index}",
        "family": f"family-{index}",
        "variant": "base",
        "base_model": f"example/model-{index}",
        "quantization": "none",
        "runtime_build": "unresolved",
        "official_upstream": "https://example.invalid/official",
        "weights_source": "https://example.invalid/weights",
        "upstream_revision": "unresolved",
        "release_date": None,
        "license_name": "unresolved",
        "license_url": "https://example.invalid/license",
        "license_class": "unclear",
        "license_verified": False,
        "commercial_use": "unknown",
        "self_hostable": False,
        "redistribution": "unknown",
        "derivative_training": "unknown",
        "open_weight": False,
        "api_required": False,
        "paid_token_required": False,
        "local_runtime_possible": False,
        "capabilities": {},
        "hardware_profile": {
            "minimum_ram_gb": None,
            "recommended_ram_gb": None,
            "minimum_vram_gb": None,
            "recommended_vram_gb": None,
            "quantization_options": [],
            "cpu_viable": "unknown",
            "apple_silicon_viable": "unknown",
        },
        "runtime_support": [],
        "context_window": None,
        "benchmark_profile": "unverified",
        "quality_class": "unverified",
        "latency_class": "unverified",
        "privacy_class": "unverified",
        "cost_class": "zero_paid_token_candidate",
        "lifecycle_state": "QUARANTINED",
        "health": "unknown",
        "last_verified": None,
        "authority": False,
        "source_evidence": ["https://example.invalid/official"],
    }


def registry_document(models: list[dict] | None = None) -> dict:
    return {
        "version": 1,
        "registry_id": "OPEN_MODEL_UNIVERSE",
        "policy": {
            "cost_policy": "OPEN_MODEL_ZERO_TOKEN_FIRST",
            "paid_fallback": "NO_PAID_FALLBACK",
            "registry_implies_activation": False,
            "auto_download": False,
        },
        "authority": {
            "routing": False,
            "reasoning": False,
            "permission": False,
            "memory": False,
            "project_truth": False,
            "final_answer": False,
        },
        "models": models or [],
    }


class OpenModelUniverseContractTests(unittest.TestCase):
    def test_schema_registry_and_tools_exist(self):
        self.assertTrue(SCHEMA.is_file())
        self.assertTrue(REGISTRY.is_file())
        self.assertTrue((TOOLS / "open_model_universe.py").is_file())
        self.assertTrue((TOOLS / "validate_open_model_universe.py").is_file())

    def test_canonical_ci_runs_the_open_model_universe_validator(self):
        text = CI_VALIDATE.read_text(encoding="utf-8")
        self.assertIn("AI_SKILL_LIBRARY/v4/tools/validate_open_model_universe.py", text)
        self.assertIn('"validate_open_model_universe.py"', text)

    def test_checked_in_registry_is_empty_authority_free_and_not_active(self):
        data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["registry_id"], "OPEN_MODEL_UNIVERSE")
        self.assertEqual(data["models"], [])
        self.assertEqual(data["policy"]["cost_policy"], "OPEN_MODEL_ZERO_TOKEN_FIRST")
        self.assertEqual(data["policy"]["paid_fallback"], "NO_PAID_FALLBACK")
        self.assertIs(data["policy"]["registry_implies_activation"], False)
        self.assertTrue(all(value is False for value in data["authority"].values()))

    def test_lifecycle_vocabulary_and_safe_transitions_are_explicit(self):
        universe = load_tool("open_model_universe")
        required = {
            "DISCOVERED", "QUARANTINED", "REGISTERED", "APPROVED", "AVAILABLE",
            "DOWNLOADING", "CACHED", "WARM", "RUNNING", "SLEEPING", "DEGRADED",
            "BROKEN", "EVICTED", "SUPERSEDED", "RETIRED", "BLOCKED",
            "QUARANTINED_UPDATE",
        }
        self.assertEqual(universe.LIFECYCLE_STATES, required)
        self.assertTrue(universe.validate_transition("APPROVED", "DOWNLOADING"))
        self.assertTrue(universe.validate_transition("RUNNING", "WARM"))
        self.assertTrue(universe.validate_transition("BROKEN", "QUARANTINED"))
        self.assertTrue(universe.validate_transition("SUPERSEDED", "RETIRED"))
        self.assertFalse(universe.validate_transition("DISCOVERED", "RUNNING"))
        self.assertFalse(universe.validate_transition("QUARANTINED", "RUNNING"))
        self.assertFalse(universe.validate_transition("UNKNOWN", "RUNNING"))
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        schema_states = set(schema["$defs"]["model"]["properties"]["lifecycle_state"]["enum"])
        self.assertEqual(schema_states, universe.LIFECYCLE_STATES)

    def test_valid_empty_and_large_registry_documents_pass(self):
        validator = load_tool("validate_open_model_universe")
        self.assertEqual(validator.validate_document(registry_document()), [])
        large = registry_document([model_record(index) for index in range(1000)])
        self.assertEqual(validator.validate_document(large), [])

    def test_duplicate_model_identity_fails_closed(self):
        validator = load_tool("validate_open_model_universe")
        row = model_record(1)
        errors = validator.validate_document(registry_document([row, deepcopy(row)]))
        self.assertTrue(any("duplicate model identity" in error for error in errors), errors)

    def test_paid_fallback_authority_and_activation_mutations_are_rejected(self):
        validator = load_tool("validate_open_model_universe")
        data = registry_document()
        data["policy"]["paid_fallback"] = "enabled"
        data["policy"]["registry_implies_activation"] = True
        data["authority"]["routing"] = True
        errors = validator.validate_document(data)
        self.assertTrue(any("NO_PAID_FALLBACK" in error for error in errors), errors)
        self.assertTrue(any("activation" in error for error in errors), errors)
        self.assertTrue(any("authority" in error for error in errors), errors)

    def test_paid_or_unknown_cost_metadata_cannot_masquerade_as_runtime_eligible(self):
        validator = load_tool("validate_open_model_universe")
        paid = model_record(1)
        paid["cost_class"] = "paid"
        errors = validator.validate_document(registry_document([paid]))
        self.assertTrue(any("cost_class" in error or "zero-cost" in error for error in errors), errors)

    def test_secret_fields_and_credential_like_values_are_rejected(self):
        validator = load_tool("validate_open_model_universe")
        data = registry_document([model_record(1)])
        data["models"][0]["api_key"] = "sk-not-a-real-key"
        errors = validator.validate_document(data)
        self.assertTrue(any("credential" in error or "secret" in error for error in errors), errors)
        for leaked in (
            "ghp_abcdefghijklmnopqrstuvwxyz1234567890",
            "xoxb-1234567890-secret",
            "AKIAABCDEFGHIJKLMNOP",
            "https://user:password@example.invalid/model",
            "https://example.invalid/model?access_token=secret-value",
        ):
            candidate = registry_document([model_record(2)])
            candidate["models"][0]["official_upstream"] = leaked
            self.assertTrue(validator.validate_document(candidate), leaked)

    def test_unapproved_runtime_state_and_authority_claim_are_rejected(self):
        validator = load_tool("validate_open_model_universe")
        row = model_record(1)
        row["lifecycle_state"] = "RUNNING"
        row["license_verified"] = True
        row["authority"] = True
        errors = validator.validate_document(registry_document([row]))
        self.assertTrue(any("runtime state" in error for error in errors), errors)
        self.assertTrue(any("model authority" in error for error in errors), errors)

    def test_duplicate_model_id_is_rejected_even_when_variant_identity_differs(self):
        validator = load_tool("validate_open_model_universe")
        first = model_record(1)
        second = model_record(2)
        second["model_id"] = first["model_id"]
        errors = validator.validate_document(registry_document([first, second]))
        self.assertTrue(any("duplicate model_id" in error for error in errors), errors)

    def test_invalid_provenance_and_dates_fail_closed(self):
        validator = load_tool("validate_open_model_universe")
        row = model_record(1)
        row["official_upstream"] = "https://"
        row["release_date"] = "not-a-date"
        row["last_verified"] = "yesterday"
        errors = validator.validate_document(registry_document([row]))
        self.assertTrue(any("provenance URL" in error for error in errors), errors)
        self.assertTrue(any("not-a-date" in error or "date" in error for error in errors), errors)

    def test_v4_validator_executes_open_model_universe_validation(self):
        from AI_SKILL_LIBRARY.validate_v4 import validate_v4

        errors, _ = validate_v4(ROOT)
        self.assertFalse([error for error in errors if "Open Model Universe" in error], errors)


if __name__ == "__main__":
    unittest.main()
