from decimal import Decimal
import pytest
from pydantic import ValidationError

from stackhub.scoring import ScoreInputs, ScoredOpportunity, rank_opportunities, score_opportunity


def make_inputs(**updates):
    data = dict(
        payout_value_usd=Decimal("20"),
        win_probability=Decimal("0.5"),
        verification_probability=Decimal("0.8"),
        model_cost_usd=Decimal("0"),
        compute_cost_usd=Decimal("0"),
        chain_fee_usd=Decimal("0"),
        expected_failed_work_cost_usd=Decimal("0"),
    )
    data.update(updates)
    return ScoreInputs(**data)


def test_score_formula(allowed_opportunity):
    result = score_opportunity(allowed_opportunity, make_inputs())
    assert result.expected_net_value_usd == Decimal("8.00")
    assert result.score_usd_per_minute == Decimal("0.4000")


def test_negative_expected_value_is_preserved(allowed_opportunity):
    result = score_opportunity(
        allowed_opportunity,
        make_inputs(model_cost_usd=Decimal("20")),
    )
    assert result.expected_net_value_usd == Decimal("-12.00")
    assert result.score_usd_per_minute == Decimal("-0.6000")


def test_probability_outside_range_is_rejected():
    with pytest.raises(ValidationError):
        make_inputs(win_probability=Decimal("1.1"))


def test_rank_is_deterministic(allowed_opportunity):
    a = allowed_opportunity.model_copy(update={"id": "a", "source": "taskbounty"})
    b = allowed_opportunity.model_copy(update={"id": "b", "source": "taskbounty"})
    result = score_opportunity(a, make_inputs())
    ranked = rank_opportunities([
        ScoredOpportunity(opportunity=b, result=result),
        ScoredOpportunity(opportunity=a, result=result),
    ])
    assert [item.opportunity.id for item in ranked] == ["a", "b"]
