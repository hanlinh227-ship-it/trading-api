from __future__ import annotations

from enum import Enum


class InvalidTransition(ValueError):
    pass


class JobState(str, Enum):
    RECEIVED = "RECEIVED"
    ASSETS_STAGED = "ASSETS_STAGED"
    VALIDATED = "VALIDATED"
    ROUTED = "ROUTED"
    QUEUED = "QUEUED"
    RENDERING = "RENDERING"
    QA = "QA"
    REPAIRING = "REPAIRING"
    PACKAGING = "PACKAGING"
    RETURNING = "RETURNING"
    COMPLETE = "COMPLETE"

    BLOCKED_ASSET = "BLOCKED_ASSET"
    BLOCKED_AUTH = "BLOCKED_AUTH"
    QUALITY_TARGET_UNAVAILABLE = "QUALITY_TARGET_UNAVAILABLE"
    PROVIDER_QUOTA = "PROVIDER_QUOTA"
    WORKER_OFFLINE = "WORKER_OFFLINE"
    RENDER_FAILED = "RENDER_FAILED"
    QA_REJECTED = "QA_REJECTED"
    RETURN_FAILED = "RETURN_FAILED"


_FAILURE_STATES = {
    JobState.BLOCKED_ASSET,
    JobState.BLOCKED_AUTH,
    JobState.QUALITY_TARGET_UNAVAILABLE,
    JobState.PROVIDER_QUOTA,
    JobState.WORKER_OFFLINE,
    JobState.RENDER_FAILED,
    JobState.QA_REJECTED,
    JobState.RETURN_FAILED,
}

_TERMINAL_STATES = _FAILURE_STATES | {JobState.COMPLETE}

_ALLOWED = {
    JobState.RECEIVED: {JobState.ASSETS_STAGED},
    JobState.ASSETS_STAGED: {JobState.VALIDATED},
    JobState.VALIDATED: {JobState.ROUTED},
    JobState.ROUTED: {JobState.QUEUED},
    JobState.QUEUED: {JobState.RENDERING},
    JobState.RENDERING: {JobState.QA},
    JobState.QA: {JobState.REPAIRING, JobState.PACKAGING},
    JobState.REPAIRING: {JobState.ROUTED, JobState.QUEUED, JobState.RENDERING, JobState.QA},
    JobState.PACKAGING: {JobState.RETURNING},
    JobState.RETURNING: {JobState.COMPLETE},
}


def transition(current: JobState, target: JobState) -> JobState:
    current = JobState(current)
    target = JobState(target)
    if current in _TERMINAL_STATES:
        raise InvalidTransition(f"terminal state {current.value} cannot transition to {target.value}")
    if target in _FAILURE_STATES:
        return target
    if target not in _ALLOWED.get(current, set()):
        raise InvalidTransition(f"invalid transition: {current.value} -> {target.value}")
    return target
