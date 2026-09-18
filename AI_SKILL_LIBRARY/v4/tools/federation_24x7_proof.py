"""Prove the federation keeps serving while things fail. Drills, not assertions.

    python AI_SKILL_LIBRARY/v4/tools/federation_24x7_proof.py --evidence /tmp/f.json

"24/7" is the easiest claim in this repository to make and the hardest to earn.
A process that is up says nothing; what matters is whether a role still has a
placeable path when the worker holding its model goes away. So every round here
breaks something real and asks the existing mesh what it does about it. Nothing
is stubbed: the registries, the breaker, the leases and the placement logic are
the ones the runtime uses.

Three families of round:

**Failure drills** take a path away - a worker offline, a lease expired, a
provider unusable, a quota spent, a breaker tripped, two workers at once - and
require either a correct failover or an explicit refusal. A silent success on a
path that should have been excluded is a failure of the round, not a pass.

**Residency drills** move a model between readings and check the reading tracks
reality. HOT execution, demotion, waking, a cold acquire, a provider standing in,
and a worker that disappears while it was holding a HOT model.

**A live end-to-end round** runs the real chain on a real local model, so at
least one round in this file is inference rather than state.

A round that cannot run says so and does not pass. `federation_status` is PROVEN
only when every round passed; anything else names what did not.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from AI_SKILL_LIBRARY.v4.local_runtime.federation_ops import (  # noqa: E402
    DemandLedger,
    FederationHealth,
    FederationOps,
    OperationalResidency,
    RoleHealth,
    RoleObservation,
    ServiceProfile,
    hotness,
)
from AI_SKILL_LIBRARY.v4.local_runtime.free_worker_mesh import (  # noqa: E402
    FreeWorkerMesh,
    MeshOutcome,
    MeshRequest,
)
from AI_SKILL_LIBRARY.v4.local_runtime.residency import ResidencyState  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.resilience import (  # noqa: E402
    BreakerState,
    FailureKind,
)
from AI_SKILL_LIBRARY.v4.local_runtime.resources import detect_resources  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.scheduler import Privacy  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.workers import (  # noqa: E402
    Attestation,
    WorkerClass,
    WorkerRecord,
    WorkerRegistry,
    WorkerState,
)
from AI_SKILL_LIBRARY.v4.tools import role_capability_matrix  # noqa: E402
from AI_SKILL_LIBRARY.v4.tools.wave3_free_execution_paths import load_registry  # noqa: E402

LOCAL_MODEL = "Qwen/Qwen3-4B-GGUF"


def _host():
    return detect_resources()


def _join(registry: WorkerRegistry, worker_id: str, *, worker_class: WorkerClass,
          privacy: Privacy, now: float, capabilities: set[str], **fields: Any) -> WorkerRecord:
    defaults: dict[str, Any] = dict(
        worker_id=worker_id, endpoint="https://worker.invalid",
        resources=_host(), runtimes=frozenset({"llama.cpp"}),
        worker_class=worker_class,
        supported_formats=frozenset({"gguf"}),
        supported_quantizations=frozenset({"Q4_K_M"}),
        supported_model_families=frozenset({"qwen3"}),
        measured_capabilities=frozenset(capabilities),
        lease_seconds=120.0, max_concurrent_jobs=2,
    )
    defaults.update(fields)
    registry.register(WorkerRecord(**defaults))
    registry.attest(worker_id, Attestation(zero_cost_only=True, max_privacy=privacy))
    registry.healthcheck(worker_id, healthy=True, now=now)
    return registry.get(worker_id)


def _request(**fields: Any) -> MeshRequest:
    defaults: dict[str, Any] = dict(
        model_id=LOCAL_MODEL, capability="deep_reasoning", ram_mb=2_000,
        runtime="llama.cpp", artifact_format="gguf", quantization="Q4_K_M",
        model_family="qwen3", privacy=Privacy.CONFIDENTIAL)
    defaults.update(fields)
    return MeshRequest(**defaults)


def _row(round_id: str, name: str, failures: list[str], **extra: Any) -> dict[str, Any]:
    return {"round": round_id, "scenario": name, "passed": not failures,
            "failures": failures, **extra}


# -- failure drills ---------------------------------------------------------

def failure_drills(root: Path, now: float, matrix: dict[str, Any]) -> list[dict[str, Any]]:
    providers, _ = load_registry(root)
    rows: list[dict[str, Any]] = []
    caps = {"deep_reasoning", "text_reasoning", "coding", "software_engineering",
            "debugging", "verifier_checker", "code_review"}

    # A - the ordinary case. Nothing below means anything if this does not hold.
    registry = WorkerRegistry()
    _join(registry, "host-0", worker_class=WorkerClass.PERSISTENT_LOCAL,
          privacy=Privacy.CONFIDENTIAL, now=now, capabilities=caps)
    mesh = FreeWorkerMesh(registry, providers)
    ops = FederationOps(mesh, matrix)
    health = ops.federation_health(now=now)
    placement = mesh.place(_request(), now=now)
    failures = []
    if placement.outcome is not MeshOutcome.EXACT_MODEL_WORKER:
        failures.append(f"baseline placement was {placement.outcome.value}")
    if health["FEDERATION_STATE"] == FederationHealth.CRITICAL.value:
        failures.append(f"baseline federation is CRITICAL: {health['reason']}")
    rows.append(_row("A", "baseline_federation_serves", failures,
                     federation_state=health["FEDERATION_STATE"],
                     placed_on=placement.worker_id))

    # B - the only local worker goes offline. Roles whose sole path is local
    # must report BLOCKED rather than continuing to claim a primary.
    registry_b = WorkerRegistry()
    _join(registry_b, "host-0", worker_class=WorkerClass.PERSISTENT_LOCAL,
          privacy=Privacy.CONFIDENTIAL, now=now, capabilities=caps)
    mesh_b = FreeWorkerMesh(registry_b, providers)
    ops_b = FederationOps(mesh_b, matrix)
    before = {r["role_id"]: r["health"] for r in ops_b.role_health(now=now)}
    registry_b.healthcheck("host-0", healthy=False, now=now)
    registry_b._move(registry_b.get("host-0"), WorkerState.OFFLINE)  # the machine went away
    after = {r["role_id"]: r["health"] for r in ops_b.role_health(now=now)}
    local_roles = [r["role_id"] for r in matrix["ROLE_CAPABILITY_MATRIX"]
                   if (r.get("primary") or {}).get("placement") == "LOCAL"]
    failures = []
    still_claiming = [r for r in local_roles
                      if after.get(r) == RoleHealth.AVAILABLE_PRIMARY.value]
    if still_claiming:
        failures.append(
            f"local-only role(s) still claim a primary with no worker serving: "
            f"{', '.join(sorted(still_claiming)[:4])}")
    if not local_roles:
        failures.append("no local-only role in the matrix, so this drill proves nothing")
    rows.append(_row("B", "local_worker_offline_blocks_local_roles", failures,
                     local_roles=len(local_roles),
                     example_before=before.get(local_roles[0]) if local_roles else None,
                     example_after=after.get(local_roles[0]) if local_roles else None))

    # C - a stale heartbeat is not a live worker, even though nothing said so.
    registry_c = WorkerRegistry()
    _join(registry_c, "laptop-0", worker_class=WorkerClass.OWNED_MAC,
          privacy=Privacy.CONFIDENTIAL, now=now - 600.0, capabilities=caps,
          lease_seconds=120.0)
    _join(registry_c, "host-0", worker_class=WorkerClass.PERSISTENT_LOCAL,
          privacy=Privacy.CONFIDENTIAL, now=now, capabilities=caps)
    mesh_c = FreeWorkerMesh(registry_c, providers)
    placement = mesh_c.place(_request(), now=now)
    failures = []
    if placement.worker_id == "laptop-0":
        failures.append("placed on a worker whose lease expired 8 minutes ago")
    if placement.outcome is not MeshOutcome.EXACT_MODEL_WORKER:
        failures.append(f"no failover to the live worker: {placement.outcome.value}")
    expired = registry_c.expire_stale(now=now, timeout_seconds=120.0)
    if "laptop-0" not in expired:
        failures.append("expire_stale did not mark the stale worker")
    rows.append(_row("C", "stale_heartbeat_fails_over", failures,
                     placed_on=placement.worker_id, expired=list(expired)))

    # D - repeated failure opens the breaker and the path leaves placement.
    registry_d = WorkerRegistry()
    _join(registry_d, "flaky-0", worker_class=WorkerClass.REMOTE_PERSISTENT,
          privacy=Privacy.INTERNAL, now=now, capabilities=caps)
    _join(registry_d, "host-0", worker_class=WorkerClass.PERSISTENT_LOCAL,
          privacy=Privacy.CONFIDENTIAL, now=now, capabilities=caps)
    mesh_d = FreeWorkerMesh(registry_d, providers)
    for _ in range(3):
        mesh_d.record_failure("flaky-0", FailureKind.CRASH, now=now)
    breaker = mesh_d.breaker("flaky-0")
    placement = mesh_d.place(_request(privacy=Privacy.INTERNAL), now=now)
    failures = []
    if breaker.state is not BreakerState.OPEN:
        failures.append(f"three crashes left the breaker {breaker.state.value}")
    if placement.worker_id == "flaky-0":
        failures.append("placed on a worker whose breaker is open")
    rows.append(_row("D", "breaker_removes_a_failing_path", failures,
                     breaker=breaker.state.value, placed_on=placement.worker_id))

    # E - an exhausted free quota is bypassed, not retried. Retrying a limit
    # that only time clears is the loop this exists to prevent.
    registry_e = WorkerRegistry()
    _join(registry_e, "free-cloud-0", worker_class=WorkerClass.FREE_CLOUD_EPHEMERAL,
          privacy=Privacy.PUBLIC, now=now, capabilities=caps,
          quota_remaining=0.0, quota_reset_at=now + 3600.0)
    _join(registry_e, "host-0", worker_class=WorkerClass.PERSISTENT_LOCAL,
          privacy=Privacy.CONFIDENTIAL, now=now, capabilities=caps)
    mesh_e = FreeWorkerMesh(registry_e, providers)
    placement = mesh_e.place(_request(privacy=Privacy.PUBLIC), now=now)
    failures = []
    if placement.worker_id == "free-cloud-0":
        failures.append("placed on a worker with zero free quota remaining")
    if placement.outcome is MeshOutcome.CAPABILITY_TEMPORARILY_UNAVAILABLE:
        failures.append("gave up instead of using the worker that had capacity")
    rows.append(_row("E", "exhausted_quota_is_bypassed", failures,
                     placed_on=placement.worker_id))

    # F - two workers fail at once. Either a correct third path, or a refusal
    # that says so. Silently returning something would be the bad outcome.
    registry_f = WorkerRegistry()
    for name in ("host-0", "laptop-0"):
        _join(registry_f, name, worker_class=WorkerClass.PERSISTENT_LOCAL,
              privacy=Privacy.CONFIDENTIAL, now=now, capabilities=caps)
    mesh_f = FreeWorkerMesh(registry_f, providers)
    for name in ("host-0", "laptop-0"):
        registry_f.healthcheck(name, healthy=False, now=now)
        registry_f._move(registry_f.get(name), WorkerState.OFFLINE)
    placement = mesh_f.place(_request(), now=now)
    failures = []
    if placement.outcome is MeshOutcome.EXACT_MODEL_WORKER:
        failures.append(f"placed on {placement.worker_id} with both workers offline")
    if not placement.fallback_reason:
        failures.append("refused without saying why")
    rows.append(_row("F", "two_simultaneous_failures_refuse_explicitly", failures,
                     outcome=placement.outcome.value, reason=placement.fallback_reason))

    # G - privacy outranks availability. A CONFIDENTIAL request must not reach
    # a third-party worker even when it is the only thing left.
    registry_g = WorkerRegistry()
    _join(registry_g, "third-party-0", worker_class=WorkerClass.FREE_CLOUD_EPHEMERAL,
          privacy=Privacy.INTERNAL, now=now, capabilities=caps,
          trust_class="third_party")
    mesh_g = FreeWorkerMesh(registry_g, providers)
    placement = mesh_g.place(_request(privacy=Privacy.CONFIDENTIAL), now=now)
    failures = []
    if placement.worker_id == "third-party-0":
        failures.append("routed CONFIDENTIAL work to a third-party worker")
    if placement.outcome is MeshOutcome.EXACT_MODEL_WORKER:
        failures.append("found an exact worker that policy should have excluded")
    rows.append(_row("G", "privacy_outranks_availability", failures,
                     outcome=placement.outcome.value, reason=placement.fallback_reason))

    # H - a provider that is not usable must not be counted as a path.
    registry_h = WorkerRegistry()
    _join(registry_h, "host-0", worker_class=WorkerClass.PERSISTENT_LOCAL,
          privacy=Privacy.CONFIDENTIAL, now=now, capabilities=caps)
    from AI_SKILL_LIBRARY.v4.local_runtime.providers import ProviderRegistry
    # Cloudflare alone goes away, and the host's own recorded LOCAL_PROCESS path
    # stays. An earlier version emptied the whole registry, which passed while
    # leaving the real case untested: the host is recorded in the paths file too,
    # and counting it as a provider let provider-only roles keep claiming to be
    # serviceable with no off-host provider left.
    surviving = ProviderRegistry([
        record for record in providers.all()
        if record.execution_type.value == "LOCAL_PROCESS"])
    mesh_h = FreeWorkerMesh(registry_h, surviving)
    ops_h = FederationOps(mesh_h, matrix)
    health_rows = {r["role_id"]: r["health"] for r in ops_h.role_health(now=now)}
    serverless_roles = [r["role_id"] for r in matrix["ROLE_CAPABILITY_MATRIX"]
                        if (r.get("primary") or {}).get("placement") == "SERVERLESS"]
    failures = []
    wrong = [r for r in serverless_roles
             if health_rows.get(r) in (RoleHealth.AVAILABLE_PRIMARY.value,
                                       RoleHealth.AVAILABLE_FALLBACK_ONLY.value)]
    if wrong:
        failures.append(f"provider-only role(s) still serviceable with no provider: "
                        f"{', '.join(sorted(wrong))}")
    if not serverless_roles:
        failures.append("no provider-only role in the matrix, so this drill proves nothing")
    rows.append(_row("H", "provider_loss_blocks_provider_only_roles", failures,
                     serverless_roles=sorted(serverless_roles),
                     surviving_paths=[r.provider_id for r in surviving.all()],
                     states={r: health_rows.get(r) for r in sorted(serverless_roles)}))

    # I - health is coverage. With the verifier's only path gone, HEALTHY is
    # the wrong answer even though the process is fine.
    failures = []
    health_i = ops_h.federation_health(now=now) if False else None
    registry_i = WorkerRegistry()
    _join(registry_i, "host-0", worker_class=WorkerClass.PERSISTENT_LOCAL,
          privacy=Privacy.CONFIDENTIAL, now=now, capabilities=caps)
    mesh_i = FreeWorkerMesh(registry_i, providers)
    ops_i = FederationOps(mesh_i, matrix)
    registry_i.healthcheck("host-0", healthy=False, now=now)
    registry_i._move(registry_i.get("host-0"), WorkerState.OFFLINE)
    health_i = ops_i.federation_health(now=now)
    if health_i["FEDERATION_STATE"] == FederationHealth.HEALTHY.value:
        failures.append("reported HEALTHY with no worker serving any local role")
    if not health_i["critical_roles_down"] and not health_i["critical_roles_degraded"]:
        failures.append("no critical role reported as down or degraded")
    rows.append(_row("I", "health_reflects_coverage_not_liveness", failures,
                     federation_state=health_i["FEDERATION_STATE"],
                     reason=health_i["reason"]))

    # J - recovery. A worker that comes back must become placeable again
    # without anything being rewritten by hand.
    registry_i.healthcheck("host-0", healthy=True, now=now + 10.0)
    recovered = ops_i.federation_health(now=now + 10.0)
    placement = mesh_i.place(_request(), now=now + 10.0)
    failures = []
    if placement.outcome is not MeshOutcome.EXACT_MODEL_WORKER:
        failures.append(f"worker returned but placement is {placement.outcome.value}")
    if recovered["FEDERATION_STATE"] == FederationHealth.CRITICAL.value:
        failures.append("still CRITICAL after the worker came back")
    rows.append(_row("J", "recovery_needs_no_manual_rewrite", failures,
                     federation_state=recovered["FEDERATION_STATE"],
                     placed_on=placement.worker_id))

    # K - a worker that joins mid-flight becomes eligible with no change to the
    # router, the mesh or any policy. This is the auto-join promise.
    registry_k = WorkerRegistry()
    mesh_k = FreeWorkerMesh(registry_k, providers)
    empty = mesh_k.place(_request(), now=now)
    _join(registry_k, "owned-gpu-0", worker_class=WorkerClass.OWNED_LINUX,
          privacy=Privacy.CONFIDENTIAL, now=now, capabilities=caps)
    after_join = mesh_k.place(_request(), now=now)
    failures = []
    if empty.outcome is MeshOutcome.EXACT_MODEL_WORKER:
        failures.append("placed work on an empty registry")
    if after_join.outcome is not MeshOutcome.EXACT_MODEL_WORKER:
        failures.append(f"a joined worker did not become eligible: {after_join.outcome.value}")
    rows.append(_row("K", "worker_auto_join_needs_no_authority_change", failures,
                     before=empty.outcome.value, after=after_join.outcome.value))

    return rows


# -- residency drills -------------------------------------------------------

def residency_drills(root: Path, now: float, matrix: dict[str, Any]) -> list[dict[str, Any]]:
    providers, _ = load_registry(root)
    rows: list[dict[str, Any]] = []
    caps = {"deep_reasoning", "text_reasoning", "verifier_checker", "code_review"}

    registry = WorkerRegistry()
    _join(registry, "host-0", worker_class=WorkerClass.PERSISTENT_LOCAL,
          privacy=Privacy.CONFIDENTIAL, now=now, capabilities=caps,
          current_models=frozenset({LOCAL_MODEL}))
    mesh = FreeWorkerMesh(registry, providers)

    # Demand, so hotness has something real to weigh rather than a guess.
    ledger = DemandLedger()
    for index in range(30):
        ledger.record(RoleObservation(
            role_id="REASONING_BRANCH", model_id=LOCAL_MODEL, executor_id="host-0",
            execution_mode="EXACT_MODEL", started_at=now - index * 30.0,
            latency_ms=900.0, succeeded=True, verified=True))
    ops = FederationOps(mesh, matrix, demand=ledger)
    costs = {LOCAL_MODEL: {"peak_ram_mb": 3200.0, "cold_load_ms": 9000.0}}

    # L - a loaded, busy, critical model reads HOT and is immediately callable.
    residency = ops.model_residency_matrix(
        now=now, physical={LOCAL_MODEL: ResidencyState.RUNNING}, model_costs=costs)
    row = next((r for r in residency if r["model_id"] == LOCAL_MODEL), None)
    failures = []
    if row is None:
        failures.append("the model under test is in no role, so this proves nothing")
    else:
        if row["current_residency"] != OperationalResidency.HOT.value:
            failures.append(f"a RUNNING model reads {row['current_residency']}")
        if not row["immediately_callable"]:
            failures.append("HOT is not reported as immediately callable")
    rows.append(_row("L", "hot_model_is_immediately_callable", failures,
                     reading=row["current_residency"] if row else None,
                     hotness=row["hotness_score"] if row else None))

    # M - demotion. With demand gone, the same model should stop deserving HOT.
    quiet = FederationOps(mesh, matrix, demand=DemandLedger())
    residency_quiet = quiet.model_residency_matrix(
        now=now, physical={LOCAL_MODEL: ResidencyState.RUNNING}, model_costs=costs)
    row_q = next((r for r in residency_quiet if r["model_id"] == LOCAL_MODEL), None)
    failures = []
    if row_q and row_q["preferred_residency"] == OperationalResidency.HOT.value:
        failures.append("still recommends HOT with no observed demand at all")
    if row_q and row_q["action"] == "none":
        failures.append("no demotion proposed for an idle resident model")
    rows.append(_row("M", "idle_model_is_demoted", failures,
                     action=row_q["action"] if row_q else None,
                     reasons=row_q["hotness_reasons"] if row_q else None))

    # N - a large rare model must not be recommended HOT. This is the whole
    # point of dynamic residency: 24/7 is not "everything loaded".
    big = hotness("big/rare-30b", requests=0, role_criticality="NORMAL",
                  peak_ram_mb=22000.0, cold_load_ms=40000.0, window_requests=30)
    failures = []
    if big.recommended is OperationalResidency.HOT:
        failures.append("a 22 GB model with no demand was recommended HOT")
    small_busy = hotness("small/busy", requests=25, role_criticality="CRITICAL",
                         peak_ram_mb=1800.0, cold_load_ms=9000.0, window_requests=30)
    if small_busy.recommended is not OperationalResidency.HOT:
        failures.append("a cheap, busy, critical model was not recommended HOT")
    rows.append(_row("N", "hot_is_earned_not_assigned", failures,
                     large_rare=big.to_dict(), small_busy=small_busy.to_dict()))

    # O - cold and JIT. A model with nothing on this machine reads JIT, which
    # is a promise about acquiring it rather than about having it.
    residency_cold = ops.model_residency_matrix(
        now=now, physical={LOCAL_MODEL: ResidencyState.COLD}, model_costs=costs)
    row_c = next((r for r in residency_cold if r["model_id"] == LOCAL_MODEL), None)
    failures = []
    if row_c and row_c["current_residency"] != OperationalResidency.JIT.value:
        failures.append(f"a COLD artifact reads {row_c['current_residency']}")
    if row_c and row_c["immediately_callable"]:
        failures.append("JIT was reported as immediately callable")
    rows.append(_row("O", "cold_artifact_reads_jit_not_callable", failures,
                     reading=row_c["current_residency"] if row_c else None))

    # P - sleeping. Intentionally inactive is not the same fact as failed, and
    # the reading has to keep them apart.
    residency_sleep = ops.model_residency_matrix(
        now=now, physical={LOCAL_MODEL: ResidencyState.SLEEPING}, model_costs=costs)
    row_s = next((r for r in residency_sleep if r["model_id"] == LOCAL_MODEL), None)
    residency_broken = ops.model_residency_matrix(
        now=now, physical={LOCAL_MODEL: ResidencyState.BROKEN}, model_costs=costs)
    row_b = next((r for r in residency_broken if r["model_id"] == LOCAL_MODEL), None)
    failures = []
    if row_s and row_s["current_residency"] != OperationalResidency.SLEEPING.value:
        failures.append(f"SLEEPING read as {row_s['current_residency']}")
    if row_b and row_b["current_residency"] != OperationalResidency.OFFLINE.value:
        failures.append(f"BROKEN read as {row_b['current_residency']}")
    if row_s and row_b and row_s["current_residency"] == row_b["current_residency"]:
        failures.append("sleeping and broken read the same")
    rows.append(_row("P", "sleeping_is_not_broken", failures,
                     sleeping=row_s["current_residency"] if row_s else None,
                     broken=row_b["current_residency"] if row_b else None))

    # Q - a provider-held model costs us no residency and reads SERVERLESS.
    provider_rows = [r for r in residency if str(r["model_id"]).startswith("@")]
    failures = []
    if not provider_rows:
        failures.append("no provider-held model in any role, so this proves nothing")
    for entry in provider_rows:
        if entry["current_residency"] != OperationalResidency.SERVERLESS.value:
            failures.append(f"{entry['model_id']} reads {entry['current_residency']}")
        if entry["hotness_score"] is not None:
            failures.append(f"{entry['model_id']} was given a hotness score it cannot act on")
    rows.append(_row("Q", "provider_model_costs_no_residency", failures,
                     provider_models=[r["model_id"] for r in provider_rows]))

    # R - the worker holding a HOT model disappears. The reading must stop
    # saying HOT; a stale HOT is how a router sends work into a void.
    registry_r = WorkerRegistry()
    _join(registry_r, "host-0", worker_class=WorkerClass.PERSISTENT_LOCAL,
          privacy=Privacy.CONFIDENTIAL, now=now, capabilities=caps,
          current_models=frozenset({LOCAL_MODEL}))
    mesh_r = FreeWorkerMesh(registry_r, providers)
    ops_r = FederationOps(mesh_r, matrix, demand=ledger)
    registry_r.healthcheck("host-0", healthy=False, now=now)
    registry_r._move(registry_r.get("host-0"), WorkerState.OFFLINE)
    worker_rows = ops_r.worker_role_matrix(now=now)
    host = next(r for r in worker_rows if r["executor_id"] == "host-0")
    failures = []
    if host["online"]:
        failures.append("an offline worker still reads online")
    if "host-0" in (ops_r.snapshot(now=now, physical={LOCAL_MODEL: ResidencyState.RUNNING},
                                   model_costs=costs)["WORKERS_ONLINE"]):
        failures.append("an offline worker appears in WORKERS_ONLINE")
    rows.append(_row("R", "worker_vanishing_clears_its_claims", failures,
                     online=host["online"], state=host["state"]))

    return rows


# -- service profiles -------------------------------------------------------

def profile_rounds(root: Path, now: float, matrix: dict[str, Any]) -> list[dict[str, Any]]:
    providers, _ = load_registry(root)
    rows: list[dict[str, Any]] = []
    caps = {"deep_reasoning", "text_reasoning", "coding", "software_engineering",
            "debugging", "verifier_checker", "code_review", "agentic_planning",
            "tool_calling", "long_context", "synthesis_generalist",
            "vietnamese_reasoning", "multilingual"}

    registry = WorkerRegistry()
    _join(registry, "host-0", worker_class=WorkerClass.PERSISTENT_LOCAL,
          privacy=Privacy.CONFIDENTIAL, now=now, capabilities=caps)
    mesh = FreeWorkerMesh(registry, providers)
    ops = FederationOps(mesh, matrix)
    profiles = ops.service_profiles(now=now)

    failures = []
    minimum = profiles[ServiceProfile.MINIMUM.value]
    if not minimum["met"]:
        failures.append(f"minimum service not met: {', '.join(minimum['unmet_roles'])}")
    rows.append(_row("S", "minimum_service_profile_is_met", failures,
                     roles=minimum["roles"], unmet=minimum["unmet_roles"]))

    normal = profiles[ServiceProfile.NORMAL.value]
    rows.append(_row("T", "normal_service_profile_is_met",
                     [] if normal["met"] else
                     [f"unmet: {', '.join(normal['unmet_roles'])}"],
                     roles=normal["roles"], unmet=normal["unmet_roles"]))

    # U - with everything local gone, MINIMUM must stop claiming to be met.
    registry.healthcheck("host-0", healthy=False, now=now)
    registry._move(registry.get("host-0"), WorkerState.OFFLINE)
    degraded = ops.service_profiles(now=now)[ServiceProfile.MINIMUM.value]
    failures = []
    if degraded["met"]:
        failures.append("minimum service still claims to be met with no worker serving")
    rows.append(_row("U", "profile_stops_claiming_when_paths_go", failures,
                     unmet=degraded["unmet_roles"]))
    return rows


# -- the live round ---------------------------------------------------------

def live_round(root: Path, now: float, matrix: dict[str, Any]) -> dict[str, Any]:
    """One round that is inference through the canonical chain, not state.

    Everything above is a state machine and proves the fabric reacts correctly.
    This proves the fabric runs: the request goes through `run_federated`, which
    is the existing USER -> task_router -> Model Mesh -> scheduler -> worker ->
    model path. Nothing here calls a backend directly, because a round that
    bypassed the router would prove the opposite of what it claims.
    """
    failures: list[str] = []
    detail: dict[str, Any] = {}
    try:
        from AI_SKILL_LIBRARY.v4.local_runtime.multi_model import (
            FederationError as MMError, run_federated)
    except Exception as exc:  # noqa: BLE001
        return _row("V", "live_federated_role_execution",
                    [f"runtime unavailable: {type(exc).__name__}: {exc}"])

    request = ("If every A is a B, and every B is a C, is every A a C? "
               "Answer yes or no and give one short reason.")
    try:
        result = run_federated(request, root=root, cache=root / ".model-cache",
                               profile="STANDARD", max_tokens=48).to_dict()
    except MMError as exc:
        # A refusal is a failed round, never a skipped one.
        return _row("V", "live_federated_role_execution",
                    [f"federation refused: {exc}"])
    except Exception as exc:  # noqa: BLE001
        return _row("V", "live_federated_role_execution",
                    [f"{type(exc).__name__}: {exc}"])

    workers = result.get("workers") or []
    answer = str(result.get("answer") or "")
    detail.update({
        "domain": result.get("domain"),
        "primary_skill": result.get("primary_skill"),
        "collaboration_mode": result.get("collaboration_mode"),
        "models_run": [w.get("model_id") for w in workers],
        "answer": answer[:160],
        "routing_authority": result.get("routing_authority"),
        "model_selection_authority": result.get("model_selection_authority"),
        "resolved_by_vote": result.get("resolved_by_vote"),
    })

    if not workers:
        failures.append("the chain ran but no worker is recorded")
    if not answer.strip():
        failures.append("the chain returned an empty answer")
    if "yes" not in answer.lower():
        failures.append(f"answer does not contain the correct conclusion: {answer[:80]!r}")
    if result.get("routing_authority") != "task_router":
        failures.append(f"routing authority was {result.get('routing_authority')!r}")
    if result.get("model_selection_authority") != "model_mesh":
        failures.append(
            f"model selection authority was {result.get('model_selection_authority')!r}")
    if result.get("resolved_by_vote") is not False:
        failures.append("the round resolved by vote, which this federation does not do")

    # The model that ran must be one the role matrix actually maps to a role.
    # A live answer from a model no branch owns would mean the matrix and the
    # runtime disagree about who serves what.
    mapped = {m for row in matrix["ROLE_CAPABILITY_MATRIX"]
              for m in (row.get("all_candidates") or [])}
    unmapped = [w.get("model_id") for w in workers if w.get("model_id") not in mapped]
    if unmapped:
        failures.append(f"ran model(s) no role branch maps: {', '.join(map(str, unmapped))}")
    detail["all_models_are_role_mapped"] = not unmapped

    return _row("V", "live_federated_role_execution", failures, **detail)


# Binding helpers, imported from the tool that already defines this repository's
# one spelling of them rather than restated here. A second implementation of
# "which revision is this" is a second implementation to drift.
from worker_execution_liveness import (  # noqa: E402
    current_source_sha as _current_source_sha,
    observing_host as _observing_host,
    utc_now as _utc_now,
)


def build(root: Path, *, skip_live: bool = False) -> dict[str, Any]:
    now = time.time()
    matrix = role_capability_matrix.build(root)
    rounds: list[dict[str, Any]] = []
    rounds.extend(failure_drills(root, now, matrix))
    rounds.extend(residency_drills(root, now, matrix))
    rounds.extend(profile_rounds(root, now, matrix))
    if skip_live:
        rounds.append(_row("V", "live_federated_role_execution",
                           ["skipped by --skip-live; a skipped round never passes"],
                           skipped=True))
    else:
        rounds.append(live_round(root, now, matrix))

    passed = sum(1 for r in rounds if r["passed"])
    return {
        "tool": "federation_24x7_proof",
        # Binding, added after this document was found asserting PROVEN 22/22
        # with nothing saying which revision, which moment or which machine it
        # was about. A claim nobody can age is a claim nobody can contradict,
        # and the scoping tool correctly refused to count it as canonical.
        # Every round below breaks something on THIS host: a CPU that takes
        # SIGILL on the engine binary reads round V the opposite way from one
        # that does not, and both readings are true of the machines they name.
        "source_sha": _current_source_sha(root),
        "proof_timestamp": _utc_now(),
        "OBSERVED_ON": _observing_host(),
        "reading_scope": ("a fact about the machine named in OBSERVED_ON at the "
                          "moment it ran, against the revision named in "
                          "source_sha; not a standing property of the code"),
        "federation_status": "PROVEN" if passed == len(rounds) else "FAILED",
        "rounds_passed": passed,
        "rounds_total": len(rounds),
        "rounds": rounds,
        "note": ("every round breaks something real and asks the existing mesh "
                 "what it does. A round that could not run does not pass."),
        "routing_authority": False,
        "admission_authority": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=repo_root)
    parser.add_argument("--evidence", type=Path, default=None)
    parser.add_argument("--skip-live", action="store_true",
                        help="skip the inference round; it is then recorded as not passing")
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = build(args.root, skip_live=args.skip_live)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")

    print(f"24X7_FEDERATION={result['federation_status']} "
          f"{result['rounds_passed']}/{result['rounds_total']}")
    for row in result["rounds"]:
        print(f"  {row['round']} {row['scenario']:<48} "
              f"{'PASS' if row['passed'] else 'FAIL'}")
        for failure in row["failures"]:
            print(f"      {failure}")
    return 0 if result["federation_status"] == "PROVEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
