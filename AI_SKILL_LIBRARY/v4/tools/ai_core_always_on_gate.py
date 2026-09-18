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
import sys
import tempfile

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
    proofs = data.get("proofs")
    if not isinstance(proofs, list) or len(proofs) == 0:
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
