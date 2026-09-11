from decimal import Decimal
import pytest
from pydantic import ValidationError
from stackhub.models import Opportunity, Reward


def test_opportunity_accepts_unknown_agent_permission():
    item = Opportunity(
        id="tb-1",
        source="taskbounty",
        url="https://www.task-bounty.com/tasks/tb-1",
        category="coding",
        reward=Reward(amount=Decimal("25"), asset="USDC", network="solana"),
        deadline=None,
        requirements=("Fix failing test",),
        acceptance_criteria=("CI passes",),
        competition_model="first_pass",
        agent_allowed=None,
        estimated_effort_minutes=30,
    )
    assert item.agent_allowed is None


def test_reward_rejects_negative_amount():
    with pytest.raises(ValidationError):
        Reward(amount=Decimal("-0.01"), asset="USDC", network="solana")
