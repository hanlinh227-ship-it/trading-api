"""Drive one real bounded self-development cycle and record what happened.

    python AI_SKILL_LIBRARY/v4/tools/local_runtime_selfdev_cycle.py --evidence /tmp/cycle.json

`v4/local_runtime/selfdev.py` is the contract: which transitions exist, which
gates are required, that a gate which did not run blocks like one that failed,
that the automation cannot approve itself. Unit tests prove the contract refuses
what it says it refuses. What no test covers is whether a real change can be
walked through it against real gates - a state machine that has never carried a
change is a design, not a capability.

So this runs the machine over an actual edit: a real git worktree at the base
commit, a real patch applied to it, and gates that are real commands whose exit
codes decide the result. Nothing is simulated and no gate is passed by
assertion. A gate passes because the command it names returned zero.

Three runs, because one of them proves the wrong thing on its own:

* **accept** - a bounded, genuine change walked IDLE -> READY_TO_MERGE. It stops
  there. Approval belongs to a human or the Brain's permission authority, and
  this tool has no way to supply it, which is checked rather than assumed.
* **reject** - a change that really breaks a gate. The gate fails on its own
  evidence, the run goes to REJECTED, and the proof is that READY_TO_MERGE is
  then unreachable: retrying the same gate is refused, so a run cannot collect a
  pass by attrition.
* **rollback** - the worktree is returned to the base commit and the tree is
  compared against it. The proof is that the diff is empty, not that a function
  returned ROLLED_BACK.

Everything happens in a throwaway worktree on a throwaway branch. The checked-out
branch, the canonical registry and main are never written to; the worktree and
its branch are removed at the end whatever the outcome.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_SKILL_LIBRARY.v4.local_runtime.selfdev import (  # noqa: E402
    AutoDevError,
    AutoDevRun,
    AutoDevState,
    GateResult,
    advance,
    approve,
    record_gate,
    reject,
    roll_back,
    start,
)

#: The gate commands. Each is a real check this repository already runs; the
#: cycle does not invent a weaker one. Kept to the suites that cover the file
#: under change, because a cycle that takes twenty minutes is one nobody runs.
GATE_COMMANDS: dict[str, list[str]] = {
    "tests": [
        sys.executable, "-m", "pytest", "-q",
        "AI_SKILL_LIBRARY/tests/test_local_runtime_autorun.py",
        "AI_SKILL_LIBRARY/tests/test_local_runtime_selfdev.py",
    ],
    "benchmark": [
        sys.executable, "AI_SKILL_LIBRARY/v4/tools/validate_open_model_universe.py",
    ],
    "security": [
        sys.executable, "-m", "pytest", "-q",
        "AI_SKILL_LIBRARY/tests/test_security_regression.py",
    ],
    "verifier": [
        sys.executable, "-m", "pytest", "-q",
        "AI_SKILL_LIBRARY/tests/test_personal_ai_self_development.py",
    ],
}

#: The state each gate's evidence is produced in, mirroring selfdev.REQUIRED_GATES.
GATE_STATE = {
    "tests": AutoDevState.TESTING,
    "benchmark": AutoDevState.BENCHMARKING,
    "security": AutoDevState.REVIEW,
    "verifier": AutoDevState.REVIEW,
}


def _git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def run_gate(worktree: Path, name: str, timeout: int = 900) -> GateResult:
    """Run a gate's real command. Its exit code is the verdict, nothing else."""
    command = GATE_COMMANDS[name]
    started = time.time()
    try:
        completed = subprocess.run(
            command, cwd=worktree, capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "PYTHONPATH": str(worktree)},
        )
        code, output = completed.returncode, (completed.stdout + completed.stderr)
    except subprocess.TimeoutExpired:
        # A gate that did not finish did not pass. It is not "probably fine".
        code, output = 124, f"timed out after {timeout}s"
    elapsed = round((time.time() - started) * 1000, 3)
    tail = output.strip().splitlines()[-6:]
    return GateResult(
        name=name,
        passed=code == 0,
        evidence_ref=f"command:{' '.join(command)}|exit:{code}|ms:{elapsed}",
        detail="\n".join(tail)[-1200:],
    )


# -- the bounded changes ---------------------------------------------------


def improve_autorun_no_record(worktree: Path) -> dict[str, Any]:
    """The genuine change: say which model ids are available on NO_RECORD.

    `local_runtime_autorun.py` reports a bare `{"status": "NO_RECORD"}` when the
    registry holds more than one model and no `--model-id` was given. That is
    the exact state the registry has been in since Wave 1, so the tool's own
    documented invocation now returns a result that names neither the problem
    nor the fix. Found by running it.
    """
    target = worktree / "AI_SKILL_LIBRARY/v4/tools/local_runtime_autorun.py"
    text = target.read_text(encoding="utf-8")
    old = '''    if record is None:
        print(json.dumps({"status": "NO_RECORD"}, indent=2))
        return 2
'''
    new = '''    if record is None:
        # A bare NO_RECORD was unactionable once the registry held more than one
        # model, which it has since Wave 1: the documented invocation with no
        # --model-id started returning a status naming neither the cause nor the
        # remedy. Say which ids are there and what to pass.
        available = [str(m.get("model_id")) for m in models]
        print(json.dumps({
            "status": "NO_RECORD",
            "reason": (
                f"--model-id {args.model_id!r} matched no registry record"
                if args.model_id else
                f"the registry holds {len(models)} models, so --model-id is required"
            ),
            "available_model_ids": available,
        }, indent=2))
        return 2
'''
    if old not in text:
        # Refused rather than quietly no-opped. A patch that matched nothing
        # would leave the run with an empty diff and walk it to READY_TO_MERGE
        # for having changed nothing - a cycle that proves the machine works by
        # never asking it to carry anything. This is also what it says once the
        # change has landed on the base commit: that run is spent, and replaying
        # it is not a second proof.
        raise RuntimeError(
            "autorun NO_RECORD branch not found; the change does not apply to this base "
            "(it has most likely already landed, in which case this run is spent)"
        )
    target.write_text(text.replace(old, new, 1), encoding="utf-8")

    test = worktree / "AI_SKILL_LIBRARY/tests/test_local_runtime_autorun.py"
    suite = test.read_text(encoding="utf-8") if test.exists() else ""
    # Self-contained: the existing suite imports only what it needed, and a
    # change that breaks its imports would fail the gate for the wrong reason.
    addition = '''

class NoRecordIsActionableTests(unittest.TestCase):
    """A refusal that names neither the cause nor the remedy is a dead end."""

    def _run(self, *args):
        import json, subprocess, sys
        from pathlib import Path as _Path
        root = _Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [sys.executable, str(root / "AI_SKILL_LIBRARY/v4/tools/local_runtime_autorun.py"), *args],
            cwd=root, capture_output=True, text=True, timeout=300,
        )
        return json.loads(result.stdout)

    def test_an_unknown_model_id_names_what_is_available(self):
        payload = self._run("--model-id", "nobody/such-model")
        self.assertEqual(payload["status"], "NO_RECORD")
        self.assertIn("nobody/such-model", payload["reason"])
        self.assertTrue(payload["available_model_ids"])

    def test_the_reason_distinguishes_absent_from_ambiguous(self):
        """Two different problems produced one indistinguishable status."""
        missing = self._run("--model-id", "nobody/such-model")["reason"]
        ambiguous = self._run()["reason"]
        self.assertNotEqual(missing, ambiguous)
        self.assertIn("--model-id is required", ambiguous)
'''
    if not suite:
        suite = '''"""Autorun: the artifact search and what it reports when it cannot proceed."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
'''
    test.write_text(suite.rstrip() + "\n" + addition, encoding="utf-8")
    return {
        "change": "autorun_no_record_names_available_models",
        "files": [
            "AI_SKILL_LIBRARY/v4/tools/local_runtime_autorun.py",
            "AI_SKILL_LIBRARY/tests/test_local_runtime_autorun.py",
        ],
        "why": (
            "The tool's documented no-argument invocation returns a status that names "
            "neither the cause nor the remedy, for every registry holding more than one "
            "model. Observed by running it."
        ),
    }


def break_a_gate_for_real(worktree: Path) -> dict[str, Any]:
    """A change that genuinely fails the tests gate.

    Deliberately wrong, and wrong in a way the existing suite catches on its own
    evidence: the run must be rejected by a gate, not by this tool deciding to
    reject it.
    """
    target = worktree / "AI_SKILL_LIBRARY/v4/local_runtime/selfdev.py"
    text = target.read_text(encoding="utf-8")
    old = "    if name.lower() in AUTOMATION_ACTORS:"
    new = "    if False and name.lower() in AUTOMATION_ACTORS:"
    if old not in text:
        raise RuntimeError("selfdev approve() guard not found; the rejection change does not apply")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")
    return {
        "change": "disable_self_approval_guard",
        "files": ["AI_SKILL_LIBRARY/v4/local_runtime/selfdev.py"],
        "why": "A change that lets the automation approve its own work. The gate must catch it.",
    }


# -- the cycle -------------------------------------------------------------


def cycle(
    root: Path,
    workdir: Path,
    run_id: str,
    patch: Callable[[Path], dict[str, Any]],
    *,
    expect: str,
) -> dict[str, Any]:
    """One run through the machine against a real worktree."""
    base_sha = _git(root, "rev-parse", "HEAD")
    branch = f"autodev/{run_id}"
    worktree = workdir / run_id
    record: dict[str, Any] = {"run_id": run_id, "expect": expect, "base_sha": base_sha}

    run = start(run_id, branch=branch, base_sha=base_sha)
    run = advance(run, AutoDevState.PLANNING, reason="bounded change selected from an observed defect")

    _git(root, "worktree", "add", "-q", "-b", branch, str(worktree), base_sha)
    try:
        run = advance(run, AutoDevState.BRANCH_CREATED,
                      reason=f"isolated worktree at {base_sha[:12]} on {branch}")
        record["worktree_is_not_the_checked_out_branch"] = (
            _git(root, "rev-parse", "--abbrev-ref", "HEAD") != branch
        )

        applied = patch(worktree)
        record["change"] = applied
        record["diff_stat"] = _git(worktree, "diff", "--stat")
        record["files_changed"] = _git(worktree, "diff", "--name-only").splitlines()
        if not record["files_changed"]:
            raise RuntimeError("the change altered nothing; there is no cycle to run")
        run = advance(run, AutoDevState.IMPLEMENTING, reason=applied["why"])

        # Gates, in the state each one's evidence belongs to.
        run = advance(run, AutoDevState.TESTING, reason="running the suites over the change")
        run = record_gate(run, run_gate(worktree, "tests"))
        if run.failed_gates:
            record.update(_terminate_rejected(run, worktree, root, branch))
            return record

        run = advance(run, AutoDevState.BENCHMARKING, reason="registry and admission validation")
        run = record_gate(run, run_gate(worktree, "benchmark"))
        if run.failed_gates:
            record.update(_terminate_rejected(run, worktree, root, branch))
            return record

        run = advance(run, AutoDevState.REVIEW, reason="security and authority review")
        run = record_gate(run, run_gate(worktree, "security"))
        run = record_gate(run, run_gate(worktree, "verifier"))
        if run.failed_gates:
            record.update(_terminate_rejected(run, worktree, root, branch))
            return record

        run = advance(run, AutoDevState.READY_TO_MERGE,
                      reason="every required gate passed on its own evidence")

        # The automation must not be able to approve what it produced. Asserted
        # by trying it, because a guard nobody exercises is a comment.
        self_approval_refused = False
        try:
            approve(run, actor="auto_dev")
        except AutoDevError as exc:
            self_approval_refused = True
            record["self_approval_refusal"] = str(exc)
        record["self_approval_refused"] = self_approval_refused
        record["can_merge_without_approval"] = run.can_merge

        record["final_state"] = run.state.value
        record["run"] = run.to_dict()
        return record
    finally:
        _cleanup(root, worktree, branch)


def _terminate_rejected(run: AutoDevRun, worktree: Path, root: Path, branch: str) -> dict[str, Any]:
    """A failed gate ends the run, and must keep it ended."""
    failed = list(run.failed_gates)
    run = reject(run, reason=f"gate(s) failed on their own evidence: {failed}")

    # The property that matters: a rejected run cannot reach merge readiness,
    # and the failed gate cannot be overwritten with a pass.
    could_still_propose = False
    try:
        advance(run, AutoDevState.READY_TO_MERGE, reason="attempting to propose a rejected run")
        could_still_propose = True
    except AutoDevError as exc:
        propose_refusal = str(exc)
    else:  # pragma: no cover - a pass here is the defect being tested for
        propose_refusal = None

    overwrite_refused = False
    try:
        record_gate(run, GateResult(name=failed[0], passed=True, evidence_ref="rerun"))
    except AutoDevError as exc:
        overwrite_refused = True
        overwrite_refusal = str(exc)
    else:  # pragma: no cover
        overwrite_refusal = None

    rolled = roll_back(run, reason="return the worktree to its base")
    _git(worktree, "checkout", "--", ".")
    clean = _git(worktree, "status", "--porcelain")

    return {
        "failed_gates": failed,
        "gate_detail": {name: run.gates[name].detail for name in failed},
        "final_state": rolled.state.value,
        "rejected_run_can_still_propose": could_still_propose,
        "propose_refusal": propose_refusal,
        "failed_gate_overwrite_refused": overwrite_refused,
        "overwrite_refusal": overwrite_refusal,
        "worktree_restored_to_base": clean == "",
        "residual_worktree_changes": clean.splitlines(),
        "run": rolled.to_dict(),
    }


def _cleanup(root: Path, worktree: Path, branch: str) -> None:
    subprocess.run(["git", "worktree", "remove", "--force", str(worktree)],
                   cwd=root, capture_output=True, text=True)
    subprocess.run(["git", "branch", "-D", branch], cwd=root, capture_output=True, text=True)
    if worktree.exists():
        shutil.rmtree(worktree, ignore_errors=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--evidence", default=None)
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    stamp = int(time.time())
    payload: dict[str, Any] = {
        "tool": "local_runtime_selfdev_cycle",
        "contract": "AI_SKILL_LIBRARY/v4/local_runtime/selfdev.py",
        "gates_are_real_commands": {name: " ".join(cmd) for name, cmd in GATE_COMMANDS.items()},
        "merge_authority": False,
        "approval_authority": False,
    }

    with tempfile.TemporaryDirectory(prefix="selfdev-") as tmp:
        workdir = Path(tmp)
        payload["accepted_run"] = cycle(
            root, workdir, f"selfdev-accept-{stamp}", improve_autorun_no_record, expect="READY_TO_MERGE",
        )
        payload["rejected_run"] = cycle(
            root, workdir, f"selfdev-reject-{stamp}", break_a_gate_for_real, expect="REJECTED",
        )

    accepted = payload["accepted_run"]
    rejected = payload["rejected_run"]
    holds = [
        accepted.get("final_state") == "AUTO_DEV_READY_TO_MERGE",
        accepted.get("self_approval_refused") is True,
        accepted.get("can_merge_without_approval") is False,
        accepted.get("worktree_is_not_the_checked_out_branch") is True,
        rejected.get("final_state") == "AUTO_DEV_ROLLED_BACK",
        bool(rejected.get("failed_gates")),
        rejected.get("rejected_run_can_still_propose") is False,
        rejected.get("failed_gate_overwrite_refused") is True,
        rejected.get("worktree_restored_to_base") is True,
    ]
    payload["properties_checked"] = len(holds)
    payload["properties_held"] = sum(1 for item in holds if item)
    payload["selfdev_cycle"] = "PROVEN" if all(holds) else "FAILED"

    text = json.dumps(payload, indent=2)
    if args.evidence:
        Path(args.evidence).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if payload["selfdev_cycle"] == "PROVEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
