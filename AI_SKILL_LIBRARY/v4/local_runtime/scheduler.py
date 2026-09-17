"""Hardware-aware placement, wake/sleep, and priority admission.

The scheduler answers one question: *given what this machine actually has right
now, which model should serve this task, and what does it cost to get it there?*

It never selects a model on merit alone. A candidate has to clear eligibility
(lifecycle state, capability, context, zero-cost entitlement, privacy, runtime
health), then the machine has to clear admission (watermark vs. priority), then
the placement itself has to fit in memory that is provably free. Anything it
cannot prove, it refuses - `plan_placement` returns a refusal with a reason and
never raises, because a scheduler that throws takes the brain down with it.

Authority note: this module holds none. `task_router` routes, the Model Mesh
nominates candidates, and this code only says whether a nomination is
physically and financially safe to run here.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

from .lifecycle import NON_SELECTABLE_STATES, ModelState
from .resources import ResourceSnapshot, Watermark


class Priority(Enum):
    """Admission classes. Interactive work is never queued behind training."""

    P0_INTERACTIVE_CRITICAL = (0, False)
    P1_INTERACTIVE = (1, False)
    P2_STANDARD = (2, False)
    P3_BACKGROUND_EVAL = (3, True)
    P4_TRAINING = (4, True)
    P5_MAINTENANCE = (5, True)

    @property
    def rank(self) -> int:
        return self.value[0]

    @property
    def preemptible(self) -> bool:
        """May this class be yielded to make room for interactive work?"""
        return self.value[1]


class QualityTier(str, Enum):
    FAST = "FAST"
    STANDARD = "STANDARD"
    DEEP = "DEEP"


class Tri(str, Enum):
    """The registry schema's three-valued truth. UNKNOWN is never coerced."""

    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"

    @classmethod
    def of(cls, value: Any) -> "Tri":
        if value is True:
            return cls.TRUE
        if value is False:
            return cls.FALSE
        return cls.UNKNOWN

    @property
    def is_true(self) -> bool:
        return self is Tri.TRUE

    @property
    def is_false(self) -> bool:
        return self is Tri.FALSE


class AdmissionStatus(str, Enum):
    """Whether projection cleared this model for placement."""

    ADMITTED = "ADMITTED"
    INELIGIBLE = "INELIGIBLE"
    #: Usable, but not for anything needing the artifact it has not proven.
    RESTRICTED = "RESTRICTED"


class Privacy(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    SECRET = "SECRET"

    @property
    def rank(self) -> int:
        return _PRIVACY_RANK[self]


_PRIVACY_RANK = {Privacy.PUBLIC: 0, Privacy.INTERNAL: 1, Privacy.CONFIDENTIAL: 2, Privacy.SECRET: 3}

#: Above INTERNAL, the payload may not leave a runtime we control.
_LOCAL_ONLY_FROM = Privacy.CONFIDENTIAL


class PlacementAction(str, Enum):
    """What has to happen before this model can take the task."""

    SERVE_RUNNING = "SERVE_RUNNING"      # already serving; no new memory
    USE_WARM = "USE_WARM"                # loaded and idle; no new memory
    WAKE = "WAKE"                        # sleeping; re-acquire a runtime handle
    LOAD_FROM_CACHE = "LOAD_FROM_CACHE"  # on disk; full load
    ACQUIRE = "ACQUIRE"                  # not on disk; download first


#: Actions that must allocate memory they do not already hold. Only these are
#: fit-checked against the snapshot - a RUNNING model is already resident, and
#: refusing it for lack of "free" memory would evict work to make room for
#: itself.
_ALLOCATING = frozenset({PlacementAction.WAKE, PlacementAction.LOAD_FROM_CACHE, PlacementAction.ACQUIRE})

_STATE_ACTION: Mapping[ModelState, PlacementAction] = {
    ModelState.RUNNING: PlacementAction.SERVE_RUNNING,
    ModelState.WARM: PlacementAction.USE_WARM,
    ModelState.DEGRADED: PlacementAction.USE_WARM,
    ModelState.SLEEPING: PlacementAction.WAKE,
    ModelState.CACHED: PlacementAction.LOAD_FROM_CACHE,
    ModelState.AVAILABLE: PlacementAction.ACQUIRE,
    ModelState.EVICTED: PlacementAction.ACQUIRE,
}

#: How close each action is to "already answering". Drives both the locality
#: score and the start estimate.
_LOCALITY = {
    PlacementAction.SERVE_RUNNING: 1.00,
    PlacementAction.USE_WARM: 0.85,
    PlacementAction.WAKE: 0.50,
    PlacementAction.LOAD_FROM_CACHE: 0.30,
    PlacementAction.ACQUIRE: 0.05,
}

_START_SECONDS = {
    PlacementAction.SERVE_RUNNING: 0.05,
    PlacementAction.USE_WARM: 0.5,
    PlacementAction.WAKE: 3.0,
    PlacementAction.LOAD_FROM_CACHE: 15.0,
    PlacementAction.ACQUIRE: 300.0,
}

#: (locality weight, quality weight) per tier.
#:
#: FAST buys latency: a warm mediocre model beats a cold excellent one, because
#: the cold start costs more than the quality gap is worth. DEEP inverts that -
#: it is allowed to pay a cold start for the better specialist.
_TIER_WEIGHTS = {
    QualityTier.FAST: (0.85, 0.15),
    QualityTier.STANDARD: (0.45, 0.55),
    QualityTier.DEEP: (0.25, 0.75),
}


@dataclass(frozen=True)
class SchedulerPolicy:
    #: Fractions of *total* capacity held back. Headroom is not spendable: the
    #: OS, the page cache and the runtime itself all need room to breathe, and a
    #: placement that consumes the last megabyte OOMs the box, not just itself.
    ram_reserve_ratio: float = 0.10
    vram_reserve_ratio: float = 0.10
    disk_reserve_ratio: float = 0.05
    #: Total placements a single task may hold. FAST is single-model by design;
    #: the mesh policy's `max_parallel` counts *additional* models, so its
    #: {FAST: 0, STANDARD: 2, DEEP: 4} is this table's {1, 2, 4} ceiling.
    max_parallel: Mapping[QualityTier, int] = field(
        default_factory=lambda: {QualityTier.FAST: 1, QualityTier.STANDARD: 2, QualityTier.DEEP: 4}
    )
    #: Added to a candidate whose declared specialization matches the task.
    specialization_bonus: float = 0.10
    #: A DEGRADED model still answers, but it is not a first choice.
    degraded_penalty: float = 0.15
    #: Idle grace before a loaded model is put to sleep, per watermark.
    warm_idle_seconds: float = 300.0
    warm_idle_seconds_under_pressure: float = 60.0
    #: Stand-in for a model whose quality was never measured. Neutral on
    #: purpose: optimism would let an unmeasured model outrank a proven one,
    #: pessimism would make it unreachable and unmeasurable forever.
    unknown_quality_prior: float = 0.5


@dataclass(frozen=True)
class ModelProfile:
    """What a model needs, and what it is entitled to be used for."""

    model_id: str
    #: Minimum RAM. `None` means the registry did not say - which is refused at
    #: fit time, never treated as "needs nothing".
    ram_mb: int | None
    #: `None` means the model does not require an accelerator at all. Contrast
    #: with `ram_mb`, where `None` means unknown - the asymmetry is deliberate:
    #: "no GPU needed" is a real answer, "no RAM needed" is not.
    vram_mb: int | None
    disk_mb: int | None
    runtime: str
    context_limit: int | None
    #: Measured quality in 0..1, or `None` when the registry carries only a
    #: quality *class* and no number. Scoring then falls back to a neutral
    #: prior and the placement reports the quality as unevidenced.
    quality: float | None
    capabilities: frozenset[str] = frozenset()
    specializations: frozenset[str] = frozenset()
    #: Zero monetary cost at execution time. False models are unreachable while
    #: the request is FREE_ONLY - there is no paid fallback, ever.
    zero_cost: bool = True
    #: Runs inside a runtime we control (the payload never leaves the machine).
    local: bool = True
    #: Highest privacy tier this model may be handed.
    max_privacy: Privacy = Privacy.SECRET

    # -- provenance and identity ------------------------------------------
    #
    # Populated by `projection.py` from the Open Model Universe registry. A
    # hand-built profile leaves them unset, which is honest: nothing here is
    # inferred, and `None` means "the registry did not say", never a default.
    family: str | None = None
    variant: str | None = None
    #: The pinned upstream revision. Acquisition refuses a floating ref.
    revision: str | None = None
    #: Artifact identity. Both are required before anything may be downloaded.
    artifact_hash: str | None = None
    artifact_size_bytes: int | None = None
    quantization: str | None = None
    #: Every runtime that can load this artifact. `runtime` is the one chosen.
    runtime_support: frozenset[str] = frozenset()
    #: `ram_mb`/`vram_mb` above are the *minimum* - what fit-checking spends.
    #: These are the comfortable figures, used for scoring, never for fit.
    recommended_ram_mb: int | None = None
    recommended_vram_mb: int | None = None
    cpu_viable: Tri = Tri.UNKNOWN
    gpu_viable: Tri = Tri.UNKNOWN
    apple_silicon_viable: Tri = Tri.UNKNOWN
    license_verified: bool = False
    health: str = "unknown"
    #: The registry's free-form quality class, kept verbatim. Mapping it to a
    #: number needs a scoring table the research lane owns, so this lane does
    #: not invent one.
    quality_class: str | None = None
    #: Whether this profile cleared projection. A directly constructed profile
    #: is trusted - the constructor is a vetted act - but `projection.py` never
    #: relies on that default and always sets this explicitly.
    admission_status: AdmissionStatus = AdmissionStatus.ADMITTED
    #: Fail closed: downloading weights is the one irreversible, outbound act
    #: here, so it is off unless something proved it safe.
    acquisition_eligible: bool = False
    #: Why projection refused, when it did.
    exclusion_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class RuntimeSlot:
    """A model as the runtime currently holds it."""

    model: ModelProfile
    state: ModelState
    device: str | None = None
    runtime_healthy: bool = True
    idle_seconds: float = 0.0
    in_flight: int = 0

    @property
    def model_id(self) -> str:
        return self.model.model_id


@dataclass(frozen=True)
class TaskRequest:
    task_id: str
    priority: Priority = Priority.P1_INTERACTIVE
    quality_tier: QualityTier = QualityTier.STANDARD
    privacy: Privacy = Privacy.INTERNAL
    required_capabilities: frozenset[str] = frozenset()
    required_context: int = 0
    #: Zero-paid-token-first. The default is the policy, not a preference.
    free_only: bool = True


@dataclass(frozen=True)
class Placement:
    model_id: str
    runtime: str
    device: str | None
    action: PlacementAction
    estimated_start_s: float
    score: float


@dataclass(frozen=True)
class PlacementDecision:
    task_id: str
    admitted: bool
    reason: str
    placements: tuple[Placement, ...] = ()
    rejected: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SleepAction:
    model_id: str
    source: ModelState
    target: ModelState
    reason: str


# -- eligibility -----------------------------------------------------------


def _eligibility_refusal(slot: RuntimeSlot, request: TaskRequest) -> str | None:
    model = slot.model
    if slot.state in NON_SELECTABLE_STATES or slot.state not in _STATE_ACTION:
        return f"not selectable in state {slot.state.value}"
    if model.admission_status is AdmissionStatus.INELIGIBLE:
        detail = "; ".join(model.exclusion_reasons) or "projection marked it ineligible"
        return f"admission status INELIGIBLE: {detail}"
    if not slot.runtime_healthy:
        return f"runtime health check failing for {model.runtime}"
    missing = request.required_capabilities - model.capabilities
    if missing:
        return f"missing capabilities: {', '.join(sorted(missing))}"
    if model.context_limit is None:
        if request.required_context > 0:
            return "context window unknown: cannot prove the request fits"
    elif request.required_context > model.context_limit:
        return f"context {request.required_context} exceeds model context limit {model.context_limit}"
    if request.free_only and not model.zero_cost:
        return "not zero-cost eligible under FREE_ONLY; no paid fallback"
    if request.privacy.rank > model.max_privacy.rank:
        return f"privacy {request.privacy.value} exceeds model ceiling {model.max_privacy.value}"
    if request.privacy.rank >= _LOCAL_ONLY_FROM.rank and not model.local:
        return f"privacy {request.privacy.value} requires a local runtime"
    return None


# -- admission -------------------------------------------------------------


def _admission_refusal(snapshot: ResourceSnapshot, request: TaskRequest) -> str | None:
    """The machine's own veto, before any candidate is costed.

    At CRITICAL the box is protecting the task a person is waiting on: nothing
    else gets in. At PRESSURE (or when a dimension is unreadable, which is not
    proof of room) background and training work stands down so interactive work
    keeps its headroom.
    """
    mark = snapshot.watermark
    if mark is Watermark.CRITICAL and request.priority.rank > Priority.P1_INTERACTIVE.rank:
        return (
            f"resource watermark CRITICAL: only P0-P1 interactive work is admitted; "
            f"{request.priority.name} stands down"
        )
    if mark.severity >= Watermark.PRESSURE.severity and request.priority.rank > Priority.P2_STANDARD.rank:
        return (
            f"resource watermark {mark.value} at or above PRESSURE: only P0-P2 work is admitted; "
            f"{request.priority.name} stands down"
        )
    return None


# -- fit -------------------------------------------------------------------


@dataclass(frozen=True)
class _Budget:
    """Capacity this plan may still spend, decremented as placements are taken."""

    ram_mb: int | None
    vram_by_device: Mapping[int, int | None]
    disk_mb: int | None

    @classmethod
    def of(cls, snapshot: ResourceSnapshot, policy: SchedulerPolicy) -> "_Budget":
        ram = None
        if snapshot.ram_total_mb is not None and snapshot.ram_available_mb is not None:
            ram = int(snapshot.ram_available_mb - snapshot.ram_total_mb * policy.ram_reserve_ratio)
        disk = None
        if snapshot.disk_total_mb is not None and snapshot.disk_free_mb is not None:
            disk = int(snapshot.disk_free_mb - snapshot.disk_total_mb * policy.disk_reserve_ratio)
        vram: dict[int, int | None] = {}
        for gpu in snapshot.gpus:
            if gpu.vram_total_mb is None or gpu.vram_available_mb is None:
                vram[gpu.index] = None
            else:
                vram[gpu.index] = int(gpu.vram_available_mb - gpu.vram_total_mb * policy.vram_reserve_ratio)
        return cls(ram_mb=ram, vram_by_device=vram, disk_mb=disk)


def _fit_refusal(
    slot: RuntimeSlot, action: PlacementAction, budget: _Budget, snapshot: ResourceSnapshot
) -> tuple[str | None, str | None, int | None]:
    """Return (refusal, device, gpu_index) for one candidate against the budget."""
    model = slot.model
    if action not in _ALLOCATING:
        # Already resident: it is spending memory it has, not memory we have.
        return None, slot.device, None

    if action is PlacementAction.ACQUIRE:
        if not model.acquisition_eligible:
            detail = "; ".join(model.exclusion_reasons) or "artifact identity not proven"
            return f"not eligible for acquisition: {detail}", None, None
        if model.disk_mb is None:
            return "artifact size unknown: cannot prove the download fits", None, None
        if budget.disk_mb is None:
            return "disk capacity unknown: cannot prove the artifact fits", None, None
        if model.disk_mb > budget.disk_mb:
            return f"disk: needs {model.disk_mb} MB, {budget.disk_mb} MB usable", None, None

    if model.ram_mb is None:
        return "model ram requirement unknown: cannot prove it fits", None, None
    if budget.ram_mb is None:
        return "ram capacity unknown: cannot prove the model fits", None, None
    if model.ram_mb > budget.ram_mb:
        return f"ram: needs {model.ram_mb} MB, {budget.ram_mb} MB usable", None, None

    if model.vram_mb is None:
        return None, None, None

    if not snapshot.gpus:
        return f"vram: needs {model.vram_mb} MB but no GPU is present", None, None

    # Place on the roomiest device that can actually take it.
    best: tuple[int, int] | None = None
    unknown = False
    for gpu in snapshot.gpus:
        headroom = budget.vram_by_device.get(gpu.index)
        if headroom is None:
            unknown = True
            continue
        if model.vram_mb <= headroom and (best is None or headroom > best[1]):
            best = (gpu.index, headroom)
    if best is None:
        if unknown:
            return "vram capacity unknown: cannot prove the model fits", None, None
        largest = max((budget.vram_by_device.get(gpu.index) or 0) for gpu in snapshot.gpus)
        return f"vram: needs {model.vram_mb} MB, {largest} MB usable on the roomiest device", None, None
    return None, f"gpu:{best[0]}", best[0]


def _spend(budget: _Budget, slot: RuntimeSlot, action: PlacementAction, gpu_index: int | None) -> _Budget:
    if action not in _ALLOCATING:
        return budget
    model = slot.model
    ram = budget.ram_mb
    if ram is not None and model.ram_mb is not None:
        ram -= model.ram_mb
    disk = budget.disk_mb
    if action is PlacementAction.ACQUIRE and disk is not None and model.disk_mb is not None:
        disk -= model.disk_mb
    vram = dict(budget.vram_by_device)
    if gpu_index is not None and model.vram_mb is not None and vram.get(gpu_index) is not None:
        vram[gpu_index] = vram[gpu_index] - model.vram_mb
    return replace(budget, ram_mb=ram, vram_by_device=vram, disk_mb=disk)


# -- scoring ---------------------------------------------------------------


def _score(slot: RuntimeSlot, action: PlacementAction, request: TaskRequest, policy: SchedulerPolicy) -> float:
    locality_weight, quality_weight = _TIER_WEIGHTS[request.quality_tier]
    quality = slot.model.quality
    if quality is None:
        quality = policy.unknown_quality_prior
    score = locality_weight * _LOCALITY[action] + quality_weight * quality
    if slot.model.specializations & request.required_capabilities:
        score += policy.specialization_bonus
    if slot.state is ModelState.DEGRADED:
        score -= policy.degraded_penalty
    return score


# -- public API ------------------------------------------------------------


def plan_placement(
    request: TaskRequest,
    candidates: Iterable[RuntimeSlot],
    snapshot: ResourceSnapshot,
    policy: SchedulerPolicy | None = None,
) -> PlacementDecision:
    """Choose where this task runs, or refuse with a reason. Never raises."""
    policy = policy or SchedulerPolicy()
    candidates = list(candidates)
    rejected: dict[str, str] = {}

    eligible: list[RuntimeSlot] = []
    for slot in candidates:
        refusal = _eligibility_refusal(slot, request)
        if refusal:
            rejected[slot.model_id] = refusal
        else:
            eligible.append(slot)

    admission = _admission_refusal(snapshot, request)
    if admission:
        return PlacementDecision(task_id=request.task_id, admitted=False, reason=admission, rejected=rejected)

    if not eligible:
        reason = (
            "no eligible candidate: the candidate set was empty"
            if not candidates
            else f"no eligible candidate: all {len(candidates)} were refused"
        )
        return PlacementDecision(task_id=request.task_id, admitted=False, reason=reason, rejected=rejected)

    # Score first, then fit in score order, so the budget is spent on the best
    # candidates rather than on whichever happened to be enumerated first.
    ranked = sorted(
        ((slot, _STATE_ACTION[slot.state]) for slot in eligible),
        key=lambda pair: _score(pair[0], pair[1], request, policy),
        reverse=True,
    )

    budget = _Budget.of(snapshot, policy)
    wanted = max(1, policy.max_parallel.get(request.quality_tier, 1))
    placements: list[Placement] = []
    for slot, action in ranked:
        if len(placements) >= wanted:
            break
        refusal, device, gpu_index = _fit_refusal(slot, action, budget, snapshot)
        if refusal:
            rejected[slot.model_id] = refusal
            continue
        budget = _spend(budget, slot, action, gpu_index)
        placements.append(
            Placement(
                model_id=slot.model_id,
                runtime=slot.model.runtime,
                device=device,
                action=action,
                estimated_start_s=_START_SECONDS[action],
                score=round(_score(slot, action, request, policy), 6),
            )
        )

    if not placements:
        return PlacementDecision(
            task_id=request.task_id,
            admitted=False,
            reason="no candidate fits the available resources",
            rejected=rejected,
        )
    return PlacementDecision(
        task_id=request.task_id,
        admitted=True,
        reason=f"placed on {len(placements)} model(s) at watermark {snapshot.watermark.value}",
        placements=tuple(placements),
        rejected=rejected,
    )


def plan_sleep(
    slots: Sequence[RuntimeSlot], snapshot: ResourceSnapshot, policy: SchedulerPolicy | None = None
) -> tuple[SleepAction, ...]:
    """Decide which loaded models release their memory.

    A model serving a task is never touched, at any watermark: shedding memory
    by killing the work someone is waiting on defeats the point.
    """
    policy = policy or SchedulerPolicy()
    mark = snapshot.watermark
    if mark is Watermark.CRITICAL:
        grace = 0.0
    elif mark.severity >= Watermark.PRESSURE.severity:
        grace = policy.warm_idle_seconds_under_pressure
    else:
        grace = policy.warm_idle_seconds

    actions: list[SleepAction] = []
    for slot in slots:
        if slot.in_flight > 0 or slot.state is ModelState.RUNNING:
            continue
        if slot.idle_seconds < grace:
            continue
        if slot.state in (ModelState.WARM, ModelState.DEGRADED):
            actions.append(
                SleepAction(
                    model_id=slot.model_id,
                    source=slot.state,
                    target=ModelState.SLEEPING,
                    reason=f"idle {slot.idle_seconds:.0f}s at watermark {mark.value}",
                )
            )
        elif slot.state is ModelState.SLEEPING and mark is Watermark.CRITICAL:
            # Only under CRITICAL is it worth paying the reload cost to hand the
            # last of a sleeping model's footprint back to the machine.
            actions.append(
                SleepAction(
                    model_id=slot.model_id,
                    source=slot.state,
                    target=ModelState.CACHED,
                    reason=f"shedding runtime footprint at watermark {mark.value}",
                )
            )
    return tuple(actions)
