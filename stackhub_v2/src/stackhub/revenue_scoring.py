from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from .opportunity import NormalizedOpportunity


class RevenueMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    success_probability: Decimal = Field(default=Decimal("0.5"), ge=0, le=1)
    payout_probability: Decimal = Field(default=Decimal("0.8"), ge=0, le=1)
    source_reliability: Decimal = Field(default=Decimal("0.8"), ge=0, le=1)
    verification_probability: Decimal = Field(default=Decimal("0.9"), ge=0, le=1)
    payout_latency_penalty: Decimal = Field(default=Decimal("1"), gt=0, le=1)
    uncertainty_penalty: Decimal = Field(default=Decimal("1"), gt=0, le=1)


def score_opportunity(
    opportunity: NormalizedOpportunity,
    metrics: RevenueMetrics,
) -> Decimal:
    if opportunity.agent_allowed is not True:
        return Decimal("-1")
    if opportunity.reward_usd_estimate is None:
        return Decimal("-1")

    worker_minutes = Decimal(opportunity.estimated_effort_minutes)
    score = (
        opportunity.reward_usd_estimate
        * metrics.success_probability
        * metrics.payout_probability
        * metrics.source_reliability
        * metrics.verification_probability
        * metrics.payout_latency_penalty
        * metrics.uncertainty_penalty
        / worker_minutes
    )
    return score.quantize(Decimal("0.000001"))
