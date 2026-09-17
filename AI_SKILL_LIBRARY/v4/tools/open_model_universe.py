"""Authority-free Open Model Universe lifecycle contracts.

This module describes metadata lifecycle only. It does not route tasks, download
weights, start runtimes, select models, or mutate Stable state.
"""
from __future__ import annotations


LIFECYCLE_STATES = {
    "DISCOVERED",
    "QUARANTINED",
    "REGISTERED",
    "APPROVED",
    "AVAILABLE",
    "DOWNLOADING",
    "CACHED",
    "WARM",
    "RUNNING",
    "SLEEPING",
    "DEGRADED",
    "BROKEN",
    "EVICTED",
    "SUPERSEDED",
    "RETIRED",
    "BLOCKED",
    "QUARANTINED_UPDATE",
}


ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "DISCOVERED": frozenset({"QUARANTINED", "BLOCKED"}),
    "QUARANTINED": frozenset({"REGISTERED", "BLOCKED", "RETIRED"}),
    "REGISTERED": frozenset({"APPROVED", "QUARANTINED", "BLOCKED", "SUPERSEDED"}),
    "APPROVED": frozenset({"AVAILABLE", "DOWNLOADING", "QUARANTINED_UPDATE", "BLOCKED"}),
    "AVAILABLE": frozenset({"DOWNLOADING", "CACHED", "WARM", "RUNNING", "DEGRADED", "BROKEN", "QUARANTINED_UPDATE"}),
    "DOWNLOADING": frozenset({"CACHED", "BROKEN", "QUARANTINED"}),
    "CACHED": frozenset({"WARM", "EVICTED", "BROKEN", "SUPERSEDED"}),
    "WARM": frozenset({"RUNNING", "SLEEPING", "CACHED", "DEGRADED", "BROKEN", "EVICTED"}),
    "RUNNING": frozenset({"WARM", "SLEEPING", "DEGRADED", "BROKEN"}),
    "SLEEPING": frozenset({"WARM", "EVICTED", "SUPERSEDED"}),
    "DEGRADED": frozenset({"AVAILABLE", "WARM", "RUNNING", "BROKEN", "QUARANTINED"}),
    "BROKEN": frozenset({"QUARANTINED", "BLOCKED", "RETIRED"}),
    "EVICTED": frozenset({"DOWNLOADING", "RETIRED", "SUPERSEDED"}),
    "SUPERSEDED": frozenset({"RETIRED"}),
    "RETIRED": frozenset(),
    "BLOCKED": frozenset({"QUARANTINED", "RETIRED"}),
    "QUARANTINED_UPDATE": frozenset({"APPROVED", "BLOCKED", "RETIRED"}),
}


def validate_transition(current: str, target: str) -> bool:
    """Return whether a single explicit lifecycle transition is allowed."""
    if current not in LIFECYCLE_STATES or target not in LIFECYCLE_STATES:
        return False
    return target in ALLOWED_TRANSITIONS[current]

