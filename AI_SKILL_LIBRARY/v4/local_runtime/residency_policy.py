"""Which admitted models are worth keeping resident, from measured evidence.

This is a *policy tier*, not a new lifecycle. `ResidencyState` already owns
where an artifact physically is - COLD, READY, WARM, RUNNING, SLEEPING - and
nothing here adds a state to that. A tier says what the scheduler should aim
for; the residency state says what is true right now. Conflating them would be
the second lifecycle the architecture forbids, so each tier is defined by the
existing state it targets:

    HOT       keep in WARM/RUNNING - loaded, no cold load on the next request
    WARM      keep READY on disk   - verified, load on demand
    COLD      keep READY on disk   - first to be evicted under pressure
    ARCHIVED  artifact evictable   - redundant or superseded

Two things decide a tier and both are measured, never assumed:

* the RAM a model actually needed when loaded, against this host's real memory,
  budgeted at the existing PRESSURE watermark rather than a fresh constant;
* its measured capability and its measured warm inference latency.

The trade the numbers expose is the whole reason this has to be evidence-driven.
On this host the strongest model is also the slowest - 0.917 capability at
5066 ms against 0.750 at 665 ms - so "keep the best model hot" and "answer
quickly" pull in opposite directions, and neither is right on its own. The plan
therefore fills HOT with a fast worker first and a strong one second, which is
what FAST and DEEP actually need, and stops when the budget is spent.

A model with no digest-bound capability measurement is never promoted above
COLD. Residency is a commitment of real memory; committing it to a model nobody
has measured is how a registry entry turns into a resource cost for nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .resources import PRESSURE_THRESHOLD

#: Tier names, and the residency state each one targets.
HOT = "HOT"
WARM = "WARM"
COLD = "COLD"
ARCHIVED = "ARCHIVED"

TARGET_STATE: Mapping[str, str] = {
    HOT: "WARM",       # loaded and idle, ready to serve without a load
    WARM: "READY",     # verified on disk, loaded on demand
    COLD: "READY",     # verified on disk, first evicted under pressure
    ARCHIVED: "COLD",  # artifact itself may be removed
}


@dataclass(frozen=True)
class ResidencyCandidate:
    """One admitted model, with what was actually measured about it."""

    model_id: str
    family: str
    peak_ram_mb: float | None
    capability: float | None
    warm_inference_ms: float | None
    cold_load_ms: float | None

    @property
    def measured(self) -> bool:
        return (
            self.capability is not None
            and self.peak_ram_mb is not None
            and self.warm_inference_ms is not None
        )


@dataclass(frozen=True)
class TierAssignment:
    model_id: str
    tier: str
    target_state: str
    reason: str
    peak_ram_mb: float | None = None
    capability: float | None = None
    warm_inference_ms: float | None = None

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "model_id": self.model_id,
            "tier": self.tier,
            "target_residency_state": self.target_state,
            "reason": self.reason,
            "peak_ram_mb": self.peak_ram_mb,
            "measured_capability": self.capability,
            "warm_inference_ms": self.warm_inference_ms,
        }


@dataclass(frozen=True)
class ResidencyPlan:
    host_ram_mb: float | None
    hot_budget_mb: float | None
    committed_mb: float
    assignments: tuple[TierAssignment, ...]

    def tier(self, model_id: str) -> str | None:
        for row in self.assignments:
            if row.model_id == model_id:
                return row.tier
        return None

    @property
    def hot(self) -> tuple[str, ...]:
        return tuple(a.model_id for a in self.assignments if a.tier == HOT)

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "host_ram_mb": self.host_ram_mb,
            "hot_budget_mb": self.hot_budget_mb,
            "committed_mb": round(self.committed_mb, 2),
            "hot": list(self.hot),
            "assignments": [a.to_dict() for a in self.assignments],
            # Restated so no consumer reads a plan as an action.
            "plan_only_nothing_loaded": True,
        }


def hot_budget_mb(host_ram_mb: float | None) -> float | None:
    """How much memory may be committed to resident models.

    The PRESSURE watermark, reused rather than reinvented: the scheduler already
    treats 80% utilisation as the point where placement stops being safe, so
    committing residency past it would be planning for a state the scheduler
    would refuse. Unknown host memory yields None - no budget, and therefore no
    HOT tier, because committing memory you cannot measure is guessing.
    """
    if host_ram_mb is None or host_ram_mb <= 0:
        return None
    return round(float(host_ram_mb) * PRESSURE_THRESHOLD, 2)


def plan_residency(candidates: Sequence[ResidencyCandidate], *,
                   host_ram_mb: float | None) -> ResidencyPlan:
    """Assign tiers under the measured RAM budget. Loads nothing."""
    budget = hot_budget_mb(host_ram_mb)
    assignments: list[TierAssignment] = []
    committed = 0.0

    measured = [c for c in candidates if c.measured]
    unmeasured = [c for c in candidates if not c.measured]

    def assign(candidate: ResidencyCandidate, tier: str, reason: str) -> None:
        assignments.append(TierAssignment(
            model_id=candidate.model_id, tier=tier, target_state=TARGET_STATE[tier],
            reason=reason, peak_ram_mb=candidate.peak_ram_mb,
            capability=candidate.capability, warm_inference_ms=candidate.warm_inference_ms,
        ))

    if budget is None:
        for candidate in candidates:
            assign(candidate, COLD, "host memory is unknown; nothing is committed to residency")
        return ResidencyPlan(host_ram_mb, None, 0.0, tuple(assignments))

    # Fastest first: a hot worker exists to remove the load from the common
    # request, and the common request wants an answer, not the best answer.
    #
    # Ties break on model_id, not on the other measurement. Breaking the
    # capability tie on latency flipped the plan between Qwen3-4B and Phi-3-mini
    # on a 28 ms difference in a ~5100 ms inference - half a percent, inside
    # measurement noise - so the chosen model changed run to run for no reason
    # anyone could act on. A deterministic, admittedly arbitrary tie-break is
    # better than an unstable one dressed as a measured preference, and the
    # assignment reason says which it was.
    fastest = sorted(measured, key=lambda c: (c.warm_inference_ms, c.model_id))
    strongest = sorted(measured, key=lambda c: (-(c.capability or 0.0), c.model_id))

    order: list[ResidencyCandidate] = []
    for candidate in (fastest[:1] + strongest[:1]):
        if candidate not in order:
            order.append(candidate)

    promoted: set[str] = set()
    for candidate in order:
        if committed + candidate.peak_ram_mb > budget:
            continue
        committed += candidate.peak_ram_mb
        role = "fastest measured worker" if candidate is fastest[0] else "strongest measured worker"
        tied = [c.model_id for c in measured if c.capability == candidate.capability] \
            if candidate is strongest[0] else []
        note = ""
        if len(tied) > 1:
            note = (f"; tied on capability with {', '.join(m for m in tied if m != candidate.model_id)}"
                    f", broken by model_id rather than by a latency difference inside noise")
        assign(candidate, HOT,
               f"{role}: capability {candidate.capability}, warm inference "
               f"{candidate.warm_inference_ms} ms, {candidate.peak_ram_mb} MB within the "
               f"{budget} MB budget{note}")
        promoted.add(candidate.model_id)

    for candidate in measured:
        if candidate.model_id in promoted:
            continue
        # Say which it actually is. Reporting "the budget is spent" while 5.5 GB
        # of 12.9 GB remained would have been false, and the distinction
        # matters: a model held back by the budget becomes promotable when
        # memory frees up, one held back for being neither fastest nor
        # strongest does not.
        if committed + (candidate.peak_ram_mb or 0.0) > budget:
            reason = (f"would exceed the {budget} MB residency budget "
                      f"({committed:.0f} MB already committed); load on demand")
        else:
            reason = ("neither the fastest nor the strongest measured worker, so residency "
                      "would cost memory without shortening any request; load on demand")
        assign(candidate, WARM, reason)

    for candidate in unmeasured:
        assign(candidate, COLD,
               "no digest-bound capability measurement; residency is not committed to an "
               "unmeasured model")

    return ResidencyPlan(host_ram_mb, budget, committed, tuple(assignments))
