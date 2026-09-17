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
    OFFLINE = "OFFLINE"        # stopped answering


_WORKER_TRANSITIONS: Mapping[WorkerState, frozenset[WorkerState]] = {
    WorkerState.REGISTERED: frozenset({WorkerState.ATTESTED, WorkerState.OFFLINE}),
    WorkerState.ATTESTED: frozenset({WorkerState.ELIGIBLE, WorkerState.DEGRADED, WorkerState.OFFLINE}),
    WorkerState.ELIGIBLE: frozenset({WorkerState.ACTIVE, WorkerState.DEGRADED, WorkerState.OFFLINE}),
    WorkerState.ACTIVE: frozenset({WorkerState.ELIGIBLE, WorkerState.DEGRADED, WorkerState.OFFLINE}),
    WorkerState.DEGRADED: frozenset({WorkerState.ELIGIBLE, WorkerState.OFFLINE}),
    # An offline worker rejoins at ELIGIBLE - its attestation still stands - or
    # is re-registered from scratch.
    WorkerState.OFFLINE: frozenset({WorkerState.ELIGIBLE, WorkerState.REGISTERED}),
}

#: States in which a worker may be handed work.
SERVING_STATES = frozenset({WorkerState.ELIGIBLE, WorkerState.ACTIVE})

_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost", "[::1]"}


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

    #: Not fields. A worker cannot be constructed with authority, and cannot
    #: acquire it later - `WorkerRecord(..., routing_authority=True)` is a
    #: TypeError, which is exactly the point.
    routing_authority = False
    reasoning_authority = False
    memory_authority = False
    model_selection_authority = False

    def to_dict(self, *, now: float) -> Mapping[str, Any]:
        return {
            "worker_id": self.worker_id,
            "endpoint": self.endpoint,
            "state": self.state.value,
            "runtimes": sorted(self.runtimes),
            "platform": self.resources.host.to_dict(),
            "health": self.last_health,
            "seconds_since_seen": None if self.last_seen is None else round(now - self.last_seen, 3),
            "routing_authority": self.routing_authority,
            "reasoning_authority": self.reasoning_authority,
            "memory_authority": self.memory_authority,
        }


@dataclass(frozen=True)
class WorkerRequirement:
    runtime: str | None = None
    ram_mb: int = 0
    vram_mb: int = 0
    privacy: Privacy = Privacy.PUBLIC
    free_only: bool = True


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

    def eligible(self, requirement: WorkerRequirement) -> tuple[WorkerRecord, ...]:
        """Workers that could take this work. Empty is a normal answer."""
        matches: list[WorkerRecord] = []
        for worker in self._workers.values():
            if worker.state not in SERVING_STATES or worker.attestation is None:
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
            matches.append(worker)
        return tuple(matches)

    def to_dict(self, *, now: float) -> Mapping[str, Mapping[str, Any]]:
        return {worker_id: worker.to_dict(now=now) for worker_id, worker in self._workers.items()}
