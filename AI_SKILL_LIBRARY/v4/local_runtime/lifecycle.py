"""Model runtime lifecycle.

A model is never "enabled" by a flag. It walks a state machine, and every hop is
checked against the graph below before it is accepted. The graph is the whole
point: it is what makes `DISCOVERED -> RUNNING` impossible to express, so a
model that was merely *seen* can never serve a task, and a half-written artifact
can never be handed to a runtime.

States
------
DISCOVERED    seen by discovery, nothing verified
REGISTERED    recorded in the Open Model Universe registry with metadata
APPROVED      licence, provenance and policy cleared for use
AVAILABLE     approved and its source is reachable; no local artifact yet
DOWNLOADING   acquisition in flight; the artifact is partial and unusable
CACHED        artifact complete on disk and checksum-verified
WARM          loaded into a runtime, holding memory, serving nothing
RUNNING       actively serving a task
SLEEPING      artifact cached, runtime handle released, cheap to wake
DEGRADED      usable but below its expected quality/latency envelope
BROKEN        failed in a way that needs triage before reuse
QUARANTINED   held out of selection by policy after failure, pending revalidation
EVICTED       artifact deleted to reclaim disk; registry history survives
SUPERSEDED    a better revision of the same model won
RETIRED       terminal; end of this model's life in the universe
BLOCKED       policy refuses it (licence, privacy, security); re-review only
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class ModelState(str, Enum):
    DISCOVERED = "DISCOVERED"
    REGISTERED = "REGISTERED"
    APPROVED = "APPROVED"
    AVAILABLE = "AVAILABLE"
    DOWNLOADING = "DOWNLOADING"
    CACHED = "CACHED"
    WARM = "WARM"
    RUNNING = "RUNNING"
    SLEEPING = "SLEEPING"
    DEGRADED = "DEGRADED"
    BROKEN = "BROKEN"
    QUARANTINED = "QUARANTINED"
    EVICTED = "EVICTED"
    SUPERSEDED = "SUPERSEDED"
    RETIRED = "RETIRED"
    BLOCKED = "BLOCKED"

    def __str__(self) -> str:  # pragma: no cover - display only
        return self.value


class LifecycleError(RuntimeError):
    """A transition that the lifecycle graph does not allow."""


#: States in which a complete, verified artifact exists on local disk.
LOCAL_ARTIFACT_STATES = frozenset(
    {ModelState.CACHED, ModelState.WARM, ModelState.RUNNING, ModelState.SLEEPING, ModelState.DEGRADED}
)

#: States in which the model occupies runtime memory.
LOADED_STATES = frozenset({ModelState.WARM, ModelState.RUNNING, ModelState.DEGRADED})

#: States eligible to serve a task without first re-acquiring the artifact.
SERVICEABLE_STATES = frozenset({ModelState.RUNNING, ModelState.WARM, ModelState.SLEEPING, ModelState.CACHED})

#: States from which policy may not select a model, whatever its score.
NON_SELECTABLE_STATES = frozenset(
    {
        ModelState.DISCOVERED,
        ModelState.REGISTERED,
        ModelState.DOWNLOADING,
        ModelState.BROKEN,
        ModelState.QUARANTINED,
        ModelState.SUPERSEDED,
        ModelState.RETIRED,
        ModelState.BLOCKED,
    }
)

# Policy may pull a model out of circulation from any live state, so BLOCKED is
# appended to every row except BLOCKED's own and the terminal state's.
_TRANSITIONS: dict[ModelState, frozenset[ModelState]] = {
    ModelState.DISCOVERED: frozenset({ModelState.REGISTERED, ModelState.RETIRED}),
    ModelState.REGISTERED: frozenset({ModelState.APPROVED, ModelState.SUPERSEDED, ModelState.RETIRED}),
    ModelState.APPROVED: frozenset({ModelState.AVAILABLE, ModelState.SUPERSEDED, ModelState.RETIRED}),
    # Acquisition may start only from APPROVED-and-reachable.
    ModelState.AVAILABLE: frozenset({ModelState.DOWNLOADING, ModelState.SUPERSEDED, ModelState.RETIRED}),
    # A download either completes into a verified artifact, fails, or is abandoned.
    ModelState.DOWNLOADING: frozenset({ModelState.CACHED, ModelState.BROKEN, ModelState.AVAILABLE}),
    ModelState.CACHED: frozenset(
        {ModelState.WARM, ModelState.EVICTED, ModelState.BROKEN, ModelState.SUPERSEDED, ModelState.RETIRED}
    ),
    ModelState.WARM: frozenset(
        {ModelState.RUNNING, ModelState.SLEEPING, ModelState.CACHED, ModelState.DEGRADED, ModelState.BROKEN}
    ),
    ModelState.RUNNING: frozenset({ModelState.WARM, ModelState.DEGRADED, ModelState.BROKEN}),
    ModelState.SLEEPING: frozenset(
        {ModelState.WARM, ModelState.CACHED, ModelState.EVICTED, ModelState.BROKEN, ModelState.RETIRED}
    ),
    ModelState.DEGRADED: frozenset(
        {ModelState.WARM, ModelState.CACHED, ModelState.BROKEN, ModelState.QUARANTINED, ModelState.RETIRED}
    ),
    # Triage decides between "watch it" and "hold it out", per policy.
    ModelState.BROKEN: frozenset(
        {ModelState.DEGRADED, ModelState.QUARANTINED, ModelState.EVICTED, ModelState.RETIRED}
    ),
    # Quarantine clears only through revalidation of the artifact itself.
    ModelState.QUARANTINED: frozenset({ModelState.CACHED, ModelState.EVICTED, ModelState.RETIRED}),
    # Weights are gone: the only way back is to acquire them again.
    ModelState.EVICTED: frozenset({ModelState.AVAILABLE, ModelState.SUPERSEDED, ModelState.RETIRED}),
    ModelState.SUPERSEDED: frozenset({ModelState.EVICTED, ModelState.RETIRED}),
    # A block is cleared by re-review, which re-enters the approval path.
    ModelState.BLOCKED: frozenset({ModelState.REGISTERED, ModelState.RETIRED}),
    ModelState.RETIRED: frozenset(),
}

_TRANSITIONS = {
    source: targets if source in (ModelState.BLOCKED, ModelState.RETIRED) else targets | {ModelState.BLOCKED}
    for source, targets in _TRANSITIONS.items()
}


def valid_targets(state: ModelState) -> frozenset[ModelState]:
    """States reachable from `state` in one hop."""
    return _TRANSITIONS[ModelState(state)]


def is_terminal(state: ModelState) -> bool:
    return not _TRANSITIONS[ModelState(state)]


def transition_reason(source: ModelState, target: ModelState) -> str | None:
    """Why `source -> target` is refused, or None when it is allowed.

    Pure: callers can pre-check a hop without touching any lifecycle.
    """
    source, target = ModelState(source), ModelState(target)
    if source is target:
        return f"{source} -> {target}: a state cannot transition to itself"
    allowed = _TRANSITIONS[source]
    if target in allowed:
        return None
    if is_terminal(source):
        return f"{source} is terminal; no transition to {target} is possible"
    legal = ", ".join(sorted(state.value for state in allowed))
    return f"{source} -> {target} is not a legal transition; legal targets are: {legal}"


@dataclass(frozen=True)
class TransitionRecord:
    source: ModelState
    target: ModelState
    reason: str


class ModelLifecycle:
    """The lifecycle of one model in the universe, with its audit trail."""

    def __init__(self, model_id: str, state: ModelState = ModelState.DISCOVERED) -> None:
        if not model_id or not model_id.strip():
            raise LifecycleError("model_id is required")
        self.model_id = model_id
        self._state = ModelState(state)
        self._history: list[TransitionRecord] = []

    @property
    def state(self) -> ModelState:
        return self._state

    @property
    def history(self) -> tuple[TransitionRecord, ...]:
        return tuple(self._history)

    @property
    def is_loaded(self) -> bool:
        """True while the model occupies runtime memory."""
        return self._state in LOADED_STATES

    @property
    def has_local_artifact(self) -> bool:
        """True only for a complete, verified artifact - never mid-download."""
        return self._state in LOCAL_ARTIFACT_STATES

    @property
    def is_selectable(self) -> bool:
        return self._state not in NON_SELECTABLE_STATES

    def can_transition(self, target: ModelState) -> bool:
        return transition_reason(self._state, target) is None

    def transition(self, target: ModelState, *, reason: str) -> TransitionRecord:
        """Move to `target`, or raise and leave the lifecycle untouched."""
        if not reason or not reason.strip():
            raise LifecycleError(f"{self.model_id}: a transition reason is required")
        target = ModelState(target)
        refusal = transition_reason(self._state, target)
        if refusal is not None:
            raise LifecycleError(f"{self.model_id}: {refusal}")
        record = TransitionRecord(source=self._state, target=target, reason=reason.strip())
        self._state = target
        self._history.append(record)
        return record

    def transition_path(self, targets: Iterable[ModelState], *, reason: str) -> None:
        """Walk several hops, failing on the first illegal one."""
        for target in targets:
            self.transition(target, reason=reason)

    def __repr__(self) -> str:  # pragma: no cover - display only
        return f"ModelLifecycle({self.model_id!r}, state={self._state.value})"
