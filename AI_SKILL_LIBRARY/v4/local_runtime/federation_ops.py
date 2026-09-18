"""The 24/7 operating view: what the federation can serve right now, and why.

Phase 6 does not add capacity, models or authority. It adds the ability to
answer, at any moment, the questions an operator actually has: which roles are
serviceable, which have one path and would go dark if it failed, which models
are worth keeping resident, and what the federation is currently promising.

**Nothing here is a registry.** `FederationOps` is constructed from the existing
`WorkerRegistry`, `ProviderRegistry` and `FreeWorkerMesh` and reads them. It
stores no worker, admits no model, selects no model and routes nothing. The
authority flags are class attributes fixed False, so a `FederationOps(...,
routing_authority=True)` is a `TypeError` - the same guard the worker contract
uses, for the same reason.

**Operational residency is derived, not a tenth enum.** Three facts already
exist and are composed rather than replaced: the policy tier from
`residency_policy` (HOT/WARM/COLD/ARCHIVED), the physical state from
`residency.ResidencyState`, and where the thing runs from the worker or
provider. HOT, WARM, COLD, JIT, SERVERLESS, REMOTE, SLEEPING and OFFLINE are
the readings that composition produces. Inventing a new state machine would
have meant two sources of truth for where a model is, and the second one would
have been wrong within a week.

**24/7 means the federation stays serviceable, not that every model stays
loaded.** A model earns HOT by demand and cheapness, and a large rare model is
supposed to be COLD. A service profile is a promise about ROLES; it is met by
whatever path is placeable at the time, including a hosted one under a
substitute's name.

**Health is role coverage, not liveness.** A process that is running while its
only verifier is offline is not HEALTHY, and this reports it as it is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

from .free_worker_mesh import FreeWorkerMesh
from .providers import VERIFIED_STATES, ProviderRegistry
from .residency import ResidencyState
from .resilience import BreakerState
from .scheduler import Privacy
from .workers import SERVING_STATES, WorkerRegistry, WorkerState


class FederationError(RuntimeError):
    """An operating question that cannot be answered from the given state."""


class RoleHealth(str, Enum):
    """What a role can promise. Ordered worst-last on purpose."""

    AVAILABLE_PRIMARY = "AVAILABLE_PRIMARY"        # preferred path placeable
    AVAILABLE_FALLBACK_ONLY = "AVAILABLE_FALLBACK_ONLY"  # only a lesser path is
    DEGRADED = "DEGRADED"                          # part of the role is served
    BLOCKED = "BLOCKED"                            # a path exists, nothing can reach it
    UNAVAILABLE = "UNAVAILABLE"                    # no measured path at all


#: Role health values in which the role answers requests at all.
SERVICEABLE_ROLE_HEALTH = frozenset({
    RoleHealth.AVAILABLE_PRIMARY, RoleHealth.AVAILABLE_FALLBACK_ONLY,
})


class FederationHealth(str, Enum):
    HEALTHY = "HEALTHY"        # every CRITICAL and HIGH role serviceable
    DEGRADED = "DEGRADED"      # a HIGH role is down or a CRITICAL one is fallback-only
    PARTIAL = "PARTIAL"        # a CRITICAL role is degraded
    CRITICAL = "CRITICAL"      # a CRITICAL role cannot be served
    RECOVERING = "RECOVERING"  # was down, paths are coming back, not yet steady


class OperationalResidency(str, Enum):
    """A derived reading, composed from tier, physical state and placement."""

    HOT = "HOT"                # loaded here and immediately callable
    WARM = "WARM"              # worker has it ready; a wake, not a load
    COLD = "COLD"              # bytes on disk, nothing in memory
    JIT = "JIT"                # not here; acquirable on demand
    SERVERLESS = "SERVERLESS"  # a provider holds it; we hold nothing
    REMOTE = "REMOTE"          # resident on another worker
    SLEEPING = "SLEEPING"      # intentionally inactive, cheap to wake
    OFFLINE = "OFFLINE"        # no path to it at this moment


#: Residency readings in which a call can be served without acquiring bytes.
IMMEDIATE_RESIDENCY = frozenset({
    OperationalResidency.HOT, OperationalResidency.WARM,
    OperationalResidency.SERVERLESS, OperationalResidency.REMOTE,
})

#: Physical state -> reading, before placement is considered.
_PHYSICAL_READING: Mapping[ResidencyState, OperationalResidency] = {
    ResidencyState.RUNNING: OperationalResidency.HOT,
    ResidencyState.WARM: OperationalResidency.WARM,
    ResidencyState.READY: OperationalResidency.COLD,
    ResidencyState.LOADING: OperationalResidency.COLD,
    ResidencyState.ACQUIRING: OperationalResidency.JIT,
    ResidencyState.COLD: OperationalResidency.JIT,
    ResidencyState.SLEEPING: OperationalResidency.SLEEPING,
    ResidencyState.DEGRADED: OperationalResidency.WARM,
    ResidencyState.BROKEN: OperationalResidency.OFFLINE,
    ResidencyState.OFFLINE: OperationalResidency.OFFLINE,
}


class ServiceProfile(str, Enum):
    MINIMUM = "MINIMUM_OPERATIONAL"
    NORMAL = "NORMAL_SERVICE"
    FULL = "FULL_CAPACITY"


#: What each profile PROMISES, by role. A profile is met when every role in it
#: is serviceable by some placeable path - not when a particular model is up.
PROFILE_ROLES: Mapping[ServiceProfile, tuple[str, ...]] = {
    ServiceProfile.MINIMUM: (
        "REASONING_BRANCH", "VERIFICATION_BRANCH", "CODING_BRANCH"),
    ServiceProfile.NORMAL: (
        "REASONING_BRANCH", "VERIFICATION_BRANCH", "CODING_BRANCH",
        "PLANNING_BRANCH", "TOOL_USE_BRANCH", "RESEARCH_BRANCH",
        "RETRIEVAL_BRANCH", "VIETNAMESE_BRANCH", "MULTILINGUAL_BRANCH"),
    ServiceProfile.FULL: (
        "REASONING_BRANCH", "VERIFICATION_BRANCH", "CODING_BRANCH",
        "PLANNING_BRANCH", "TOOL_USE_BRANCH", "RESEARCH_BRANCH",
        "RETRIEVAL_BRANCH", "MEMORY_BRANCH", "VIETNAMESE_BRANCH",
        "MULTILINGUAL_BRANCH", "SCIENCE_TECH_BRANCH", "VISION_BRANCH",
        "DOCUMENT_OCR_BRANCH", "SPEECH_BRANCH"),
}


@dataclass(frozen=True)
class RoleObservation:
    """One completed piece of role work. Content is deliberately not recorded."""

    role_id: str
    model_id: str
    executor_id: str
    execution_mode: str
    started_at: float
    latency_ms: float
    succeeded: bool
    failure_kind: str | None = None
    verified: bool | None = None
    retries: int = 0
    escalated_from: str | None = None

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "role_id": self.role_id, "model_id": self.model_id,
            "executor_id": self.executor_id, "execution_mode": self.execution_mode,
            "started_at": self.started_at, "latency_ms": self.latency_ms,
            "succeeded": self.succeeded, "failure_kind": self.failure_kind,
            "verified": self.verified, "retries": self.retries,
            "escalated_from": self.escalated_from,
        }


@dataclass
class DemandLedger:
    """Observed role demand. Never a projection with no observations behind it."""

    observations: list[RoleObservation] = field(default_factory=list)

    def record(self, observation: RoleObservation) -> None:
        self.observations.append(observation)

    def window(self, *, now: float, seconds: float) -> list[RoleObservation]:
        return [o for o in self.observations if now - o.started_at <= seconds]

    def demand(self, *, now: float, seconds: float = 3600.0) -> Mapping[str, Any]:
        rows = self.window(now=now, seconds=seconds)
        per_role: dict[str, dict[str, Any]] = {}
        for observation in rows:
            entry = per_role.setdefault(observation.role_id, {
                "requests": 0, "failures": 0, "retries": 0,
                "latency_ms_total": 0.0, "models": set(), "escalations": 0,
            })
            entry["requests"] += 1
            entry["failures"] += int(not observation.succeeded)
            entry["retries"] += observation.retries
            entry["latency_ms_total"] += observation.latency_ms
            entry["models"].add(observation.model_id)
            entry["escalations"] += int(bool(observation.escalated_from))
        for entry in per_role.values():
            entry["mean_latency_ms"] = round(
                entry["latency_ms_total"] / entry["requests"], 3)
            entry["failure_rate"] = round(entry["failures"] / entry["requests"], 4)
            entry["models"] = sorted(entry["models"])
            entry.pop("latency_ms_total")
        return {
            # OBSERVED_ONLY until there is enough history to say anything else.
            # A demand model built on no traffic is a guess wearing a number.
            "mode": "OBSERVED_ONLY" if len(rows) < 20 else "OBSERVED",
            "window_seconds": seconds,
            "observations": len(rows),
            "per_role": per_role,
            "note": ("counts only what actually ran. No synthetic traffic, and "
                     "no extrapolation from a window this thin."),
        }


@dataclass(frozen=True)
class Hotness:
    """Why a model does or does not deserve to stay loaded."""

    model_id: str
    score: float
    recommended: OperationalResidency
    reasons: tuple[str, ...]
    requests: int
    peak_ram_mb: float | None
    cold_load_ms: float | None
    role_criticality: str

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "model_id": self.model_id, "hotness_score": round(self.score, 6),
            "recommended_residency": self.recommended.value,
            "reasons": list(self.reasons), "requests_in_window": self.requests,
            "peak_ram_mb": self.peak_ram_mb, "cold_load_ms": self.cold_load_ms,
            "role_criticality": self.role_criticality,
        }


#: Criticality weights. A role nothing can run without is worth keeping ready
#: even when it is quiet; an opportunistic one is not.
_CRITICALITY_WEIGHT = {
    "CRITICAL": 1.0, "HIGH": 0.7, "NORMAL": 0.4, "OPPORTUNISTIC": 0.1,
}

#: Above this, a model is worth a HOT slot if the budget allows.
HOT_THRESHOLD = 0.55
#: Above this but below HOT, keep it WARM rather than paying a cold load.
WARM_THRESHOLD = 0.25


def hotness(
    model_id: str, *, requests: int, role_criticality: str,
    peak_ram_mb: float | None, cold_load_ms: float | None,
    window_requests: int,
) -> Hotness:
    """HOT is earned, not assigned.

    Demand and criticality push a model up; the memory it holds and the load it
    would cost push it down. A large rare model scores low and is meant to: the
    point of dynamic residency is that scarce memory goes to what is actually
    being asked for.
    """
    reasons: list[str] = []
    share = (requests / window_requests) if window_requests else 0.0
    weight = _CRITICALITY_WEIGHT.get(role_criticality, 0.4)

    score = 0.6 * share + 0.4 * weight
    if share == 0.0:
        reasons.append("no observed demand in the window")
    else:
        reasons.append(f"{requests} of {window_requests} observed requests")
    reasons.append(f"role criticality {role_criticality}")

    if peak_ram_mb and peak_ram_mb > 6000:
        score *= 0.5
        reasons.append(f"{int(peak_ram_mb)} MB resident is expensive for a HOT slot")
    if cold_load_ms is not None and cold_load_ms < 2000:
        # Cheap to load means there is little to gain by holding it.
        score *= 0.8
        reasons.append(f"cold load is only {int(cold_load_ms)} ms, so holding it buys little")
    elif cold_load_ms is not None and cold_load_ms > 8000:
        score *= 1.15
        reasons.append(f"cold load is {int(cold_load_ms)} ms, which is worth avoiding")

    score = max(0.0, min(1.0, score))
    if score >= HOT_THRESHOLD:
        recommended = OperationalResidency.HOT
    elif score >= WARM_THRESHOLD:
        recommended = OperationalResidency.WARM
    else:
        recommended = OperationalResidency.COLD
        reasons.append("below the warm threshold; JIT or cold load on demand")
    return Hotness(model_id=model_id, score=score, recommended=recommended,
                   reasons=tuple(reasons), requests=requests,
                   peak_ram_mb=peak_ram_mb, cold_load_ms=cold_load_ms,
                   role_criticality=role_criticality)


class FederationOps:
    """Reads the existing registries and answers operating questions."""

    # Not constructor arguments. The operating view observes; it cannot acquire
    # authority by being asked nicely.
    routing_authority = False
    reasoning_authority = False
    memory_authority = False
    model_selection_authority = False
    admission_authority = False
    scheduling_authority = False
    evidence_authority = False

    def __init__(
        self,
        mesh: FreeWorkerMesh,
        role_matrix: Mapping[str, Any],
        *,
        demand: DemandLedger | None = None,
    ) -> None:
        self.mesh = mesh
        self.role_matrix = role_matrix
        self.demand = demand or DemandLedger()

    # -- workers -----------------------------------------------------------

    @property
    def workers(self) -> WorkerRegistry:
        return self.mesh.workers

    @property
    def providers(self) -> ProviderRegistry:
        return self.mesh.providers

    def worker_role_matrix(self, *, now: float) -> list[Mapping[str, Any]]:
        """Every executor, what it can serve, and what it contributes."""
        roles = self.role_matrix.get("ROLE_CAPABILITY_MATRIX") or []
        rows: list[Mapping[str, Any]] = []

        for worker in self.workers.all():
            breaker = self.mesh.breaker(worker.worker_id)
            stale = worker.lease_expired(now=now)
            online = worker.state in SERVING_STATES and not stale
            # A worker serves a role when it is MEASURED for every capability
            # that role needs. Declared capabilities advertise and do not count.
            served = [
                row["role_id"] for row in roles
                if row.get("required_capabilities")
                and set(row["required_capabilities"]) <= set(worker.measured_capabilities)
            ]
            rows.append({
                "executor_id": worker.worker_id,
                "kind": "WORKER",
                "worker_class": worker.worker_class.value,
                "state": worker.state.value,
                "online": online,
                "stale_lease": stale,
                "last_seen": worker.last_seen,
                "lease_seconds": worker.lease_seconds,
                "ram_total_mb": worker.resources.ram_total_mb,
                "ram_available_mb": worker.resources.ram_available_mb,
                "gpus": len(worker.resources.gpus),
                "disk_free_mb": worker.resources.disk_free_mb,
                "runtimes": sorted(worker.runtimes),
                "formats": sorted(worker.supported_formats),
                "measured_capabilities": sorted(worker.measured_capabilities),
                "declared_capabilities": sorted(worker.declared_capabilities),
                "supported_roles": sorted(served),
                "loaded_models": sorted(worker.current_models),
                "concurrency": f"{worker.current_jobs}/{worker.max_concurrent_jobs}",
                "queue_headroom": max(0, worker.max_concurrent_jobs - worker.current_jobs),
                "quota_remaining": worker.quota_remaining,
                "quota_exhausted": worker.quota_exhausted(now=now),
                "trust_class": worker.trust_class,
                "third_party": worker.is_third_party,
                "privacy_ceiling": (worker.attestation.max_privacy.value
                                    if worker.attestation else None),
                "circuit": breaker.state.value,
                "cost_class": worker.cost_class,
            })

        for provider in self.providers.all():
            usable = provider.verification_state in VERIFIED_STATES
            rows.append({
                "executor_id": provider.provider_id,
                "kind": "PROVIDER",
                "worker_class": provider.execution_type.value,
                "state": provider.verification_state.value,
                "online": usable,
                "holds_our_weights": provider.custom_weights,
                "credential_here": provider.credential_available_here,
                "credential_held_by_worker": provider.credential_held_by_worker,
                "cost_class": provider.cost_class.value,
                "usable": usable,
            })
        return rows

    # -- roles -------------------------------------------------------------

    def role_health(self, *, now: float) -> list[Mapping[str, Any]]:
        """Static mapping meets live capacity. Both, or the answer is a guess."""
        rows: list[Mapping[str, Any]] = []
        worker_rows = self.worker_role_matrix(now=now)
        online_workers = {r["executor_id"] for r in worker_rows
                          if r["kind"] == "WORKER" and r["online"]
                          and r.get("circuit") != BreakerState.OPEN.value
                          and not r.get("quota_exhausted")}
        online_providers = {r["executor_id"] for r in worker_rows
                            if r["kind"] == "PROVIDER" and r["online"]}
        any_local = bool(online_workers)
        any_serverless = bool(online_providers)

        for row in self.role_matrix.get("ROLE_CAPABILITY_MATRIX") or []:
            role = str(row.get("role_id"))
            mapped = str(row.get("status") or "UNAVAILABLE")
            if row.get("placeholder"):
                rows.append({"role_id": role, "health": "PLACEHOLDER",
                             "criticality": row.get("criticality"),
                             "reason": "a forward-looking name, not a requirement"})
                continue

            primary = row.get("primary") or {}
            placement = str(primary.get("placement") or "")
            # A mapping is a promise about evidence; whether it can be kept
            # right now is a question about live capacity.
            if mapped == "UNAVAILABLE":
                health, reason = RoleHealth.UNAVAILABLE, "no measured path exists"
            elif mapped == "DEGRADED":
                health = RoleHealth.DEGRADED
                reason = (f"measured: {', '.join(row.get('capabilities_covered') or [])}; "
                          f"no path: {', '.join(row.get('capabilities_uncovered') or [])}")
            elif placement in ("SERVERLESS",) and not any_serverless:
                health, reason = RoleHealth.BLOCKED, "its only path is a provider that is not usable now"
            elif placement in ("LOCAL",) and not any_local:
                health, reason = RoleHealth.BLOCKED, "its only path is local and no worker is serving"
            elif placement == "MIXED" and not (any_local or any_serverless):
                health, reason = RoleHealth.BLOCKED, "no executor of either kind is serving"
            elif mapped == "AVAILABLE_PRIMARY":
                health, reason = RoleHealth.AVAILABLE_PRIMARY, "preferred path placeable"
            else:
                health = RoleHealth.AVAILABLE_FALLBACK_ONLY
                reason = "a path exists, but only one and not the preferred shape"

            rows.append({
                "role_id": role,
                "criticality": row.get("criticality"),
                "health": health.value,
                "reason": reason,
                "mapped_status": mapped,
                "primary_model": primary.get("model_id"),
                "execution_mode": primary.get("execution_mode"),
                "placement": placement or None,
                "independent_paths": row.get("independent_paths"),
                "single_path_risk": bool(row.get("single_path_risk")),
                "privacy_classes": row.get("privacy_classes") or [],
            })
        return rows

    def federation_health(self, *, now: float) -> Mapping[str, Any]:
        """Coverage, not liveness. A running process with no verifier is not healthy."""
        roles = self.role_health(now=now)
        by_criticality: dict[str, list[Mapping[str, Any]]] = {}
        for row in roles:
            if row["health"] == "PLACEHOLDER":
                continue
            by_criticality.setdefault(str(row.get("criticality")), []).append(row)

        def down(level: str) -> list[str]:
            return [r["role_id"] for r in by_criticality.get(level, [])
                    if r["health"] not in {h.value for h in SERVICEABLE_ROLE_HEALTH}]

        critical_down = down("CRITICAL")
        high_down = down("HIGH")
        critical_degraded = [r["role_id"] for r in by_criticality.get("CRITICAL", [])
                             if r["health"] == RoleHealth.DEGRADED.value]
        critical_fallback = [r["role_id"] for r in by_criticality.get("CRITICAL", [])
                             if r["health"] == RoleHealth.AVAILABLE_FALLBACK_ONLY.value]

        if critical_down:
            state = FederationHealth.CRITICAL
            why = f"CRITICAL role(s) cannot be served: {', '.join(critical_down)}"
        elif critical_degraded:
            state = FederationHealth.PARTIAL
            why = f"CRITICAL role(s) partly served: {', '.join(critical_degraded)}"
        elif high_down or critical_fallback:
            state = FederationHealth.DEGRADED
            why = ("HIGH role(s) down: " + ", ".join(high_down) if high_down
                   else "CRITICAL role(s) on a fallback path only: "
                        + ", ".join(critical_fallback))
        else:
            state = FederationHealth.HEALTHY
            why = "every CRITICAL and HIGH role has a placeable path"

        return {
            "FEDERATION_STATE": state.value,
            "reason": why,
            "critical_roles_down": critical_down,
            "critical_roles_degraded": critical_degraded,
            "critical_roles_fallback_only": critical_fallback,
            "high_roles_down": high_down,
            "roles_serviceable": sum(
                1 for r in roles
                if r["health"] in {h.value for h in SERVICEABLE_ROLE_HEALTH}),
            "roles_total": sum(1 for r in roles if r["health"] != "PLACEHOLDER"),
            "health_is": ("role coverage, not process liveness. A running "
                          "federation with no serviceable verifier is not HEALTHY."),
        }

    # -- profiles ----------------------------------------------------------

    def service_profiles(self, *, now: float) -> Mapping[str, Any]:
        """Which promises the federation can currently keep."""
        health = {r["role_id"]: r["health"] for r in self.role_health(now=now)}
        serviceable = {h.value for h in SERVICEABLE_ROLE_HEALTH}
        out: dict[str, Any] = {}
        for profile, roles in PROFILE_ROLES.items():
            missing = [r for r in roles if health.get(r) not in serviceable]
            out[profile.value] = {
                "roles": list(roles),
                "met": not missing,
                "unmet_roles": missing,
                "degraded_roles": [r for r in roles
                                   if health.get(r) == RoleHealth.DEGRADED.value],
            }
        return out

    # -- residency ---------------------------------------------------------

    def model_residency_matrix(
        self, *, now: float,
        physical: Mapping[str, ResidencyState] | None = None,
        model_costs: Mapping[str, Mapping[str, Any]] | None = None,
        window_seconds: float = 3600.0,
    ) -> list[Mapping[str, Any]]:
        """Every model a role maps to: where it is, and where it should be."""
        physical = physical or {}
        model_costs = model_costs or {}
        demand = self.demand.demand(now=now, seconds=window_seconds)
        per_role = demand["per_role"]
        window_requests = int(demand["observations"])

        # Which roles each model serves, and the highest criticality among them.
        serves: dict[str, list[str]] = {}
        criticality: dict[str, str] = {}
        order = ["OPPORTUNISTIC", "NORMAL", "HIGH", "CRITICAL"]
        for row in self.role_matrix.get("ROLE_CAPABILITY_MATRIX") or []:
            level = str(row.get("criticality") or "NORMAL")
            for candidate in (row.get("all_candidates") or []):
                serves.setdefault(candidate, []).append(str(row.get("role_id")))
                if order.index(level) > order.index(criticality.get(candidate, "OPPORTUNISTIC")):
                    criticality[candidate] = level
            pipeline = row.get("pipeline") or {}
            for model in pipeline.values():
                if not model:
                    continue
                serves.setdefault(model, []).append(str(row.get("role_id")))
                if order.index(level) > order.index(criticality.get(model, "OPPORTUNISTIC")):
                    criticality[model] = level

        worker_of: dict[str, str] = {}
        for worker in self.workers.all():
            for model in worker.current_models:
                worker_of[model] = worker.worker_id

        rows: list[Mapping[str, Any]] = []
        for model in sorted(serves):
            roles = sorted(set(serves[model]))
            requests = sum(int(per_role.get(r, {}).get("requests", 0)) for r in roles)
            costs = model_costs.get(model, {})
            is_provider = model.startswith("@") or " + " in model

            if is_provider:
                usable = any(p.verification_state in VERIFIED_STATES
                             for p in self.providers.all())
                current = (OperationalResidency.SERVERLESS if usable
                           else OperationalResidency.OFFLINE)
                recommendation = current
                score = None
                reasons = ["provider-held; we hold no bytes and pay no residency"]
            else:
                state = physical.get(model)
                current = _PHYSICAL_READING.get(state, OperationalResidency.JIT) \
                    if state is not None else OperationalResidency.JIT
                holder = worker_of.get(model)
                if holder and current in (OperationalResidency.HOT, OperationalResidency.WARM):
                    # Resident somewhere that is not this host is REMOTE, which
                    # is a different promise from HOT: it needs a network hop.
                    local = next((w for w in self.workers.all()
                                  if w.worker_id == holder and not w.is_third_party), None)
                    if local is None:
                        current = OperationalResidency.REMOTE
                scored = hotness(
                    model, requests=requests,
                    role_criticality=criticality.get(model, "NORMAL"),
                    peak_ram_mb=costs.get("peak_ram_mb"),
                    cold_load_ms=costs.get("cold_load_ms"),
                    window_requests=window_requests)
                recommendation = scored.recommended
                score = round(scored.score, 6)
                reasons = list(scored.reasons)

            rows.append({
                "model_id": model,
                "roles": roles,
                "role_criticality": criticality.get(model, "NORMAL"),
                "current_residency": current.value,
                "preferred_residency": recommendation.value,
                "action": ("none" if current == recommendation
                           else f"{current.value} -> {recommendation.value}"),
                "immediately_callable": current in IMMEDIATE_RESIDENCY,
                "worker": worker_of.get(model),
                "hotness_score": score,
                "hotness_reasons": reasons,
                "peak_ram_mb": costs.get("peak_ram_mb"),
                "cold_load_ms": costs.get("cold_load_ms"),
                "requests_in_window": requests,
            })
        return rows

    # -- capacity ----------------------------------------------------------

    def role_capacity_plan(self, *, now: float,
                           window_seconds: float = 3600.0) -> list[Mapping[str, Any]]:
        """What each role needs, what it has, and the shortfall between them."""
        demand = self.demand.demand(now=now, seconds=window_seconds)
        per_role = demand["per_role"]
        worker_rows = self.worker_role_matrix(now=now)
        headroom = sum(int(r.get("queue_headroom") or 0)
                       for r in worker_rows if r["kind"] == "WORKER" and r["online"])
        serverless_up = any(r["kind"] == "PROVIDER" and r["online"] for r in worker_rows)
        health = {r["role_id"]: r["health"] for r in self.role_health(now=now)}

        plans: list[Mapping[str, Any]] = []
        for row in self.role_matrix.get("ROLE_CAPABILITY_MATRIX") or []:
            if row.get("placeholder"):
                continue
            role = str(row.get("role_id"))
            level = str(row.get("criticality") or "NORMAL")
            observed = per_role.get(role, {})
            primary = row.get("primary") or {}
            serverless = str(primary.get("placement")) == "SERVERLESS"

            # Concurrency target, from criticality rather than from traffic we
            # have not seen. With no observations this is a floor, and it says so.
            target = {"CRITICAL": 2, "HIGH": 1, "NORMAL": 1, "OPPORTUNISTIC": 1}[level]
            available = headroom if not serverless else (1 if serverless_up else 0)
            deficit = max(0, target - available)

            plans.append({
                "role_id": role,
                "criticality": level,
                "primary_model": primary.get("model_id"),
                "fallback_model": (row.get("secondary") or {}).get("model_id"),
                "residency_policy": row.get("residency_target"),
                "worker_class": "SERVERLESS_INFERENCE" if serverless else "LOCAL_PROCESS",
                "redundancy": "REDUNDANT" if row.get("redundant") else "SINGLE_PATH",
                "observed_requests": int(observed.get("requests", 0)),
                "observed_mean_latency_ms": observed.get("mean_latency_ms"),
                "observed_failure_rate": observed.get("failure_rate"),
                "concurrency_target": target,
                "concurrency_available": available,
                "capacity_deficit": deficit,
                "capacity_status": ("DEFICIT" if deficit else
                                    "OK" if health.get(role) in
                                    {h.value for h in SERVICEABLE_ROLE_HEALTH}
                                    else "NO_PATH"),
                "demand_basis": demand["mode"],
            })
        return plans

    # -- one surface -------------------------------------------------------

    def snapshot(self, *, now: float, **kwargs: Any) -> Mapping[str, Any]:
        """The whole operating picture, in the order an operator reads it."""
        worker_rows = self.worker_role_matrix(now=now)
        breakers = {r["executor_id"]: r.get("circuit") for r in worker_rows
                    if r["kind"] == "WORKER" and r.get("circuit") != BreakerState.CLOSED.value}
        return {
            **self.federation_health(now=now),
            "ROLE_HEALTH": self.role_health(now=now),
            "WORKER_ROLE_MATRIX": worker_rows,
            "MODEL_RESIDENCY_MATRIX": self.model_residency_matrix(now=now, **kwargs),
            "ROLE_CAPACITY_PLAN": self.role_capacity_plan(now=now),
            "SERVICE_PROFILES": self.service_profiles(now=now),
            "DEMAND": self.demand.demand(now=now),
            "WORKERS_ONLINE": sorted(r["executor_id"] for r in worker_rows
                                     if r["kind"] == "WORKER" and r["online"]),
            "WORKERS_OFFLINE": sorted(r["executor_id"] for r in worker_rows
                                      if r["kind"] == "WORKER" and not r["online"]),
            "VERIFIED_PROVIDERS": sorted(r["executor_id"] for r in worker_rows
                                         if r["kind"] == "PROVIDER" and r["online"]),
            "CIRCUIT_BREAKERS": breakers,
            "CAPACITY_DEFICITS": [p["role_id"] for p in self.role_capacity_plan(now=now)
                                  if p["capacity_deficit"]],
            "SINGLE_PATH_RISKS": self.role_matrix.get("single_path_risks") or [],
            "routing_authority": False,
            "model_selection_authority": False,
            "scheduling_authority": False,
        }
