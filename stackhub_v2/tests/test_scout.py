from decimal import Decimal

import pytest

from stackhub.adapters.base import ClaimReceipt, SubmissionReceipt
from stackhub.models import Opportunity, Reward
from stackhub.scout import Scout
from stackhub.source_capabilities import SourceCapabilities


class Pool:
    def __init__(self):
        self.items = []
        self.health = []

    def ingest(self, item):
        self.items.append(item)

    def record_source_health(self, *args):
        self.health.append(args)


class Adapter:
    source_name = "alpha"
    capabilities = SourceCapabilities(agent_allowed=True, auto_discovery=True)

    def __init__(self):
        self.claim_calls = 0
        self.submit_calls = 0

    async def discover(self, limit=50):
        return [
            Opportunity(
                id="1",
                source="alpha",
                url="https://a",
                category="data",
                reward=Reward(amount=Decimal("5"), asset="USD"),
                competition_model="best",
                agent_allowed=True,
            )
        ]

    async def claim(self, *args):
        self.claim_calls += 1
        return ClaimReceipt("alpha", "1", "workspace")

    async def submit(self, *args):
        self.submit_calls += 1
        return SubmissionReceipt("alpha", "1", "reference")


@pytest.mark.asyncio
async def test_scout_is_discovery_only():
    adapter = Adapter()
    pool = Pool()

    result = await Scout(adapter, pool).run_once()

    assert result.discovered == 1
    assert len(pool.items) == 1
    assert adapter.claim_calls == 0
    assert adapter.submit_calls == 0


def test_scout_rejects_source_without_discovery_permission():
    adapter = Adapter()
    adapter.capabilities = SourceCapabilities(agent_allowed=True, auto_discovery=False)

    with pytest.raises(ValueError):
        Scout(adapter, Pool())
