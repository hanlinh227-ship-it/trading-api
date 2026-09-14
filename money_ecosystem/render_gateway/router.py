from __future__ import annotations

from dataclasses import dataclass

from .contract import CostPolicy, QualityTier, RenderJob
from .providers.base import ProviderMode, RenderProvider


class QualityTargetUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class RejectedRoute:
    provider_id: str
    reason: str


@dataclass(frozen=True)
class RouteDecision:
    selected_provider_id: str
    requires_user_approval: bool
    rejected: tuple[RejectedRoute, ...]
    reason: str


_QUALITY_RANK = {
    QualityTier.DRAFT_LOCAL: 0,
    QualityTier.HIGH: 1,
    QualityTier.FLOW_GRADE: 2,
}


def route(job: RenderJob, providers: list[RenderProvider]) -> RouteDecision:
    rejected: list[RejectedRoute] = []
    candidates: list[tuple[tuple[int, int, float], RenderProvider, bool]] = []

    for provider in providers:
        caps = provider.capabilities()
        status = provider.preflight()
        provider_id = caps.provider_id
        if not status.available:
            rejected.append(RejectedRoute(provider_id, status.reason or "provider unavailable"))
            continue
        if job.job_type not in caps.job_types:
            rejected.append(RejectedRoute(provider_id, f"job type {job.job_type} unsupported"))
            continue
        if _QUALITY_RANK[caps.max_quality_tier] < _QUALITY_RANK[job.quality_tier]:
            rejected.append(RejectedRoute(provider_id, f"max quality {caps.max_quality_tier.value} below {job.quality_tier.value}"))
            continue
        if job.cost_policy is CostPolicy.LOCAL_ONLY and provider.mode is not ProviderMode.LOCAL:
            rejected.append(RejectedRoute(provider_id, "LOCAL_ONLY policy"))
            continue

        estimate = provider.estimate(job)
        requires_approval = False
        if estimate.requires_new_paid_credits:
            covered = estimate.covered_by_existing_entitlement is True
            if job.cost_policy is CostPolicy.USE_EXISTING_ENTITLEMENTS and not covered:
                rejected.append(RejectedRoute(provider_id, "requires new paid credits not covered by existing entitlement"))
                continue
            if job.cost_policy is CostPolicy.LOCAL_ONLY:
                rejected.append(RejectedRoute(provider_id, "paid execution forbidden under LOCAL_ONLY"))
                continue
            if job.cost_policy is CostPolicy.ASK_BEFORE_PAID and not covered:
                requires_approval = True

        quality_score = _QUALITY_RANK[caps.max_quality_tier]
        mode_score = {
            ProviderMode.API: 4,
            ProviderMode.CONNECTOR: 3,
            ProviderMode.LOCAL: 2,
            ProviderMode.INTERACTIVE: 1,
            ProviderMode.DISABLED: 0,
        }[provider.mode]
        latency = estimate.estimated_seconds if estimate.estimated_seconds is not None else 1e9
        candidates.append(((quality_score, mode_score, -float(latency)), provider, requires_approval))

    if not candidates:
        details = "; ".join(f"{item.provider_id}: {item.reason}" for item in rejected) or "no providers registered"
        raise QualityTargetUnavailable(
            f"QUALITY_TARGET_UNAVAILABLE for {job.quality_tier.value}: {details}"
        )

    candidates.sort(key=lambda item: item[0], reverse=True)
    _, selected, requires_approval = candidates[0]
    return RouteDecision(
        selected_provider_id=selected.capabilities().provider_id,
        requires_user_approval=requires_approval,
        rejected=tuple(rejected),
        reason=(
            f"selected highest qualifying provider for {job.quality_tier.value}; "
            f"cost_policy={job.cost_policy.value}"
        ),
    )
