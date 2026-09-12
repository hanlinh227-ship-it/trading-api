from decimal import Decimal

from stackhub.models import Opportunity, Reward
from stackhub.opportunity_pool import RepositoryOpportunityPool


class Repo:
    def __init__(self):
        self.saved = None

    def upsert_opportunity(self, opportunity, decision, score):
        self.saved = (opportunity, decision, score)


class Source:
    enabled = True
    agent_native = True


class Config:
    external_spend_limit_usd = Decimal("0")
    sources = {"taskforce": Source()}


def test_usdc_reward_is_scored_as_usd_stable_value():
    repo = Repo()
    item = Opportunity(
        id="one",
        source="taskforce",
        url="https://example.com/one",
        category="development",
        reward=Reward(amount=Decimal("10"), asset="USDC", network="Solana"),
        requirements=("Write a short technical answer",),
        acceptance_criteria=(),
        competition_model="application",
        agent_allowed=True,
        estimated_effort_minutes=10,
    )
    RepositoryOpportunityPool(Config(), repo).ingest(item)
    assert repo.saved is not None
    score = repo.saved[2]
    assert score is not None
    assert score.expected_net_value_usd == Decimal("2.63")
    assert score.score_usd_per_minute == Decimal("0.2625")
