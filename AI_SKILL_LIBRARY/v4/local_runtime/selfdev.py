"""Controlled self-development orchestration.

The state machine a change must walk before it can be proposed for merge. It
exists to make the dangerous shortcuts unrepresentable rather than merely
discouraged.

Four properties are structural, not conventional:

**Main is never the working branch.** `start()` refuses a protected branch
outright, so there is no state in which this machine is editing the branch it
would later merge into.

**A gate that did not run is not a gate that passed.** Gates are three-valued -
passed, failed, not-run - and `READY_TO_MERGE` requires every declared gate to
be explicitly `True`. Absent evidence blocks exactly like failed evidence, which
is the same rule the admission boundary uses and for the same reason.

**The runtime cannot approve itself.** `approve()` rejects any actor this module
considers part of the automation. A run reaches `READY_TO_MERGE` on its own
merits and then stops; the last step across is a human or the Brain's permission
authority, and nothing here can supply it.

**A failed gate is terminal for that run.** It goes to `REJECTED`, not back to
`IMPLEMENTING` for another try at the same gate. Retrying is a new run with a
new branch, so a run's history cannot accumulate a passing result by attrition.

This module holds no routing, reasoning or merge authority, and performs no git
operations - it records and constrains. Whatever executes the steps asks it
whether a transition is allowed.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Mapping


class AutoDevState(str, Enum):
    IDLE = "AUTO_DEV_IDLE"
    PLANNING = "AUTO_DEV_PLANNING"
    BRANCH_CREATED = "AUTO_DEV_BRANCH_CREATED"
    IMPLEMENTING = "AUTO_DEV_IMPLEMENTING"
    TESTING = "AUTO_DEV_TESTING"
    BENCHMARKING = "AUTO_DEV_BENCHMARKING"
    REVIEW = "AUTO_DEV_REVIEW"
    READY_TO_MERGE = "AUTO_DEV_READY_TO_MERGE"
    REJECTED = "AUTO_DEV_REJECTED"
    ROLLED_BACK = "AUTO_DEV_ROLLED_BACK"

    def __str__(self) -> str:  # pragma: no cover - display only
        return self.value


#: Branches this machine may never use as its working branch.
PROTECTED_BRANCHES = frozenset({"main", "master", "trunk", "release", "production"})

#: Gates every run must clear before it may be proposed. Each maps to the state
#: that produces its evidence.
REQUIRED_GATES: Mapping[str, AutoDevState] = {
    "tests": AutoDevState.TESTING,
    "benchmark": AutoDevState.BENCHMARKING,
    "security": AutoDevState.REVIEW,
    "verifier": AutoDevState.REVIEW,
}

#: Actors that are part of the automation and therefore cannot approve its work.
AUTOMATION_ACTORS = frozenset(
    {"auto_dev", "autodev", "self_development", "runtime", "claude_local_runtime", "system"}
)

_TRANSITIONS: Mapping[AutoDevState, frozenset[AutoDevState]] = {
    AutoDevState.IDLE: frozenset({AutoDevState.PLANNING}),
    AutoDevState.PLANNING: frozenset({AutoDevState.BRANCH_CREATED, AutoDevState.REJECTED}),
    AutoDevState.BRANCH_CREATED: frozenset(
        {AutoDevState.IMPLEMENTING, AutoDevState.REJECTED, AutoDevState.ROLLED_BACK}
    ),
    AutoDevState.IMPLEMENTING: frozenset(
        {AutoDevState.TESTING, AutoDevState.REJECTED, AutoDevState.ROLLED_BACK}
    ),
    AutoDevState.TESTING: frozenset(
        {AutoDevState.BENCHMARKING, AutoDevState.REJECTED, AutoDevState.ROLLED_BACK}
    ),
    AutoDevState.BENCHMARKING: frozenset(
        {AutoDevState.REVIEW, AutoDevState.REJECTED, AutoDevState.ROLLED_BACK}
    ),
    AutoDevState.REVIEW: frozenset(
        {AutoDevState.READY_TO_MERGE, AutoDevState.REJECTED, AutoDevState.ROLLED_BACK}
    ),
    # Terminal for this machine: merging is somebody else's authority, and a
    # regression found afterwards rolls back rather than transitioning onward.
    AutoDevState.READY_TO_MERGE: frozenset({AutoDevState.ROLLED_BACK, AutoDevState.REJECTED}),
    AutoDevState.REJECTED: frozenset({AutoDevState.ROLLED_BACK}),
    AutoDevState.ROLLED_BACK: frozenset(),
}


class AutoDevError(RuntimeError):
    """A transition or action the contract does not allow."""


@dataclass(frozen=True)
class GateResult:
    name: str
    #: None means the gate has not run. It blocks exactly like False.
    passed: bool | None = None
    evidence_ref: str | None = None
    detail: str | None = None

    @property
    def cleared(self) -> bool:
        return self.passed is True


@dataclass(frozen=True)
class TransitionRecord:
    source: AutoDevState
    target: AutoDevState
    reason: str


@dataclass(frozen=True)
class AutoDevRun:
    run_id: str
    state: AutoDevState = AutoDevState.IDLE
    branch: str | None = None
    base_sha: str | None = None
    gates: Mapping[str, GateResult] = field(default_factory=dict)
    approved_by: str | None = None
    rollback_ref: str | None = None
    history: tuple[TransitionRecord, ...] = ()

    #: This machine decides nothing beyond its own progress.
    routing_authority = False
    reasoning_authority = False
    merge_authority = False

    # -- gates -------------------------------------------------------------

    @property
    def outstanding_gates(self) -> tuple[str, ...]:
        """Required gates that have not explicitly passed."""
        return tuple(
            name for name in sorted(REQUIRED_GATES) if not self.gates.get(name, GateResult(name)).cleared
        )

    @property
    def failed_gates(self) -> tuple[str, ...]:
        return tuple(
            name for name, result in sorted(self.gates.items()) if result.passed is False
        )

    @property
    def can_propose(self) -> bool:
        return not self.outstanding_gates

    @property
    def can_merge(self) -> bool:
        """Ready *and* approved by someone outside the automation."""
        return (
            self.state is AutoDevState.READY_TO_MERGE
            and self.can_propose
            and bool(self.approved_by)
        )

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "run_id": self.run_id,
            "state": self.state.value,
            "branch": self.branch,
            "base_sha": self.base_sha,
            "gates": {
                name: {"passed": r.passed, "evidence_ref": r.evidence_ref, "detail": r.detail}
                for name, r in sorted(self.gates.items())
            },
            "outstanding_gates": list(self.outstanding_gates),
            "failed_gates": list(self.failed_gates),
            "approved_by": self.approved_by,
            "can_propose": self.can_propose,
            "can_merge": self.can_merge,
            "rollback_ref": self.rollback_ref,
            "routing_authority": self.routing_authority,
            "merge_authority": self.merge_authority,
            "history": [
                {"source": h.source.value, "target": h.target.value, "reason": h.reason}
                for h in self.history
            ],
        }


def valid_autodev_targets(state: AutoDevState) -> frozenset[AutoDevState]:
    return _TRANSITIONS[AutoDevState(state)]


def start(run_id: str, *, branch: str, base_sha: str) -> AutoDevRun:
    """Begin a run on an isolated branch. Refuses a protected branch."""
    if not run_id.strip():
        raise AutoDevError("run_id is required")
    if not branch.strip():
        raise AutoDevError("an isolated branch is required")
    if branch.strip().lower() in PROTECTED_BRANCHES:
        raise AutoDevError(
            f"{branch!r} is protected; self-development never works on the branch it merges into"
        )
    if not base_sha.strip():
        raise AutoDevError("base_sha is required so the run can be rolled back")
    return AutoDevRun(run_id=run_id, branch=branch, base_sha=base_sha, rollback_ref=base_sha)


def record_gate(run: AutoDevRun, result: GateResult) -> AutoDevRun:
    """Attach gate evidence. A gate may not be overwritten once it failed."""
    existing = run.gates.get(result.name)
    if existing is not None and existing.passed is False and result.passed is True:
        raise AutoDevError(
            f"gate {result.name!r} already failed; a rerun is a new run, not an overwrite"
        )
    return replace(run, gates={**run.gates, result.name: result})


def advance(run: AutoDevRun, target: AutoDevState, *, reason: str) -> AutoDevRun:
    """Move the run, or raise and leave it untouched."""
    if not reason.strip():
        raise AutoDevError("a transition reason is required")
    target = AutoDevState(target)
    allowed = _TRANSITIONS[run.state]
    if target not in allowed:
        legal = ", ".join(sorted(s.value for s in allowed)) or "<terminal>"
        raise AutoDevError(
            f"{run.run_id}: {run.state.value} -> {target.value} is not allowed; legal: {legal}"
        )
    if target is AutoDevState.READY_TO_MERGE and run.outstanding_gates:
        raise AutoDevError(
            f"{run.run_id}: cannot propose with outstanding gates: {list(run.outstanding_gates)}"
        )
    if target is AutoDevState.READY_TO_MERGE and run.failed_gates:
        raise AutoDevError(f"{run.run_id}: cannot propose with failed gates: {list(run.failed_gates)}")
    return replace(
        run,
        state=target,
        history=(*run.history, TransitionRecord(run.state, target, reason.strip())),
    )


def approve(run: AutoDevRun, *, actor: str) -> AutoDevRun:
    """Record external approval. The automation cannot approve itself."""
    name = (actor or "").strip()
    if not name:
        raise AutoDevError("an approving actor is required")
    if name.lower() in AUTOMATION_ACTORS:
        raise AutoDevError(
            f"{name!r} is part of the automation and cannot approve its own change; "
            "approval is a human or Brain permission decision"
        )
    if run.state is not AutoDevState.READY_TO_MERGE:
        raise AutoDevError(f"{run.run_id}: only a READY_TO_MERGE run may be approved")
    if run.outstanding_gates:
        raise AutoDevError(f"{run.run_id}: outstanding gates: {list(run.outstanding_gates)}")
    return replace(run, approved_by=name)


def reject(run: AutoDevRun, *, reason: str) -> AutoDevRun:
    return advance(run, AutoDevState.REJECTED, reason=reason)


def roll_back(run: AutoDevRun, *, reason: str) -> AutoDevRun:
    """Return to the recorded base. Always available after a branch exists."""
    if run.rollback_ref is None:
        raise AutoDevError(f"{run.run_id}: no rollback ref recorded")
    return advance(run, AutoDevState.ROLLED_BACK, reason=reason)
