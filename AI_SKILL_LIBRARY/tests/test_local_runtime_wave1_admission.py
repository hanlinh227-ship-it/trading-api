"""Wave 1 admission: the ways a model could be admitted without earning it.

The pipeline is generic so that one model's evidence can never become another's.
These tests are the specific routes by which that could happen anyway - a scan
result quoted from different bytes, a capability inherited, a quantization
misparsed so intake compares against the wrong thing, a "pass" from a scanner
that read nothing.
"""

import copy
import json
import unittest
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.local_runtime.scanner import gguf_metadata
from AI_SKILL_LIBRARY.v4.tools.local_runtime_admit import build_record, quantization_of
from AI_SKILL_LIBRARY.v4.tools.local_runtime_record_capability import refusals
from AI_SKILL_LIBRARY.v4.tools.validate_open_model_universe import (
    _capability_refusals,
    _scan_reference_refusals,
)

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"
MANIFEST = ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/staging_manifest.json"


def registry():
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))


def entry(model_id="qwen3-1.7b-q8_0"):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return next(e for e in manifest["entries"] if e["id"] == model_id)


def verified(digest="a" * 64, size=100):
    return {"sha256": digest, "size_bytes": size,
            "structural_scan": {"status": "pass", "gguf_version": 3,
                                "tensor_count": 310, "kv_count": 28}}


def scan(digest="a" * 64, status="pass"):
    return {"artifact_sha256": digest, "malware_scan_status": status,
            "engine": "ClamAV 1.5.3", "signature_database_version": "28126",
            "scanned_at": "2026-09-17T09:34:59+00:00", "scanned_by": "github-actions"}


class QuantizationParsingTests(unittest.TestCase):
    """A wrong quantization is not cosmetic - intake compares against it."""

    def test_multi_underscore_tags_are_read_whole(self):
        self.assertEqual(quantization_of("granite-3.3-2b-instruct-Q4_K_M.gguf"), "Q4_K_M")
        self.assertEqual(quantization_of("Qwen3-4B-Q4_K_M.gguf"), "Q4_K_M")

    def test_simple_tags_still_work(self):
        self.assertEqual(quantization_of("Qwen3-1.7B-Q8_0.gguf"), "Q8_0")
        self.assertEqual(quantization_of("model-F16.gguf"), "F16")

    def test_an_absent_tag_is_unknown_not_a_guess(self):
        self.assertEqual(quantization_of("model.gguf"), "unknown")


class AdmissionGateTests(unittest.TestCase):
    def test_a_model_with_complete_evidence_becomes_available(self):
        record = build_record(entry(), verified(), scan(), {"license_declared": "apache-2.0"})
        self.assertEqual(record["admission_gaps"], [])
        self.assertEqual(record["lifecycle_state"], "AVAILABLE")

    def test_a_scan_of_different_bytes_does_not_count(self):
        """The route by which one model's clearance becomes another's."""
        record = build_record(entry(), verified(digest="a" * 64),
                              scan(digest="b" * 64), {"license_declared": "apache-2.0"})
        self.assertIn("malware_scan_result_is_bound_to_different_bytes", record["admission_gaps"])
        self.assertEqual(record["lifecycle_state"], "QUARANTINED")

    def test_no_scan_leaves_the_model_quarantined(self):
        record = build_record(entry(), verified(), None, {"license_declared": "apache-2.0"})
        self.assertEqual(record["lifecycle_state"], "QUARANTINED")
        self.assertIn("malware_scan_status=not_run", record["admission_gaps"])

    def test_a_failed_scan_is_not_an_absent_scan(self):
        record = build_record(entry(), verified(), scan(status="fail"),
                              {"license_declared": "apache-2.0"})
        self.assertEqual(record["lifecycle_state"], "QUARANTINED")
        self.assertIn("malware_scan_status=fail", record["admission_gaps"])

    def test_an_undeclared_licence_is_never_inferred_from_the_family(self):
        record = build_record(entry(), verified(), scan(), {"license_declared": None})
        self.assertIn("license_undeclared_upstream", record["admission_gaps"])
        self.assertIsNone(record["license_declared"])

    def test_an_unverified_revision_blocks_admission(self):
        row = dict(entry())
        row["revision_status"] = "digest_differs_from_current_head"
        record = build_record(row, verified(), scan(), {"license_declared": "apache-2.0"})
        self.assertIn("immutable_revision_unverified", record["admission_gaps"])

    def test_a_failed_structural_scan_blocks_admission(self):
        broken = verified()
        broken["structural_scan"]["status"] = "fail"
        record = build_record(entry(), broken, scan(), {"license_declared": "apache-2.0"})
        self.assertIn("structural_scan_not_passed", record["admission_gaps"])

    def test_a_new_model_declares_no_capability(self):
        """It cannot inherit one; a score arrives only from its own run."""
        record = build_record(entry(), verified(), scan(), {"license_declared": "apache-2.0"})
        self.assertEqual(record["capabilities"], {"text_reasoning": 0.0})


class CapabilityWriteBackTests(unittest.TestCase):
    def evidence(self, **override):
        base = {
            "promotable": True,
            "artifact_identity": {"model_id": "m", "artifact_sha256": "c" * 64},
            "benchmark_run": {"capability": "text_reasoning", "score": 0.8, "errors": 0,
                              "run_status": "COMPLETE", "suite_id": "s", "suite_version": "1",
                              "suite_hash": "d" * 64, "attempted": 24, "passed": 19,
                              "started_at": "now", "backend_version": "llama-cpp-python/0.3.35"},
        }
        base.update(override)
        return base

    def test_a_measurement_for_a_digest_in_the_registry_is_accepted(self):
        text = "      sha256: " + "c" * 64
        self.assertEqual(refusals(self.evidence(), text)[0], [])

    def test_a_measurement_for_an_unknown_digest_is_refused(self):
        problems, _ = refusals(self.evidence(), "nothing here")
        self.assertTrue(any("no registry record" in p for p in problems))

    def test_a_degraded_run_is_refused(self):
        run = dict(self.evidence()["benchmark_run"], errors=2, run_status="DEGRADED")
        problems, _ = refusals(self.evidence(promotable=False, benchmark_run=run), "x")
        self.assertTrue(any("not promotable" in p for p in problems))
        self.assertTrue(any("partial run" in p for p in problems))


class LiveRegistryTests(unittest.TestCase):
    """Every admitted model must stand on its own evidence."""

    def setUp(self):
        self.models = registry()["models"]

    def test_every_model_satisfies_the_capability_rule(self):
        for index, model in enumerate(self.models):
            with self.subTest(model_id=model["model_id"]):
                self.assertEqual(_capability_refusals(model, index), [])

    def test_every_scan_reference_names_its_own_artifact(self):
        for index, model in enumerate(self.models):
            with self.subTest(model_id=model["model_id"]):
                self.assertEqual(_scan_reference_refusals(model, index), [])

    def test_no_two_models_share_a_capability_measurement(self):
        """A measurement is bound to one digest; two rows citing one run
        would mean a score was copied rather than earned."""
        seen = {}
        for model in self.models:
            evidence = (model.get("capability_evidence") or {}).get("text_reasoning")
            if not evidence:
                continue
            digest = evidence["artifact_sha256"]
            self.assertEqual(digest, model["artifact_identity"]["sha256"], model["model_id"])
            self.assertNotIn(digest, seen, f"{model['model_id']} reuses {seen.get(digest)}'s run")
            seen[digest] = model["model_id"]

    def test_only_the_first_model_carries_an_operator_risk_acceptance(self):
        """The acceptance was scoped to one artifact and must not spread.

        Wave 1 closed malware_scan_status with real CI scans instead, which is
        why no second acceptance was ever needed.
        """
        accepted = [m["model_id"] for m in self.models if m.get("operator_risk_acceptance")]
        self.assertEqual(accepted, ["Qwen/Qwen3-0.6B-GGUF"])

    def test_wave1_models_hold_a_real_scan_rather_than_an_acceptance(self):
        for model in self.models:
            if model["model_id"] == "Qwen/Qwen3-0.6B-GGUF":
                continue
            with self.subTest(model_id=model["model_id"]):
                self.assertEqual(model["admission_evidence"]["malware_scan_status"], "pass")
                self.assertNotIn("operator_risk_acceptance", model)

    def test_context_windows_came_from_the_artifacts(self):
        """Read from the GGUF header, not from a model card."""
        cache = ROOT / ".model-cache"
        if not cache.is_dir():
            self.skipTest("no local cache")
        for model in self.models:
            declared = model.get("context_window")
            if not declared:
                continue
            digest = model["artifact_identity"]["sha256"]
            matches = [p for p in cache.rglob("*.gguf")]
            for path in matches:
                metadata = gguf_metadata(path)
                architecture = metadata.get("general.architecture")
                if not architecture:
                    continue
                observed = metadata.get(f"{architecture}.context_length")
                if observed == declared:
                    break
            else:
                if matches:
                    self.fail(f"{model['model_id']} context_window {declared} matches no artifact")


if __name__ == "__main__":
    unittest.main()


class ResidencyProfileEvidenceTests(unittest.TestCase):
    """Latency evidence must be measured under stated conditions, or it is noise."""

    def setUp(self):
        path = ROOT / "CHECKPOINTS/evidence/RESIDENCY_LATENCY_PROFILE.json"
        if not path.is_file():
            self.skipTest("no residency profile committed")
        self.profile = json.loads(path.read_text(encoding="utf-8"))

    def test_cold_loads_were_measured_against_a_cold_page_cache(self):
        """Without this the first load measures whatever was read last.

        It is recorded as a flag rather than assumed, because a profile taken
        without the privilege to drop caches is still useful and must not claim
        to be a cold-load measurement.
        """
        self.assertTrue(self.profile["cold_loads_are_page_cache_cold"])
        for model in self.profile["models"]:
            if model.get("measured"):
                self.assertTrue(model["page_cache_dropped_before_load"], model["model_id"])

    def test_every_admitted_model_was_profiled_on_the_same_prompt(self):
        """A latency comparison across different prompts compares the prompts."""
        self.assertTrue(self.profile["prompt"])
        self.assertTrue(all(m.get("measured") for m in self.profile["models"]))

    def test_residency_saving_is_derived_from_the_measured_parts(self):
        for model in self.profile["models"]:
            with self.subTest(model_id=model["model_id"]):
                expected = (model["cold_load_ms"] + model["cold_inference_ms"]
                            - model["warm_inference_ms"])
                self.assertAlmostEqual(model["residency_saving_ms"], expected, places=2)

    def test_the_models_cannot_all_be_resident_at_once(self):
        """The constraint behind a HOT tier of one or two, not four."""
        total = sum(m["peak_ram_mb"] for m in self.profile["models"] if m.get("measured"))
        self.assertGreater(total, self.profile["host_ram_total_mb"] * 0.8)

    def test_capability_and_latency_do_not_move_together(self):
        """The trade the routing utility has to price.

        The most capable model is also the slowest, so a selection weighted on
        capability alone systematically picks the slowest worker.
        """
        measured = [m for m in self.profile["models"] if m.get("measured_capability")]
        strongest = max(measured, key=lambda m: m["measured_capability"])
        fastest = min(measured, key=lambda m: m["warm_inference_ms"])
        self.assertNotEqual(strongest["model_id"], fastest["model_id"])
