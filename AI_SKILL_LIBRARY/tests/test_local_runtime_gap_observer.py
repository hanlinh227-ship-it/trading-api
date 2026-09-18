"""The OBSERVE step: it must see the truth, and be unable to act on it.

Two failure modes matter here and they pull in opposite directions. An observer
that cannot act is safe and useless if it reports stale or invented gaps; an
observer that can act is useful and is the self-approval the policy forbids. So
these tests check both halves: that every gap it reports is real and traceable,
and that it has no capability beyond reading.
"""

import json
import unittest
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.local_runtime.gap_observer import (
    observe,
    observe_baseline,
    observe_models,
    observe_residency,
    observe_transport,
)

ROOT = Path(__file__).resolve().parents[2]
GAPS = ROOT / "CHECKPOINTS/evidence/SELFDEV_OBSERVED_GAPS.json"


class CapabilityBoundaryTests(unittest.TestCase):
    """What it must not be able to do."""

    def setUp(self):
        self.result = observe(ROOT)

    def test_it_declares_only_the_ability_to_read(self):
        capabilities = self.result["capabilities"]
        self.assertTrue(capabilities["reads_evidence"])
        for forbidden in ("writes_code", "edits_registry", "runs_models",
                          "starts_autodev_runs", "approves_anything"):
            with self.subTest(capability=forbidden):
                self.assertFalse(capabilities[forbidden])

    def test_it_does_not_rank_gaps(self):
        """Ordering is a judgement about what to do next, and not its call."""
        self.assertFalse(self.result["capabilities"]["ranks_by_importance"])

    def test_observing_changes_no_file(self):
        registry = ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"
        before = registry.read_bytes()
        observe(ROOT)
        self.assertEqual(registry.read_bytes(), before)

    def test_every_gap_is_marked_a_proposal(self):
        for gap in self.result["gaps"]:
            with self.subTest(subject=gap["subject"]):
                self.assertTrue(gap["is_a_proposal_not_a_change"])


class ModelGapTests(unittest.TestCase):
    def record(self, **overrides):
        base = {
            "model_id": "m", "lifecycle_state": "AVAILABLE",
            "artifact_identity": {"sha256": "a" * 64},
            "admission_evidence": {"malware_scan_status": "pass"},
            "capability_evidence": {"text_reasoning": {"artifact_sha256": "a" * 64}},
        }
        base.update(overrides)
        return {"models": [base]}

    def test_a_clean_record_yields_no_gap(self):
        self.assertEqual(observe_models(self.record()), [])

    def test_a_quarantined_model_is_reported(self):
        gaps = observe_models(self.record(lifecycle_state="QUARANTINED"))
        self.assertEqual(gaps[0].kind, "model_not_admitted")

    def test_an_unscanned_model_is_reported(self):
        gaps = observe_models(self.record(admission_evidence={"malware_scan_status": "not_run"}))
        self.assertTrue(any(g.kind == "no_signature_scan" for g in gaps))

    def test_a_capability_measured_on_other_bytes_counts_as_unmeasured(self):
        """The same digest-binding rule the mesh and the validator apply."""
        gaps = observe_models(self.record(
            capability_evidence={"text_reasoning": {"artifact_sha256": "b" * 64}}))
        self.assertTrue(any(g.kind == "capability_unmeasured" for g in gaps))


class BaselineGapTests(unittest.TestCase):
    def test_a_frozen_baseline_reports_no_gap(self):
        baseline = {"baseline_status": "READY", "passed": 12, "total": 12,
                    "wave_report": {"runs": [{"verifier_passed": True, "reproducible": True}]}}
        self.assertEqual(observe_baseline(baseline), [])

    def test_a_failed_task_is_named_with_its_reason(self):
        baseline = {"baseline_status": "NOT_READY", "passed": 11, "total": 12, "model_id": "m",
                    "wave_report": {"runs": [{"model_id": "m", "task_id": "vi-03",
                                              "verifier_passed": False, "reproducible": True,
                                              "failure": {"verifier_failures": ["expected_term_absent"]}}]}}
        gaps = observe_baseline(baseline)
        self.assertTrue(any("expected_term_absent" in g.detail for g in gaps))

    def test_a_non_reproducible_task_is_reported_separately(self):
        baseline = {"baseline_status": "READY", "passed": 12, "total": 12,
                    "wave_report": {"runs": [{"model_id": "m", "task_id": "t",
                                              "verifier_passed": True, "reproducible": False}]}}
        self.assertEqual(observe_baseline(baseline)[0].kind, "task_not_reproducible")

    def test_no_baseline_yields_no_gaps_rather_than_an_error(self):
        self.assertEqual(observe_baseline(None), [])


class TransportGapTests(unittest.TestCase):
    def test_a_staged_model_already_registered_is_not_a_gap(self):
        manifest = {"entries": [{"id": "x", "expected_sha256": "a" * 64}]}
        registry = {"models": [{"artifact_identity": {"sha256": "a" * 64}}]}
        self.assertEqual(observe_transport(manifest, registry), [])

    def test_a_staged_model_not_registered_is_a_gap(self):
        manifest = {"entries": [{"id": "x", "expected_sha256": "a" * 64,
                                 "license_declared": "apache-2.0"}]}
        gaps = observe_transport(manifest, {"models": []})
        self.assertEqual(gaps[0].kind, "staged_not_admitted")
        self.assertNotIn("licence", gaps[0].detail)

    def test_a_missing_licence_is_read_from_the_entry_not_from_a_stale_note(self):
        """The first version keyed off a marker written when the licence was
        unknown, so it kept reporting the gap after the licence arrived."""
        manifest = {"entries": [{"id": "x", "expected_sha256": "a" * 64,
                                 "license_gap": "not yet fetched"}]}
        gaps = observe_transport(manifest, {"models": []})
        self.assertIn("licence is not yet established", gaps[0].detail)

        manifest["entries"][0]["license_declared"] = "mit"
        gaps = observe_transport(manifest, {"models": []})
        self.assertNotIn("licence", gaps[0].detail)


class ResidencyGapTests(unittest.TestCase):
    def test_a_cold_unmeasured_model_is_reported(self):
        plan = {"assignments": [{"model_id": "m", "tier": "COLD", "measured_capability": None}]}
        self.assertEqual(observe_residency(plan)[0].kind, "residency_withheld")

    def test_a_cold_but_measured_model_is_not(self):
        plan = {"assignments": [{"model_id": "m", "tier": "COLD", "measured_capability": 0.8}]}
        self.assertEqual(observe_residency(plan), [])


class CommittedGapsTests(unittest.TestCase):
    def setUp(self):
        if not GAPS.is_file():
            self.skipTest("no observed gaps committed")
        self.gaps = json.loads(GAPS.read_text(encoding="utf-8"))

    def test_every_gap_cites_evidence_that_exists(self):
        for gap in self.gaps["gaps"]:
            with self.subTest(subject=gap["subject"]):
                self.assertTrue((ROOT / gap["evidence_ref"]).exists(), gap["evidence_ref"])

    def test_every_suggested_tool_exists(self):
        """A suggestion pointing at nothing is worse than no suggestion.

        Some tools live on the ops lane rather than here - the signature scan
        runs in CI, where an engine and a database are reachable - so a
        suggestion may be branch-qualified and is then checked on that branch.
        """
        import subprocess

        for gap in self.gaps["gaps"]:
            tool = gap.get("suggested_tool")
            if not tool:
                continue
            with self.subTest(tool=tool):
                if ":" in tool:
                    branch, path = tool.split(":", 1)
                    found = subprocess.run(
                        ["git", "cat-file", "-e", f"origin/{branch}:{path}"],
                        cwd=ROOT, capture_output=True,
                    )
                    if found.returncode != 0:
                        self.skipTest(f"branch origin/{branch} not fetched here")
                else:
                    self.assertTrue((ROOT / tool).exists(), tool)

    def test_reported_unscanned_models_really_are_unscanned(self):
        """A gap that is not real is worse than one that is missed."""
        registry = yaml.safe_load(
            (ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml").read_text(encoding="utf-8"))
        by_id = {m["model_id"]: m for m in registry["models"]}
        for gap in self.gaps["gaps"]:
            if gap["kind"] != "no_signature_scan":
                continue
            with self.subTest(subject=gap["subject"]):
                record = by_id[gap["subject"]]
                self.assertNotEqual(record["admission_evidence"]["malware_scan_status"], "pass")


if __name__ == "__main__":
    unittest.main()
