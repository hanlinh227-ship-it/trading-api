"""Execution liveness, and the ways "healthy" can mean nothing.

The probe exists because a worker can satisfy every health field the fabric
collects and still be unable to run a model. These tests drive the probe's
classifier directly with the outcomes a real subprocess produces, because the
interesting cases - killed by a signal, hung, exited non-zero - cannot be
produced on demand by the live machine.
"""

import json
import subprocess
import tempfile
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


class StructuredFieldTests(unittest.TestCase):
    """The fields a downstream redundancy proof reads, and what they may not do.

    These fields exist so that a consumer never re-derives execution truth from
    prose. That makes them load-bearing in a way the narrative keys are not: if
    ``execution_liveness`` ever disagreed with ``LOCAL_ENGINE.state``, a gate
    reading the short field would pass on a host that cannot run anything.
    """

    #: The contract Task 2 names. Driven from one tuple so that a field dropped
    #: from the report fails here rather than silently at the consumer.
    CONTRACT = ("worker_id", "execution_liveness", "stranded_roles",
                "critical_stranded", "source_sha", "proof_timestamp")

    def _build(self, state):
        with mock.patch.object(liveness, "probe_local_engine",
                               return_value={"state": state, "reason": "x"}):
            return liveness.build(ROOT, source_sha="a" * 40)

    def test_the_report_carries_every_field_the_contract_names(self):
        report = self._build("EXECUTION_LIVE")
        missing = [field for field in self.CONTRACT if field not in report]
        self.assertEqual(missing, [])

    def test_execution_liveness_is_the_engine_state_verbatim(self):
        for state in ("EXECUTION_LIVE", "EXECUTION_DEAD", "EXECUTION_UNKNOWN"):
            with self.subTest(state=state):
                report = self._build(state)
                self.assertEqual(report["execution_liveness"], state)
                self.assertEqual(report["execution_liveness"],
                                 report["LOCAL_ENGINE"]["state"])

    def test_a_sigill_reading_stays_dead_in_the_short_field_too(self):
        """The whole point: the new field must not launder a signal into health."""
        with mock.patch.object(liveness.subprocess, "run",
                               return_value=_completed(-4)):
            engine = liveness.probe_local_engine(ROOT)
        with mock.patch.object(liveness, "probe_local_engine", return_value=engine):
            report = liveness.build(ROOT, source_sha="a" * 40)
        self.assertEqual(report["execution_liveness"], "EXECUTION_DEAD")
        self.assertIs(report["EXECUTION_LIVE"], False)
        self.assertEqual(report["LOCAL_ENGINE"]["signal"], 4)

    def test_an_unknown_probe_is_not_reported_as_live(self):
        report = self._build("EXECUTION_UNKNOWN")
        self.assertEqual(report["execution_liveness"], "EXECUTION_UNKNOWN")
        self.assertIs(report["EXECUTION_LIVE"], False)

    def test_the_short_role_fields_repeat_the_long_ones_exactly(self):
        report = self._build("EXECUTION_DEAD")
        self.assertEqual(report["stranded_roles"],
                         report["roles_stranded_if_the_local_engine_is_dead"])
        self.assertEqual(report["critical_stranded"], report["critical_roles_stranded"])

    def test_the_worker_id_names_the_host_that_answered(self):
        report = self._build("EXECUTION_LIVE")
        self.assertIn(report["OBSERVED_ON"]["host_fingerprint"][:16], report["worker_id"])

    def test_a_revision_that_cannot_be_read_is_null_rather_than_invented(self):
        with mock.patch.object(liveness, "current_source_sha", return_value=None):
            with mock.patch.object(liveness, "probe_local_engine",
                                   return_value={"state": "EXECUTION_LIVE", "reason": "x"}):
                report = liveness.build(ROOT)
        self.assertIsNone(report["source_sha"])

    def test_the_timestamp_is_an_rfc3339_utc_instant(self):
        report = self._build("EXECUTION_LIVE")
        self.assertRegex(report["proof_timestamp"],
                         r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")


class PerHostReadingTests(unittest.TestCase):
    """One reading per machine, each one naming its own revision and instant."""

    def _write_reading(self, path, state, fingerprint):
        observed = {"host_fingerprint": fingerprint, "platform": "test"}
        with mock.patch.object(liveness, "observing_host", return_value=observed):
            with mock.patch.object(liveness, "probe_local_engine",
                                   return_value={"state": state, "reason": "x"}):
                report = liveness.build(ROOT, source_sha="b" * 40)
        merged = liveness._merge_readings(path, report)
        path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        return merged

    def test_two_hosts_both_survive_and_each_names_its_own_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "live.json"
            self._write_reading(path, "EXECUTION_LIVE", "aaaa1111")
            merged = self._write_reading(path, "EXECUTION_DEAD", "bbbb2222")
        readings = merged["READINGS_BY_HOST"]
        self.assertEqual(sorted(readings), ["aaaa1111", "bbbb2222"])
        for key, reading in readings.items():
            with self.subTest(host=key):
                self.assertEqual(reading["source_sha"], "b" * 40)
                self.assertIn("proof_timestamp", reading)
                self.assertEqual(reading["execution_liveness"],
                                 reading["LOCAL_ENGINE"]["state"])
        self.assertIs(merged["EXECUTION_IS_HOST_DEPENDENT"], True)

    def test_a_legacy_reading_without_a_revision_is_not_retrofitted_with_one(self):
        """An unattributable reading must not be made to look current."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "live.json"
            path.write_text(json.dumps({
                "OBSERVED_ON": {},
                "LOCAL_ENGINE": {"state": "EXECUTION_LIVE", "reason": "old"},
                "EXECUTION_LIVE": True,
            }), encoding="utf-8")
            merged = self._write_reading(path, "EXECUTION_DEAD", "cccc3333")
        legacy = merged["READINGS_BY_HOST"]["host_not_recorded"]
        self.assertIsNone(legacy.get("source_sha"))
        self.assertEqual(merged["READINGS_BY_HOST"]["cccc3333"]["source_sha"], "b" * 40)


class SuppliedSourceShaIsValidatedTests(unittest.TestCase):
    """The CLI's revision was written into evidence without being read.

    ``current_source_sha`` validates what it reads from git; the ``--source-sha``
    path did not, so ``"not-a-sha\n\x00 DROP"`` landed literally in a committed
    evidence file, NUL and newline included. It fails closed downstream, but a
    tool that writes attacker-controlled bytes into evidence is not fail-closed
    at the point that matters. Same pattern as every sibling tool, ``\Z`` and
    all.
    """

    BAD = ("not-a-sha", "", "   ", "a" * 40 + "\n", "a" * 40 + "\x00 DROP",
           "A" * 40, "g" * 40, "a" * 6, "a" * 65, "../../etc/passwd")

    def test_the_pattern_refuses_a_trailing_newline(self):
        self.assertIsNone(liveness.SOURCE_SHA_RE.match("a" * 40 + "\n"))

    def test_build_refuses_a_revision_that_is_not_one(self):
        for bad in self.BAD:
            with self.subTest(sha=bad):
                with self.assertRaises(ValueError):
                    liveness.build(ROOT, source_sha=bad)

    def test_build_still_accepts_a_real_revision(self):
        report = liveness.build(ROOT, source_sha="a" * 40)
        self.assertEqual(report["source_sha"], "a" * 40)

    def test_an_abbreviated_revision_is_still_a_revision(self):
        report = liveness.build(ROOT, source_sha="abcdef1")
        self.assertEqual(report["source_sha"], "abcdef1")

    def test_the_cli_writes_nothing_when_the_revision_is_not_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "WORKER_EXECUTION_LIVENESS.json"
            code = liveness.main(["--root", str(ROOT), "--evidence", str(out),
                                  "--source-sha", "not-a-sha\n\x00 DROP"])
            self.assertEqual(code, 2)
            self.assertFalse(out.exists())
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
