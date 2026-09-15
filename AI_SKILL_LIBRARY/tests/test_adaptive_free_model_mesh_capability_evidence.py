import json
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]


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
            self.assertTrue((ROOT / rel).is_file(), rel)

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


if __name__ == "__main__":
    unittest.main()
