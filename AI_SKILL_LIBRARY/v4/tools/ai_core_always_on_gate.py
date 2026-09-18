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
import subprocess
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

#: The surfaces these six gates are about. A revision older than HEAD can still
#: be the revision under test - committing the evidence changes the sha, so
#: otherwise no evidence could ever name the commit that contains it - but only
#: while nothing here has moved since.
PROVED_SURFACES = ("AI_SKILL_LIBRARY/", "cloudflare-worker/")

#: How long git is given to answer. A hung git is not a verified revision.
GIT_TIMEOUT_SECONDS = 30

#: Fields a gate's evidence file may not carry. The tool ignored anything extra,
#: so a forged file could assert the aggregate verdict, or another gate, or an
#: authority it does not have, and still be accepted: harmless to the
#: arithmetic here and thoroughly misleading to the person who reads the file
#: afterwards, which is who evidence is for. A `*_authority` key is permitted
#: only when it says False - that is a disclaimer, and the producers in this
#: lane write exactly those.
AGGREGATE_FIELD = "AI_CORE_ALWAYS_ON_READY"
_AUTHORITY_SUFFIX = "_authority"

GATES = [
    ("CONTROL_PLANE_READY", "control"),
    ("DURABLE_JOB_READY", "durable_job"),
    ("CRITICAL_ROLE_REDUNDANCY_READY", "critical_redundancy"),
    ("SURVIVAL_PLANE_READY", "survival"),
    ("DISASTER_RECOVERY_READY", "disaster_recovery"),
    ("FRONT_DOOR_READY", "front_door"),
]


def repo_root():
    """The repository this tool lives in: AI_SKILL_LIBRARY/v4/tools/<here>."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, os.pardir, os.pardir, os.pardir))


def _git(root, *args):
    """Run one git command. Returns (returncode, stdout) or (None, "")."""
    try:
        completed = subprocess.run(
            ["git", "-C", root] + list(args),
            capture_output=True, text=True, shell=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None, ""
    return completed.returncode, (completed.stdout or "").strip()


def verify_revision(source_sha, root):
    """Is this a real revision of this repository, and the one under test?

    The aggregator used to compare the evidence's sha to a string on its own
    command line and stop there, so a well-formed but entirely invented sha was
    accepted by all six gates. Being a revision is the thing the evidence is
    bound to; nobody was checking that it was one.

    Accepted: HEAD, or an ancestor of HEAD with no change to any proved surface
    since. The second case is not a loosening - it is what lets evidence name
    the revision that contains it, because committing the evidence moves the
    sha. Everything else, including an unreadable or absent git, fails closed.

    Returns (True, "") or (False, reason).
    """
    returncode, resolved = _git(root, "rev-parse", "--verify",
                                "%s^{commit}" % source_sha)
    if returncode is None:
        return False, ("git could not be run, so no revision could be verified; "
                       "an unverifiable revision is not a verified one")
    if returncode != 0 or not _SOURCE_SHA_RE.match(resolved or ""):
        return False, ("%s names no commit in this repository" % source_sha)

    head_rc, head = _git(root, "rev-parse", "--verify", "HEAD^{commit}")
    if head_rc is None or head_rc != 0 or not _SOURCE_SHA_RE.match(head or ""):
        return False, "HEAD could not be read, so nothing can be compared to it"
    if resolved == head:
        return True, ""

    ancestor_rc, _ = _git(root, "merge-base", "--is-ancestor", resolved, head)
    if ancestor_rc != 0:
        return False, ("%s is not HEAD and is not an ancestor of HEAD, so it is "
                       "not the revision under test" % source_sha)

    diff_rc, _ = _git(root, "diff", "--quiet", resolved, head, "--",
                      *PROVED_SURFACES)
    if diff_rc != 0:
        return False, ("%s is an ancestor of HEAD, but %s changed between them; "
                       "evidence from before a change to a proved surface does "
                       "not describe HEAD" % (source_sha, " or ".join(PROVED_SURFACES)))
    return True, ""


def _overreaches(data, expected_gate):
    """A gate file that claims more than one gate's worth of fact, or authority."""
    if AGGREGATE_FIELD in data:
        return True
    for gate_name, _ in GATES:
        if gate_name in data:
            return True
    for key, value in data.items():
        if key.endswith(_AUTHORITY_SUFFIX) and value is not False:
            return True
    return False


def evaluate_gate(path, source_sha, expected_gate):
    """Return True only if evidence at path is valid for this gate."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return False

    if not isinstance(data, dict):
        return False
    if _overreaches(data, expected_gate):
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
    parser.add_argument("--repo-root", dest="repo_root", default=None,
                        help="the repository the revision is verified against")
    args = parser.parse_args(argv)

    if not _SOURCE_SHA_RE.match(args.source_sha or ""):
        # Fail closed and say why: a run that cannot name its revision has not
        # proved anything about one. Every gate stays false.
        sys.stderr.write(
            "--source-sha must be a git revision (7-64 hex characters); "
            "a blank or non-revision value binds the evidence to nothing\n")
        for gate_name, _ in GATES:
            sys.stdout.write("%s=false\n" % gate_name)
        sys.stdout.write("%s=false\n" % AGGREGATE_FIELD)
        sys.stdout.flush()
        return 1

    root = os.path.abspath(args.repo_root or repo_root())
    verified, reason = verify_revision(args.source_sha, root)
    if not verified:
        # Fail closed and say so. A revision nobody can find is not a revision
        # six gates were proved on.
        sys.stderr.write("--source-sha was not verified against git: %s\n" % reason)
        for gate_name, _ in GATES:
            sys.stdout.write("%s=false\n" % gate_name)
        sys.stdout.write("%s=false\n" % AGGREGATE_FIELD)
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

    if args.output:
        # `--output` was unbounded and written after evaluation, so aiming it at
        # one of the six inputs silently destroyed that gate's evidence. It is
        # refused before anything is read, and nothing is written.
        target = os.path.realpath(os.path.abspath(args.output))
        for key, candidate in paths.items():
            if os.path.realpath(os.path.abspath(candidate)) == target:
                sys.stderr.write(
                    "--output would overwrite the %s evidence it reads; an "
                    "aggregator that destroys its own inputs proves nothing\n" % key)
                return 2

    results = {}
    for gate_name, key in GATES:
        results[gate_name] = evaluate_gate(paths[key], args.source_sha, gate_name)

    all_ready = all(results[gate_name] for gate_name, _ in GATES)

    for gate_name, _ in GATES:
        sys.stdout.write("%s=%s\n" % (gate_name, "true" if results[gate_name] else "false"))
    sys.stdout.write("%s=%s\n" % (AGGREGATE_FIELD, "true" if all_ready else "false"))
    sys.stdout.flush()

    if args.output:
        summary = {"source_sha": args.source_sha}
        for gate_name, _ in GATES:
            summary[gate_name] = results[gate_name]
        summary[AGGREGATE_FIELD] = all_ready
        write_atomic(args.output, summary)

    return 0 if all_ready else 1


if __name__ == "__main__":
    sys.exit(main())
