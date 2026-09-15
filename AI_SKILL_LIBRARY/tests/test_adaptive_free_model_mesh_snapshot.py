import json
import tempfile
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.tools.compile_model_mesh_snapshot import compile_snapshot
from AI_SKILL_LIBRARY.v4.tools.model_mesh import normalize_candidate
from AI_SKILL_LIBRARY.v4.tools.validate_model_mesh_snapshot import validate_snapshot


ROOT = Path(__file__).resolve().parents[2]
SOURCE_SHA = "a" * 40
GENERATED_AT = "2026-09-15T06:00:00Z"
OBSERVED_AT = "2026-09-15T05:55:00Z"


class AdaptiveFreeModelMeshSnapshotTests(unittest.TestCase):
    def _candidate(
        self,
        provider: str,
        model: str,
        family: str,
        *,
        free_status: str = "recurring",
        provider_class: str = "F1",
        benchmarked: bool = True,
    ) -> dict:
        raw = {
            "provider_class": provider_class,
            "model_id": model,
            "model_family": family,
            "model_variant": "hosted",
            "endpoint_family": "openai_compatible",
            "free_status": free_status,
            "free_verified_at": OBSERVED_AT if free_status in {"recurring", "limited_time", "trial_credit", "account_specific"} else None,
            "quota_scope": "account",
            "quota_dimensions": ["rpm", "tpm"],
            "reset_semantics": "minute",
            "capabilities": {
                "text_reasoning": {
                    "supported": True,
                    "score": 0.88 if benchmarked else 0.0,
                    "evidence": ["bench:reasoning"] if benchmarked else [],
                    "verified_at": OBSERVED_AT if benchmarked else None,
                }
            },
            "context_window": 131072,
            "privacy_class": "public_safe",
            "data_training_allowed_by_provider": False,
            "retention_policy": "verified public workload policy",
            "usage_terms": "production_allowed",
            "health": "healthy",
            "latency_ema_ms": 150.0,
            "success_rate_ema": 0.98,
            "quality_scores": {"core": 0.86} if benchmarked else {},
            "last_benchmark_at": OBSERVED_AT if benchmarked else None,
            "source_evidence": [f"evidence:{provider}:{model}"],
        }
        return normalize_candidate(provider, raw, observed_at=OBSERVED_AT)

    def test_checkpoint_resolves_exact_model_mesh_paths(self):
        checkpoint = json.loads((ROOT / "AI_SKILL_LIBRARY/checkpoint.json").read_text(encoding="utf-8"))
        expected = {
            "model_mesh_policy_path": "AI_SKILL_LIBRARY/v4/model_mesh/policy.yaml",
            "model_mesh_provider_registry_path": "AI_SKILL_LIBRARY/v4/model_mesh/providers.yaml",
            "model_mesh_domain_capabilities_path": "AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml",
            "model_mesh_snapshot_schema_path": "AI_SKILL_LIBRARY/v4/schemas/model_mesh_snapshot.schema.json",
            "model_mesh_snapshot_compiler_path": "AI_SKILL_LIBRARY/v4/tools/compile_model_mesh_snapshot.py",
            "model_mesh_snapshot_validator_path": "AI_SKILL_LIBRARY/v4/tools/validate_model_mesh_snapshot.py",
        }
        for key, value in expected.items():
            self.assertEqual(checkpoint.get(key), value)
            self.assertTrue((ROOT / value).is_file(), value)

    def test_ci_and_release_integrate_model_mesh_contracts(self):
        ci_text = (ROOT / "AI_SKILL_LIBRARY/v4/tools/ci_validate.py").read_text(encoding="utf-8")
        self.assertIn('"AI_SKILL_LIBRARY/v4/tools/validate_model_mesh.py"', ci_text)
        self.assertIn("compile_model_mesh_snapshot.py", ci_text)
        self.assertIn("validate_model_mesh_snapshot.py", ci_text)

        release_text = (ROOT / "AI_SKILL_LIBRARY/v4/tools/release.py").read_text(encoding="utf-8")
        required_release_files = (
            "AI_SKILL_LIBRARY/v4/stable/reliability.yaml",
            "AI_SKILL_LIBRARY/v4/stable/reputation.yaml",
            "AI_SKILL_LIBRARY/v4/model_mesh/policy.yaml",
            "AI_SKILL_LIBRARY/v4/model_mesh/providers.yaml",
            "AI_SKILL_LIBRARY/v4/model_mesh/discovery.yaml",
            "AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml",
            "AI_SKILL_LIBRARY/v4/model_mesh/upstreams.yaml",
        )
        for rel in required_release_files:
            self.assertIn(rel, release_text)

    def test_snapshot_compile_is_deterministic_filtered_and_secret_free(self):
        eligible_b = self._candidate("provider-b", "model-b", "family-b")
        eligible_a = self._candidate("provider-a", "model-a", "family-a")
        unknown = self._candidate("provider-u", "model-u", "family-u", free_status="unknown")
        paid = self._candidate("provider-p", "model-p", "family-p", free_status="paid")
        quarantined = self._candidate("provider-q", "model-q", "family-q", provider_class="Q")
        no_benchmark = self._candidate("provider-n", "model-n", "family-n", benchmarked=False)

        # Simulate hostile/untrusted discovery payload fields. Compiler must whitelist normalized fields.
        eligible_b["api_key"] = "SECRET_DO_NOT_COPY"
        eligible_b["authorization"] = "Bearer SECRET_DO_NOT_COPY"
        report = {
            "state": "quarantine",
            "routing_authority": False,
            "stable_mutation": False,
            "candidates": [eligible_b, unknown, paid, eligible_a, quarantined, no_benchmark],
        }

        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            candidates_path = temp_root / "candidates.json"
            output_a = temp_root / "snapshot-a.json"
            output_b = temp_root / "snapshot-b.json"
            candidates_path.write_text(json.dumps(report), encoding="utf-8")

            first = compile_snapshot(
                ROOT,
                source_sha=SOURCE_SHA,
                candidates_path=candidates_path,
                output=output_a,
                generated_at=GENERATED_AT,
            )
            second = compile_snapshot(
                ROOT,
                source_sha=SOURCE_SHA,
                candidates_path=candidates_path,
                output=output_b,
                generated_at=GENERATED_AT,
            )

            self.assertEqual(first, second)
            self.assertEqual(output_a.read_text(encoding="utf-8"), output_b.read_text(encoding="utf-8"))
            self.assertEqual(first["schema_version"], 1)
            self.assertEqual(first["source_sha"], SOURCE_SHA)
            self.assertEqual(first["mode"], "FREE_ONLY")
            self.assertFalse(first["routing_authority"])
            self.assertFalse(first["reasoning_authority"])
            self.assertEqual(
                [(row["provider_id"], row["model_id"]) for row in first["models"]],
                [("provider-a", "model-a"), ("provider-b", "model-b")],
            )

            serialized = output_a.read_text(encoding="utf-8").lower()
            for forbidden in ("secret_do_not_copy", "api_key", "authorization", "bearer secret"):
                self.assertNotIn(forbidden, serialized)

            errors = validate_snapshot(ROOT, output_a, expected_source_sha=SOURCE_SHA)
            self.assertEqual(errors, [])

    def test_snapshot_validator_rejects_wrong_source_sha_and_paid_model(self):
        paid = self._candidate("provider-p", "model-p", "family-p", free_status="paid")
        snapshot = {
            "schema_version": 1,
            "source_sha": SOURCE_SHA,
            "mode": "FREE_ONLY",
            "routing_authority": False,
            "reasoning_authority": False,
            "generated_at": GENERATED_AT,
            "models": [paid],
        }
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "snapshot.json"
            path.write_text(json.dumps(snapshot), encoding="utf-8")
            errors = validate_snapshot(ROOT, path, expected_source_sha="b" * 40)
            self.assertTrue(any("source_sha" in item for item in errors))
            self.assertTrue(any("FREE_ONLY" in item or "free" in item.lower() for item in errors))


if __name__ == "__main__":
    unittest.main()
