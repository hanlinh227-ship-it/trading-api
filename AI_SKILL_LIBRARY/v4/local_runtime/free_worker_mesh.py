"""One view over every execution path, for every wave, holding no authority.

The federation has two kinds of executor and they were answering separately:
`WorkerRegistry` for machines that take our weights, `ProviderRegistry` for
hosted catalogs that serve their own. Asking each in turn works until a third
kind appears - an operator's Mac, a free GPU tier, something that does not exist
yet - and then every caller has to learn about it. This is the single surface
they all arrive through, so adding an executor is a registration rather than a
change to anything that selects.

**The mesh is capacity, not authority.** It advertises resources, reports
health, and answers "which of these could run this". It does not route, does not
choose a model, does not admit anything. `task_router` routes, the Model Mesh
selects, the Open Model Universe admits, and the runtime scheduler places. This
answers one question those authorities ask, and the authority flags are class
attributes fixed at False so it cannot acquire a second job by accident.

**What makes it wave-independent** is that a capability is a string. Wave 3 asks
for `coding`; a later wave asks for `vision` or `OCR` or `audio_understanding`,
and nothing here changes - the new requirement matches against the *measured*
capability tags a worker carries, and a worker that has not been measured for it
is simply not eligible. A capability may be named before it is measured. It may
not qualify anything before it is measured, which is the whole difference
between a taxonomy and a claim.

**Four things exclude a worker before capability is even considered**, because
each of them means the job would not arrive:

* a stale lease - the heartbeat is older than the worker promised, so the
  machine may already be gone;
* an open circuit - it has failed repeatedly and is in cooldown;
* exhausted quota - a free tier with nothing left, which retrying cannot fix
  and only the reset clears;
* no spare capacity - it is already carrying its maximum.

Selection among what remains is not by cost alone. Cost is a filter (nothing
paid, ever, without a human), and among the zero-cost survivors the ordering is
by fit: owned hardware first because it is private and has no quota, then
measured latency, then the ones with headroom. A provider that happens to be
listed first in a config file gets no advantage from it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from .providers import ProviderRegistry, ProviderResolution
from .resilience import CircuitBreaker, FailureKind
from .scheduler import Privacy
from .workers import (
    OWNED_CLASSES,
    WorkerClass,
    WorkerRecord,
    WorkerRegistry,
    WorkerRequirement,
)


class ExecutionMode(str, Enum):
    """The distinction that must survive every layer between here and evidence."""

    #: The artifact the Open Model Universe admitted, running on a worker that
    #: loaded those exact bytes. A measurement here belongs to that model.
    EXACT_MODEL = "EXACT_MODEL"
    #: A provider's own model, supplying the capability under its own name. A
    #: measurement here belongs to the provider's model and never to the one
    #: that was asked for.
    CAPABILITY_PROVIDER = "CAPABILITY_PROVIDER"


class MeshOutcome(str, Enum):
    EXACT_MODEL_WORKER = "EXACT_MODEL_WORKER"
    CAPABILITY_PROVIDER = "CAPABILITY_PROVIDER"
    #: Nothing can serve it now, and the reason is recorded. This is a truthful
    #: answer and the only permitted alternative to running something.
    CAPABILITY_TEMPORARILY_UNAVAILABLE = "CAPABILITY_TEMPORARILY_UNAVAILABLE"


#: Wave-independent capability vocabulary. Naming a capability here costs
#: nothing and proves nothing: a worker becomes eligible for one only by
#: carrying it in `measured_capabilities`. The later entries exist precisely so
#: that a future wave declaring `vision` or `OCR` needs no new scheduler, no new
#: router and no new Model Mesh - only a worker that has been measured for it.
CAPABILITY_TAGS: frozenset[str] = frozenset({
    "text_reasoning", "deep_reasoning",
    "coding", "software_engineering", "debugging", "code_review",
    "verifier", "checker", "synthesis",
    "vietnamese", "multilingual",
    "long_context", "tool_calling",
    "vision", "image_understanding",
    "ocr", "document_understanding",
    "audio_understanding", "speech_to_text", "text_to_speech",
    "embedding", "reranking",
    "image_generation", "video_generation",
    "future_multimodal",
})


@dataclass(frozen=True)
class MeshRequest:
    """What has to be true of an executor for this piece of work.

    Assembled by the authorities above - the Model Mesh names the model, the
    router names the privacy class - and answered here.
    """

    model_id: str
    capability: str | None = None
    ram_mb: int = 0
    vram_mb: int = 0
    disk_mb: int = 0
    runtime: str | None = None
    artifact_format: str | None = None
    quantization: str | None = None
    model_family: str | None = None
    context: int | None = None
    privacy: Privacy = Privacy.PUBLIC
    #: Whether a provider serving a *different* model is an acceptable answer.
    #: Off by default: a caller has to say that a substitute will do, because
    #: silently substituting is how a benchmark ends up attributed to the wrong
    #: model.
    allow_capability_fallback: bool = False
    free_only: bool = True

    def to_worker_requirement(self) -> WorkerRequirement:
        return WorkerRequirement(
            runtime=self.runtime,
            ram_mb=self.ram_mb,
            vram_mb=self.vram_mb,
            disk_mb=self.disk_mb,
            privacy=self.privacy,
            free_only=self.free_only,
            artifact_format=self.artifact_format,
            quantization=self.quantization,
            model_family=self.model_family,
            context=self.context,
            capability=self.capability,
            # A worker taking the exact artifact must be able to hold weights.
            requires_custom_weights=True,
        )


@dataclass(frozen=True)
class MeshPlacement:
    outcome: MeshOutcome
    request_model_id: str
    execution_mode: ExecutionMode | None = None
    worker_id: str | None = None
    worker_class: str | None = None
    provider_id: str | None = None
    executed_model_id: str | None = None
    fallback_reason: str | None = None
    #: Every worker that was passed over, and why. A placement that cannot
    #: explain its refusals is indistinguishable from one that did not look.
    refusals: Mapping[str, tuple[str, ...]] = None  # type: ignore[assignment]
    provider_refusals: Mapping[str, tuple[str, ...]] = None  # type: ignore[assignment]
    candidates_considered: int = 0

    @property
    def ran_the_requested_model(self) -> bool:
        return self.execution_mode is ExecutionMode.EXACT_MODEL

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "outcome": self.outcome.value,
            "requested_model": self.request_model_id,
            "execution_mode": None if self.execution_mode is None else self.execution_mode.value,
            "executed_model": self.executed_model_id,
            "ran_the_requested_model": self.ran_the_requested_model,
            "worker_id": self.worker_id,
            "worker_class": self.worker_class,
            "provider_id": self.provider_id,
            "fallback_reason": self.fallback_reason,
            "candidates_considered": self.candidates_considered,
            "worker_refusals": {k: list(v) for k, v in sorted((self.refusals or {}).items())},
            "provider_refusals": {
                k: list(v) for k, v in sorted((self.provider_refusals or {}).items())},
            # Restated on every placement, because this is the thing a reader
            # most needs to not have to take on trust.
            "routing_authority": False,
            "model_selection_authority": False,
            "admission_authority": False,
        }


def _fit_score(worker: WorkerRecord) -> tuple[int, float, int]:
    """Ordering among workers that are all already eligible and all zero-cost.

    Owned hardware first - it is private, has no quota and no third party sees
    the payload. Then measured warm latency, with unmeasured last rather than
    first, because an unmeasured worker has not earned a position. Then spare
    capacity. Cost is deliberately absent: everything here is already free, so
    scoring on it again would just be noise.
    """
    owned = 0 if worker.worker_class in OWNED_CLASSES else 1
    latency = worker.warm_latency_ms if worker.warm_latency_ms is not None else float("inf")
    headroom = worker.max_concurrent_jobs - worker.current_jobs
    return (owned, latency, -headroom)


class FreeWorkerMesh:
    """Capacity across every executor. Reports; never decides."""

    routing_authority = False
    reasoning_authority = False
    memory_authority = False
    model_selection_authority = False
    admission_authority = False
    evidence_authority = False

    def __init__(
        self,
        workers: WorkerRegistry,
        providers: ProviderRegistry | None = None,
        *,
        failure_threshold: int = 3,
        cooldown_seconds: float = 30.0,
    ) -> None:
        self.workers = workers
        self.providers = providers or ProviderRegistry()
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        self._breakers: dict[str, CircuitBreaker] = {}

    # -- health ------------------------------------------------------------

    def breaker(self, worker_id: str) -> CircuitBreaker:
        if worker_id not in self._breakers:
            self._breakers[worker_id] = CircuitBreaker(
                failure_threshold=self._failure_threshold,
                cooldown_seconds=self._cooldown_seconds,
            )
        return self._breakers[worker_id]

    def record_failure(self, worker_id: str, kind: FailureKind, *, now: float) -> None:
        """A worker failed a job. Enough of these and it is taken out of rotation.

        Never a permanent removal: the breaker reopens on a cooldown and lets a
        probe through, because one bad job is not evidence that a machine is
        gone.
        """
        self.breaker(worker_id).record_failure(kind, now=now)

    def record_success(self, worker_id: str, *, now: float) -> None:
        self.breaker(worker_id).record_success(now=now)

    def serving(self, *, now: float) -> tuple[WorkerRecord, ...]:
        """Workers that are up, in-lease, in-quota and not in cooldown."""
        return tuple(
            worker for worker in self.workers.all()
            if not worker.lease_expired(now=now)
            and not worker.quota_exhausted(now=now)
            and self.breaker(worker.worker_id).allow(now=now)
        )

    # -- placement ---------------------------------------------------------

    def place(self, request: MeshRequest, *, now: float) -> MeshPlacement:
        """Where this work can run, and if nowhere, exactly why not.

        The order is fixed and is the free-first policy: the exact model on a
        worker we control, then the exact model on any eligible worker, then -
        only if the caller allowed it - a provider's own model under its own
        name. Nothing paid at any step.
        """
        requirement = request.to_worker_requirement()
        eligible = list(self.workers.eligible(requirement, now=now))

        # The breaker is applied after eligibility rather than inside it: a
        # worker in cooldown is a health fact, and folding it into the resource
        # match would report "insufficient RAM" for a machine that is simply
        # resting.
        open_circuits: dict[str, tuple[str, ...]] = {}
        available: list[WorkerRecord] = []
        for worker in eligible:
            breaker = self.breaker(worker.worker_id)
            if breaker.allow(now=now):
                available.append(worker)
            else:
                open_circuits[worker.worker_id] = (
                    f"circuit is {breaker.state.value} after repeated failures; "
                    f"{round(breaker.cooldown_remaining(now=now), 1)}s of cooldown remain",
                )

        refusals = dict(self.workers.refusals(requirement, now=now))
        refusals.update(open_circuits)

        if available:
            chosen = sorted(available, key=_fit_score)[0]
            return MeshPlacement(
                outcome=MeshOutcome.EXACT_MODEL_WORKER,
                request_model_id=request.model_id,
                execution_mode=ExecutionMode.EXACT_MODEL,
                worker_id=chosen.worker_id,
                worker_class=chosen.worker_class.value,
                executed_model_id=request.model_id,
                refusals={k: v for k, v in refusals.items() if k != chosen.worker_id},
                provider_refusals={},
                candidates_considered=len(eligible),
            )

        resolution: ProviderResolution = self.providers.resolve(
            request.model_id, free_only=request.free_only)
        provider_refusals = {
            **{k: tuple(v) for k, v in resolution.rejected.items()},
            **{k: tuple(v) for k, v in resolution.pending.items()},
        }

        # A provider serving *this* model is still exact-model execution: the
        # weights are the same weights, someone else is holding them.
        if resolution.exact:
            provider_id, offering = resolution.exact[0]
            if request.privacy.rank > Privacy.INTERNAL.rank:
                provider_refusals[provider_id] = (
                    f"serves the model, but a {request.privacy.value} payload may not leave "
                    f"hardware the operator controls, and no cost saving changes that",
                )
            else:
                return MeshPlacement(
                    outcome=MeshOutcome.EXACT_MODEL_WORKER,
                    request_model_id=request.model_id,
                    execution_mode=ExecutionMode.EXACT_MODEL,
                    provider_id=provider_id,
                    executed_model_id=offering.provider_model_id,
                    refusals=refusals,
                    provider_refusals=provider_refusals,
                    candidates_considered=len(eligible),
                )

        if resolution.capability and request.allow_capability_fallback:
            provider_id, offering = resolution.capability[0]
            if request.privacy.rank <= Privacy.INTERNAL.rank:
                return MeshPlacement(
                    outcome=MeshOutcome.CAPABILITY_PROVIDER,
                    request_model_id=request.model_id,
                    execution_mode=ExecutionMode.CAPABILITY_PROVIDER,
                    provider_id=provider_id,
                    executed_model_id=offering.provider_model_id,
                    fallback_reason=(
                        f"no worker could run {request.model_id}; {provider_id} serves "
                        f"{offering.provider_model_id}, which covers the capability under "
                        f"its own name. {offering.substitution_reason}"
                    ),
                    refusals=refusals,
                    provider_refusals=provider_refusals,
                    candidates_considered=len(eligible),
                )
            provider_refusals[provider_id] = (
                f"a {request.privacy.value} payload may not go to a third party",
            )

        reason = "no worker is registered at all"
        if refusals:
            reason = f"{len(refusals)} worker(s) were considered and each refused"
        if resolution.capability and not request.allow_capability_fallback:
            reason += (
                "; a provider serves a substitute model, but the caller did not permit "
                "a capability fallback"
            )
        return MeshPlacement(
            outcome=MeshOutcome.CAPABILITY_TEMPORARILY_UNAVAILABLE,
            request_model_id=request.model_id,
            fallback_reason=reason,
            refusals=refusals,
            provider_refusals=provider_refusals,
            candidates_considered=len(eligible),
        )

    def to_dict(self, *, now: float) -> Mapping[str, Any]:
        return {
            "workers": [w.to_dict(now=now) for w in self.workers.all()],
            "serving_now": [w.worker_id for w in self.serving(now=now)],
            "providers": [p.to_dict() for p in self.providers.all()],
            "breakers": {
                worker_id: dict(breaker.to_dict(now=now))
                for worker_id, breaker in self._breakers.items()
            },
            "capability_vocabulary": sorted(CAPABILITY_TAGS),
            "worker_classes": sorted(c.value for c in WorkerClass),
            "routing_authority": False,
            "model_selection_authority": False,
            "admission_authority": False,
            "note": (
                "Execution capacity only. Models are governed by the Open Model "
                "Universe, selected by the Model Mesh and placed by the runtime "
                "scheduler; this reports which executors could carry the work."
            ),
        }
