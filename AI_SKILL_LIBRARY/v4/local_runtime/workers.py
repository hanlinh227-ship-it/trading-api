"""Multi-worker runtime contract and cross-machine preparation.

A worker is a machine that can hold weights and run them: the Windows box with
the GPU, the Mac Studio, a Linux node, a free-tier cloud runner. This module is
the contract they join under, and the registry that tracks whether each one is
currently worth handing work to.

The load-bearing rule is that **a worker never gains authority by joining**.
`routing_authority`, `reasoning_authority` and `memory_authority` are class
attributes fixed at False and not constructor arguments, so a worker cannot
declare itself a router even by accident - passing the flag is a `TypeError`.
A worker contributes capacity. It does not get a vote on where work goes.

Attestation is where a worker says what it will and will not do, and the
registry checks that against policy before the worker is usable at all: no
arbitrary shell, no financial execution, no credential storage, zero-cost only,
and a privacy ceiling it may narrow but never widen.

Everything is addressed by endpoint rather than by assuming the process is
local, so the same code path serves an in-process runtime and a GPU box down
the hall. That is the whole of the cross-machine preparation: contracts that do
not need rewriting when the first remote worker actually appears. Remote
transport itself is deliberately not implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping
from urllib.parse import urlparse

from .resources import ResourceSnapshot
from .scheduler import Privacy


class WorkerError(RuntimeError):
    """A worker operation that policy or the state machine does not allow."""


class WorkerState(str, Enum):
    REGISTERED = "REGISTERED"  # known, nothing verified
    ATTESTED = "ATTESTED"      # declared its limits and they passed policy
    ELIGIBLE = "ELIGIBLE"      # attested and answering healthchecks
    ACTIVE = "ACTIVE"          # carrying work
    DEGRADED = "DEGRADED"      # answering, but failing its health signal
    #: Healthy, reachable, and out of free quota until it resets. Deliberately
    #: not DEGRADED: nothing is wrong with it, and retrying it would be a loop
    #: against a limit that only time clears.
    QUOTA_LIMITED = "QUOTA_LIMITED"
    #: A laptop that closed its lid. Expected to come back, so it is not the
    #: same fact as a worker that failed.
    SLEEPING = "SLEEPING"
    OFFLINE = "OFFLINE"        # stopped answering


_WORKER_TRANSITIONS: Mapping[WorkerState, frozenset[WorkerState]] = {
    WorkerState.REGISTERED: frozenset({WorkerState.ATTESTED, WorkerState.OFFLINE}),
    WorkerState.ATTESTED: frozenset({WorkerState.ELIGIBLE, WorkerState.DEGRADED, WorkerState.OFFLINE}),
    WorkerState.ELIGIBLE: frozenset({
        WorkerState.ACTIVE, WorkerState.DEGRADED, WorkerState.QUOTA_LIMITED,
        WorkerState.SLEEPING, WorkerState.OFFLINE}),
    WorkerState.ACTIVE: frozenset({
        WorkerState.ELIGIBLE, WorkerState.DEGRADED, WorkerState.QUOTA_LIMITED,
        WorkerState.SLEEPING, WorkerState.OFFLINE}),
    WorkerState.DEGRADED: frozenset({WorkerState.ELIGIBLE, WorkerState.OFFLINE}),
    # Quota clears on its own, so this returns to ELIGIBLE without a probe. It
    # may also simply go away while it waits.
    WorkerState.QUOTA_LIMITED: frozenset({
        WorkerState.ELIGIBLE, WorkerState.DEGRADED, WorkerState.OFFLINE}),
    WorkerState.SLEEPING: frozenset({WorkerState.ELIGIBLE, WorkerState.OFFLINE}),
    # An offline worker rejoins at ELIGIBLE - its attestation still stands - or
    # is re-registered from scratch.
    WorkerState.OFFLINE: frozenset({WorkerState.ELIGIBLE, WorkerState.REGISTERED}),
}

#: States in which a worker may be handed work.
SERVING_STATES = frozenset({WorkerState.ELIGIBLE, WorkerState.ACTIVE})

_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost", "[::1]"}


class WorkerClass(str, Enum):
    """Where a worker lives and how long it lasts.

    This is descriptive metadata, not a permission tier. A REMOTE_PERSISTENT
    worker has exactly the same authority as an EPHEMERAL_LOCAL one, which is
    none; the class only tells the scheduler what to expect of it - whether its
    cache survives, whether it must acquire an artifact before it can run one,
    and whether its absence is a transient or a standing fact.
    """

    EPHEMERAL_LOCAL = "EPHEMERAL_LOCAL"      # this container; cache dies with it
    PERSISTENT_LOCAL = "PERSISTENT_LOCAL"    # an operator machine that keeps its cache
    REMOTE_EPHEMERAL = "REMOTE_EPHEMERAL"    # a CI runner or similar, per-job
    REMOTE_PERSISTENT = "REMOTE_PERSISTENT"  # a standing remote host
    JIT_REMOTE = "JIT_REMOTE"                # started on demand, then released

    # Operator hardware. Split by platform because what each one can run
    # differs - Metal on the Mac, CUDA on a Windows box with an NVIDIA card -
    # and a scheduler that cannot tell them apart cannot honour that.
    OWNED_MAC = "OWNED_MAC"
    OWNED_WINDOWS = "OWNED_WINDOWS"
    OWNED_LINUX = "OWNED_LINUX"
    OWNED_VPS = "OWNED_VPS"

    REMOTE_CPU = "REMOTE_CPU"
    REMOTE_GPU = "REMOTE_GPU"
    FREE_CLOUD_EPHEMERAL = "FREE_CLOUD_EPHEMERAL"
    CI_EPHEMERAL = "CI_EPHEMERAL"

    #: Holds its own weights behind an API. It is in this enum so one contract
    #: covers everything that can execute, and it is the class for which
    #: `supports_custom_weights` is False - the distinction that keeps an
    #: admitted artifact from being recorded as running somewhere it cannot.
    SERVERLESS_INFERENCE = "SERVERLESS_INFERENCE"
    MODEL_PROVIDER = "MODEL_PROVIDER"

    #: A class that does not exist yet. Present so that adding a worker type is
    #: a registration, not a code change: an unrecognised worker registers here
    #: and is matched on its declared capabilities like any other.
    FUTURE_PROVIDER = "FUTURE_PROVIDER"


#: Classes whose machine is the operator's own, so running on it costs nothing
#: further and a confidential payload never leaves hardware they control.
OWNED_CLASSES = frozenset({
    WorkerClass.PERSISTENT_LOCAL, WorkerClass.EPHEMERAL_LOCAL,
    WorkerClass.OWNED_MAC, WorkerClass.OWNED_WINDOWS,
    WorkerClass.OWNED_LINUX, WorkerClass.OWNED_VPS,
})

#: The highest privacy a worker on somebody else's infrastructure may hold.
#: A CONFIDENTIAL or LOCAL_ONLY payload has to stay on hardware the operator
#: controls, and a provider cannot attest its way past that: the ceiling comes
#: from where the machine is, not from what its operator promises.
THIRD_PARTY_PRIVACY_CEILING = Privacy.INTERNAL

#: Classes that are somebody else's infrastructure. A payload above INTERNAL
#: must never reach one, whatever it costs.
THIRD_PARTY_CLASSES = frozenset({
    WorkerClass.SERVERLESS_INFERENCE, WorkerClass.MODEL_PROVIDER,
    WorkerClass.FREE_CLOUD_EPHEMERAL, WorkerClass.CI_EPHEMERAL,
    WorkerClass.FUTURE_PROVIDER,
})


def valid_worker_targets(state: WorkerState) -> frozenset[WorkerState]:
    return _WORKER_TRANSITIONS[WorkerState(state)]


@dataclass(frozen=True)
class Attestation:
    """What a worker promises about itself, checked against policy on arrival."""

    zero_cost_only: bool
    max_privacy: Privacy
    shell_execution: bool = False
    financial_execution: bool = False
    credential_storage: bool = False

    def refusals(self, *, ceiling: Privacy = Privacy.SECRET) -> tuple[str, ...]:
        """Policy violations in this attestation. Empty means acceptable."""
        refusals: list[str] = []
        if not self.zero_cost_only:
            refusals.append("worker is not zero-cost only; no paid fallback is permitted")
        if self.shell_execution:
            refusals.append("arbitrary shell execution is not permitted by default")
        if self.financial_execution:
            refusals.append("financial execution is never permitted on a runtime worker")
        if self.credential_storage:
            refusals.append("credential storage on a worker is not permitted")
        if self.max_privacy.rank > ceiling.rank:
            refusals.append(
                f"privacy ceiling {self.max_privacy.value} widens the permitted "
                f"ceiling {ceiling.value}; a worker may narrow it, never widen it"
            )
        return tuple(refusals)


@dataclass(frozen=True)
class AttestationResult:
    accepted: bool
    refusals: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkerRecord:
    worker_id: str
    endpoint: str
    resources: ResourceSnapshot
    runtimes: frozenset[str]
    state: WorkerState = WorkerState.REGISTERED
    attestation: Attestation | None = None
    last_seen: float | None = None
    last_health: bool | None = None

    #: What this worker can actually load. Empty means "not declared", which is
    #: treated as unknown rather than as universal: a requirement naming a
    #: format is only matched by a worker that named the same one. Declaring
    #: nothing therefore narrows a worker's usefulness instead of widening it,
    #: which is the safe direction for a default.
    worker_class: WorkerClass = WorkerClass.EPHEMERAL_LOCAL
    supported_formats: frozenset[str] = frozenset()
    supported_quantizations: frozenset[str] = frozenset()
    supported_model_families: frozenset[str] = frozenset()
    max_context: int | None = None
    #: Measured, when this worker has been measured. None is not zero.
    load_latency_ms: float | None = None
    warm_latency_ms: float | None = None
    cost_class: str = "owned_hardware_zero_marginal"
    network_reachable: bool | None = None
    last_verified_at: str | None = None

    #: Capabilities this worker can serve, as wave-independent tags. Two sets,
    #: never one: a capability may be *named* before anything has measured it,
    #: but it may not make a worker eligible before that. `declared` is what the
    #: worker says it could do and is advertising only; `measured` is what a
    #: benchmark on this fleet established, and it alone is matched against a
    #: capability requirement. Collapsing them would let a provider's marketing
    #: copy stand in for evidence.
    declared_capabilities: frozenset[str] = frozenset()
    measured_capabilities: frozenset[str] = frozenset()

    #: Can this worker be handed weights, or does it only serve its own?
    #: A serverless catalog answers False, which is what stops an admitted
    #: artifact from being recorded as running there.
    supports_custom_weights: bool = True
    supports_jit_acquisition: bool = True
    supports_cache: bool = True
    supports_eviction: bool = True

    #: Free-tier accounting. `quota_remaining` of 0 is a real limit; None means
    #: unmetered or unknown and is never read as exhausted.
    free_quota: str | None = None
    quota_remaining: float | None = None
    quota_reset_at: float | None = None

    #: How long a heartbeat is good for. A worker that has not beaten within
    #: its lease is stale, and stale is not selectable - a machine that went
    #: away mid-job is the failure this prevents.
    lease_seconds: float = 120.0

    #: Concurrency, so one worker is not handed every job at once.
    max_concurrent_jobs: int = 1
    current_jobs: int = 0
    current_models: frozenset[str] = frozenset()

    egress_policy: str | None = None
    trust_class: str = "operator_owned"

    #: Not fields. A worker cannot be constructed with authority, and cannot
    #: acquire it later - `WorkerRecord(..., routing_authority=True)` is a
    #: TypeError, which is exactly the point.
    routing_authority = False
    reasoning_authority = False
    memory_authority = False
    model_selection_authority = False

    def lease_expired(self, *, now: float) -> bool:
        """Whether this worker's last heartbeat has gone stale.

        A worker that has never been seen has not proven it is there, so it is
        stale rather than fresh. That is the safe direction: the cost of
        wrongly calling a live worker stale is a missed placement; the cost of
        the reverse is a job handed to a machine that is gone.
        """
        if self.last_seen is None:
            return True
        return (now - self.last_seen) > self.lease_seconds

    @property
    def has_capacity(self) -> bool:
        return self.current_jobs < self.max_concurrent_jobs

    @property
    def is_third_party(self) -> bool:
        return self.worker_class in THIRD_PARTY_CLASSES

    def quota_exhausted(self, *, now: float) -> bool:
        """Out of free quota, and not yet reset. None means unmetered."""
        if self.quota_remaining is None:
            return False
        if self.quota_remaining > 0:
            return False
        # A reset time in the past means the window has rolled over; the
        # remaining count is simply stale and a probe will refresh it.
        return not (self.quota_reset_at is not None and now >= self.quota_reset_at)

    def to_dict(self, *, now: float) -> Mapping[str, Any]:
        return {
            "worker_id": self.worker_id,
            "endpoint": self.endpoint,
            "state": self.state.value,
            "runtimes": sorted(self.runtimes),
            "platform": self.resources.host.to_dict(),
            "health": self.last_health,
            "seconds_since_seen": None if self.last_seen is None else round(now - self.last_seen, 3),
            "worker_class": self.worker_class.value,
            "supported_formats": sorted(self.supported_formats),
            "supported_quantizations": sorted(self.supported_quantizations),
            "supported_model_families": sorted(self.supported_model_families),
            "max_context": self.max_context,
            "available_ram_mb": self.resources.ram_available_mb,
            "available_vram_mb": self.resources.total_vram_available_mb,
            "available_disk_mb": self.resources.disk_free_mb,
            "load_latency_ms": self.load_latency_ms,
            "warm_latency_ms": self.warm_latency_ms,
            "cost_class": self.cost_class,
            "privacy_class": None if self.attestation is None else self.attestation.max_privacy.value,
            "network_reachable": self.network_reachable,
            "last_verified_at": self.last_verified_at,
            "declared_capabilities": sorted(self.declared_capabilities),
            "measured_capabilities": sorted(self.measured_capabilities),
            "supports_custom_weights": self.supports_custom_weights,
            "supports_jit_acquisition": self.supports_jit_acquisition,
            "supports_cache": self.supports_cache,
            "supports_eviction": self.supports_eviction,
            "free_quota": self.free_quota,
            "quota_remaining": self.quota_remaining,
            "quota_reset_at": self.quota_reset_at,
            "lease_seconds": self.lease_seconds,
            "lease_expired": self.lease_expired(now=now),
            "max_concurrent_jobs": self.max_concurrent_jobs,
            "current_jobs": self.current_jobs,
            "current_models": sorted(self.current_models),
            "has_capacity": self.has_capacity,
            "egress_policy": self.egress_policy,
            "trust_class": self.trust_class,
            "is_third_party": self.is_third_party,
            "routing_authority": self.routing_authority,
            "reasoning_authority": self.reasoning_authority,
            "memory_authority": self.memory_authority,
            "model_selection_authority": self.model_selection_authority,
        }


@dataclass(frozen=True)
class WorkerRequirement:
    runtime: str | None = None
    ram_mb: int = 0
    vram_mb: int = 0
    privacy: Privacy = Privacy.PUBLIC
    free_only: bool = True

    #: Disk needed to hold the artifact, for a worker that does not have it yet.
    #: A worker with the artifact already cached passes this trivially; one that
    #: must acquire it does not, and that difference is the whole of JIT
    #: placement.
    disk_mb: int = 0
    artifact_format: str | None = None
    quantization: str | None = None
    model_family: str | None = None
    context: int | None = None

    #: A wave-independent capability tag - "coding", "vision", "OCR". Matched
    #: against a worker's *measured* set only, so a Wave 4 requirement needs no
    #: scheduler change: it is a new string, not new code.
    capability: str | None = None
    #: Whether the work needs weights of ours loaded. False lets a hosted
    #: catalog answer; True restricts to workers that can take an artifact.
    requires_custom_weights: bool = False


def _validate_endpoint(endpoint: str) -> None:
    if not (endpoint or "").strip():
        raise WorkerError("a worker endpoint is required; localhost is not assumed")
    parsed = urlparse(endpoint)
    if parsed.scheme == "https":
        return
    # Plaintext is acceptable only to a runtime on this machine, where the
    # traffic never reaches a network. Anything else must be encrypted.
    if parsed.scheme == "http" and (parsed.hostname or "") in _LOOPBACK_HOSTS:
        return
    raise WorkerError(
        f"endpoint {endpoint!r} must be https, or http on loopback for a same-machine worker"
    )


class WorkerRegistry:
    """Tracks workers and answers which of them can take a piece of work.

    It holds no authority of its own: it reports capacity, and `task_router`
    plus the Model Mesh decide what to do with that.
    """

    routing_authority = False
    reasoning_authority = False
    memory_authority = False
    model_selection_authority = False

    def __init__(self) -> None:
        self._workers: dict[str, WorkerRecord] = {}

    # -- lifecycle ---------------------------------------------------------

    def register(self, worker: WorkerRecord) -> WorkerRecord:
        _validate_endpoint(worker.endpoint)
        if not worker.worker_id.strip():
            raise WorkerError("worker_id is required")
        fresh = replace(worker, state=WorkerState.REGISTERED, attestation=None)
        self._workers[worker.worker_id] = fresh
        return fresh

    def get(self, worker_id: str) -> WorkerRecord:
        try:
            return self._workers[worker_id]
        except KeyError:
            raise WorkerError(f"unknown worker {worker_id!r}") from None

    def all(self) -> tuple[WorkerRecord, ...]:
        return tuple(self._workers.values())

    def _move(self, worker: WorkerRecord, target: WorkerState, **fields: Any) -> WorkerRecord:
        if target not in valid_worker_targets(worker.state) and target is not worker.state:
            raise WorkerError(
                f"{worker.worker_id}: {worker.state.value} -> {target.value} is not a legal transition"
            )
        moved = replace(worker, state=target, **fields)
        self._workers[worker.worker_id] = moved
        return moved

    def attest(
        self, worker_id: str, attestation: Attestation, *, ceiling: Privacy = Privacy.SECRET
    ) -> AttestationResult:
        """Record and check a worker's declared limits.

        A failed attestation leaves the worker where it was - unusable - rather
        than admitting it in a reduced form. A worker that asked for more than
        policy allows has not shown it will respect a narrower grant.
        """
        worker = self.get(worker_id)
        # Where the machine is caps what it may be trusted with, under whatever
        # ceiling the caller passed. A third-party worker attesting to
        # CONFIDENTIAL is refused here rather than filtered at selection time,
        # so the record never exists to be read wrongly later.
        if worker.is_third_party and ceiling.rank > THIRD_PARTY_PRIVACY_CEILING.rank:
            ceiling = THIRD_PARTY_PRIVACY_CEILING
        refusals = attestation.refusals(ceiling=ceiling)
        if refusals:
            return AttestationResult(accepted=False, refusals=refusals)
        self._move(worker, WorkerState.ATTESTED, attestation=attestation)
        return AttestationResult(accepted=True)

    def healthcheck(self, worker_id: str, *, healthy: bool, now: float) -> WorkerRecord:
        worker = self.get(worker_id)
        if worker.attestation is None:
            raise WorkerError(f"{worker_id}: cannot healthcheck a worker that has not attested")
        if not healthy:
            target = WorkerState.DEGRADED if worker.state is not WorkerState.DEGRADED else worker.state
        elif worker.state is WorkerState.ACTIVE:
            target = WorkerState.ACTIVE  # carrying work; a good beat changes nothing
        else:
            target = WorkerState.ELIGIBLE
        return self._move(worker, target, last_seen=now, last_health=healthy)

    def activate(self, worker_id: str) -> WorkerRecord:
        worker = self.get(worker_id)
        if worker.state is not WorkerState.ELIGIBLE:
            raise WorkerError(
                f"{worker_id}: only an ELIGIBLE worker may be activated (currently {worker.state.value})"
            )
        return self._move(worker, WorkerState.ACTIVE)

    def expire_stale(self, *, now: float, timeout_seconds: float) -> tuple[str, ...]:
        """Move workers that stopped answering to OFFLINE. Never raises.

        Losing a worker is an ordinary event in a personal federation - a laptop
        closes, a machine sleeps - and it must cost the caller nothing but
        capacity.
        """
        expired: list[str] = []
        for worker_id, worker in list(self._workers.items()):
            if worker.state is WorkerState.OFFLINE or worker.last_seen is None:
                continue
            if now - worker.last_seen <= timeout_seconds:
                continue
            try:
                self._move(worker, WorkerState.OFFLINE, last_health=False)
                expired.append(worker_id)
            except WorkerError:
                continue
        return tuple(expired)

    # -- selection ---------------------------------------------------------

    def eligible(
        self, requirement: WorkerRequirement, *, now: float | None = None
    ) -> tuple[WorkerRecord, ...]:
        """Workers that could take this work. Empty is a normal answer.

        `now` enables the time-dependent checks - lease staleness and quota
        resets. Without it those are skipped rather than guessed, because a
        wrong clock would silently exclude every worker.
        """
        matches: list[WorkerRecord] = []
        for worker in self._workers.values():
            if worker.state not in SERVING_STATES or worker.attestation is None:
                continue
            # A heartbeat older than the lease means the worker may already be
            # gone. Selecting it would hand a job to a machine that cannot
            # answer, so staleness excludes before anything else is considered.
            if now is not None and worker.lease_expired(now=now):
                continue
            if now is not None and worker.quota_exhausted(now=now):
                continue
            if not worker.has_capacity:
                continue
            if requirement.requires_custom_weights and not worker.supports_custom_weights:
                continue
            # Measured only. A declared capability advertises; it does not
            # qualify.
            if requirement.capability and requirement.capability not in worker.measured_capabilities:
                continue
            if requirement.free_only and not worker.attestation.zero_cost_only:
                continue
            if requirement.privacy.rank > worker.attestation.max_privacy.rank:
                continue
            if requirement.runtime and requirement.runtime not in worker.runtimes:
                continue
            resources = worker.resources
            if requirement.ram_mb:
                if resources.ram_available_mb is None or resources.ram_available_mb < requirement.ram_mb:
                    continue
            if requirement.vram_mb and resources.total_vram_available_mb < requirement.vram_mb:
                continue
            if requirement.disk_mb:
                if resources.disk_free_mb is None or resources.disk_free_mb < requirement.disk_mb:
                    continue
            # A worker that declared no formats matches no format requirement.
            # Silence is not a claim of universal support, and treating it as
            # one is how a GGUF lands on a runtime that cannot read it.
            if requirement.artifact_format and requirement.artifact_format not in worker.supported_formats:
                continue
            if requirement.quantization and requirement.quantization not in worker.supported_quantizations:
                continue
            if requirement.model_family and requirement.model_family not in worker.supported_model_families:
                continue
            if requirement.context and (worker.max_context is None or worker.max_context < requirement.context):
                continue
            matches.append(worker)
        return tuple(matches)

    def refusals(
        self, requirement: WorkerRequirement, *, now: float | None = None
    ) -> Mapping[str, tuple[str, ...]]:
        """Per worker, why it cannot take this work.

        `eligible()` returning empty is a normal answer but an unhelpful one:
        "no worker" and "no worker with 40 GB of RAM" are different facts, and
        the second is the one that tells an operator what to provision.
        """
        out: dict[str, tuple[str, ...]] = {}
        for worker_id, worker in self._workers.items():
            why: list[str] = []
            if worker.state not in SERVING_STATES:
                why.append(f"state is {worker.state.value}, not serving")
            if now is not None and worker.lease_expired(now=now):
                seen = "never" if worker.last_seen is None else f"{round(now - worker.last_seen, 1)}s ago"
                why.append(
                    f"last heartbeat {seen}, past its {worker.lease_seconds}s lease, so it "
                    f"may already be gone"
                )
            if now is not None and worker.quota_exhausted(now=now):
                why.append(
                    f"free quota is exhausted ({worker.quota_remaining} remaining); this "
                    f"clears on reset, not on retry"
                )
            if not worker.has_capacity:
                why.append(
                    f"is carrying {worker.current_jobs} of {worker.max_concurrent_jobs} jobs"
                )
            if requirement.requires_custom_weights and not worker.supports_custom_weights:
                why.append("cannot be handed weights; it serves only its own catalog")
            if requirement.capability and requirement.capability not in worker.measured_capabilities:
                declared = requirement.capability in worker.declared_capabilities
                why.append(
                    f"has no measured {requirement.capability} capability"
                    + (" (it declares one, which advertises but does not qualify)" if declared else "")
                )
            if worker.attestation is None:
                why.append("has not attested")
            elif requirement.free_only and not worker.attestation.zero_cost_only:
                why.append("is not zero-cost and the request is free-only")
            elif requirement.privacy.rank > worker.attestation.max_privacy.rank:
                why.append(
                    f"privacy ceiling {worker.attestation.max_privacy.value} is below "
                    f"the requested {requirement.privacy.value}"
                )
            if requirement.runtime and requirement.runtime not in worker.runtimes:
                why.append(f"does not run {requirement.runtime}")
            resources = worker.resources
            if requirement.ram_mb and (resources.ram_available_mb or 0) < requirement.ram_mb:
                why.append(
                    f"has {resources.ram_available_mb} MB RAM available, needs {requirement.ram_mb} MB"
                )
            if requirement.vram_mb and resources.total_vram_available_mb < requirement.vram_mb:
                why.append(
                    f"has {resources.total_vram_available_mb} MB VRAM, needs {requirement.vram_mb} MB"
                )
            if requirement.disk_mb and (resources.disk_free_mb or 0) < requirement.disk_mb:
                why.append(
                    f"has {resources.disk_free_mb} MB disk free, needs {requirement.disk_mb} MB"
                )
            if requirement.artifact_format and requirement.artifact_format not in worker.supported_formats:
                why.append(f"does not declare support for {requirement.artifact_format}")
            if requirement.quantization and requirement.quantization not in worker.supported_quantizations:
                why.append(f"does not declare support for quantization {requirement.quantization}")
            if requirement.model_family and requirement.model_family not in worker.supported_model_families:
                why.append(f"does not declare support for family {requirement.model_family}")
            if requirement.context and (worker.max_context is None or worker.max_context < requirement.context):
                why.append(f"max_context {worker.max_context} is below the requested {requirement.context}")
            if why:
                out[worker_id] = tuple(why)
        return out

    def to_dict(self, *, now: float) -> Mapping[str, Mapping[str, Any]]:
        return {worker_id: worker.to_dict(now=now) for worker_id, worker in self._workers.items()}
