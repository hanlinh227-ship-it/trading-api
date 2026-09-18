#!/usr/bin/env python3
"""Focused stdlib tests for the fail-closed six-gate aggregator."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
TOOL = os.path.join(REPO_ROOT, "AI_SKILL_LIBRARY", "v4", "tools", "ai_core_always_on_gate.py")

SHA = "a" * 40

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


def valid_evidence(gate_name, sha=SHA):
    return {
        "source_sha": sha,
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
        cmd = [sys.executable, TOOL, "--source-sha", SHA]
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
        short = "a" * 12
        result = self.run_tool(["--source-sha", short], sha=short)
        self.assertEqual(result.returncode, 0)


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


if __name__ == "__main__":
    unittest.main()
