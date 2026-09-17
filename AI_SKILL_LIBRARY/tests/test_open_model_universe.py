from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "AI_SKILL_LIBRARY/v4/tools"
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
    revision = f"{index + 1:040x}"
    digest = f"{index + 1:064x}"
    model_id = f"example/model-{index}"
    family = f"family-{index}"
    return {
        "model_id": model_id,
        "family": family,
        "variant": "base",
        "base_model": model_id,
        "quantization": "none",
        "runtime_build": "unresolved",
        "official_upstream": "https://example.invalid/official",
        "weights_source": f"https://example.invalid/{revision}/weights.gguf",
        "upstream_revision": revision,
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
        "offline_eligible": "unknown",
        "lineage": {
            "source_model_id": model_id,
            "source_revision": None,
            "conversion_owner": "unknown",
            "conversion_verified": False,
        },
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
        "artifact_identity": {
            "model_id": model_id,
            "family": family,
            "variant": "base",
            "immutable_revision": revision,
            "sha256": digest,
            "size_bytes": 1,
            "format": "gguf",
            "quantization": "none",
        },
        "admission_evidence": {
            "license_verified": False,
            "provenance_verified": False,
            "safe_format_verified": False,
            "pickle_safe": "unknown",
            "trust_remote_code_required": "unknown",
            "custom_code_required": "unknown",
            "malware_scan_status": "unknown",
            "isolated_first_load_required": True,
            "first_load_egress_allowed": False,
            "quarantine_status": "quarantined",
        },
        "model_mesh_local_candidate_eligible": False,
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
        "integration": {
            "brain_authority": "GITHUB_BRAIN_V4",
            "routed_by": "task_router",
            "model_selection_authority": "model_mesh",
            "activation_source": "AI_SKILL_LIBRARY/v4/model_mesh/active.json",
            "registry_membership_is_activation": False,
            "ingress_hardcodes_model": False,
            "runtime_residency_contract": {
                "owner": "claude_local_runtime",
                "governance_state_source": "Open Model Universe",
                "open_model_universe_has_runtime_residency_authority": False,
            },
        },
        "models": models or [],
    }


class OpenModelUniverseContractTests(unittest.TestCase):
    def test_canonical_ci_runs_the_open_model_universe_validator(self):
        text = CI_VALIDATE.read_text(encoding="utf-8")
        self.assertIn("AI_SKILL_LIBRARY/v4/tools/validate_open_model_universe.py", text)

    def test_checked_in_registry_is_authority_free_and_not_active(self):
        data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(data["registry_id"], "OPEN_MODEL_UNIVERSE")
        # Not a count. How many models are registered is an operational fact
        # that changes every time one is admitted; what must hold is that
        # registration confers nothing. Asserting "exactly 1" made admitting a
        # second model look like a contract breach.
        self.assertTrue(data["models"])
        self.assertFalse(data["policy"]["registry_implies_activation"])
        self.assertTrue(all(value is False for value in data["authority"].values()))

    def test_mesh_eligibility_is_never_granted_without_justifying_evidence(self):
        """The invariant behind "not active": eligibility must be earned.

        This previously asserted the one checked-in row was ineligible, which
        captured that row's state at the time rather than the rule. Eligibility
        is a governance decision that can legitimately be granted, so the rule
        worth enforcing is that it is never granted for free: a mesh-eligible
        model must carry either a passing malware scan or a valid, digest-bound
        operator risk acceptance recording what was not checked.
        """
        data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
        for model in data["models"]:
            with self.subTest(model_id=model["model_id"]):
                if not model.get("model_mesh_local_candidate_eligible"):
                    continue
                evidence = model.get("admission_evidence") or {}
                acceptance = model.get("operator_risk_acceptance") or {}
                scanned = evidence.get("malware_scan_status") == "pass"
                accepted = (
                    acceptance.get("scope") == "single_artifact"
                    and acceptance.get("artifact_sha256")
                    == (model.get("artifact_identity") or {}).get("sha256")
                    and "malware_scan_status" in (acceptance.get("covers") or [])
                    and bool(acceptance.get("accepted_by"))
                    and bool(acceptance.get("missing_evidence"))
                )
                self.assertTrue(
                    scanned or accepted,
                    f"{model['model_id']} is mesh-eligible with neither a passing malware "
                    f"scan nor a valid operator risk acceptance",
                )
                # An acceptance must never be recorded as though it were a scan.
                if accepted and not scanned:
                    self.assertEqual(evidence.get("malware_scan_status"), "not_run")
                    self.assertIs(acceptance.get("is_a_scan_result"), False)

    def test_lifecycle_vocabulary_is_governance_only(self):
        universe = load_tool("open_model_universe")
        required = {
            "DISCOVERED", "QUARANTINED", "QUARANTINED_UPDATE", "REGISTERED",
            "APPROVED", "AVAILABLE", "BLOCKED", "SUPERSEDED", "RETIRED",
        }
        self.assertEqual(universe.LIFECYCLE_STATES, required)
        self.assertTrue(universe.validate_transition("REGISTERED", "APPROVED"))
        self.assertTrue(universe.validate_transition("APPROVED", "AVAILABLE"))
        self.assertFalse(universe.validate_transition("AVAILABLE", "RUNNING"))
        self.assertFalse(universe.validate_transition("QUARANTINED", "RUNNING"))

    def test_valid_empty_and_large_registry_documents_pass(self):
        validator = load_tool("validate_open_model_universe")
        self.assertEqual(validator.validate_document(registry_document()), [])
        large = registry_document([model_record(index) for index in range(100)])
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

    def test_secret_fields_and_credential_like_values_are_rejected(self):
        validator = load_tool("validate_open_model_universe")
        data = registry_document([model_record(1)])
        data["models"][0]["api_key"] = "sk-not-a-real-key"
        errors = validator.validate_document(data)
        self.assertTrue(any("credential" in error or "secret" in error for error in errors), errors)

    def test_runtime_state_and_authority_claim_are_rejected(self):
        validator = load_tool("validate_open_model_universe")
        row = model_record(1)
        row["lifecycle_state"] = "RUNNING"
        row["authority"] = True
        errors = validator.validate_document(registry_document([row]))
        self.assertTrue(any("runtime state" in error or "schema" in error for error in errors), errors)
        self.assertTrue(any("model authority" in error for error in errors), errors)

    def test_v4_validator_executes_open_model_universe_validation(self):
        from AI_SKILL_LIBRARY.validate_v4 import validate_v4

        errors, _ = validate_v4(ROOT)
        self.assertFalse([error for error in errors if "Open Model Universe" in error], errors)


if __name__ == "__main__":
    unittest.main()
