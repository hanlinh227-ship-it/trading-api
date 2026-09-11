from decimal import Decimal
from pathlib import Path
import textwrap
import pytest
from pydantic import ValidationError

from stackhub.models import Opportunity, Reward
from stackhub.config import load_runtime_config


def test_opportunity_accepts_unknown_agent_permission():
    item = Opportunity(
        id="tb-1",
        source="taskbounty",
        url="https://www.task-bounty.com/task/tb-1",
        category="coding",
        reward=Reward(amount=Decimal("25"), asset="USD", network=None),
        deadline=None,
        requirements=("Fix failing test",),
        acceptance_criteria=("CI passes",),
        competition_model="best_submission",
        agent_allowed=None,
        estimated_effort_minutes=30,
    )
    assert item.agent_allowed is None


def test_reward_rejects_negative_amount():
    with pytest.raises(ValidationError):
        Reward(amount=Decimal("-0.01"), asset="USDC", network="base")


def _write_config(path: Path, *, dry_run="true", spend="0", read_only="true", base_url="https://www.task-bounty.com/api/v1"):
    path.write_text(textwrap.dedent(f"""
    runtime:
      dry_run: {dry_run}
      external_spend_limit_usd: "{spend}"
      scan_interval_seconds: 300
      max_concurrent_tasks: 1
    sources:
      taskbounty:
        enabled: true
        base_url: "{base_url}"
        agent_native: true
        read_only: {read_only}
        request_timeout_seconds: 20
        min_poll_interval_seconds: 60
    """), encoding="utf-8")


@pytest.mark.parametrize("kwargs", [
    {"dry_run": "false"},
    {"spend": "0.01"},
    {"read_only": "false"},
    {"base_url": "https://task-bounty.example.com/api/v1"},
])
def test_config_rejects_unsafe_values(tmp_path, kwargs):
    path = tmp_path / "sources.yaml"
    _write_config(path, **kwargs)
    with pytest.raises(ValueError):
        load_runtime_config(path)
