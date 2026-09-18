#!/usr/bin/env python3
"""Fail-closed same-revision closure evidence runner (Task 4A).

Runs focused subprocess checks bound to one exact source SHA and writes three
evidence JSON files. Never persists child stdout/stderr.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
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
PROBE_TIMEOUT_SECONDS = 60

#: `--python` used to accept any executable and was never asked what it was,
#: while `_proof_line` deliberately stripped it from the evidence. Between them
#: a two-line shell script that exits 0 manufactured three ready gates whose
#: proof strings were byte-identical to an honest run. The interpreter is now
#: asked to identify itself before a single gate command is run, and anything
#: that is not CPython at or above this floor is refused outright.
MIN_PYTHON = (3, 11)
CPYTHON = "cpython"

#: Answered by the interpreter itself, in its own words, on stdout.
IDENTITY_PROBE = (
    "import sys,json;"
    "print(json.dumps([list(sys.version_info[:3]), sys.implementation.name]))"
)

#: `-m pytest ... -> exit 1` is what a failing suite looks like and also what a
#: missing pytest looks like. A reader chasing the first when it was the second
#: is chasing a bug that does not exist, so each gate says which it was.
PYTEST_PROBE = "import pytest"
PREFLIGHT_PYTEST = "preflight_pytest_importable"


class InterpreterRejected(ValueError):
    """An interpreter that cannot be identified runs nothing."""

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


def _probe(python_exe: str, code: str, cwd: str):
    """Run `<python> -c <code>` and return (returncode, stdout) or (None, "")."""
    try:
        completed = subprocess.run(
            [python_exe, "-c", code],
            cwd=cwd,
            shell=False,
            capture_output=True,
            timeout=PROBE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired, subprocess.SubprocessError):
        return None, ""
    stdout = completed.stdout or b""
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", "replace")
    return completed.returncode, stdout


def resolved_interpreter_path(python_exe: str) -> str:
    """The real file `--python` names, symlinks and PATH lookup resolved."""
    located = shutil.which(python_exe) or python_exe
    return os.path.realpath(os.path.abspath(located))


def interpreter_identity(python_exe: str, cwd: str) -> dict:
    """Ask the interpreter what it is, and refuse it unless it answers well.

    Returns a *bounded* identity: the implementation, the three-part version,
    and a sha256 of the resolved real path. The digest, not the path: the path
    differs between this container and CI, so printing it would make otherwise
    identical evidence look different, while a digest of it still makes two
    different interpreters distinguishable and leaks neither location.
    """
    returncode, stdout = _probe(python_exe, IDENTITY_PROBE, cwd)
    if returncode != 0 or not stdout.strip():
        raise InterpreterRejected(
            "the interpreter did not answer the identity probe; an executable "
            "that cannot say what it is runs no gate here")
    try:
        answer = json.loads(stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise InterpreterRejected(
            "the interpreter's identity probe answer was not JSON")
    if (not isinstance(answer, list) or len(answer) != 2
            or not isinstance(answer[0], list) or len(answer[0]) != 3
            or not all(isinstance(part, int) and not isinstance(part, bool)
                       for part in answer[0])
            or not isinstance(answer[1], str)):
        raise InterpreterRejected(
            "the interpreter's identity probe answer was not the expected shape")
    version = tuple(answer[0])
    implementation = answer[1]
    if implementation != CPYTHON:
        raise InterpreterRejected(
            "the interpreter is %r, not CPython" % implementation[:32])
    if version < MIN_PYTHON:
        raise InterpreterRejected(
            "the interpreter is CPython %d.%d.%d, below the %d.%d floor"
            % (version + MIN_PYTHON))
    digest = hashlib.sha256(
        resolved_interpreter_path(python_exe).encode("utf-8", "replace")).hexdigest()
    return {
        "implementation": implementation,
        "version": "%d.%d.%d" % version,
        "path_sha256": digest,
    }


def interpreter_token(identity: dict) -> str:
    """The bounded identity as it appears in a proof line. No path."""
    return "%s %s path:sha256:%s" % (
        identity["implementation"], identity["version"], identity["path_sha256"])


def _proof_line(args, returncode: int, identity: dict) -> str:
    """One checkable sentence per command, bounded, naming the interpreter.

    The absolute path to the python executable is environment detail, not
    evidence, and it differs between this container and CI - which would make
    otherwise-identical evidence look different for no reason. What the
    interpreter *is* is evidence, so the version, the implementation and a
    digest of the resolved path travel here instead of the path itself.
    """
    line = "[%s] %s -> exit %d" % (
        interpreter_token(identity),
        " ".join(str(part) for part in args),
        returncode,
    )
    return line[:MAX_PROOF_CHARS]


def build_evidence(source_sha: str, python_exe: str, cwd: str):
    identity = interpreter_identity(python_exe, cwd)
    pytest_rc, _ = _probe(python_exe, PYTEST_PROBE, cwd)
    pytest_importable = pytest_rc == 0
    preflight = _proof_line(
        ["%s=%s" % (PREFLIGHT_PYTEST, "pass" if pytest_importable else "fail")],
        0 if pytest_importable else 1,
        identity,
    )
    results = []
    for gate_name, commands in GATES:
        proofs = [preflight]
        ready = True
        for args in commands:
            returncode = run_command(python_exe, args, cwd)
            proofs.append(_proof_line(args, returncode, identity))
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

    try:
        evidence = build_evidence(args.source_sha, args.python, cwd)
    except InterpreterRejected as exc:
        # Nothing is created: a run that cannot name its interpreter has not
        # proved anything, and must not leave a directory that looks like it
        # tried.
        sys.stderr.write("refusing --python: %s\n" % exc)
        return 2

    os.makedirs(args.output_dir, exist_ok=True)

    all_ready = True
    for item in evidence:
        atomic_write_json(os.path.join(args.output_dir, item["gate"] + ".json"), item)
        print("%s=%s" % (item["gate"], "true" if item["ready"] else "false"))
        if not item["ready"]:
            all_ready = False

    return 0 if all_ready else 1


if __name__ == "__main__":
    sys.exit(main())
