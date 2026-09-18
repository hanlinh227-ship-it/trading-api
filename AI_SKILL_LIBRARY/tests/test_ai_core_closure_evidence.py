import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOL = os.path.abspath(
    os.path.join(_HERE, os.pardir, "v4", "tools", "ai_core_closure_evidence.py")
)

_spec = importlib.util.spec_from_file_location("ai_core_closure_evidence", _TOOL)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

VALID_SHA = "abcdef1"


def _completed(returncode):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=b"", stderr=b"")


def _run_with(returncodes, sha=VALID_SHA):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        rc = returncodes[len(calls) - 1]
        return _completed(rc)

    with tempfile.TemporaryDirectory() as outdir:
        with mock.patch.object(mod.subprocess, "run", side_effect=fake_run):
            code = mod.main(
                ["--source-sha", sha, "--output-dir", outdir, "--python", "python3"]
            )
        files = {}
        for name in os.listdir(outdir):
            with open(os.path.join(outdir, name), "r", encoding="utf-8") as handle:
                files[name] = json.load(handle)
    return code, files, calls


def _all_zero():
    total = sum(len(cmds) for _, cmds in mod.GATES)
    return [0] * total


class ClosureEvidenceTests(unittest.TestCase):
    def test_all_zero_all_true(self):
        code, files, calls = _run_with(_all_zero())
        self.assertEqual(code, 0)
        self.assertEqual(len(files), 3)
        for name, payload in files.items():
            self.assertTrue(payload["ready"], name)
            self.assertEqual(payload["source_sha"], VALID_SHA)
            self.assertTrue(payload["proofs"])
            for proof in payload["proofs"]:
                self.assertEqual(proof["returncode"], 0)
                self.assertIn("command", proof)

    def test_one_durable_failure(self):
        rcs = _all_zero()
        rcs[1] = 1
        code, files, _ = _run_with(rcs)
        self.assertEqual(code, 1)
        self.assertFalse(files["DURABLE_JOB_READY.json"]["ready"])
        self.assertTrue(files["CONTROL_PLANE_READY.json"]["ready"])
        self.assertTrue(files["SURVIVAL_PLANE_READY.json"]["ready"])

    def test_timeout_marks_survival_false(self):
        calls = []

        def fake_run(argv, **kwargs):
            calls.append(argv)
            if "test_survival_secrets" in " ".join(argv):
                raise subprocess.TimeoutExpired(cmd=argv, timeout=1)
            return _completed(0)

        with tempfile.TemporaryDirectory() as outdir:
            with mock.patch.object(mod.subprocess, "run", side_effect=fake_run):
                code = mod.main(
                    ["--source-sha", VALID_SHA, "--output-dir", outdir, "--python", "python3"]
                )
            with open(os.path.join(outdir, "SURVIVAL_PLANE_READY.json"), encoding="utf-8") as handle:
                survival = json.load(handle)
            with open(os.path.join(outdir, "CONTROL_PLANE_READY.json"), encoding="utf-8") as handle:
                control = json.load(handle)
        self.assertEqual(code, 1)
        self.assertFalse(survival["ready"])
        self.assertTrue(control["ready"])
        self.assertEqual(len(calls), sum(len(cmds) for _, cmds in mod.GATES))

    def test_invalid_sha_fails_closed(self):
        with tempfile.TemporaryDirectory() as outdir:
            with mock.patch.object(mod.subprocess, "run") as run_mock:
                code = mod.main(
                    ["--source-sha", "NOT-A-SHA", "--output-dir", outdir, "--python", "python3"]
                )
            run_mock.assert_not_called()
            self.assertEqual(code, 2)
            self.assertEqual(os.listdir(outdir), [])

    def test_argv_no_shell_and_cwd_repo_root(self):
        _, _, calls = _run_with(_all_zero())
        expected_root = mod.repo_root()
        for argv, kwargs in calls:
            self.assertFalse(kwargs.get("shell", False))
            self.assertEqual(kwargs.get("cwd"), expected_root)
            self.assertEqual(argv[0], "python3")

    def test_stdout_stderr_not_persisted(self):
        def fake_run(argv, **kwargs):
            return subprocess.CompletedProcess(
                args=argv, returncode=0, stdout=b"SECRET-OUT", stderr=b"SECRET-ERR"
            )

        with tempfile.TemporaryDirectory() as outdir:
            with mock.patch.object(mod.subprocess, "run", side_effect=fake_run):
                mod.main(["--source-sha", VALID_SHA, "--output-dir", outdir, "--python", "python3"])
            for name in os.listdir(outdir):
                with open(os.path.join(outdir, name), encoding="utf-8") as handle:
                    text = handle.read()
                self.assertNotIn("SECRET", text)
                payload = json.loads(text)
                for proof in payload["proofs"]:
                    self.assertEqual(set(proof.keys()), {"command", "returncode"})

    def test_atomic_output_no_temp_files(self):
        with tempfile.TemporaryDirectory() as outdir:
            with mock.patch.object(mod.subprocess, "run", side_effect=lambda argv, **kw: _completed(0)):
                mod.main(["--source-sha", VALID_SHA, "--output-dir", outdir, "--python", "python3"])
            names = sorted(os.listdir(outdir))
        self.assertEqual(
            names,
            ["CONTROL_PLANE_READY.json", "DURABLE_JOB_READY.json", "SURVIVAL_PLANE_READY.json"],
        )

    def test_command_inventory_stable(self):
        inventory = {name: [list(c) for c in cmds] for name, cmds in mod.GATES}
        self.assertEqual(
            inventory["CONTROL_PLANE_READY"],
            [["-m", "unittest", "AI_SKILL_LIBRARY.tests.test_personal_ai_control_plane_wiring", "-v"]],
        )
        self.assertEqual(
            inventory["DURABLE_JOB_READY"],
            [
                ["-m", "unittest", "AI_SKILL_LIBRARY.tests.test_always_on_job_contract", "-v"],
                ["-m", "pytest", "-q", "AI_SKILL_LIBRARY/tests/test_always_on_retry.py"],
                ["-m", "pytest", "-q", "AI_SKILL_LIBRARY/tests/test_always_on_reconciler.py"],
            ],
        )
        self.assertEqual(
            inventory["SURVIVAL_PLANE_READY"],
            [
                ["-m", "unittest", "AI_SKILL_LIBRARY.tests.test_survival_policy", "-v"],
                ["-m", "unittest", "AI_SKILL_LIBRARY.tests.test_survival_secrets", "-v"],
                ["-m", "unittest", "AI_SKILL_LIBRARY.tests.test_survival_provenance", "-v"],
                ["-m", "pytest", "-q", "AI_SKILL_LIBRARY/tests/test_survival_recovery.py"],
                ["-m", "pytest", "-q", "AI_SKILL_LIBRARY/tests/test_survival_plane_proof.py"],
            ],
        )
        pytest_count = sum(
            1 for _, cmds in mod.GATES for c in cmds if c[:2] == ["-m", "pytest"]
        )
        self.assertEqual(pytest_count, 4)


if __name__ == "__main__":
    unittest.main()
