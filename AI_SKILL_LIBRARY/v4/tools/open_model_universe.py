"""Authority-free Open Model Universe governance lifecycle contracts.

This module owns metadata governance only. Runtime residency (acquiring, loading,
ready, running, warm, sleeping, degraded, evicted) is explicitly Claude-owned
and is not represented as Open Model Universe authority.
"""
from __future__ import annotations


LIFECYCLE_STATES = {
    "DISCOVERED",
    "QUARANTINED",
    "QUARANTINED_UPDATE",
    "REGISTERED",
    "APPROVED",
    "AVAILABLE",
    "BLOCKED",
    "SUPERSEDED",
    "RETIRED",
}

RUNTIME_RESIDENCY_OWNER = "claude_local_runtime"
RUNTIME_RESIDENCY_STATES = {
    "COLD",
    "ACQUIRING",
    "LOADING",
    "READY",
    "RUNNING",
    "WARM",
    "SLEEPING",
    "DEGRADED",
    "BROKEN",
    "EVICTED",
}

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "DISCOVERED": frozenset({"QUARANTINED", "BLOCKED"}),
    "QUARANTINED": frozenset({"REGISTERED", "BLOCKED", "RETIRED"}),
    "REGISTERED": frozenset({"APPROVED", "QUARANTINED", "BLOCKED", "SUPERSEDED"}),
    "APPROVED": frozenset({"AVAILABLE", "QUARANTINED_UPDATE", "BLOCKED", "SUPERSEDED"}),
    "AVAILABLE": frozenset({"QUARANTINED_UPDATE", "BLOCKED", "SUPERSEDED", "RETIRED"}),
    "BLOCKED": frozenset({"QUARANTINED", "RETIRED"}),
    "SUPERSEDED": frozenset({"RETIRED"}),
    "RETIRED": frozenset(),
    "QUARANTINED_UPDATE": frozenset({"APPROVED", "BLOCKED", "RETIRED"}),
}


def validate_transition(current: str, target: str) -> bool:
    """Return whether a single governance transition is allowed."""
    if current not in LIFECYCLE_STATES or target not in LIFECYCLE_STATES:
        return False
    return target in ALLOWED_TRANSITIONS[current]
