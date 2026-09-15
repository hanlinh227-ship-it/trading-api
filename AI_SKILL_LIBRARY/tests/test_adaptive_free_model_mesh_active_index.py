import json
import tempfile
import unittest
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.tools.compile_model_mesh_active_index import compile_active_index
from AI_SKILL_LIBRARY.v4.tools.compile_model_mesh_policy import compile_policy
from AI_SKILL_LIBRARY.v4.tools.validate_model_mesh_active_index import validate_active_index


ROOT = Path(__file__).resolve().parents[2]
SOURCE_SHA = "a" * 40
GENERATED_AT = "2026-09-15T12:00:00Z"


def model(provider, model_id, family, *, coding_score=0.90):
    return {
        "provider_id": provider,
        "provider_class": "F1",
        "model_id": model_id,
        "model_family": family,
        "model_variant": "hosted",
        "endpoint_family": "openai_compatible",
        "free_status": "recurring",
        "free_verified_at": "2026-09-15T10:00:00Z",
        "observed_at": "2026-09-15T10:00:00Z",
        "quota_scope": "account",
        "quota_dimensions": ["rpm"],
        "reset_semantics": "minute",
        "capabilities": {
            "coding": {"supported": True, "score": coding_score, "evidence": ["provider:declared"], "verified_at": "2026-09-15T10:00:00Z"},
            "text_reasoning": {"supported": True, "score": 0.85, "evidence": ["provider:declared"], "verified_at": "2026-09-15T10:00:00Z"},
        },
        "context_window": 131072,
        "privacy_class": "public_safe",
        "data_training_allowed_by_provider": False,
        "retention_policy": "verified",
        "usage_terms": "production_allowed",
        "health": "healthy",
        "latency_ema_ms": 100.0,
        "success_rate_ema": 0.98,
        "quality_scores": {"engineering": 0.90, "core": 0.88},
        "last_benchmark_at": "2026-09-15T10:00:00Z",
        "source_evidence": [f"fixture:{provider}:{model_id}"],
    }


def evidence(provider, model_id, family, capability, evidence_id):
    return {
        "evidence_id": evidence_id,
        "provider_id": provider,
        "model_id": model_id,
        "model_family": family,
        "capability": capability,
        "benchmark_id": f"bench-{capability}",
        "benchmark_version": "1",
        "score": 0.92,
        "threshold": 0.80,
        "passed": True,
        "measured_at": "2026-09-15T10:00:00Z",
        "source_sha": SOURCE_SHA,
        "environment": {"protocol": "openai_compatible", "runtime": "test"},
        "provenance": {"kind": "benchmark", "reference": f"fixture:{evidence_id}"},
    }


class ActiveCandidateIndexTests(unittest.TestCase):
    def _write_inputs(self, root: Path, models, records, *, capabilities=None):
        snapshot = {
            "schema_version": 1,
            "source_sha": SOURCE_SHA,
            "mode": "FREE_ONLY",
            "routing_authority": False,
            "reasoning_authority": False,
            "generated_at": GENERATED_AT,
            "models": list(models),
        }
        ledger = {"version": 1, "routing_authority": False, "reasoning_authority": False, "records": list(records)}
        snapshot_path = root / "snapshot.json"
        ledger_path = root / "ledger.json"
        capabilities_path = root / "domain_capabilities.yaml"
        snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
        ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
        if capabilities is None:
            capabilities = yaml.safe_load((ROOT / "AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml").read_text(encoding="utf-8"))
        capabilities_path.write_text(yaml.safe_dump(capabilities, sort_keys=False), encoding="utf-8")
        return snapshot_path, ledger_path, capabilities_path

    def test_compile_is_deterministic_and_cannot_create_index_only_model(self):
        rows = [model("p2", "m2", "f2"), model("p1", "m1", "f1")]
        records = [
            evidence("p1", "m1", "f1", "coding", "e1"),
            evidence("ghost", "ghost-model", "ghost-family", "coding", "ghost-evidence"),
        ]
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            snapshot_path, ledger_path, capabilities_path = self._write_inputs(temp_root, rows, records)
            output_a = temp_root / "index-a.json"
            output_b = temp_root / "index-b.json"
            first = compile_active_index(ROOT, source_sha=SOURCE_SHA, snapshot_path=snapshot_path, ledger_path=ledger_path, capabilities_path=capabilities_path, output=output_a, generated_at=GENERATED_AT)
            second = compile_active_index(ROOT, source_sha=SOURCE_SHA, snapshot_path=snapshot_path, ledger_path=ledger_path, capabilities_path=capabilities_path, output=output_b, generated_at=GENERATED_AT)
            self.assertEqual(first, second)
            self.assertEqual(output_a.read_text(encoding="utf-8"), output_b.read_text(encoding="utf-8"))
            self.assertEqual([row["candidate_key"] for row in first["entries"]], ["p1:m1", "p2:m2"])
            self.assertNotIn("ghost:ghost-model", output_a.read_text(encoding="utf-8"))
            self.assertEqual(first["entries"][0]["capability_evidence"]["coding"]["state"], "VERIFIED")

    def test_index_is_bounded_by_admitted_snapshot_not_ledger_size(self):
        rows = [model("p1", "m1", "f1"), model("p2", "m2", "f2"), model("p3", "m3", "f3")]
        records = [evidence(f"ghost-{i}", f"ghost-model-{i}", f"ghost-family-{i}", "coding", f"ghost-{i}") for i in range(100)]
        records.append(evidence("p1", "m1", "f1", "coding", "admitted-evidence"))
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            snapshot_path, ledger_path, capabilities_path = self._write_inputs(temp_root, rows, records)
            output = temp_root / "index.json"
            index = compile_active_index(ROOT, source_sha=SOURCE_SHA, snapshot_path=snapshot_path, ledger_path=ledger_path, capabilities_path=capabilities_path, output=output, generated_at=GENERATED_AT)
            self.assertEqual(len(index["entries"]), 3)
            self.assertEqual({row["candidate_key"] for row in index["entries"]}, {"p1:m1", "p2:m2", "p3:m3"})
            self.assertNotIn("ghost-model-", output.read_text(encoding="utf-8"))

    def test_coverage_requires_two_verified_and_eighty_percent(self):
        rows = [model("p1", "m1", "f1"), model("p2", "m2", "f2")]
        records = [
            evidence("p1", "m1", "f1", "coding", "e1"),
            evidence("p2", "m2", "f2", "coding", "e2"),
        ]
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            snapshot_path, ledger_path, capabilities_path = self._write_inputs(temp_root, rows, records)
            output = temp_root / "index.json"
            index = compile_active_index(ROOT, source_sha=SOURCE_SHA, snapshot_path=snapshot_path, ledger_path=ledger_path, capabilities_path=capabilities_path, output=output, generated_at=GENERATED_AT)
            row = index["coverage"]["engineering.coding"]
            self.assertEqual(row["eligible_candidates"], 2)
            self.assertEqual(row["verified_candidates"], 2)
            self.assertEqual(row["coverage_ratio"], 1.0)
            self.assertTrue(row["gate_eligible"])
            self.assertFalse(row["requested_enabled"])
            self.assertFalse(row["enabled"])

    def test_requested_gate_before_coverage_fails_closed(self):
        rows = [model("p1", "m1", "f1"), model("p2", "m2", "f2")]
        records = [evidence("p1", "m1", "f1", "coding", "e1")]
        config = yaml.safe_load((ROOT / "AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml").read_text(encoding="utf-8"))
        config["capability_evidence"]["hard_gate"]["overrides"] = {"engineering.coding": True}
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            snapshot_path, ledger_path, capabilities_path = self._write_inputs(temp_root, rows, records, capabilities=config)
            with self.assertRaisesRegex(ValueError, "CAPABILITY_HARD_GATE_COVERAGE_INSUFFICIENT"):
                compile_active_index(ROOT, source_sha=SOURCE_SHA, snapshot_path=snapshot_path, ledger_path=ledger_path, capabilities_path=capabilities_path, output=temp_root / "index.json", generated_at=GENERATED_AT)

    def test_validator_rejects_source_drift_and_index_only_identity(self):
        rows = [model("p1", "m1", "f1")]
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            snapshot_path, ledger_path, capabilities_path = self._write_inputs(temp_root, rows, [])
            output = temp_root / "index.json"
            index = compile_active_index(ROOT, source_sha=SOURCE_SHA, snapshot_path=snapshot_path, ledger_path=ledger_path, capabilities_path=capabilities_path, output=output, generated_at=GENERATED_AT)
            index["source_sha"] = "b" * 40
            index["entries"].append({
                "candidate_key": "ghost:model",
                "provider_id": "ghost",
                "model_id": "model",
                "model_family": "ghost-family",
                "capability_evidence": {},
            })
            output.write_text(json.dumps(index), encoding="utf-8")
            errors = validate_active_index(ROOT, output, snapshot_path=snapshot_path, expected_source_sha=SOURCE_SHA)
            self.assertTrue(any("source_sha" in item for item in errors))
            self.assertTrue(any("not present in admitted snapshot" in item for item in errors))

    def test_validator_does_not_treat_prompt_media_capability_as_a_secret_key(self):
        rows = [model("p1", "m1", "f1")]
        config = yaml.safe_load((ROOT / "AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            snapshot_path, ledger_path, capabilities_path = self._write_inputs(temp_root, rows, [], capabilities=config)
            output = temp_root / "index.json"
            index = compile_active_index(ROOT, source_sha=SOURCE_SHA, snapshot_path=snapshot_path, ledger_path=ledger_path, capabilities_path=capabilities_path, output=output, generated_at=GENERATED_AT)
            self.assertIn("prompt_media", index["entries"][0]["capability_evidence"])
            self.assertEqual(validate_active_index(ROOT, output, snapshot_path=snapshot_path, expected_source_sha=SOURCE_SHA), [])

    def test_checkpoint_compiler_and_validator_paths_exist_after_task_three(self):
        checkpoint = json.loads((ROOT / "AI_SKILL_LIBRARY/checkpoint.json").read_text(encoding="utf-8"))
        for key in ("model_mesh_active_index_compiler_path", "model_mesh_active_index_validator_path"):
            self.assertTrue((ROOT / checkpoint[key]).is_file(), checkpoint[key])

    def test_compiled_policy_carries_phase_a_evidence_rollout_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "policy.json"
            contract = compile_policy(
                ROOT,
                policy_path=Path("AI_SKILL_LIBRARY/v4/model_mesh/policy.yaml"),
                capabilities_path=Path("AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml"),
                output=output,
            )
            evidence_policy = contract["capability_evidence"]
            self.assertFalse(evidence_policy["routing_authority"])
            self.assertEqual(evidence_policy["default_freshness_hours"], 168)
            self.assertFalse(evidence_policy["hard_gate"]["default_enabled"])
            self.assertEqual(evidence_policy["hard_gate"]["min_verified_candidates"], 2)
            self.assertEqual(evidence_policy["hard_gate"]["min_coverage_ratio"], 0.80)
            self.assertEqual(evidence_policy["hard_gate"]["overrides"], {})


if __name__ == "__main__":
    unittest.main()
