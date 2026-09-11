from decimal import Decimal
from stackhub.models import Opportunity, Reward
from stackhub.scoring import ScoreInputs, ScoredOpportunity, score_opportunity, rank_opportunities


def opp(id: str, minutes: int = 20):
    return Opportunity(
        id=id, source="taskbounty", url=f"https://www.task-bounty.com/task/{id}", category="coding",
        reward=Reward(amount=Decimal("20"), asset="USD", network=None), deadline=None,
        requirements=(), acceptance_criteria=(), competition_model="best_submission",
        agent_allowed=True, estimated_effort_minutes=minutes,
    )


def test_score_formula():
    result = score_opportunity(opp("a"), ScoreInputs(
        payout_value_usd=Decimal("20"), win_probability=Decimal("0.5"), verification_probability=Decimal("0.8"),
        model_cost_usd=Decimal("0"), compute_cost_usd=Decimal("0"), chain_fee_usd=Decimal("0"),
        expected_failed_work_cost_usd=Decimal("0"),
    ))
    assert result.expected_net_value_usd == Decimal("8.00")
    assert result.score_usd_per_minute == Decimal("0.4000")


def test_negative_expected_value_is_preserved():
    result = score_opportunity(opp("a"), ScoreInputs(
        payout_value_usd=Decimal("1"), win_probability=Decimal("1"), verification_probability=Decimal("1"),
        model_cost_usd=Decimal("2"), compute_cost_usd=Decimal("0"), chain_fee_usd=Decimal("0"),
        expected_failed_work_cost_usd=Decimal("0"),
    ))
    assert result.expected_net_value_usd == Decimal("-1")


def test_rank_is_deterministic():
    same = ScoreInputs(
        payout_value_usd=Decimal("10"), win_probability=Decimal("1"), verification_probability=Decimal("1"),
        model_cost_usd=Decimal("0"), compute_cost_usd=Decimal("0"), chain_fee_usd=Decimal("0"), expected_failed_work_cost_usd=Decimal("0"),
    )
    b, a = opp("b", 10), opp("a", 10)
    ranked = rank_opportunities([
        ScoredOpportunity(opportunity=b, result=score_opportunity(b, same)),
        ScoredOpportunity(opportunity=a, result=score_opportunity(a, same)),
    ])
    assert [x.opportunity.id for x in ranked] == ["a", "b"]
