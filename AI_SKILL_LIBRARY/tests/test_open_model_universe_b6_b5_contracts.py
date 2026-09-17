from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
V4 = ROOT / "AI_SKILL_LIBRARY/v4"
SCHEMA_PATH = V4 / "schemas/open_model_universe.schema.json"
REGISTRY_PATH = V4 / "open_model_universe/registry.yaml"
ADMISSION_POLICY_PATH = V4 / "open_model_universe/admission_policy.yaml"
VALIDATOR_PATH = V4 / "tools/validate_open_model_universe.py"

GOVERNANCE_STATES = {
    "DISCOVERED",
    "QUARANTINED",
    "QUARANTINED_UPDATE",
    "REGISTERED",
    "APPROVED",
    "AVAILABLE",
    "BLOCKED",
    "SUPERSEDED",
    "RETIRED",
}
RUNTIME_ONLY_STATES = {"DOWNLOADING", "CACHED", "WARM", "RUNNING", "SLEEPING", "DEGRADED", "BROKEN", "EVICTED"}
ARTIFACT_FIELDS = {
    "model_id",
    "family",
    "variant",
    "immutable_revision",
    "sha256",
    "size_bytes",
    "format",
    "quantization",
}
ADMISSION_FIELDS = {
    "license_verified",
    "provenance_verified",
    "safe_format_verified",
    "pickle_safe",
    "trust_remote_code_required",
    "custom_code_required",
    "malware_scan_status",
    "isolated_first_load_required",
    "first_load_egress_allowed",
    "quarantine_status",
}


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_open_model_universe", VALIDATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GovernanceRuntimeSeparationTests(unittest.TestCase):
    def test_registry_owns_governance_states_only(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        states = set(schema["$defs"]["model"]["properties"]["lifecycle_state"]["enum"])
        self.assertEqual(states, GOVERNANCE_STATES)
        self.assertTrue(states.isdisjoint(RUNTIME_ONLY_STATES))

    def test_runtime_residency_is_explicitly_claude_owned(self):
        registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
        contract = registry["integration"]["runtime_residency_contract"]
        self.assertEqual(contract["owner"], "claude_local_runtime")
        self.assertFalse(contract["open_model_universe_has_runtime_residency_authority"])
        self.assertEqual(contract["governance_state_source"], "Open Model Universe")


class ArtifactIdentityTests(unittest.TestCase):
    def test_artifact_identity_is_required_and_lossless(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        artifact = schema["$defs"]["artifact_identity"]
        self.assertEqual(set(artifact["required"]), ARTIFACT_FIELDS)
        self.assertFalse(artifact["additionalProperties"])

    def test_validator_rejects_identity_drift(self):
        validator = load_validator()
        registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
        model = deepcopy(registry["models"][0])
        model["artifact_identity"]["model_id"] = "different/model"
        mutated = deepcopy(registry)
        mutated["models"] = [model]
        errors = validator.validate_document(mutated)
        self.assertTrue(any("artifact identity" in item.lower() and "model_id" in item for item in errors), errors)


class AdmissionContractTests(unittest.TestCase):
    def test_admission_evidence_schema_is_complete(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        admission = schema["$defs"]["admission_evidence"]
        self.assertEqual(set(admission["required"]), ADMISSION_FIELDS)
        self.assertFalse(admission["additionalProperties"])

    def test_unknown_critical_evidence_blocks_local_candidate(self):
        validator = load_validator()
        registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
        model = deepcopy(registry["models"][0])
        model["model_mesh_local_candidate_eligible"] = True
        model["admission_evidence"]["malware_scan_status"] = "unknown"
        mutated = deepcopy(registry)
        mutated["models"] = [model]
        errors = validator.validate_document(mutated)
        self.assertTrue(any("malware" in item.lower() or "admission" in item.lower() for item in errors), errors)

    def test_blocked_or_quarantined_model_never_enters_local_candidate_path(self):
        validator = load_validator()
        registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
        for state in ("BLOCKED", "QUARANTINED", "QUARANTINED_UPDATE"):
            with self.subTest(state=state):
                model = deepcopy(registry["models"][0])
                model["lifecycle_state"] = state
                model["model_mesh_local_candidate_eligible"] = True
                mutated = deepcopy(registry)
                mutated["models"] = [model]
                errors = validator.validate_document(mutated)
                self.assertTrue(any("candidate" in item.lower() or "admission" in item.lower() for item in errors), errors)

    def test_boundary_is_registry_then_admission_then_mesh_then_claude(self):
        policy = yaml.safe_load(ADMISSION_POLICY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            policy["flow"],
            ["open_model_universe", "admission_gate", "model_mesh_local_candidate", "claude_runtime_projection"],
        )
        self.assertFalse(policy["registry_membership_implies_activation"])
        self.assertFalse(policy["ingress_hardcodes_model"])
        self.assertEqual(policy["runtime_residency_owner"], "claude_local_runtime")


class FirstModelRecordTests(unittest.TestCase):
    def test_the_canonical_first_record_is_still_exactly_itself(self):
        """The original record must not drift as other models are added.

        This used to assert the registry held exactly one model, which stopped
        being a contract the moment Wave 1 admitted more. The part worth
        keeping is that the first real record's identity is unchanged - every
        field of it, because identity is a tuple and a single altered field
        makes it a different artifact.
        """
        registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
        model = next(m for m in registry["models"]
                     if m["model_id"] == "Qwen/Qwen3-0.6B-GGUF")
        self.assertEqual(model["artifact_identity"], {
            "model_id": "Qwen/Qwen3-0.6B-GGUF",
            "family": "Qwen3",
            "variant": "0.6B-Q8_0-GGUF",
            "immutable_revision": "1eaf4d9657fe65ad10a51eab76a8db5b363bddaa",
            "sha256": "9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031",
            "size_bytes": 639446688,
            "format": "gguf",
            "quantization": "Q8_0",
        })

    def test_every_record_carries_a_distinct_artifact_identity(self):
        """No model may be admitted on another's bytes."""
        registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
        digests = [m["artifact_identity"]["sha256"] for m in registry["models"]]
        self.assertEqual(len(digests), len(set(digests)))
        for model in registry["models"]:
            with self.subTest(model_id=model["model_id"]):
                self.assertEqual(len(model["artifact_identity"]["sha256"]), 64)

    def test_the_record_is_only_mesh_eligible_once_admission_justifies_it(self):
        """Governance state is a decision; what it must rest on is the rule.

        This previously pinned the row to ineligible and to a pre-approval
        lifecycle state, which captured where the record happened to be rather
        than what must be true of it. An operator can legitimately advance it,
        so the assertion is now on the justification instead.
        """
        registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
        model = registry["models"][0]
        if not model.get("model_mesh_local_candidate_eligible"):
            self.assertIn(
                model["lifecycle_state"],
                {"DISCOVERED", "QUARANTINED", "REGISTERED", "APPROVED"},
            )
            return

        self.assertEqual(model["lifecycle_state"], "AVAILABLE")
        evidence = model["admission_evidence"]
        for field in ("license_verified", "provenance_verified", "safe_format_verified",
                      "pickle_safe"):
            self.assertIs(evidence[field], True, field)
        for field in ("trust_remote_code_required", "custom_code_required"):
            self.assertIs(evidence[field], False, field)
        self.assertEqual(evidence["quarantine_status"], "clear")

        if evidence["malware_scan_status"] != "pass":
            # Accepted rather than scanned: the acceptance must be complete,
            # bound to these bytes, and must not overstate itself.
            acceptance = model["operator_risk_acceptance"]
            self.assertEqual(evidence["malware_scan_status"], "not_run")
            self.assertEqual(acceptance["scope"], "single_artifact")
            self.assertEqual(acceptance["artifact_sha256"], model["artifact_identity"]["sha256"])
            self.assertEqual(acceptance["covers"], ["malware_scan_status"])
            self.assertIs(acceptance["is_a_scan_result"], False)
            self.assertTrue(acceptance["accepted_by"])
            self.assertIn("signature_based_malware_scan", acceptance["missing_evidence"])


if __name__ == "__main__":
    unittest.main()
