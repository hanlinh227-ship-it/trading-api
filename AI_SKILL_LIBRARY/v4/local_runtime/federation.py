"""The one entry point the rest of the brain calls.

`serve()` walks a task through the whole local runtime plane - placement,
invocation, then housekeeping - and returns an outcome. It is the seam where
the guarantee each module makes individually becomes a guarantee about the
subsystem as a whole: **a failure anywhere in here degrades this task, and
nothing else.**

That is why the body is wrapped. Every module below is written not to raise,
but "written not to raise" is a claim about code as it exists today, and this
subsystem will keep growing. The wrapper makes the invariant structural rather
than aspirational: if some future adapter, probe or policy throws, the stable
brain gets a `degraded=True` outcome with the reason in it, not a traceback
climbing out of the runtime plane and into the router.

Authority: none. `task_router` routed the request and the Model Mesh nominated
the candidates before `serve()` was called. This decides only how an
already-chosen piece of work meets already-chosen hardware.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .cache import CacheEntry, CachePolicy, EvictionAction, plan_eviction
from .free_worker_mesh import FreeWorkerMesh, MeshOutcome, MeshPlacement, MeshRequest
from .lifecycle import ModelState
from .resources import ResourceSnapshot
from .runtime import (
    InvocationStatus,
    RegistryClaim,
    RuntimeMesh,
    TaskContract,
)
from .scheduler import (
    Placement,
    PlacementAction,
    RuntimeSlot,
    SchedulerPolicy,
    SleepAction,
    TaskRequest,
    plan_placement,
    plan_sleep,
)


@dataclass(frozen=True)
class ServeOutcome:
    task_id: str
    admitted: bool
    reason: str
    status: InvocationStatus | None = None
    model_id: str | None = None
    runtime: str | None = None
    action: PlacementAction | None = None
    output: Any = None
    #: Housekeeping the caller should apply after the task settles.
    sleep_actions: tuple[SleepAction, ...] = ()
    eviction_actions: tuple[EvictionAction, ...] = ()
    #: True when the runtime plane itself failed and was contained.
    degraded: bool = False
    rejected: Mapping[str, str] = field(default_factory=dict)
    #: The Free Worker Mesh's answer, when one was consulted. Carried onto the
    #: outcome so a reader can see which executor was chosen and, on a refusal,
    #: why this host was not it.
    worker_placement: Mapping[str, Any] | None = None

    @property
    def ok(self) -> bool:
        return self.admitted and self.status is InvocationStatus.OK


def _contract(request: TaskRequest, placement: Placement, payload: Mapping[str, Any]) -> TaskContract:
    return TaskContract(
        task_id=request.task_id,
        model_id=placement.model_id,
        payload=payload,
        context_tokens=request.required_context,
        modality="text",
        free_only=request.free_only,
    )


def serve(
    request: TaskRequest,
    slots: Sequence[RuntimeSlot],
    snapshot: ResourceSnapshot,
    mesh: RuntimeMesh,
    claims: Mapping[str, RegistryClaim],
    *,
    now: float,
    payload: Mapping[str, Any] | None = None,
    cache_entries: Sequence[CacheEntry] = (),
    scheduler_policy: SchedulerPolicy | None = None,
    cache_policy: CachePolicy | None = None,
    worker_mesh: FreeWorkerMesh | None = None,
    mesh_request: MeshRequest | None = None,
    local_worker_id: str | None = None,
) -> ServeOutcome:
    """Place, invoke and tidy up. Never raises into the caller.

    When a `worker_mesh` is supplied it is consulted first, because it answers a
    question the slot scheduler cannot: *which machine*. The slots below are all
    on this host, so if the mesh names a different worker, running here anyway
    would produce a result attributed to hardware that never touched it. That is
    refused rather than silently localised - remote transport is deliberately
    not implemented, and pretending otherwise is the failure this guard exists
    to prevent.
    """
    try:
        mesh_placement: MeshPlacement | None = None
        if worker_mesh is not None and mesh_request is not None:
            mesh_placement = worker_mesh.place(mesh_request, now=now)
            refusal = _mesh_refusal(mesh_placement, local_worker_id)
            if refusal is not None:
                return ServeOutcome(
                    task_id=request.task_id, admitted=False, reason=refusal,
                    worker_placement=dict(mesh_placement.to_dict()),
                )

        decision = plan_placement(request, slots, snapshot, policy=scheduler_policy)
        housekeeping = plan_sleep(slots, snapshot, policy=scheduler_policy)
        evictions = plan_eviction(cache_entries, need_bytes=0, snapshot=snapshot, policy=cache_policy)

        if not decision.admitted:
            return ServeOutcome(
                task_id=request.task_id,
                admitted=False,
                reason=decision.reason,
                sleep_actions=housekeeping,
                eviction_actions=evictions,
                rejected=decision.rejected,
                worker_placement=None if mesh_placement is None else dict(mesh_placement.to_dict()),
            )

        placement = decision.placements[0]
        claim = claims.get(placement.model_id)
        if claim is None:
            # A candidate the Model Mesh nominated but did not describe cannot be
            # negotiated against. Refusing beats inventing a claim for it.
            return ServeOutcome(
                task_id=request.task_id,
                admitted=False,
                reason=f"no registry claim for {placement.model_id}; cannot negotiate capability",
                sleep_actions=housekeeping,
                eviction_actions=evictions,
                rejected=decision.rejected,
            )

        result = mesh.invoke(_contract(request, placement, payload or {}), claim, now=now)
        return ServeOutcome(
            task_id=request.task_id,
            admitted=True,
            reason=result.reason,
            status=result.status,
            model_id=placement.model_id,
            runtime=result.runtime,
            action=placement.action,
            output=result.output,
            sleep_actions=housekeeping,
            eviction_actions=evictions,
            rejected=decision.rejected,
            worker_placement=None if mesh_placement is None else dict(mesh_placement.to_dict()),
        )
    except Exception as exc:  # noqa: BLE001 - the containment boundary itself
        return ServeOutcome(
            task_id=getattr(request, "task_id", "<unknown>"),
            admitted=False,
            reason=f"local runtime plane degraded: {type(exc).__name__}: {exc}",
            degraded=True,
        )


def _mesh_refusal(placement: MeshPlacement, local_worker_id: str | None) -> str | None:
    """Why this host must not carry the work the mesh just placed. None means it may.

    Three cases, and each would be a different lie if it ran here anyway:
    nothing can serve the request at all; a provider would serve it, which is
    not this process; or another machine was chosen.
    """
    if placement.outcome is MeshOutcome.CAPABILITY_TEMPORARILY_UNAVAILABLE:
        return f"no executor is available: {placement.fallback_reason}"
    if placement.provider_id is not None:
        return (
            f"the mesh placed this on provider {placement.provider_id} running "
            f"{placement.executed_model_id}; this process serves local slots only, and "
            f"running here would attribute the result to the wrong executor"
        )
    if local_worker_id is not None and placement.worker_id != local_worker_id:
        return (
            f"the mesh placed this on worker {placement.worker_id}, not this host "
            f"({local_worker_id}); remote transport is not implemented, and a local run "
            f"would be recorded against a machine that never touched it"
        )
    return None


def wake_transitions(placement: Placement) -> tuple[tuple[ModelState, ModelState], ...]:
    """The lifecycle hops a placement implies, in order.

    Kept here rather than in the scheduler so placement stays a pure decision:
    the caller applies these against the real `ModelLifecycle`, and the graph
    rejects any hop this function got wrong.
    """
    if placement.action is PlacementAction.SERVE_RUNNING:
        return ()
    if placement.action is PlacementAction.USE_WARM:
        return ((ModelState.WARM, ModelState.RUNNING),)
    if placement.action is PlacementAction.WAKE:
        return ((ModelState.SLEEPING, ModelState.WARM), (ModelState.WARM, ModelState.RUNNING))
    if placement.action is PlacementAction.LOAD_FROM_CACHE:
        return ((ModelState.CACHED, ModelState.WARM), (ModelState.WARM, ModelState.RUNNING))
    return (
        (ModelState.AVAILABLE, ModelState.DOWNLOADING),
        (ModelState.DOWNLOADING, ModelState.CACHED),
        (ModelState.CACHED, ModelState.WARM),
        (ModelState.WARM, ModelState.RUNNING),
    )
