#!/usr/bin/env python3
"""Fail-closed same-revision closure evidence runner (Task 4A).

Runs focused subprocess checks bound to one exact source SHA and writes three
evidence JSON files. Never persists child stdout/stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

#: `\Z`, not `$`: Python's `$` also matches before a trailing newline, so a sha
#: read from a file with `read()` instead of `.strip()` would have passed. This
#: repository has found that same anchor bug several times.
SHA_RE = re.compile(r"^[0-9a-f]{7,64}\Z")

#: The aggregator this tool feeds requires each proof to be a non-blank string
#: (the plan's own Task 1 fixture is `["test-proof"]`). Emitting a dict here
#: would have produced evidence no gate could ever accept, and the failure
#: would have surfaced at final aggregation as an unexplained false. One line
#: per command, carrying the same facts the dict did.
MAX_PROOF_CHARS = 4096
TIMEOUT_SECONDS = 180

GATES = (
    (
        "CONTROL_PLANE_READY",
        (
            ["-m", "unittest", "AI_SKILL_LIBRARY.tests.test_personal_ai_control_plane_wiring", "-v"],
        ),
    ),
    (
        "DURABLE_JOB_READY",
        (
            ["-m", "unittest", "AI_SKILL_LIBRARY.tests.test_always_on_job_contract", "-v"],
            ["-m", "pytest", "-q", "AI_SKILL_LIBRARY/tests/test_always_on_retry.py"],
            ["-m", "pytest", "-q", "AI_SKILL_LIBRARY/tests/test_always_on_reconciler.py"],
        ),
    ),
    (
        "SURVIVAL_PLANE_READY",
        (
            ["-m", "unittest", "AI_SKILL_LIBRARY.tests.test_survival_policy", "-v"],
            ["-m", "unittest", "AI_SKILL_LIBRARY.tests.test_survival_secrets", "-v"],
            ["-m", "unittest", "AI_SKILL_LIBRARY.tests.test_survival_provenance", "-v"],
            ["-m", "pytest", "-q", "AI_SKILL_LIBRARY/tests/test_survival_recovery.py"],
            ["-m", "pytest", "-q", "AI_SKILL_LIBRARY/tests/test_survival_plane_proof.py"],
        ),
    ),
)


def repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, os.pardir, os.pardir, os.pardir))


def run_command(python_exe: str, args, cwd: str) -> int:
    argv = [python_exe] + list(args)
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            shell=False,
            capture_output=True,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return 124
    except (OSError, subprocess.SubprocessError):
        return 127
    returncode = completed.returncode
    if returncode is None:
        return 127
    if returncode < 0:
        return 128 + (-returncode)
    return returncode


def atomic_write_json(path: str, payload: dict) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".evidence-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _proof_line(args, returncode: int) -> str:
    """One checkable sentence per command, bounded, with no interpreter path.

    The absolute path to the python executable is environment detail, not
    evidence, and it differs between this container and CI - which would make
    otherwise-identical evidence look different for no reason.
    """
    line = "%s -> exit %d" % (" ".join(str(part) for part in args), returncode)
    return line[:MAX_PROOF_CHARS]


def build_evidence(source_sha: str, python_exe: str, cwd: str):
    results = []
    for gate_name, commands in GATES:
        proofs = []
        ready = True
        for args in commands:
            returncode = run_command(python_exe, args, cwd)
            proofs.append(_proof_line(args, returncode))
            if returncode != 0:
                ready = False
        results.append(
            {
                "source_sha": source_sha,
                "gate": gate_name,
                "ready": ready,
                "proofs": proofs,
            }
        )
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="AI CORE closure evidence runner")
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args(argv)

    if not SHA_RE.match(args.source_sha or ""):
        sys.stderr.write("invalid --source-sha\n")
        return 2

    cwd = repo_root()
    os.makedirs(args.output_dir, exist_ok=True)

    evidence = build_evidence(args.source_sha, args.python, cwd)

    all_ready = True
    for item in evidence:
        atomic_write_json(os.path.join(args.output_dir, item["gate"] + ".json"), item)
        print("%s=%s" % (item["gate"], "true" if item["ready"] else "false"))
        if not item["ready"]:
            all_ready = False

    return 0 if all_ready else 1


if __name__ == "__main__":
    sys.exit(main())
