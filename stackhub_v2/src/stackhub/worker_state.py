from __future__ import annotations

from enum import StrEnum


class WorkerState(StrEnum):
    DISCOVERED = "DISCOVERED"
    ELIGIBLE = "ELIGIBLE"
    RESERVED = "RESERVED"
    PENDING_AWARD = "PENDING_AWARD"
    CLAIMED = "CLAIMED"
    SOLVING = "SOLVING"
    VERIFIED = "VERIFIED"
    SUBMITTED = "SUBMITTED"
    PAID = "PAID"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_PERMANENT = "FAILED_PERMANENT"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"

    # Compatibility aliases for pre-V2 callers. Persisted values are canonicalized.
    ACCESSED = "CLAIMED"
    WON = "PAID"
    LOST = "REJECTED"
    FAILED = "FAILED_PERMANENT"


_ALLOWED: dict[WorkerState, set[WorkerState]] = {
    WorkerState.DISCOVERED: {
        WorkerState.ELIGIBLE,
        WorkerState.FAILED_RETRYABLE,
        WorkerState.FAILED_PERMANENT,
        WorkerState.EXPIRED,
    },
    WorkerState.ELIGIBLE: {
        WorkerState.RESERVED,
        WorkerState.FAILED_RETRYABLE,
        WorkerState.FAILED_PERMANENT,
        WorkerState.EXPIRED,
    },
    WorkerState.RESERVED: {
        WorkerState.PENDING_AWARD,
        WorkerState.CLAIMED,
        WorkerState.FAILED_RETRYABLE,
        WorkerState.FAILED_PERMANENT,
        WorkerState.EXPIRED,
    },
    WorkerState.PENDING_AWARD: {
        WorkerState.CLAIMED,
        WorkerState.REJECTED,
        WorkerState.FAILED_RETRYABLE,
        WorkerState.FAILED_PERMANENT,
        WorkerState.EXPIRED,
    },
    WorkerState.CLAIMED: {
        WorkerState.SOLVING,
        WorkerState.FAILED_RETRYABLE,
        WorkerState.FAILED_PERMANENT,
        WorkerState.EXPIRED,
    },
    WorkerState.SOLVING: {
        WorkerState.VERIFIED,
        WorkerState.FAILED_RETRYABLE,
        WorkerState.FAILED_PERMANENT,
        WorkerState.EXPIRED,
    },
    WorkerState.VERIFIED: {
        WorkerState.SUBMITTED,
        WorkerState.FAILED_RETRYABLE,
        WorkerState.FAILED_PERMANENT,
        WorkerState.EXPIRED,
    },
    WorkerState.SUBMITTED: {
        WorkerState.PAID,
        WorkerState.REJECTED,
        WorkerState.FAILED_RETRYABLE,
        WorkerState.FAILED_PERMANENT,
        WorkerState.EXPIRED,
    },
    WorkerState.PAID: set(),
    WorkerState.FAILED_RETRYABLE: {
        WorkerState.ELIGIBLE,
        WorkerState.EXPIRED,
        WorkerState.FAILED_PERMANENT,
    },
    WorkerState.FAILED_PERMANENT: set(),
    WorkerState.EXPIRED: set(),
    WorkerState.REJECTED: set(),
}

TERMINAL_STATES = frozenset(
    {
        WorkerState.PAID,
        WorkerState.FAILED_PERMANENT,
        WorkerState.EXPIRED,
        WorkerState.REJECTED,
    }
)


def assert_transition(current: WorkerState, target: WorkerState) -> None:
    if target not in _ALLOWED[current]:
        raise ValueError(f"illegal worker transition: {current} -> {target}")
