from __future__ import annotations

from math import inf
from typing import Iterable

from .models import Opportunity


def score_opportunity(item: Opportunity) -> float:
    if item.requires_deposit:
        return -inf
    minutes = max(float(item.estimated_minutes), 1.0)
    probability = min(max(float(item.approval_probability), 0.0), 1.0)
    base = max(float(item.expected_reward_usd), 0.0) * probability / minutes
    if item.payout_threshold_usd > 0:
        remaining = max(item.payout_threshold_usd - item.current_balance_usd, 0.0)
        threshold_penalty = 1.0 / (1.0 + remaining / max(item.payout_threshold_usd, 1.0))
        base *= threshold_penalty
    return base


def rank_opportunities(items: Iterable[Opportunity]) -> list[Opportunity]:
    eligible = [item for item in items if score_opportunity(item) != -inf]
    return sorted(
        eligible,
        key=lambda item: (-score_opportunity(item), item.source.lower(), item.title.lower()),
    )
