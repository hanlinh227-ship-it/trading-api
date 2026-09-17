import copy
import unittest

import yaml

from AI_SKILL_LIBRARY.v4.control_plane.model_selection import (
    project_local_candidate,
    select_models,
    validate_selection_request,
)


def admitted_record():
    with open("AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml", encoding="utf-8") as handle:
        row = copy.deepcopy(yaml.safe_load(handle)["models"][0])
    row["lifecycle_state"] = "AVAILABLE"
    row["model_mesh_local_candidate_eligible"] = True
    row["admission_evidence"]["malware_scan_status"] = "pass"
    row["admission_evidence"]["quarantine_status"] = "clear"
    row["privacy_class"] = "confidential_safe"
    return row


def evidence():
    return {
        "resource": {"ram_required_mb": 1024, "vram_required_mb": 0, "artifact_size_bytes": 639446688},
        "health": {"state": "healthy", "checked_at": "2026-09-17T06:00:00Z"},
        "benchmark": {"capabilities": {}, "quality": None, "evidence_refs": []},
        "runtime": {"supported": True, "offline_ready": True, "backend": "llama_cpp"},
    }


class LocalCandidateProjectionTests(unittest.TestCase):
    def test_quarantined_record_cannot_project(self):
        row = admitted_record()
        row["lifecycle_state"] = "QUARANTINED"
        with self.assertRaisesRegex(ValueError, "admission"):
            project_local_candidate(row, evidence())

    def test_unknown_critical_runtime_evidence_fails_closed(self):
        runtime_evidence = evidence()
        runtime_evidence["health"]["state"] = "unknown"
        with self.assertRaisesRegex(ValueError, "health"):
            project_local_candidate(admitted_record(), runtime_evidence)

    def test_projection_is_generic_identity_lossless_and_unknown_stays_unknown(self):
        row = admitted_record()
        projected = project_local_candidate(row, evidence())
        self.assertEqual(projected["provider_id"], "local_runtime")
        self.assertEqual(projected["candidate_key"], "local_runtime:" + row["artifact_identity"]["sha256"])
        self.assertEqual(projected["artifact_identity"], row["artifact_identity"])
        self.assertEqual(projected["capabilities"]["text_reasoning"]["supported"], "unknown")
        self.assertIsNone(projected["capabilities"]["text_reasoning"]["score"])
        self.assertTrue(projected["zero_cost"])
        self.assertTrue(projected["offline_ready"])

    def test_projection_does_not_name_a_specific_model_in_implementation(self):
        row = admitted_record()
        row["model_id"] = row["artifact_identity"]["model_id"] = "Example/Other"
        row["family"] = row["artifact_identity"]["family"] = "Other"
        row["variant"] = row["artifact_identity"]["variant"] = "small"
        projected = project_local_candidate(row, evidence())
        self.assertEqual(projected["model_id"], "Example/Other")


class SelectionContractTests(unittest.TestCase):
    def request(self, profile="STANDARD"):
        return {
            "task_id": "task-1",
            "domain": "CODING",
            "required_capabilities": ["coding"],
            "privacy": "CONFIDENTIAL",
            "context": {"tokens": 1000},
            "latency_budget": {"max_ms": 5000},
            "resource_budget": {"ram_mb": 8192, "vram_mb": 0},
            "execution_profile": profile,
            "verifier_requirement": "CODING",
        }

    def candidate(self, key, *, family, lineage, quality, warm=False, ram=1024):
        return {
            "candidate_key": key,
            "provider_id": "local_runtime",
            "model_id": key,
            "model_family": family,
            "family_id": family,
            "lineage_id": lineage,
            "independence_score": 1.0,
            "capabilities": {"coding": {"supported": True, "score": quality, "evidence": ["bench:1"]}},
            "privacy": "confidential_safe",
            "zero_cost": True,
            "offline_ready": True,
            "runtime_support": ["llama_cpp"],
            "resource_evidence": {"ram_required_mb": ram, "vram_required_mb": 0},
            "health_evidence": {"state": "healthy"},
            "benchmark_evidence": {"quality": quality, "evidence_refs": ["bench:1"]},
            "warm_state": warm,
            "load_cost_ms": 1000,
            "latency_ms": 200,
        }

    def test_selection_request_requires_all_canonical_fields(self):
        request = self.request()
        del request["privacy"]
        with self.assertRaisesRegex(ValueError, "privacy"):
            validate_selection_request(request)

    def test_profile_caps_and_warm_preference_inside_small_quality_delta(self):
        cold = self.candidate("cold", family="a", lineage="a", quality=.94)
        warm = self.candidate("warm", family="b", lineage="b", quality=.92, warm=True)
        other = self.candidate("other", family="c", lineage="c", quality=.80)
        standard = select_models(self.request("STANDARD"), [cold, warm, other])
        self.assertEqual(standard["primary_model"]["candidate_key"], "warm")
        self.assertLessEqual(1 + len(standard["supporting_models"]), 2)
        deep = select_models(self.request("DEEP"), [cold, warm, other])
        self.assertLessEqual(1 + len(deep["supporting_models"]), 4)

    def test_same_lineage_is_fallback_not_independent_support(self):
        first = self.candidate("one", family="a", lineage="shared", quality=.95)
        quant = self.candidate("quant", family="a", lineage="shared", quality=.94)
        independent = self.candidate("independent", family="b", lineage="other", quality=.90)
        result = select_models(self.request("DEEP"), [first, quant, independent])
        selected = [result["primary_model"], *result["supporting_models"]]
        self.assertEqual({row["candidate_key"] for row in selected}, {"one", "independent"})
        self.assertEqual(result["fallback_chain"][0]["candidate_key"], "quant")

    def test_oversized_or_unknown_capability_candidates_are_ineligible(self):
        oversized = self.candidate("large", family="a", lineage="a", quality=.99, ram=16384)
        unknown = self.candidate("unknown", family="b", lineage="b", quality=.99)
        unknown["capabilities"]["coding"] = {"supported": "unknown", "score": None, "evidence": []}
        with self.assertRaisesRegex(ValueError, "eligible"):
            select_models(self.request(), [oversized, unknown])


if __name__ == "__main__":
    unittest.main()
