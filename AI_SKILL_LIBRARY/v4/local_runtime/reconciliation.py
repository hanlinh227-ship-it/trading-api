"""The boundary between governance and runtime residency.

Two planes, deliberately not merged into one enum:

**A. Governance / admission** - owned by the Open Model Universe control plane
(`v4/tools/open_model_universe.py`). It decides whether a model record is
allowed to exist, is licensed, is provenanced, is approved, is quarantined, is
blocked. It moves *records*.

**B. Runtime residency** - owned by this lane. It decides where an artifact
physically is: on disk, in memory, serving, asleep, evicted. It moves *bytes*.

The two vocabularies overlap in spelling, and that overlap is the trap this
module exists to close. `APPROVED` in the registry is a governance fact.
`RUNNING` in the registry is, at best, a claim somebody typed into YAML.
Neither is runtime truth, which is observed here and nowhere else.

The seam is a single, documented edge:

    registry record -> admission gate -> eligible candidate
                    -> projection -> ModelProfile
                    -> ENTRY_STATE (AVAILABLE) -> runtime lifecycle

`ENTRY_STATE` is the only door. A projected model always enters runtime
residency at `AVAILABLE` - approved, not yet fetched - regardless of what the
registry row claimed about being cached, warm or running. Everything after that
door is this lane's graph and this lane's evidence.

**Governance states never project.** `BLOCKED`, `QUARANTINED` and
`QUARANTINED_UPDATE` are admission verdicts, and a model carrying one produces
no runtime candidate at all - not a degraded one, not a restricted one, none.
`assert_separation()` checks that as a structural property rather than trusting
the projection code to remember.

One naming note worth keeping straight: this lane's runtime `QUARANTINED` means
"an artifact on disk failed verification and is held pending revalidation of
its bytes". It is reached only from runtime failure states and is not the
governance quarantine above. A governance quarantine never becomes either one -
it simply never projects.
"""

from __future__ import annotations

from typing import Any, Mapping

from ..tools.open_model_universe import LIFECYCLE_STATES as REGISTRY_STATES
from .lifecycle import ModelState

#: Governance verdicts. A registry row in one of these produces no runtime
#: candidate, at any admission status.
GOVERNANCE_ONLY_STATES = frozenset({"BLOCKED", "QUARANTINED", "QUARANTINED_UPDATE"})

#: Registry states that assert something about a live runtime. The research
#: lane rejects these from the registry pending runtime evidence, and this lane
#: treats them as unverified claims rather than facts.
RUNTIME_BEARING_REGISTRY_STATES = frozenset(
    {"DOWNLOADING", "CACHED", "WARM", "RUNNING", "SLEEPING", "DEGRADED"}
)

#: Registry states that are purely about admission progress.
ADMISSION_REGISTRY_STATES = frozenset(
    {"DISCOVERED", "REGISTERED", "APPROVED", "AVAILABLE", "SUPERSEDED", "RETIRED", "EVICTED", "BROKEN"}
)

#: The one door from governance into runtime residency. A projected model
#: enters here and nowhere else.
ENTRY_STATE = ModelState.AVAILABLE

#: Runtime residency states - this lane's territory, about bytes not records.
RESIDENCY_STATES = frozenset(
    {
        ModelState.AVAILABLE,
        ModelState.DOWNLOADING,
        ModelState.CACHED,
        ModelState.WARM,
        ModelState.RUNNING,
        ModelState.SLEEPING,
        ModelState.DEGRADED,
        ModelState.BROKEN,
        ModelState.EVICTED,
        ModelState.QUARANTINED,
    }
)


class SeparationBreach(RuntimeError):
    """A governance concept leaked into the runtime plane, or vice versa."""


def registry_state_is_runtime_bearing(state: str) -> bool:
    """Does this registry state claim something this lane must verify itself?"""
    return state in RUNTIME_BEARING_REGISTRY_STATES


def registry_state_is_governance_verdict(state: str) -> bool:
    """Is this an admission verdict that must never produce a candidate?"""
    return state in GOVERNANCE_ONLY_STATES


def residency_entry_state(registry_state: str) -> ModelState | None:
    """The runtime state a projected record enters at, or None if it may not.

    Always `AVAILABLE` for anything projectable. A registry row claiming
    `RUNNING` does not enter at `RUNNING`: residency is proven by observation,
    and the door is the same width for every record.
    """
    if registry_state_is_governance_verdict(registry_state):
        return None
    return ENTRY_STATE


def assert_separation() -> None:
    """Structural checks on the boundary. Raises rather than warns."""
    # 1. The runtime plane must not have invented a state for a governance-only
    #    concept. QUARANTINED_UPDATE is purely an admission verdict.
    runtime_names = {state.value for state in ModelState}
    if "QUARANTINED_UPDATE" in runtime_names:
        raise SeparationBreach(
            "QUARANTINED_UPDATE is a governance verdict and must not exist as a runtime state"
        )

    # 2. Every governance-only state must refuse to produce an entry state.
    for state in GOVERNANCE_ONLY_STATES:
        if residency_entry_state(state) is not None:
            raise SeparationBreach(f"governance state {state} projected into runtime residency")

    # 3. Projection's placeable set must exclude every governance verdict.
    from .projection import PLACEABLE_STATES

    leaked = PLACEABLE_STATES & GOVERNANCE_ONLY_STATES
    if leaked:
        raise SeparationBreach(f"projection would place models in governance states: {sorted(leaked)}")

    # 4. The door is one state wide.
    if ENTRY_STATE not in RESIDENCY_STATES:
        raise SeparationBreach("the entry state is not a residency state")


def boundary_report() -> Mapping[str, Any]:
    """A JSON-safe description of the boundary, for evidence artifacts."""
    return {
        "governance_plane": "AI_SKILL_LIBRARY/v4/tools/open_model_universe.py",
        "runtime_plane": "AI_SKILL_LIBRARY/v4/local_runtime/lifecycle.py",
        "entry_state": ENTRY_STATE.value,
        "governance_only_states": sorted(GOVERNANCE_ONLY_STATES),
        "runtime_bearing_registry_states": sorted(RUNTIME_BEARING_REGISTRY_STATES),
        "admission_registry_states": sorted(ADMISSION_REGISTRY_STATES),
        "residency_states": sorted(state.value for state in RESIDENCY_STATES),
        "registry_vocabulary": sorted(REGISTRY_STATES),
        "separated": True,
    }
