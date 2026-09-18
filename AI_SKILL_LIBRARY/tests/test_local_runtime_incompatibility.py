"""A verified runtime incompatibility is a resolved finding, not an open gap.

BitNet b1.58 and Ministral 3 are intact artifacts (their bytes match the staged
digests) that the available llama.cpp build genuinely cannot load. Reporting
them forever as actionable admission gaps trains the operator to ignore the
observer, and admitting them anyway would be a lie about what runs. So the
incompatibility is recorded as evidence bound to the digest, the model stays
QUARANTINED, and the observer separates it from work that can actually be done.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.local_runtime import gap_observer

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "CHECKPOINTS/evidence/RUNTIME_INCOMPATIBILITY_EVIDENCE.json"

BITNET = "microsoft/bitnet-b1.58-2B-4T-gguf"
MINISTRAL = "mistralai/Ministral-3-3B-Reasoning-2512-GGUF"
BITNET_SHA = "4221b252fdd5fd25e15847adfeb5ee88886506ba50b8a34548374492884c2162"
MINISTRAL_SHA = "7e9516cc01a039bb3e2d41227cdf388849bc1c942c4624c84567b1684cd9c0fc"


class IncompatibilityEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(EVIDENCE.is_file(), "runtime incompatibility evidence must be committed")
        self.doc = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.records = {r["model_id"]: r for r in self.doc["records"]}

    def test_evidence_is_bound_to_the_exact_artifact_digest(self):
        # A finding about other bytes is worthless: it must name the digest it was observed on.
        self.assertEqual(self.records[BITNET]["artifact_sha256"], BITNET_SHA)
        self.assertEqual(self.records[MINISTRAL]["artifact_sha256"], MINISTRAL_SHA)

    def test_evidence_records_the_real_diagnostic_not_a_summary(self):
        # "Failed to load" is not a reason. The runtime's own words are the evidence.
        self.assertIn("type 36", self.records[BITNET]["runtime_diagnostic"])
        self.assertIn("tokenizer.ggml.scores", self.records[MINISTRAL]["runtime_diagnostic"])
        for record in self.records.values():
            self.assertTrue(record["runtimes_tried"])
            for tried in record["runtimes_tried"]:
                self.assertTrue(tried["runtime"] and tried["runtime_version"])
                self.assertIs(tried["loaded"], False)

    def test_artifacts_are_recorded_intact_not_corrupt(self):
        # The distinction the whole finding rests on.
        for record in self.records.values():
            self.assertIs(record["artifact_intact"], True)
            self.assertEqual(record["verdict"], "INCOMPATIBLE_WITH_AVAILABLE_RUNTIMES")

    def test_no_capability_score_is_invented(self):
        for record in self.records.values():
            self.assertIs(record.get("capability_measured", False), False)
            self.assertNotIn("capability_score", record)

    def test_quarantine_is_preserved(self):
        import yaml
        registry = yaml.safe_load((ROOT / gap_observer.REGISTRY_REL).read_text(encoding="utf-8"))
        states = {m["model_id"]: m["lifecycle_state"] for m in registry["models"]}
        self.assertEqual(states[BITNET], "QUARANTINED")
        self.assertEqual(states[MINISTRAL], "QUARANTINED")


class ObserverSeparatesResolvedFromActionableTests(unittest.TestCase):
    def setUp(self):
        self.report = gap_observer.observe(ROOT)

    def test_incompatible_models_are_not_actionable_gaps(self):
        subjects = {g["subject"] for g in self.report["gaps"]}
        self.assertNotIn(BITNET, subjects, "a known-incompatible model is not an open gap")
        self.assertNotIn(MINISTRAL, subjects)

    def test_they_are_still_reported_as_resolved_findings(self):
        # Not silently dropped: suppressing it would hide a real limitation.
        resolved = {r["subject"]: r for r in self.report["resolved"]}
        self.assertIn(BITNET, resolved)
        self.assertIn(MINISTRAL, resolved)
        for record in resolved.values():
            self.assertEqual(record["verdict"], "INCOMPATIBLE_WITH_AVAILABLE_RUNTIMES")
            self.assertTrue(record["evidence_ref"])
            self.assertTrue(record["revisit_if"])

    def test_gap_count_counts_only_actionable_work(self):
        self.assertEqual(self.report["gap_count"], len(self.report["gaps"]))
        self.assertIn("resolved_count", self.report)
        self.assertEqual(self.report["resolved_count"], len(self.report["resolved"]))

    def test_a_different_digest_reopens_the_gap(self):
        # Resolution is bound to bytes. New bytes have never been tested.
        registry = {"models": [{
            "model_id": BITNET, "lifecycle_state": "QUARANTINED",
            "artifact_identity": {"sha256": "0" * 64},
            "admission_evidence": {"malware_scan_status": "pass"},
        }]}
        gaps = gap_observer.observe_models(registry, resolutions=gap_observer.load_resolutions(ROOT))
        self.assertTrue(any(g.kind == "model_not_admitted" for g in gaps),
                        "a resolution must not carry over to bytes it was never observed on")

    def test_an_unknown_model_is_unaffected(self):
        registry = {"models": [{
            "model_id": "someone/else", "lifecycle_state": "QUARANTINED",
            "artifact_identity": {"sha256": "a" * 64},
            "admission_evidence": {"malware_scan_status": "pass"},
        }]}
        gaps = gap_observer.observe_models(registry, resolutions=gap_observer.load_resolutions(ROOT))
        self.assertTrue(any(g.kind == "model_not_admitted" for g in gaps))


if __name__ == "__main__":
    unittest.main()
