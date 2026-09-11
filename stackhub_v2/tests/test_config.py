from pathlib import Path
from decimal import Decimal
import pytest
from pydantic import ValidationError

from stackhub.config import RuntimeConfig, SourceConfig, load_runtime_config


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


def test_load_runtime_config_accepts_locked_read_only_file():
    path = Path(__file__).parents[1] / "config" / "sources.yaml"
    config = load_runtime_config(path)
    assert config.dry_run is True
    assert config.external_spend_limit_usd == Decimal("0")
    assert config.sources["taskbounty"].read_only is True


@pytest.mark.parametrize(
    "updates",
    [
        {"dry_run": False},
        {"external_spend_limit_usd": Decimal("0.01")},
    ],
)
def test_runtime_rejects_non_readonly_runtime_settings(updates):
    data = dict(
        dry_run=True,
        external_spend_limit_usd=Decimal("0"),
        scan_interval_seconds=300,
        max_concurrent_tasks=1,
        sources={"taskbounty": base_source()},
    )
    data.update(updates)
    with pytest.raises(ValidationError):
        RuntimeConfig(**data)


def test_runtime_rejects_non_readonly_taskbounty():
    with pytest.raises(ValidationError):
        RuntimeConfig(
            dry_run=True,
            external_spend_limit_usd=Decimal("0"),
            scan_interval_seconds=300,
            max_concurrent_tasks=1,
            sources={"taskbounty": base_source(read_only=False)},
        )


def test_runtime_rejects_lookalike_taskbounty_hostname():
    with pytest.raises(ValidationError):
        RuntimeConfig(
            dry_run=True,
            external_spend_limit_usd=Decimal("0"),
            scan_interval_seconds=300,
            max_concurrent_tasks=1,
            sources={"taskbounty": base_source(base_url="https://task-bounty.example.com/api/v1")},
        )
