from __future__ import annotations

from enum import StrEnum


class WorkerState(StrEnum):
    DISCOVERED = "DISCOVERED"
    ELIGIBLE = "ELIGIBLE"
    ACCESSED = "ACCESSED"
    SOLVING = "SOLVING"
    VERIFIED = "VERIFIED"
    SUBMITTED = "SUBMITTED"
    WON = "WON"
    LOST = "LOST"
    FAILED = "FAILED"


_ALLOWED: dict[WorkerState, set[WorkerState]] = {
    WorkerState.DISCOVERED: {WorkerState.ELIGIBLE, WorkerState.FAILED},
    WorkerState.ELIGIBLE: {WorkerState.ACCESSED, WorkerState.FAILED},
    WorkerState.ACCESSED: {WorkerState.SOLVING, WorkerState.FAILED},
    WorkerState.SOLVING: {WorkerState.VERIFIED, WorkerState.FAILED},
    WorkerState.VERIFIED: {WorkerState.SUBMITTED, WorkerState.FAILED},
    WorkerState.SUBMITTED: {WorkerState.WON, WorkerState.LOST, WorkerState.FAILED},
    WorkerState.WON: set(),
    WorkerState.LOST: set(),
    WorkerState.FAILED: set(),
}


def assert_transition(current: WorkerState, target: WorkerState) -> None:
    if target not in _ALLOWED[current]:
        raise ValueError(f"illegal worker transition: {current} -> {target}")
