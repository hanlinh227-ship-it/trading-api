import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.tools.evergreen import (
    compare_candidate,
    detect_gaps,
    failure_to_regression,
    next_patch_version,
    source_lifecycle,
)

ROOT = Path(__file__).resolve().parents[2]


class Brain48ContinuousIntelligenceTests(unittest.TestCase):
    def _yaml(self, rel: str) -> dict:
        path = ROOT / rel
        self.assertTrue(path.is_file(), rel)
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertIsInstance(data, dict, rel)
        return data

    def test_checkpoint_resolves_continuous_intelligence_contract(self):
        checkpoint = json.loads((ROOT / "AI_SKILL_LIBRARY/checkpoint.json").read_text(encoding="utf-8"))
        rel = checkpoint.get("stable_continuous_intelligence_path")
        self.assertEqual(rel, "AI_SKILL_LIBRARY/v4/stable/continuous_intelligence.yaml")
        contract = self._yaml(rel)
        self.assertEqual(contract.get("version"), "4.8.1")
        self.assertEqual(contract.get("plane"), "evergreen_update_only")
        self.assertFalse(contract.get("stable_request_dependency"))
        self.assertEqual(contract.get("canonical_skill_count_target"), 109)

    def test_autonomous_promotion_is_bounded_to_a_and_b(self):
        contract = self._yaml("AI_SKILL_LIBRARY/v4/stable/continuous_intelligence.yaml")
        auto = contract["autonomous_promotion"]
        self.assertTrue(auto["A"])
        self.assertTrue(auto["B"])
        self.assertFalse(auto["C"])
        self.assertFalse(auto["D"])
        promotion = self._yaml("AI_SKILL_LIBRARY/v4/evergreen/promotion.yaml")
        self.assertFalse(promotion["classes"]["C"]["automatic_promotion"])
        self.assertFalse(promotion["classes"]["D"]["automatic_promotion"])

    def test_next_patch_version_tracks_active_minor_line(self):
        self.assertEqual(next_patch_version("4.7.0"), "4.7.1")
        self.assertEqual(next_patch_version("4.8.0"), "4.8.1")
        self.assertEqual(next_patch_version("4.12.9"), "4.12.10")
        with self.assertRaises(ValueError):
            next_patch_version("5.0.0")
        with self.assertRaises(ValueError):
            next_patch_version("4.8")

    def test_source_lifecycle_is_deterministic(self):
        now = datetime(2026, 9, 14, 2, 0, tzinfo=timezone.utc)
        self.assertEqual(
            source_lifecycle(now=now, last_verified=now - timedelta(hours=12), stale_after_hours=48),
            "active",
        )
        self.assertEqual(
            source_lifecycle(now=now, last_verified=now - timedelta(hours=49), stale_after_hours=48),
            "stale",
        )
        self.assertEqual(
            source_lifecycle(now=now, last_verified=now, stale_after_hours=48, reverify=True),
            "reverify",
        )
        self.assertEqual(
            source_lifecycle(now=now, last_verified=now, stale_after_hours=48, deprecated=True),
            "deprecated",
        )
        self.assertEqual(
            source_lifecycle(now=now, last_verified=now, stale_after_hours=48, archived=True),
            "archived",
        )

    def test_gap_detector_requires_evidence_and_orders_by_severity(self):
        rows = [
            {
                "domain": "engineering",
                "signal_type": "retry_rate",
                "severity": 2,
                "evidence_ref": "eval:eng-12",
                "recommended_capability": "dependency_recovery",
                "created_at": "2026-09-14T00:00:00Z",
            },
            {
                "domain": "design_2d",
                "signal_type": "verification_gap",
                "severity": 5,
                "evidence_ref": "eval:ux-9",
                "recommended_capability": "runtime_visual_verification",
                "created_at": "2026-09-14T00:00:00Z",
            },
            {"domain": "writing", "signal_type": "quality", "severity": 5},
        ]
        gaps = detect_gaps(rows)
        self.assertEqual(len(gaps), 2)
        self.assertEqual(gaps[0]["domain"], "design_2d")
        self.assertEqual(gaps[0]["severity"], 5)
        self.assertTrue(gaps[0]["gap_id"].startswith("gap:"))
        self.assertEqual(gaps[0]["evidence_refs"], ["eval:ux-9"])

    def test_failure_to_regression_sanitizes_and_rejects_sensitive_fields(self):
        failure = {
            "failure_id": "f-001",
            "domain": "data_docs",
            "failure_class": "output_error",
            "observable_symptom": "table pagination broke across pages",
            "expected_outcome": "table remains readable across page break",
            "evidence_ref": "eval:doc-14",
            "timestamp": "2026-09-14T01:00:00Z",
        }
        regression = failure_to_regression(failure)
        self.assertEqual(regression["source_failure_id"], "f-001")
        self.assertEqual(regression["state"], "candidate_regression")
        self.assertTrue(regression["verified"])
        self.assertNotIn("root_cause", regression)

        unsafe = dict(failure)
        unsafe["chain_of_thought"] = "private"
        with self.assertRaises(ValueError):
            failure_to_regression(unsafe)

    def test_candidate_comparison_requires_gain_and_zero_protected_regression(self):
        policy = {
            "min_primary_quality_gain": 0.01,
            "max_relative_latency_regression": 0.10,
            "max_relative_cost_regression": 0.05,
            "protected_dimensions": ["correctness", "authority", "security", "verification", "project_isolation"],
        }
        baseline = {
            "quality": 0.80,
            "latency": 100.0,
            "cost": 1.0,
            "correctness": 1.0,
            "authority": 1.0,
            "security": 1.0,
            "verification": 1.0,
            "project_isolation": 1.0,
        }
        better = dict(baseline, quality=0.82, latency=105.0, cost=1.02)
        self.assertEqual(compare_candidate(baseline, better, policy), "promote")

        protected_regression = dict(better, security=0.99)
        self.assertEqual(compare_candidate(baseline, protected_regression, policy), "reject")

        no_gain = dict(baseline, quality=0.805)
        self.assertEqual(compare_candidate(baseline, no_gain, policy), "hold")

        permission_expansion = dict(better, permission_expansion=True)
        self.assertEqual(compare_candidate(baseline, permission_expansion, policy), "manual_authorization_required")

        missing = dict(better)
        del missing["quality"]
        self.assertEqual(compare_candidate(baseline, missing, policy), "hold")

    def test_hourly_continuous_intelligence_schedule(self):
        contract = self._yaml("AI_SKILL_LIBRARY/v4/stable/continuous_intelligence.yaml")
        self.assertEqual(contract["schedules"]["source_refresh_hours"], 1)
        self.assertEqual(contract["schedules"]["candidate_cycle"], "hourly")

        scan = ROOT / ".github/workflows/ai-brain-evergreen-scan.yml"
        candidate = ROOT / ".github/workflows/ai-brain-evergreen-candidate.yml"
        for path in (scan, candidate):
            self.assertTrue(path.is_file(), str(path))
            text = path.read_text(encoding="utf-8")
            self.assertIn("schedule:", text)
            self.assertNotIn("git push origin main", text)

        scan_text = scan.read_text(encoding="utf-8")
        candidate_text = candidate.read_text(encoding="utf-8")
        self.assertIn("17 * * * *", scan_text)
        self.assertNotIn("17 */6 * * *", scan_text)
        self.assertIn("41 * * * *", candidate_text)
        self.assertNotIn("41 2 * * *", candidate_text)
        self.assertIn("23 3 * * 0", scan_text)
        self.assertIn("weekly-intelligence-audit", scan_text)
        self.assertIn("ci_validate.py", scan_text)
        self.assertIn("ci_validate.py", candidate_text)

    def test_release_tool_includes_continuous_intelligence_contract(self):
        release_text = (ROOT / "AI_SKILL_LIBRARY/v4/tools/release.py").read_text(encoding="utf-8")
        self.assertIn("AI_SKILL_LIBRARY/v4/stable/continuous_intelligence.yaml", release_text)
        self.assertIn('"continuous_intelligence"', release_text)

    def test_release_target_preserves_brain_4_8_or_newer(self):
        pointer = json.loads((ROOT / "AI_SKILL_LIBRARY/v4/releases/current.json").read_text(encoding="utf-8"))
        version = str(pointer.get("version", ""))
        parts = version.split(".")
        self.assertEqual(len(parts), 3)
        major, minor, patch = (int(part) for part in parts)
        self.assertEqual(major, 4)
        self.assertGreaterEqual((minor, patch), (8, 1))


if __name__ == "__main__":
    unittest.main()
