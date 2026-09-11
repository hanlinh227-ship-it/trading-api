from decimal import Decimal

import pytest
from pydantic import ValidationError

from stackhub.config import RuntimeConfig, SourceConfig, WorkerPoolConfig


def base_source(**updates):
    data = dict(
        enabled=True,
        base_url="https://www.task-bounty.com/api/v1",
        agent_native=True,
        read_only=True,
        request_timeout_seconds=20,
        min_poll_interval_seconds=60,
    )
    data.update(updates)
    return SourceConfig(**data)


def test_pool_defaults_match_approved_design():
    pools = WorkerPoolConfig()
    assert pools.scouts == 3
    assert pools.code_fix == 2
    assert pools.research_data == 2
    assert pools.service == 2
    assert pools.verification == 2
    assert pools.submission == 1


def test_active_claim_limit_accepts_four():
    config = RuntimeConfig(
        dry_run=True,
        worker_enabled=False,
        external_spend_limit_usd=Decimal("0"),
        scan_interval_seconds=300,
        max_concurrent_tasks=4,
        max_active_claims=4,
        sources={"taskbounty": base_source()},
    )
    assert config.max_active_claims == 4


def test_active_claim_limit_is_capped_at_four():
    with pytest.raises(ValidationError):
        RuntimeConfig(
            dry_run=True,
            worker_enabled=False,
            external_spend_limit_usd=Decimal("0"),
            scan_interval_seconds=300,
            max_concurrent_tasks=5,
            max_active_claims=5,
            sources={"taskbounty": base_source()},
        )


def test_worker_pool_ceilings_are_hard_bounds():
    with pytest.raises(ValidationError):
        WorkerPoolConfig(scouts=4)
    with pytest.raises(ValidationError):
        WorkerPoolConfig(submission=2)
