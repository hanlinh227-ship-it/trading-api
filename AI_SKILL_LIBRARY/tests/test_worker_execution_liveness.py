"""Execution liveness, and the ways "healthy" can mean nothing.

The probe exists because a worker can satisfy every health field the fabric
collects and still be unable to run a model. These tests drive the probe's
classifier directly with the outcomes a real subprocess produces, because the
interesting cases - killed by a signal, hung, exited non-zero - cannot be
produced on demand by the live machine.
"""

import subprocess
import unittest
from pathlib import Path
from unittest import mock

from AI_SKILL_LIBRARY.v4.tools import worker_execution_liveness as liveness

ROOT = Path(__file__).resolve().parents[2]


def _completed(returncode: int, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(args=["python"], returncode=returncode,
                                       stdout=stdout, stderr=stderr)


class ClassifierTests(unittest.TestCase):
    def _probe(self, result):
        with mock.patch.object(liveness.subprocess, "run", return_value=result):
            return liveness.probe_local_engine(ROOT)

    def test_an_engine_that_identifies_itself_is_live(self):
        self.assertEqual(self._probe(_completed(0, "ENGINE_OK"))["state"], "EXECUTION_LIVE")

    def test_a_probe_killed_by_a_signal_is_dead_not_unknown(self):
        """The case that started this: SIGILL cannot be caught, only observed."""
        result = self._probe(_completed(-4))
        self.assertEqual(result["state"], "EXECUTION_DEAD")
        self.assertEqual(result["signal"], 4)
        self.assertIn("CPU refused an instruction", result["detail"])

    def test_a_signal_other_than_sigill_is_still_dead(self):
        result = self._probe(_completed(-9))
        self.assertEqual(result["state"], "EXECUTION_DEAD")
        self.assertEqual(result["signal"], 9)

    def test_an_absent_engine_is_dead_but_says_it_is_absent(self):
        """Absent and broken are different; neither one serves a model."""
        result = self._probe(_completed(0, "ENGINE_ABSENT"))
        self.assertEqual(result["state"], "EXECUTION_DEAD")
        self.assertIn("no local inference engine", result["reason"])

    def test_a_non_zero_exit_is_dead(self):
        self.assertEqual(self._probe(_completed(1, "", "boom"))["state"], "EXECUTION_DEAD")

    def test_a_hung_probe_is_dead_rather_than_passing_on_a_timeout(self):
        with mock.patch.object(liveness.subprocess, "run",
                               side_effect=subprocess.TimeoutExpired(cmd="p", timeout=1)):
            result = liveness.probe_local_engine(ROOT, timeout=1)
        self.assertEqual(result["state"], "EXECUTION_DEAD")

    def test_a_probe_that_cannot_be_started_is_unknown_and_unknown_is_not_a_pass(self):
        with mock.patch.object(liveness.subprocess, "run", side_effect=OSError("no exec")):
            result = liveness.probe_local_engine(ROOT)
        self.assertEqual(result["state"], "EXECUTION_UNKNOWN")
        self.assertNotEqual(result["state"], "EXECUTION_LIVE")


class ReportTests(unittest.TestCase):
    def test_a_dead_engine_strands_the_roles_whose_primary_is_local(self):
        with mock.patch.object(liveness, "probe_local_engine",
                               return_value={"state": "EXECUTION_DEAD", "reason": "x"}):
            report = liveness.build(ROOT)
        self.assertFalse(report["EXECUTION_LIVE"])
        self.assertIn("FEDERATION_IMPACT", report)

    def test_a_live_engine_reports_no_federation_impact(self):
        with mock.patch.object(liveness, "probe_local_engine",
                               return_value={"state": "EXECUTION_LIVE", "reason": "x"}):
            report = liveness.build(ROOT)
        self.assertTrue(report["EXECUTION_LIVE"])
        self.assertNotIn("FEDERATION_IMPACT", report)

    def test_the_reading_names_the_host_that_produced_it(self):
        """Two sessions on different hardware must not overwrite each other."""
        with mock.patch.object(liveness, "probe_local_engine",
                               return_value={"state": "EXECUTION_LIVE", "reason": "x"}):
            report = liveness.build(ROOT)
        host = report["OBSERVED_ON"]
        self.assertTrue(host["host_fingerprint"])
        self.assertIn("cpu_flags_present", host)
        self.assertIn("not a property of the commit", report["reading_scope"])

    def test_it_grants_nothing_and_changes_nothing(self):
        with mock.patch.object(liveness, "probe_local_engine",
                               return_value={"state": "EXECUTION_LIVE", "reason": "x"}):
            report = liveness.build(ROOT)
        for key in ("routing_authority", "admission_authority", "scheduling_authority"):
            self.assertIs(report[key], False, key)
        self.assertIs(report["changes_nothing"], True)

    def test_it_names_the_health_fields_that_would_still_look_fine(self):
        """The point of the tool is this list; an empty one would hide the gap."""
        with mock.patch.object(liveness, "probe_local_engine",
                               return_value={"state": "EXECUTION_DEAD", "reason": "x"}):
            report = liveness.build(ROOT)
        self.assertIn("circuit", report["health_fields_that_would_still_read_healthy"])
        self.assertIn("online", report["health_fields_that_would_still_read_healthy"])

    def test_strict_mode_exits_non_zero_only_when_the_engine_is_dead(self):
        with mock.patch.object(liveness, "probe_local_engine",
                               return_value={"state": "EXECUTION_DEAD", "reason": "x"}):
            self.assertEqual(liveness.main(["--root", str(ROOT), "--strict"]), 1)
        with mock.patch.object(liveness, "probe_local_engine",
                               return_value={"state": "EXECUTION_LIVE", "reason": "x"}):
            self.assertEqual(liveness.main(["--root", str(ROOT), "--strict"]), 0)


if __name__ == "__main__":
    unittest.main()
