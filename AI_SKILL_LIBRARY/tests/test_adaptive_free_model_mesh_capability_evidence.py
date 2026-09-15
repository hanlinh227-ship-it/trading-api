import json
import tempfile
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from AI_SKILL_LIBRARY.v4.tools.capability_evidence import (
    capability_evidence_state,
    index_evidence_records,
    load_capability_ledger,
)


ROOT = Path(__file__).resolve().parents[2]
NOW = "2026-09-15T12:00:00Z"
SOURCE_SHA = "a" * 40


def candidate(*, declared=True, family="family-a"):
    capabilities = {}
    if declared:
        capabilities["coding"] = {
            "supported": True,
            "score": 0.77,
            "evidence": ["provider-declaration"],
            "verified_at": "2026-09-15T10:00:00Z",
        }
    return {
        "provider_id": "provider-a",
        "model_id": "model-a",
        "model_family": family,
        "capabilities": capabilities,
    }


def record(
    evidence_id="coding-bench-1",
    *,
    measured_at="2026-09-15T10:00:00Z",
    score=0.90,
    threshold=0.80,
    passed=True,
    family="family-a",
):
    return {
        "evidence_id": evidence_id,
        "provider_id": "provider-a",
        "model_id": "model-a",
        "model_family": family,
        "capability": "coding",
        "benchmark_id": "coding-bench",
        "benchmark_version": "1",
        "score": score,
        "threshold": threshold,
        "passed": passed,
        "measured_at": measured_at,
        "source_sha": SOURCE_SHA,
        "environment": {"protocol": "openai_compatible", "runtime": "test"},
        "provenance": {"kind": "benchmark", "reference": "fixture:coding-bench"},
    }


class CapabilityEvidenceContractTests(unittest.TestCase):
    def test_checkpoint_resolves_capability_evidence_paths(self):
        checkpoint = json.loads((ROOT / "AI_SKILL_LIBRARY/checkpoint.json").read_text(encoding="utf-8"))
        expected = {
            "model_mesh_capability_evidence_path": "AI_SKILL_LIBRARY/v4/model_mesh/capability_evidence.json",
            "model_mesh_capability_evidence_schema_path": "AI_SKILL_LIBRARY/v4/schemas/capability_evidence_ledger.schema.json",
            "model_mesh_active_index_schema_path": "AI_SKILL_LIBRARY/v4/schemas/model_mesh_active_candidate_index.schema.json",
            "model_mesh_active_index_compiler_path": "AI_SKILL_LIBRARY/v4/tools/compile_model_mesh_active_index.py",
            "model_mesh_active_index_validator_path": "AI_SKILL_LIBRARY/v4/tools/validate_model_mesh_active_index.py",
        }
        for key, rel in expected.items():
            self.assertEqual(checkpoint.get(key), rel)
        for key in (
            "model_mesh_capability_evidence_path",
            "model_mesh_capability_evidence_schema_path",
            "model_mesh_active_index_schema_path",
        ):
            self.assertTrue((ROOT / checkpoint[key]).is_file(), checkpoint[key])

    def test_evidence_rollout_policy_is_non_authoritative_and_off_by_default(self):
        config = yaml.safe_load((ROOT / "AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml").read_text(encoding="utf-8"))
        policy = config["capability_evidence"]
        self.assertFalse(policy["routing_authority"])
        self.assertFalse(policy["hard_gate"]["default_enabled"])
        self.assertEqual(policy["hard_gate"]["min_verified_candidates"], 2)
        self.assertEqual(policy["hard_gate"]["min_coverage_ratio"], 0.80)
        self.assertEqual(policy["default_freshness_hours"], 168)

    def test_empty_canonical_ledger_is_schema_valid_and_authority_free(self):
        schema = json.loads((ROOT / "AI_SKILL_LIBRARY/v4/schemas/capability_evidence_ledger.schema.json").read_text(encoding="utf-8"))
        ledger = json.loads((ROOT / "AI_SKILL_LIBRARY/v4/model_mesh/capability_evidence.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        errors = list(Draft202012Validator(schema).iter_errors(ledger))
        self.assertEqual(errors, [])
        self.assertEqual(ledger["version"], 1)
        self.assertFalse(ledger["routing_authority"])
        self.assertFalse(ledger["reasoning_authority"])
        self.assertEqual(ledger["records"], [])

    def test_active_index_schema_accepts_only_known_evidence_states(self):
        schema = json.loads((ROOT / "AI_SKILL_LIBRARY/v4/schemas/model_mesh_active_candidate_index.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        state_schema = schema["$defs"]["capabilityEvidenceState"]["properties"]["state"]
        self.assertEqual(set(state_schema["enum"]), {"VERIFIED", "PROVISIONAL", "UNKNOWN", "STALE"})


class CapabilityEvidenceStateTests(unittest.TestCase):
    def _map(self, *records):
        return index_evidence_records({
            "version": 1,
            "routing_authority": False,
            "reasoning_authority": False,
            "records": list(records),
        })

    def test_fresh_passing_measured_record_is_verified(self):
        state = capability_evidence_state(candidate(), "coding", self._map(record()), now=NOW, freshness_hours=168)
        self.assertEqual(state["state"], "VERIFIED")
        self.assertEqual(state["score"], 0.90)
        self.assertEqual(state["evidence_ids"], ["coding-bench-1"])
        self.assertEqual(state["measured_at"], "2026-09-15T10:00:00Z")

    def test_fresh_record_below_threshold_is_provisional(self):
        state = capability_evidence_state(candidate(), "coding", self._map(record(score=0.60, threshold=0.80, passed=False)), now=NOW, freshness_hours=168)
        self.assertEqual(state["state"], "PROVISIONAL")
        self.assertEqual(state["evidence_ids"], ["coding-bench-1"])

    def test_provider_declaration_without_measurement_is_only_provisional(self):
        state = capability_evidence_state(candidate(declared=True), "coding", {}, now=NOW, freshness_hours=168)
        self.assertEqual(state["state"], "PROVISIONAL")
        self.assertEqual(state["score"], 0.77)
        self.assertEqual(state["evidence_ids"], [])
        self.assertIsNone(state["measured_at"])

    def test_no_measurement_and_no_declaration_is_unknown(self):
        state = capability_evidence_state(candidate(declared=False), "coding", {}, now=NOW, freshness_hours=168)
        self.assertEqual(state["state"], "UNKNOWN")
        self.assertEqual(state["score"], 0.0)

    def test_old_passing_measurement_is_stale(self):
        state = capability_evidence_state(candidate(), "coding", self._map(record(measured_at="2026-08-01T10:00:00Z")), now=NOW, freshness_hours=168)
        self.assertEqual(state["state"], "STALE")
        self.assertEqual(state["evidence_ids"], ["coding-bench-1"])

    def test_family_mismatch_is_ignored(self):
        state = capability_evidence_state(candidate(family="family-a"), "coding", self._map(record(family="family-b")), now=NOW, freshness_hours=168)
        self.assertEqual(state["state"], "PROVISIONAL")
        self.assertEqual(state["evidence_ids"], [])

    def test_malformed_timestamp_never_verifies(self):
        state = capability_evidence_state(candidate(), "coding", self._map(record(measured_at="not-a-time")), now=NOW, freshness_hours=168)
        self.assertEqual(state["state"], "PROVISIONAL")

    def test_future_timestamp_never_verifies(self):
        state = capability_evidence_state(candidate(), "coding", self._map(record(measured_at="2026-09-16T10:00:00Z")), now=NOW, freshness_hours=168)
        self.assertEqual(state["state"], "PROVISIONAL")
        self.assertEqual(state["evidence_ids"], [])

    def test_strict_loader_rejects_extra_secret_shaped_field(self):
        ledger = {
            "version": 1,
            "routing_authority": False,
            "reasoning_authority": False,
            "records": [{**record(), "api_key": "SHOULD_NOT_BE_ACCEPTED"}],
        }
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "ledger.json"
            path.write_text(json.dumps(ledger), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_capability_ledger(ROOT, path)


if __name__ == "__main__":
    unittest.main()
