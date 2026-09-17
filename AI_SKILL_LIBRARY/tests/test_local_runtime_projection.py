"""Projection tests.

The fixture below is a *synthetic* record. It is never written to
`registry.yaml` - population is the research lane's Phase D and needs real
provenance. To stop the fixture drifting away from the contract it stands for,
`SchemaFidelityTests` validates it against the checked-in
`open_model_universe.schema.json`, so a schema change breaks these tests rather
than silently invalidating them.
"""

import copy
import json
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.local_runtime.projection import (
    PRIVACY_CLASS_MAP,
    ProjectionResult,
    load_registry,
    project_record,
    project_registry,
)
from AI_SKILL_LIBRARY.v4.local_runtime.resources import GpuDevice, GpuVendor, HostFacts, ResourceSnapshot
from AI_SKILL_LIBRARY.v4.local_runtime.scheduler import AdmissionStatus, Privacy, Tri

ROOT = Path(__file__).resolve().parents[2]

# A schema-valid record standing in for a row the research lane has not yet
# published. Values are placeholders, not claims about any real model.
FIXTURE = {
    "model_id": "fixture-model-a",
    "family": "fixture-family",
    "variant": "8b-instruct",
    "base_model": "fixture-family-8b",
    "quantization": "Q4_K_M",
    "runtime_build": "fixture-build-1",
    "official_upstream": "https://example.invalid/fixture",
    "weights_source": "https://example.invalid/fixture/weights",
    "upstream_revision": "0123456789abcdef0123456789abcdef01234567",
    "release_date": "2026-01-01",
    "license_name": "Apache-2.0",
    "license_url": "https://example.invalid/license",
    "license_class": "permissive",
    "license_verified": True,
    "commercial_use": True,
    "self_hostable": True,
    "redistribution": "allowed",
    "derivative_training": "allowed",
    "open_weight": True,
    "api_required": False,
    "paid_token_required": False,
    "local_runtime_possible": True,
    "capabilities": {"text": 0.9, "code": 0.85, "vision": 0.1},
    "hardware_profile": {
        "minimum_ram_gb": 8,
        "recommended_ram_gb": 16,
        "minimum_vram_gb": None,
        "recommended_vram_gb": None,
        "quantization_options": ["Q4_K_M", "Q5_K_M"],
        "cpu_viable": True,
        "apple_silicon_viable": True,
    },
    "runtime_support": ["llama_cpp", "ollama"],
    "context_window": 32768,
    "benchmark_profile": "fixture-profile",
    "quality_class": "mid",
    "latency_class": "fast",
    "privacy_class": "local_only",
    "cost_class": "owned_hardware_zero_marginal",
    "lifecycle_state": "APPROVED",
    "health": "healthy",
    "last_verified": "2026-09-17T00:00:00Z",
    "authority": False,
    "source_evidence": ["https://example.invalid/fixture"],
}

HOST = HostFacts(system="Linux", machine="x86_64", release="6.8.0")


def record(**overrides):
    row = copy.deepcopy(FIXTURE)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(row.get(key), dict):
            row[key] = {**row[key], **value}
        else:
            row[key] = value
    return row


def snapshot(ram_total_mb=64_000, gpus=(), **kwargs):
    return ResourceSnapshot(
        host=HOST, cpu_logical=16, cpu_physical=8, ram_total_mb=ram_total_mb,
        ram_available_mb=kwargs.pop("ram_available_mb", 32_000),
        disk_total_mb=1_000_000, disk_free_mb=500_000, gpus=gpus, **kwargs,
    )


class SchemaFidelityTests(unittest.TestCase):
    def test_the_fixture_validates_against_the_checked_in_schema(self):
        from jsonschema import Draft202012Validator

        schema = json.loads(
            (ROOT / "AI_SKILL_LIBRARY/v4/schemas/open_model_universe.schema.json").read_text(encoding="utf-8")
        )
        model_schema = {**schema["$defs"]["model"], "$defs": schema["$defs"]}
        errors = sorted(Draft202012Validator(model_schema).iter_errors(FIXTURE), key=str)
        self.assertEqual(errors, [], "projection fixture no longer matches the registry schema")

    def test_the_canonical_registry_is_still_readable_and_empty(self):
        registry = load_registry(ROOT)
        self.assertEqual(registry["registry_id"], "OPEN_MODEL_UNIVERSE")
        self.assertEqual(registry["policy"]["paid_fallback"], "NO_PAID_FALLBACK")
        # Population is the research lane's Phase D. Nothing here adds rows.
        self.assertEqual(project_registry(registry), ())

    def test_every_privacy_class_maps_to_a_real_ceiling(self):
        for value in PRIVACY_CLASS_MAP.values():
            self.assertIsInstance(value, Privacy)


class AdmittedProjectionTests(unittest.TestCase):
    def test_a_complete_record_projects_to_a_profile(self):
        result = project_record(record(), snapshot=snapshot())
        self.assertIsNotNone(result.profile)
        self.assertTrue(result.placeable)
        self.assertEqual(result.profile.model_id, "fixture-model-a")
        self.assertEqual(result.profile.family, "fixture-family")
        self.assertEqual(result.profile.variant, "8b-instruct")
        self.assertEqual(result.profile.quantization, "Q4_K_M")

    def test_gigabytes_become_megabytes(self):
        profile = project_record(record(), snapshot=snapshot()).profile
        self.assertEqual(profile.ram_mb, 8 * 1024)
        self.assertEqual(profile.recommended_ram_mb, 16 * 1024)

    def test_the_pinned_revision_is_carried_through(self):
        profile = project_record(record(), snapshot=snapshot()).profile
        self.assertEqual(profile.revision, FIXTURE["upstream_revision"])

    def test_runtime_names_are_mapped_to_adapter_names(self):
        profile = project_record(record(), snapshot=snapshot()).profile
        self.assertEqual(profile.runtime_support, frozenset({"llama.cpp", "ollama"}))
        self.assertEqual(profile.runtime, "llama.cpp")

    def test_the_runtime_is_chosen_from_what_the_host_offers(self):
        profile = project_record(record(), snapshot=snapshot(), available_runtimes=["ollama"]).profile
        self.assertEqual(profile.runtime, "ollama")

    def test_high_scoring_capabilities_become_specializations(self):
        profile = project_record(record(), snapshot=snapshot()).profile
        self.assertEqual(profile.capabilities, frozenset({"text", "code", "vision"}))
        self.assertEqual(profile.specializations, frozenset({"text", "code"}))

    def test_privacy_class_maps_to_a_ceiling(self):
        profile = project_record(record(), snapshot=snapshot()).profile
        self.assertEqual(profile.max_privacy, Privacy.SECRET)

    def test_cpu_viability_is_three_valued(self):
        self.assertEqual(
            project_record(record(), snapshot=snapshot()).profile.cpu_viable, Tri.TRUE
        )
        unknown = record(hardware_profile={"cpu_viable": "unknown"})
        self.assertEqual(project_record(unknown, snapshot=snapshot()).profile.cpu_viable, Tri.UNKNOWN)

    def test_projection_is_deterministic(self):
        first = project_record(record(), snapshot=snapshot())
        second = project_record(record(), snapshot=snapshot())
        self.assertEqual(first.profile, second.profile)
        self.assertEqual(first.exclusion_reasons, second.exclusion_reasons)


class UnknownPreservationTests(unittest.TestCase):
    def test_a_null_ram_requirement_stays_none(self):
        result = project_record(record(hardware_profile={"minimum_ram_gb": None}), snapshot=snapshot())
        self.assertIsNone(result.profile.ram_mb)
        self.assertIn("hardware_profile.minimum_ram_gb", result.unknown_fields)

    def test_a_null_vram_requirement_means_no_accelerator_needed(self):
        profile = project_record(record(), snapshot=snapshot()).profile
        self.assertIsNone(profile.vram_mb)
        self.assertEqual(profile.gpu_viable, Tri.UNKNOWN)

    def test_a_null_context_window_stays_none(self):
        result = project_record(record(context_window=None), snapshot=snapshot())
        self.assertIsNone(result.profile.context_limit)
        self.assertIn("context_window", result.unknown_fields)

    def test_quality_is_never_invented_from_a_quality_class(self):
        profile = project_record(record(quality_class="frontier"), snapshot=snapshot()).profile
        self.assertIsNone(profile.quality)
        self.assertEqual(profile.quality_class, "frontier")

    def test_no_unknown_field_is_reported_twice(self):
        result = project_record(record(context_window=None), snapshot=snapshot())
        self.assertEqual(len(result.unknown_fields), len(set(result.unknown_fields)))


class AcquisitionEligibilityTests(unittest.TestCase):
    def test_a_record_without_artifact_identity_is_restricted_not_admitted(self):
        result = project_record(record(), snapshot=snapshot())
        self.assertEqual(result.admission_status, AdmissionStatus.RESTRICTED)
        self.assertFalse(result.profile.acquisition_eligible)
        self.assertTrue(any("hash" in reason for reason in result.exclusion_reasons))
        self.assertTrue(any("size" in reason for reason in result.exclusion_reasons))

    def test_a_restricted_record_is_still_placeable_from_cache(self):
        self.assertTrue(project_record(record(), snapshot=snapshot()).placeable)

    def test_artifact_identity_admits_the_record_for_acquisition(self):
        result = project_record(
            record(artifact_hash="a" * 64, artifact_size_bytes=4_000_000_000), snapshot=snapshot()
        )
        self.assertEqual(result.admission_status, AdmissionStatus.ADMITTED)
        self.assertTrue(result.profile.acquisition_eligible)
        self.assertEqual(result.profile.disk_mb, 4_000_000_000 // (1024 * 1024))

    def test_a_missing_size_alone_still_blocks_acquisition(self):
        result = project_record(record(artifact_hash="a" * 64), snapshot=snapshot())
        self.assertFalse(result.profile.acquisition_eligible)
        self.assertIsNone(result.profile.disk_mb)


class GateTests(unittest.TestCase):
    def _reasons(self, **overrides):
        return project_record(record(**overrides), snapshot=snapshot()).exclusion_reasons

    def test_missing_revision_is_rejected(self):
        result = project_record(record(upstream_revision=""), snapshot=snapshot())
        self.assertEqual(result.admission_status, AdmissionStatus.INELIGIBLE)
        self.assertIsNone(result.profile)
        self.assertTrue(any("upstream_revision" in r for r in result.exclusion_reasons))

    def test_floating_revisions_are_rejected(self):
        for revision in ("main", "master", "latest", "HEAD", "dev", "stable"):
            with self.subTest(revision=revision):
                reasons = self._reasons(upstream_revision=revision)
                self.assertTrue(any("floating ref" in r for r in reasons), reasons)

    def test_unverified_license_is_rejected(self):
        self.assertTrue(any("license_verified" in r for r in self._reasons(license_verified=False)))

    def test_restricted_and_unclear_licenses_are_rejected(self):
        for license_class in ("restricted", "unclear"):
            with self.subTest(license_class=license_class):
                self.assertTrue(any("license_class" in r for r in self._reasons(license_class=license_class)))

    def test_paid_token_models_are_rejected(self):
        self.assertTrue(any("paid" in r for r in self._reasons(paid_token_required=True)))

    def test_unknown_cost_class_is_rejected(self):
        # "not known to cost anything" is not "provably free".
        self.assertTrue(any("cost_class" in r for r in self._reasons(cost_class="unknown")))

    def test_a_non_self_hostable_model_is_rejected(self):
        self.assertTrue(any("self_hostable" in r for r in self._reasons(self_hostable=False)))
        self.assertTrue(any("local_runtime_possible" in r for r in self._reasons(local_runtime_possible=False)))

    def test_a_record_claiming_authority_is_rejected(self):
        self.assertTrue(any("authority" in r for r in self._reasons(authority=True)))

    def test_non_placeable_lifecycle_states_are_rejected(self):
        for state in ("DISCOVERED", "QUARANTINED", "REGISTERED", "BLOCKED", "RETIRED", "BROKEN"):
            with self.subTest(state=state):
                self.assertTrue(any("lifecycle_state" in r for r in self._reasons(lifecycle_state=state)))

    def test_broken_or_blocked_health_is_rejected(self):
        for health in ("broken", "blocked"):
            with self.subTest(health=health):
                self.assertTrue(any("health" in r for r in self._reasons(health=health)))

    def test_empty_runtime_support_is_rejected(self):
        self.assertTrue(any("runtime_support" in r for r in self._reasons(runtime_support=[])))

    def test_a_runtime_this_host_does_not_offer_is_rejected(self):
        result = project_record(record(), snapshot=snapshot(), available_runtimes=["vllm"])
        self.assertEqual(result.admission_status, AdmissionStatus.INELIGIBLE)
        self.assertTrue(any("no supported runtime" in r for r in result.exclusion_reasons))

    def test_an_unmapped_privacy_class_is_rejected_not_guessed(self):
        reasons = self._reasons(privacy_class="vibes")
        self.assertTrue(any("not guessed" in r for r in reasons), reasons)

    def test_a_missing_model_id_is_rejected(self):
        self.assertTrue(any("model_id" in r for r in self._reasons(model_id="")))

    def test_every_failing_gate_is_reported_not_just_the_first(self):
        reasons = self._reasons(license_verified=False, paid_token_required=True, upstream_revision="main")
        self.assertGreaterEqual(len(reasons), 3)

    def test_a_malformed_record_is_a_refusal_not_a_crash(self):
        result = project_record({"model_id": "broken", "hardware_profile": "not-a-mapping"})
        self.assertEqual(result.admission_status, AdmissionStatus.INELIGIBLE)
        self.assertTrue(result.exclusion_reasons)

    def test_an_empty_record_is_a_refusal(self):
        self.assertEqual(project_record({}).admission_status, AdmissionStatus.INELIGIBLE)


class HardwareImpossibilityTests(unittest.TestCase):
    def test_a_model_larger_than_total_ram_is_rejected(self):
        reasons = project_record(
            record(hardware_profile={"minimum_ram_gb": 512}), snapshot=snapshot(ram_total_mb=16_000)
        ).exclusion_reasons
        self.assertTrue(any("RAM" in r for r in reasons), reasons)

    def test_a_gpu_only_model_is_rejected_on_a_cpu_only_host(self):
        reasons = project_record(
            record(hardware_profile={"minimum_vram_gb": 24, "cpu_viable": False}), snapshot=snapshot()
        ).exclusion_reasons
        self.assertTrue(any("VRAM" in r for r in reasons), reasons)

    def test_a_cpu_viable_model_survives_a_gpu_less_host(self):
        result = project_record(
            record(hardware_profile={"minimum_vram_gb": 24, "cpu_viable": True}), snapshot=snapshot()
        )
        self.assertTrue(result.placeable)

    def test_a_gpu_host_accepts_the_gpu_model(self):
        gpus = (GpuDevice(index=0, vendor=GpuVendor.NVIDIA, name="RTX 4090",
                          vram_total_mb=24_576, vram_available_mb=20_000),)
        result = project_record(
            record(hardware_profile={"minimum_vram_gb": 24, "cpu_viable": False}),
            snapshot=snapshot(gpus=gpus),
        )
        self.assertTrue(result.placeable)

    def test_without_a_snapshot_no_hardware_claim_is_made(self):
        result = project_record(record(hardware_profile={"minimum_ram_gb": 512}))
        self.assertTrue(result.placeable)


class RuntimeStateClaimTests(unittest.TestCase):
    def test_a_registry_runtime_state_is_recorded_as_unverified(self):
        for state in ("RUNNING", "WARM", "CACHED", "SLEEPING", "DOWNLOADING", "DEGRADED"):
            with self.subTest(state=state):
                result = project_record(record(lifecycle_state=state), snapshot=snapshot())
                self.assertTrue(result.unverified_claims, state)
                self.assertIn("observed here", result.unverified_claims[0])

    def test_an_approved_record_makes_no_runtime_claim(self):
        self.assertEqual(project_record(record(), snapshot=snapshot()).unverified_claims, ())

    def test_projection_result_is_json_safe(self):
        payload = project_record(record(), snapshot=snapshot()).to_dict()
        self.assertEqual(json.loads(json.dumps(payload))["admission_status"], "RESTRICTED")


class BatchTests(unittest.TestCase):
    def test_a_bad_row_does_not_stop_the_good_ones(self):
        registry = {"models": [record(), {"model_id": "bad"}, record(model_id="fixture-model-b")]}
        results = project_registry(registry, snapshot=snapshot())
        self.assertEqual(len(results), 3)
        self.assertEqual([r.placeable for r in results], [True, False, True])

    def test_non_mapping_rows_are_skipped(self):
        results = project_registry({"models": [record(), "garbage", None]}, snapshot=snapshot())
        self.assertEqual(len(results), 1)

    def test_a_registry_with_no_models_key_projects_empty(self):
        self.assertEqual(project_registry({}), ())
        self.assertIsInstance(project_registry({"models": []}), tuple)

    def test_results_are_immutable_value_objects(self):
        result = project_record(record(), snapshot=snapshot())
        self.assertIsInstance(result, ProjectionResult)
        with self.assertRaises(Exception):
            result.model_id = "mutated"


if __name__ == "__main__":
    unittest.main()
