from decimal import Decimal

from stackhub.models import Opportunity, Reward
from stackhub.opportunity import RevenueLane, normalize_legacy
from stackhub.revenue_scoring import RevenueMetrics, score_opportunity


def test_normalize_legacy_preserves_source_and_lane():
    old = Opportunity(
        id="1",
        source="a",
        url="https://x",
        category="coding",
        reward=Reward(amount=Decimal("50"), asset="USD"),
        competition_model="best",
        agent_allowed=True,
        estimated_effort_minutes=25,
    )
    normalized = normalize_legacy(old, title="Fix it", lane=RevenueLane.EXTERNAL_JOB)

    assert normalized.external_id == "1"
    assert normalized.source == "a"
    assert normalized.title == "Fix it"
    assert normalized.reward_usd_estimate == Decimal("50")


def test_score_ranks_expected_realized_revenue_per_minute():
    slow = normalize_legacy(
        Opportunity(
            id="a",
            source="one",
            url="https://a",
            category="coding",
            reward=Reward(amount=Decimal("100"), asset="USD"),
            competition_model="best",
            agent_allowed=True,
            estimated_effort_minutes=50,
        )
    )
    fast = normalize_legacy(
        Opportunity(
            id="b",
            source="two",
            url="https://b",
            category="coding",
            reward=Reward(amount=Decimal("40"), asset="USD"),
            competition_model="best",
            agent_allowed=True,
            estimated_effort_minutes=10,
        )
    )
    metrics = RevenueMetrics(
        success_probability=Decimal("0.5"),
        payout_probability=Decimal("1"),
        source_reliability=Decimal("1"),
        verification_probability=Decimal("1"),
    )

    assert score_opportunity(fast, metrics) > score_opportunity(slow, metrics)


def test_unpriced_or_not_agent_allowed_is_not_rankable():
    unpriced = normalize_legacy(
        Opportunity(
            id="x",
            source="x",
            url="https://x",
            category="data",
            reward=Reward(amount=Decimal("2"), asset="TOKEN"),
            competition_model="best",
            agent_allowed=True,
        )
    )
    prohibited = unpriced.model_copy(
        update={"reward_usd_estimate": Decimal("2"), "agent_allowed": False}
    )

    assert score_opportunity(unpriced, RevenueMetrics()) == Decimal("-1")
    assert score_opportunity(prohibited, RevenueMetrics()) == Decimal("-1")
