from decimal import Decimal
import pytest
from stackhub.config import RuntimeConfig, SourceConfig
from stackhub.models import Opportunity, Reward


@pytest.fixture
def runtime_config():
    return RuntimeConfig(
        dry_run=True,
        external_spend_limit_usd=Decimal("0"),
        scan_interval_seconds=300,
        max_concurrent_tasks=1,
        sources={
            "taskbounty": SourceConfig(
                enabled=True,
                base_url="https://www.task-bounty.com/api/v1",
                agent_native=True,
                read_only=True,
                request_timeout_seconds=20,
                min_poll_interval_seconds=60,
            )
        },
    )


@pytest.fixture
def allowed_opportunity():
    return Opportunity(
        id="tb-allowed",
        source="taskbounty",
        url="https://www.task-bounty.com/tasks/tb-allowed",
        category="coding",
        reward=Reward(amount=Decimal("20"), asset="USDC", network="solana"),
        deadline=None,
        requirements=("Fix bug",),
        acceptance_criteria=("Tests pass",),
        competition_model="first_pass",
        agent_allowed=True,
        estimated_effort_minutes=20,
    )
