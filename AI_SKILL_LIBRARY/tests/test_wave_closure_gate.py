"""The rules the capability-wave gates exist to enforce, as tests.

Each of these is a way a wave could be made to look closed when it is not, and
each has to fail loudly rather than quietly pass.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from AI_SKILL_LIBRARY.v4.tools import ai_core_convergence, wave_closure_gate  # noqa: E402

REQ = "AI_SKILL_LIBRARY/v4/open_model_universe/wave{n}_capability_requirements.yaml"


def _write(tmp: Path, wave: int, rows: list[dict]) -> None:
    path = tmp / REQ.format(n=wave)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"capability_requirements": rows}), encoding="utf-8")


class UnmeasurableWork(unittest.TestCase):
    def test_an_actionable_gap_blocks_closure(self) -> None:
        """NO_SUITE_YET means go and measure it, not write it down neatly."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _write(tmp, 4, [{"tag": "vision", "measured_covered": False,
                             "blocker_class": "NO_SUITE_YET"}])
            result = wave_closure_gate.build(tmp, 4)
        self.assertFalse(result["WAVE4_OPERATIONAL_CLOSED"])
        self.assertIn("vision", result["measurable_work_outstanding"])

    def test_a_terminal_gap_does_not_block_closure(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _write(tmp, 4, [{"tag": "vision", "measured_covered": False,
                             "blocker_class": "HUMAN_GATE_REQUIRED"}])
            result = wave_closure_gate.build(tmp, 4)
        self.assertTrue(result["WAVE4_OPERATIONAL_CLOSED"])
        # Closed is still not covered, and the gate must keep saying so.
        self.assertFalse(result["WAVE4_ALL_CAPABILITIES_COVERED"])


class CoverageNeedsAMeasurement(unittest.TestCase):
    def test_covered_without_a_measurement_fails(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _write(tmp, 5, [{"tag": "coding", "measured_covered": True,
                             "measured_model": "some/model", "evidence_class": "NONE"}])
            result = wave_closure_gate.build(tmp, 5)
        self.assertFalse(result["WAVE5_OPERATIONAL_CLOSED"])
        self.assertTrue(any("evidence_class" in f for f in result["failures"]))

    def test_covered_naming_no_model_fails(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _write(tmp, 5, [{"tag": "coding", "measured_covered": True,
                             "evidence_class": "MEASURED"}])
            result = wave_closure_gate.build(tmp, 5)
        self.assertFalse(result["WAVE5_OPERATIONAL_CLOSED"])

    def test_an_unclassified_gap_fails(self) -> None:
        """A gap with no blocker_class is asserted, not classified."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _write(tmp, 5, [{"tag": "coding", "measured_covered": False}])
            result = wave_closure_gate.build(tmp, 5)
        self.assertFalse(result["WAVE5_OPERATIONAL_CLOSED"])


class SubstitutesAreNeverExactModels(unittest.TestCase):
    def test_a_provider_model_covers_but_is_flagged(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _write(tmp, 5, [{"tag": "embedding", "measured_covered": True,
                             "measured_model": "@cf/baai/bge-m3",
                             "evidence_class": "MEASURED"}])
            result = wave_closure_gate.build(tmp, 5)
        self.assertTrue(result["WAVE5_ALL_CAPABILITIES_COVERED"])
        # Covered, and explicitly NOT the requested model being available.
        self.assertFalse(result["WAVE5_ALL_EXACT_MODELS_AVAILABLE"])
        self.assertIn("embedding", result["covered_by_a_provider_substitute"])

    def test_a_placeholder_is_not_counted_against_coverage(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _write(tmp, 4, [{"tag": "future", "measured_covered": False,
                             "blocker_class": "PLACEHOLDER_TAG"}])
            result = wave_closure_gate.build(tmp, 4)
        self.assertEqual(result["capabilities_total"], 0)
        self.assertEqual(result["capabilities_uncovered"], [])


class TheRealFilesHold(unittest.TestCase):
    def test_both_waves_close_on_the_recorded_requirements(self) -> None:
        for wave in (4, 5):
            with self.subTest(wave=wave):
                result = wave_closure_gate.build(ROOT, wave)
                self.assertTrue(result[f"WAVE{wave}_OPERATIONAL_CLOSED"],
                                result["failures"])

    def test_closure_never_implies_coverage(self) -> None:
        """The distinction the whole gate exists for."""
        for wave in (4, 5):
            with self.subTest(wave=wave):
                result = wave_closure_gate.build(ROOT, wave)
                self.assertTrue(result[f"WAVE{wave}_OPERATIONAL_CLOSED"])
                self.assertFalse(result[f"WAVE{wave}_ALL_CAPABILITIES_COVERED"])

    def test_the_gate_grants_nothing(self) -> None:
        result = wave_closure_gate.build(ROOT, 4)
        self.assertFalse(result["routing_authority"])
        self.assertFalse(result["admission_authority"])


class Convergence(unittest.TestCase):
    def test_done_is_not_covered(self) -> None:
        result = ai_core_convergence.build(ROOT)
        self.assertTrue(result["AI_CORE_DONE"], result["failures"])
        self.assertFalse(result["AI_CORE_ALL_CAPABILITIES_COVERED"])
        self.assertFalse(result["AI_CORE_ALL_EXACT_MODELS_AVAILABLE"])

    def test_absent_evidence_is_not_passing(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            result = ai_core_convergence.build(Path(td))
        self.assertFalse(result["AI_CORE_DONE"])
        self.assertTrue(result["failures"])

    def test_it_grants_nothing(self) -> None:
        result = ai_core_convergence.build(ROOT)
        for flag in ("routing_authority", "admission_authority", "merge_authority"):
            self.assertFalse(result[flag])


if __name__ == "__main__":
    unittest.main()
