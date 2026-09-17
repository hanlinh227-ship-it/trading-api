"""Runtime residency lifecycle.

The split QA asked for. Governance and residency were answering different
questions with one vocabulary, and the overlap hid the difference:

* **Governance** (Open Model Universe) asks *may this model be used at all* -
  is it discovered, registered, licensed, approved, quarantined, blocked,
  retired. It is about a record, and it is not this lane's to decide.
* **Residency** (here) asks *where are these bytes right now* - not on disk, in
  flight, loading, on disk, in memory, serving, asleep, degraded, gone. It is
  about an artifact on a machine, and it is observed rather than declared.

They are not two views of one axis. A model can be `APPROVED` and `COLD`
simultaneously, because those answer different questions; expressing both with
one enum forced a choice between facts that are both true. So residency gets its
own names, with no governance state duplicated among them.

The two planes meet at exactly one gate, `admit_to_residency()`, and it takes
three separate proofs:

1. governance says `APPROVED` (or a later non-verdict state),
2. artifact/security admission passed,
3. the model is runtime-eligible on this host.

All three, or no residency at all. `BLOCKED` and `QUARANTINED` return `None` -
not `OFFLINE`, not `BROKEN`, nothing. A governance verdict does not produce a
degraded runtime object; it produces no runtime object.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .lifecycle import ModelState


class ResidencyState(str, Enum):
    """Where an artifact physically is. No governance state appears here."""

    COLD = "COLD"            # approved, nothing on this machine
    ACQUIRING = "ACQUIRING"  # transfer in flight; bytes are partial and unusable
    LOADING = "LOADING"      # verified on disk, being brought into memory
    READY = "READY"          # verified on disk, not loaded
    WARM = "WARM"            # in memory, idle
    RUNNING = "RUNNING"      # in memory, serving
    SLEEPING = "SLEEPING"    # on disk, runtime handle released, cheap to wake
    DEGRADED = "DEGRADED"    # usable, below its expected envelope
    BROKEN = "BROKEN"        # failed; needs triage before reuse
    OFFLINE = "OFFLINE"      # the host or worker holding it is unreachable

    def __str__(self) -> str:  # pragma: no cover - display only
        return self.value


#: Governance states that are verdicts: they produce no residency at all.
GOVERNANCE_VERDICTS = frozenset({"BLOCKED", "QUARANTINED", "QUARANTINED_UPDATE", "RETIRED"})

#: Governance states from which residency may begin, once the other two proofs
#: are in hand. Note `DISCOVERED` and `REGISTERED` are absent: being known is
#: not being approved.
RESIDENCY_ELIGIBLE_GOVERNANCE = frozenset({"APPROVED", "AVAILABLE"})

#: States in which the artifact is complete and verified on disk.
ON_DISK = frozenset(
    {
        ResidencyState.READY,
        ResidencyState.LOADING,
        ResidencyState.WARM,
        ResidencyState.RUNNING,
        ResidencyState.SLEEPING,
        ResidencyState.DEGRADED,
    }
)

#: States in which the artifact occupies memory.
IN_MEMORY = frozenset({ResidencyState.WARM, ResidencyState.RUNNING, ResidencyState.DEGRADED})

_TRANSITIONS: Mapping[ResidencyState, frozenset[ResidencyState]] = {
    ResidencyState.COLD: frozenset({ResidencyState.ACQUIRING, ResidencyState.OFFLINE}),
    # A transfer either completes into a verified artifact, fails, or is
    # abandoned back to COLD. It never becomes READY without verification.
    ResidencyState.ACQUIRING: frozenset(
        {ResidencyState.READY, ResidencyState.BROKEN, ResidencyState.COLD, ResidencyState.OFFLINE}
    ),
    ResidencyState.READY: frozenset(
        {ResidencyState.LOADING, ResidencyState.COLD, ResidencyState.BROKEN, ResidencyState.OFFLINE}
    ),
    ResidencyState.LOADING: frozenset(
        {ResidencyState.WARM, ResidencyState.BROKEN, ResidencyState.READY, ResidencyState.OFFLINE}
    ),
    ResidencyState.WARM: frozenset(
        {
            ResidencyState.RUNNING,
            ResidencyState.SLEEPING,
            ResidencyState.READY,
            ResidencyState.DEGRADED,
            ResidencyState.BROKEN,
            ResidencyState.OFFLINE,
        }
    ),
    ResidencyState.RUNNING: frozenset(
        {ResidencyState.WARM, ResidencyState.DEGRADED, ResidencyState.BROKEN, ResidencyState.OFFLINE}
    ),
    ResidencyState.SLEEPING: frozenset(
        {ResidencyState.LOADING, ResidencyState.READY, ResidencyState.COLD,
         ResidencyState.BROKEN, ResidencyState.OFFLINE}
    ),
    ResidencyState.DEGRADED: frozenset(
        {ResidencyState.WARM, ResidencyState.READY, ResidencyState.BROKEN, ResidencyState.OFFLINE}
    ),
    ResidencyState.BROKEN: frozenset({ResidencyState.COLD, ResidencyState.READY, ResidencyState.OFFLINE}),
    # A worker that comes back re-proves what it holds; it does not resume.
    ResidencyState.OFFLINE: frozenset({ResidencyState.COLD}),
}

#: How residency maps onto the artifact-lifecycle states the scheduler and
#: cache already speak. One direction only, and deliberately partial: residency
#: is the runtime's own vocabulary and the bridge exists so the two do not have
#: to be migrated in one step.
_TO_MODEL_STATE: Mapping[ResidencyState, ModelState] = {
    ResidencyState.COLD: ModelState.AVAILABLE,
    ResidencyState.ACQUIRING: ModelState.DOWNLOADING,
    ResidencyState.READY: ModelState.CACHED,
    ResidencyState.LOADING: ModelState.CACHED,
    ResidencyState.WARM: ModelState.WARM,
    ResidencyState.RUNNING: ModelState.RUNNING,
    ResidencyState.SLEEPING: ModelState.SLEEPING,
    ResidencyState.DEGRADED: ModelState.DEGRADED,
    ResidencyState.BROKEN: ModelState.BROKEN,
    ResidencyState.OFFLINE: ModelState.EVICTED,
}


class ResidencyError(RuntimeError):
    """A residency transition the graph does not allow."""


def valid_residency_targets(state: ResidencyState) -> frozenset[ResidencyState]:
    return _TRANSITIONS[ResidencyState(state)]


def to_model_state(state: ResidencyState) -> ModelState:
    """Bridge into the artifact-lifecycle vocabulary the scheduler speaks."""
    return _TO_MODEL_STATE[ResidencyState(state)]


def residency_transition_reason(source: ResidencyState, target: ResidencyState) -> str | None:
    source, target = ResidencyState(source), ResidencyState(target)
    if source is target:
        return f"{source} -> {target}: a state cannot transition to itself"
    if target in _TRANSITIONS[source]:
        return None
    legal = ", ".join(sorted(state.value for state in _TRANSITIONS[source]))
    return f"{source} -> {target} is not a legal residency transition; legal targets are: {legal}"


@dataclass(frozen=True)
class AdmissionDecision:
    """Why residency was or was not granted."""

    state: ResidencyState | None
    reasons: tuple[str, ...] = ()

    @property
    def granted(self) -> bool:
        return self.state is not None

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "residency_state": self.state.value if self.state else None,
            "granted": self.granted,
            "reasons": list(self.reasons),
        }


def admit_to_residency(
    governance_state: str,
    *,
    artifact_admitted: bool,
    runtime_eligible: bool,
    artifact_on_disk: bool = False,
) -> AdmissionDecision:
    """The single gate from governance into runtime residency.

    Three independent proofs, all required. A model that is approved but whose
    artifact failed the safe-loader check gets no residency, and neither does a
    safe artifact whose model was never approved.
    """
    reasons: list[str] = []
    state = str(governance_state or "").strip().upper()

    if state in GOVERNANCE_VERDICTS:
        # Deliberately terminal: a verdict yields no runtime object of any kind.
        return AdmissionDecision(
            state=None,
            reasons=(f"governance state {state} is a verdict; it does not project into runtime",),
        )
    if state not in RESIDENCY_ELIGIBLE_GOVERNANCE:
        reasons.append(
            f"governance state {state or '<missing>'} is not approved for residency; "
            f"expected one of {sorted(RESIDENCY_ELIGIBLE_GOVERNANCE)}"
        )
    if not artifact_admitted:
        reasons.append("artifact/security admission did not pass")
    if not runtime_eligible:
        reasons.append("model is not runtime-eligible on this host")

    if reasons:
        return AdmissionDecision(state=None, reasons=tuple(reasons))
    return AdmissionDecision(state=ResidencyState.READY if artifact_on_disk else ResidencyState.COLD)
