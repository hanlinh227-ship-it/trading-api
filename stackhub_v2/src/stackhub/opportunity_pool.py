from __future__ import annotations

from decimal import Decimal

from .policy import evaluate_opportunity
from .scoring import ScoreInputs, score_opportunity


class RepositoryOpportunityPool:
    """Policy-gated shared pool backed by StackHubRepository."""

    def __init__(self, config, repository):
        self.config = config
        self.repository = repository

    def ingest(self, opportunity) -> None:
        decision = evaluate_opportunity(opportunity, self.config)
        score = None
        if decision.allowed:
            score = score_opportunity(
                opportunity,
                ScoreInputs(
                    payout_value_usd=(
                        opportunity.reward.amount
                        if opportunity.reward.asset.upper() in {"USD", "USDC"}
                        else Decimal("0")
                    ),
                    win_probability=Decimal("0.35"),
                    verification_probability=Decimal("0.75"),
                    model_cost_usd=Decimal("0"),
                    compute_cost_usd=Decimal("0"),
                    chain_fee_usd=Decimal("0"),
                    expected_failed_work_cost_usd=Decimal("0"),
                ),
            )
        self.repository.upsert_opportunity(opportunity, decision, score)

    def record_source_health(
        self,
        source,
        ok,
        status_code,
        error_code,
        observed_at,
    ) -> None:
        self.repository.record_source_health(
            source,
            ok,
            status_code,
            error_code,
            observed_at,
        )
