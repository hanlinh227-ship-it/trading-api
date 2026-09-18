#!/usr/bin/env python3
"""Fail-closed six-gate AI CORE always-on readiness aggregator.

Reads six evidence JSON files, validates each against an exact source SHA and
expected gate name, and prints one KEY=true|false line per gate followed by
AI_CORE_ALWAYS_ON_READY=true|false.

Exit code 0 only when all six gates are true on the requested SHA.
No network, no secrets, no repository writes except optional --output.
"""

import argparse
import json
import os
import re
import sys
import tempfile

#: A revision, not merely a string two copies of which are equal. The original
#: check was `evidence.source_sha == --source-sha`, which two empty strings
#: satisfy, and two runs of whitespace likewise - turning the one field that
#: binds all six gates to a single integrated revision into a field that can
#: bind them to nothing. Abbreviated hashes are legitimate, so the floor is 7.
_SOURCE_SHA_RE = re.compile(r"^[0-9a-f]{7,64}\Z")

#: A proof is a statement someone can check. The original test was
#: `isinstance(proofs, list) and len(proofs) > 0`, which [""] and [None] both
#: satisfy: the list was bounded in length and unbounded in content. That is
#: the allowed-but-unbounded shape this repository has been bitten by four
#: times, and this is the one tool whose whole job is refusing unproven claims.
_MAX_PROOFS = 64
_MAX_PROOF_CHARS = 4096

GATES = [
    ("CONTROL_PLANE_READY", "control"),
    ("DURABLE_JOB_READY", "durable_job"),
    ("CRITICAL_ROLE_REDUNDANCY_READY", "critical_redundancy"),
    ("SURVIVAL_PLANE_READY", "survival"),
    ("DISASTER_RECOVERY_READY", "disaster_recovery"),
    ("FRONT_DOOR_READY", "front_door"),
]


def evaluate_gate(path, source_sha, expected_gate):
    """Return True only if evidence at path is valid for this gate."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return False

    if not isinstance(data, dict):
        return False
    if data.get("source_sha") != source_sha:
        return False
    if data.get("gate") != expected_gate:
        return False
    if data.get("ready") is not True:
        return False
    return _proofs_are_proofs(data.get("proofs"))


def _proofs_are_proofs(proofs):
    """Non-empty, bounded, and every entry a non-blank string."""
    if not isinstance(proofs, list) or not proofs:
        return False
    if len(proofs) > _MAX_PROOFS:
        return False
    for proof in proofs:
        # bool first: isinstance(True, int) is True, and True is not a proof.
        if isinstance(proof, bool) or not isinstance(proof, str):
            return False
        if not proof.strip() or len(proof) > _MAX_PROOF_CHARS:
            return False
    return True


def write_atomic(path, payload):
    """Atomically write JSON payload to path."""
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".ai_core_gate_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fail-closed AI CORE always-on gate aggregator")
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--control", required=True)
    parser.add_argument("--durable-job", required=True)
    parser.add_argument("--critical-redundancy", required=True)
    parser.add_argument("--survival", required=True)
    parser.add_argument("--disaster-recovery", required=True)
    parser.add_argument("--front-door", required=True)
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)

    if not _SOURCE_SHA_RE.match(args.source_sha or ""):
        # Fail closed and say why: a run that cannot name its revision has not
        # proved anything about one. Every gate stays false.
        sys.stderr.write(
            "--source-sha must be a git revision (7-64 hex characters); "
            "a blank or non-revision value binds the evidence to nothing\n")
        for gate_name, _ in GATES:
            sys.stdout.write("%s=false\n" % gate_name)
        sys.stdout.write("AI_CORE_ALWAYS_ON_READY=false\n")
        sys.stdout.flush()
        return 1

    paths = {
        "control": args.control,
        "durable_job": args.durable_job,
        "critical_redundancy": args.critical_redundancy,
        "survival": args.survival,
        "disaster_recovery": args.disaster_recovery,
        "front_door": args.front_door,
    }

    results = {}
    for gate_name, key in GATES:
        results[gate_name] = evaluate_gate(paths[key], args.source_sha, gate_name)

    all_ready = all(results[gate_name] for gate_name, _ in GATES)

    for gate_name, _ in GATES:
        sys.stdout.write("%s=%s\n" % (gate_name, "true" if results[gate_name] else "false"))
    sys.stdout.write("AI_CORE_ALWAYS_ON_READY=%s\n" % ("true" if all_ready else "false"))
    sys.stdout.flush()

    if args.output:
        summary = {"source_sha": args.source_sha}
        for gate_name, _ in GATES:
            summary[gate_name] = results[gate_name]
        summary["AI_CORE_ALWAYS_ON_READY"] = all_ready
        write_atomic(args.output, summary)

    return 0 if all_ready else 1


if __name__ == "__main__":
    sys.exit(main())
