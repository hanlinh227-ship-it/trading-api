#!/usr/bin/env python3
"""Focused stdlib tests for the fail-closed six-gate aggregator."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
TOOL = os.path.join(REPO_ROOT, "AI_SKILL_LIBRARY", "v4", "tools", "ai_core_always_on_gate.py")

#: A real one-commit repository, built once for the module. The aggregator now
#: asks git whether the revision it is handed exists, is HEAD or is an ancestor
#: of HEAD with the proved surfaces unchanged since - so a fixture sha of
#: "a" * 40 would make every test here measure that refusal instead of the
#: thing it names. This is the fixture, not the subject.
GIT_DIR = None
SHA = "a" * 40
PARENT_SHA = None
ORPHAN_SHA = None
NOT_A_REPO = None


def _git(*args, cwd=None):
    return subprocess.run(["git"] + list(args), cwd=cwd or GIT_DIR,
                          capture_output=True, text=True, check=True)


def _commit(message):
    _git("add", "-A")
    _git("-c", "user.name=t", "-c", "user.email=t@example.invalid",
         "commit", "-q", "-m", message)
    return _git("rev-parse", "HEAD").stdout.strip()


def _write(relative, text):
    path = os.path.join(GIT_DIR, relative)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def setUpModule():
    global GIT_DIR, SHA, PARENT_SHA, ORPHAN_SHA, NOT_A_REPO
    GIT_DIR = tempfile.mkdtemp(prefix="always-on-gate-repo-")
    NOT_A_REPO = tempfile.mkdtemp(prefix="always-on-gate-plain-")
    _git("init", "-q", "-b", "main")
    _write("AI_SKILL_LIBRARY/marker.txt", "one\n")
    _write("cloudflare-worker/marker.mjs", "// one\n")
    _write("README.md", "one\n")
    PARENT_SHA = _commit("first")
    _write("README.md", "two\n")
    SHA = _commit("second, outside the proved surfaces")
    _git("checkout", "-q", "--orphan", "elsewhere")
    _write("README.md", "orphan\n")
    ORPHAN_SHA = _commit("an unrelated history")
    _git("checkout", "-q", "main")


def tearDownModule():
    for path in (GIT_DIR, NOT_A_REPO):
        if path:
            shutil.rmtree(path, ignore_errors=True)

GATE_NAMES = [
    "CONTROL_PLANE_READY",
    "DURABLE_JOB_READY",
    "CRITICAL_ROLE_REDUNDANCY_READY",
    "SURVIVAL_PLANE_READY",
    "DISASTER_RECOVERY_READY",
    "FRONT_DOOR_READY",
]

FLAGS = [
    "--control",
    "--durable-job",
    "--critical-redundancy",
    "--survival",
    "--disaster-recovery",
    "--front-door",
]


def valid_evidence(gate_name, sha=None):
    return {
        "source_sha": SHA if sha is None else sha,
        "gate": gate_name,
        "ready": True,
        "proofs": ["proof-1"],
    }


class GateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name
        self.paths = []
        for index, gate_name in enumerate(GATE_NAMES):
            path = os.path.join(self.dir, "gate_%d.json" % index)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(valid_evidence(gate_name), handle)
            self.paths.append(path)

    def write(self, index, payload):
        with open(self.paths[index], "w", encoding="utf-8") as handle:
            if isinstance(payload, str):
                handle.write(payload)
            else:
                json.dump(payload, handle)

    def run_tool(self, extra=None, *, sha=None, proofs=None):
        """Run the tool, optionally rewriting every evidence file first.

        `sha` and `proofs` rewrite all six fixtures so a degenerate value is
        tested the way it would actually arrive - consistently across the
        evidence and the command line - rather than as a mismatch the tool
        would reject for the wrong reason.
        """
        if sha is not None or proofs is not None:
            for path, gate_name in zip(self.paths, GATE_NAMES):
                payload = valid_evidence(gate_name, SHA if sha is None else sha)
                if proofs is not None:
                    payload["proofs"] = proofs
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle)
        cmd = [sys.executable, TOOL, "--source-sha", SHA,
               "--repo-root", GIT_DIR]
        for flag, path in zip(FLAGS, self.paths):
            cmd.extend([flag, path])
        if extra:
            cmd.extend(extra)
        return subprocess.run(cmd, capture_output=True, text=True)

    def parse(self, stdout):
        lines = [line for line in stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 7)
        values = {}
        for line in lines:
            key, _, value = line.partition("=")
            values[key] = value
        return values

    def test_all_valid_exit_zero(self):
        result = self.run_tool()
        self.assertEqual(result.returncode, 0, result.stderr)
        values = self.parse(result.stdout)
        for gate_name in GATE_NAMES:
            self.assertEqual(values[gate_name], "true")
        self.assertEqual(values["AI_CORE_ALWAYS_ON_READY"], "true")

    def test_missing_evidence(self):
        os.unlink(self.paths[0])
        result = self.run_tool()
        self.assertEqual(result.returncode, 1)
        values = self.parse(result.stdout)
        self.assertEqual(values["CONTROL_PLANE_READY"], "false")
        self.assertEqual(values["AI_CORE_ALWAYS_ON_READY"], "false")

    def test_malformed_json(self):
        self.write(1, "{not json")
        result = self.run_tool()
        self.assertEqual(result.returncode, 1)
        values = self.parse(result.stdout)
        self.assertEqual(values["DURABLE_JOB_READY"], "false")
        self.assertEqual(values["AI_CORE_ALWAYS_ON_READY"], "false")

    def test_stale_sha(self):
        self.write(2, valid_evidence(GATE_NAMES[2], sha="b" * 40))
        result = self.run_tool()
        self.assertEqual(result.returncode, 1)
        values = self.parse(result.stdout)
        self.assertEqual(values["CRITICAL_ROLE_REDUNDANCY_READY"], "false")
        self.assertEqual(values["AI_CORE_ALWAYS_ON_READY"], "false")

    def test_wrong_gate_name(self):
        self.write(3, valid_evidence("SOME_OTHER_GATE"))
        result = self.run_tool()
        self.assertEqual(result.returncode, 1)
        values = self.parse(result.stdout)
        self.assertEqual(values["SURVIVAL_PLANE_READY"], "false")
        self.assertEqual(values["AI_CORE_ALWAYS_ON_READY"], "false")

    def test_one_false_gate(self):
        payload = valid_evidence(GATE_NAMES[4])
        payload["ready"] = False
        self.write(4, payload)
        result = self.run_tool()
        self.assertEqual(result.returncode, 1)
        values = self.parse(result.stdout)
        self.assertEqual(values["DISASTER_RECOVERY_READY"], "false")
        self.assertEqual(values["AI_CORE_ALWAYS_ON_READY"], "false")

    def test_empty_proofs(self):
        payload = valid_evidence(GATE_NAMES[5])
        payload["proofs"] = []
        self.write(5, payload)
        result = self.run_tool()
        self.assertEqual(result.returncode, 1)
        values = self.parse(result.stdout)
        self.assertEqual(values["FRONT_DOOR_READY"], "false")
        self.assertEqual(values["AI_CORE_ALWAYS_ON_READY"], "false")

    def test_output_summary_atomic(self):
        out_path = os.path.join(self.dir, "summary.json")
        result = self.run_tool(["--output", out_path])
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(out_path, "r", encoding="utf-8") as handle:
            summary = json.load(handle)
        self.assertEqual(summary["source_sha"], SHA)
        for gate_name in GATE_NAMES:
            self.assertIs(summary[gate_name], True)
        self.assertIs(summary["AI_CORE_ALWAYS_ON_READY"], True)
        leftovers = [name for name in os.listdir(self.dir) if name.startswith(".ai_core_gate_")]
        self.assertEqual(leftovers, [])

    def test_output_summary_false_booleans(self):
        payload = valid_evidence(GATE_NAMES[0])
        payload["ready"] = False
        self.write(0, payload)
        out_path = os.path.join(self.dir, "summary.json")
        result = self.run_tool(["--output", out_path])
        self.assertEqual(result.returncode, 1)
        with open(out_path, "r", encoding="utf-8") as handle:
            summary = json.load(handle)
        self.assertIs(summary["CONTROL_PLANE_READY"], False)
        self.assertIs(summary["AI_CORE_ALWAYS_ON_READY"], False)

    def test_inputs_not_mutated(self):
        before = []
        for path in self.paths:
            with open(path, "rb") as handle:
                before.append(handle.read())
        self.run_tool()
        for path, original in zip(self.paths, before):
            with open(path, "rb") as handle:
                self.assertEqual(handle.read(), original)


class DegenerateSourceShaTests(GateTest):
    """A revision identifier that names no revision must not certify anything.

    The aggregator compared --source-sha to the evidence's source_sha and
    accepted any pair that matched. Two empty strings match. So did two runs of
    whitespace. That turns the one field binding all six gates to a single
    integrated revision into a field that can bind them to nothing at all,
    which is the opposite of what it is for.
    """

    def test_an_empty_source_sha_certifies_nothing(self):
        result = self.run_tool(["--source-sha", ""], sha="")
        self.assertEqual(result.returncode, 1)
        self.assertIn("AI_CORE_ALWAYS_ON_READY=false", result.stdout)

    def test_a_whitespace_source_sha_certifies_nothing(self):
        result = self.run_tool(["--source-sha", "   "], sha="   ")
        self.assertEqual(result.returncode, 1)
        self.assertIn("AI_CORE_ALWAYS_ON_READY=false", result.stdout)

    def test_a_sha_that_is_not_a_hex_revision_certifies_nothing(self):
        # "a"*7 is deliberately absent: seven hex characters is a legitimate
        # abbreviated revision, and the test below requires it to be accepted.
        for bad in ("not-a-sha", "zzzz", "a" * 6, "a" * 65, "A" * 40 + "!"):
            with self.subTest(sha=bad):
                result = self.run_tool(["--source-sha", bad], sha=bad)
                self.assertEqual(result.returncode, 1, bad)
                self.assertIn("AI_CORE_ALWAYS_ON_READY=false", result.stdout)

    def test_a_real_revision_still_certifies(self):
        result = self.run_tool()
        self.assertEqual(result.returncode, 0)
        self.assertIn("AI_CORE_ALWAYS_ON_READY=true", result.stdout)

    def test_a_short_hex_revision_is_accepted(self):
        """An abbreviated sha is a revision; only a non-revision is refused."""
        short = SHA[:12]
        result = self.run_tool(["--source-sha", short], sha=short)
        self.assertEqual(result.returncode, 0, result.stderr)


class ProofsMustBeProofsTests(GateTest):
    """A non-empty list of nothing is not evidence.

    The length check was satisfied by [""] and by [None]. The contents of the
    list were never looked at, so a gate could be certified by a proof that
    asserts nothing - the same allowed-but-unbounded shape this repository has
    now been bitten by four times, in the one tool whose entire job is to
    refuse unproven claims.
    """

    def test_a_list_of_empty_strings_is_not_a_proof(self):
        result = self.run_tool(proofs=[""])
        self.assertEqual(result.returncode, 1)
        self.assertIn("CONTROL_PLANE_READY=false", result.stdout)

    def test_a_list_of_nulls_is_not_a_proof(self):
        result = self.run_tool(proofs=[None])
        self.assertEqual(result.returncode, 1)

    def test_a_list_of_whitespace_is_not_a_proof(self):
        result = self.run_tool(proofs=["   ", "\t"])
        self.assertEqual(result.returncode, 1)

    def test_a_non_string_proof_is_not_a_proof(self):
        for bad in (1, True, {"p": 1}, ["nested"], 1.5):
            with self.subTest(proof=repr(bad)):
                self.assertEqual(self.run_tool(proofs=[bad]).returncode, 1)

    def test_one_bad_proof_among_good_ones_still_refuses(self):
        self.assertEqual(self.run_tool(proofs=["real-proof", ""]).returncode, 1)

    def test_an_unbounded_proof_is_refused(self):
        self.assertEqual(self.run_tool(proofs=["x" * 4097]).returncode, 1)

    def test_too_many_proofs_are_refused(self):
        self.assertEqual(self.run_tool(proofs=["p%d" % i for i in range(65)]).returncode, 1)

    def test_real_proofs_still_certify(self):
        result = self.run_tool(proofs=["ran AI_SKILL_LIBRARY.tests.test_x: 12 OK"])
        self.assertEqual(result.returncode, 0)


class RevisionMustExistTests(GateTest):
    """A well-formed sha that names no commit named no revision.

    The aggregator compared the evidence's sha to a string on its own command
    line and never asked git anything, so a fictional but well-formed sha was
    accepted by all six gates - and because committing the evidence changes the
    sha, the evidence could never name the revision that contains it. The
    revision must now exist, and be HEAD or an ancestor of HEAD with none of
    the proved surfaces changed since.
    """

    def test_an_invented_but_well_formed_sha_certifies_nothing(self):
        invented = "0" * 40
        result = self.run_tool(["--source-sha", invented], sha=invented)
        self.assertEqual(result.returncode, 1)
        self.assertIn("AI_CORE_ALWAYS_ON_READY=false", result.stdout)
        for gate_name in GATE_NAMES:
            self.assertIn("%s=false" % gate_name, result.stdout)

    def test_head_is_accepted(self):
        result = self.run_tool()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_an_ancestor_untouched_on_the_proved_surfaces_is_accepted(self):
        """Evidence can name the revision that contains it: that is the point."""
        result = self.run_tool(["--source-sha", PARENT_SHA], sha=PARENT_SHA)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_an_ancestor_with_a_changed_proved_surface_is_refused(self):
        _write("AI_SKILL_LIBRARY/marker.txt", "two\n")
        moved = _commit("a change inside a proved surface")
        try:
            result = self.run_tool(["--source-sha", PARENT_SHA], sha=PARENT_SHA)
            self.assertEqual(result.returncode, 1)
            self.assertIn("AI_CORE_ALWAYS_ON_READY=false", result.stdout)
        finally:
            _git("reset", "-q", "--hard", SHA)
        self.assertNotEqual(moved, SHA)

    def test_a_commit_on_an_unrelated_history_is_refused(self):
        result = self.run_tool(["--source-sha", ORPHAN_SHA], sha=ORPHAN_SHA)
        self.assertEqual(result.returncode, 1)
        self.assertIn("AI_CORE_ALWAYS_ON_READY=false", result.stdout)

    def test_no_repository_fails_closed_and_says_so(self):
        cmd = [sys.executable, TOOL, "--source-sha", SHA,
               "--repo-root", NOT_A_REPO]
        for flag, path in zip(FLAGS, self.paths):
            cmd.extend([flag, path])
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("AI_CORE_ALWAYS_ON_READY=false", result.stdout)
        self.assertTrue(result.stderr.strip())

    def test_there_is_no_way_to_skip_the_check(self):
        """No escape hatch was added; if one ever is, it must be loud."""
        result = self.run_tool(["--allow-unverified-sha"])
        self.assertNotEqual(result.returncode, 0)


class ClosedFieldSetTests(GateTest):
    """A gate file that claims the aggregate, or authority, is not evidence.

    The tool ignored extra fields, so a forged file could carry
    `AI_CORE_ALWAYS_ON_READY: true` and `evidence_authority: true` and still be
    accepted - harmless to the arithmetic, and thoroughly misleading to the
    human reading the file afterwards, which is who evidence is for.
    """

    def test_a_gate_file_may_not_claim_the_aggregate_verdict(self):
        payload = valid_evidence(GATE_NAMES[0])
        payload["AI_CORE_ALWAYS_ON_READY"] = True
        self.write(0, payload)
        result = self.run_tool()
        self.assertEqual(result.returncode, 1)
        self.assertIn("CONTROL_PLANE_READY=false", result.stdout)

    def test_a_gate_file_may_not_claim_another_gate(self):
        payload = valid_evidence(GATE_NAMES[1])
        payload["FRONT_DOOR_READY"] = True
        self.write(1, payload)
        result = self.run_tool()
        self.assertEqual(result.returncode, 1)
        self.assertIn("DURABLE_JOB_READY=false", result.stdout)

    def test_a_gate_file_may_not_claim_authority(self):
        payload = valid_evidence(GATE_NAMES[2])
        payload["evidence_authority"] = True
        self.write(2, payload)
        result = self.run_tool()
        self.assertEqual(result.returncode, 1)
        self.assertIn("CRITICAL_ROLE_REDUNDANCY_READY=false", result.stdout)

    def test_authority_flags_that_disclaim_authority_are_still_accepted(self):
        """The redundancy proof writes exactly these, all false, on purpose."""
        payload = valid_evidence(GATE_NAMES[2])
        payload.update({
            "tool": "critical_role_redundancy_proof",
            "routing_authority": False,
            "admission_authority": False,
            "scheduling_authority": False,
            "model_selection_authority": False,
            "evidence_authority": False,
            "changes_nothing": True,
        })
        self.write(2, payload)
        result = self.run_tool()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class OutputMayNotDestroyAnInputTests(GateTest):
    """`--output` wrote after evaluation, so aiming it at an input erased it."""

    def _read(self, index):
        with open(self.paths[index], "rb") as handle:
            return handle.read()

    def test_writing_over_an_input_is_refused(self):
        before = self._read(3)
        result = self.run_tool(["--output", self.paths[3]])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self._read(3), before)

    def test_writing_over_an_input_by_another_spelling_is_refused(self):
        spelled = os.path.join(self.dir, ".", "gate_3.json")
        before = self._read(3)
        result = self.run_tool(["--output", spelled])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self._read(3), before)

    def test_a_fresh_output_path_still_works(self):
        out_path = os.path.join(self.dir, "summary.json")
        result = self.run_tool(["--output", out_path])
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(out_path, encoding="utf-8") as handle:
            self.assertIs(json.load(handle)["AI_CORE_ALWAYS_ON_READY"], True)


if __name__ == "__main__":
    unittest.main()
