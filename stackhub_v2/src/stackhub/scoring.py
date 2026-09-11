from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Sequence
from pydantic import BaseModel, Field

from .models import Opportunity


class ScoreInputs(BaseModel):
    payout_value_usd: Decimal
    win_probability: Decimal = Field(ge=0, le=1)
    verification_probability: Decimal = Field(ge=0, le=1)
    model_cost_usd: Decimal = Decimal("0")
    compute_cost_usd: Decimal = Decimal("0")
    chain_fee_usd: Decimal = Decimal("0")
    expected_failed_work_cost_usd: Decimal = Decimal("0")


class ScoreResult(BaseModel):
    expected_net_value_usd: Decimal
    score_usd_per_minute: Decimal


class ScoredOpportunity(BaseModel):
    opportunity: Opportunity
    result: ScoreResult


def score_opportunity(opportunity: Opportunity, inputs: ScoreInputs) -> ScoreResult:
    expected = (
        inputs.payout_value_usd
        * inputs.win_probability
        * inputs.verification_probability
        - inputs.model_cost_usd
        - inputs.compute_cost_usd
        - inputs.chain_fee_usd
        - inputs.expected_failed_work_cost_usd
    )
    minutes = max(opportunity.estimated_effort_minutes or 1, 1)
    score = expected / Decimal(minutes)
    return ScoreResult(
        expected_net_value_usd=expected.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        score_usd_per_minute=score.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
    )


def rank_opportunities(items: Sequence[ScoredOpportunity]) -> list[ScoredOpportunity]:
    return sorted(
        items,
        key=lambda x: (
            -x.result.score_usd_per_minute,
            -x.result.expected_net_value_usd,
            x.opportunity.source,
            x.opportunity.id,
        ),
    )
