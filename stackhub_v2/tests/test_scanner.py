from decimal import Decimal
import asyncio
import pytest

from stackhub.config import RuntimeConfig, SourceConfig
from stackhub.models import Opportunity, Reward
from stackhub.repository import StackHubRepository
from stackhub.scanner import Scanner
from stackhub.adapters.taskbounty import TaskBountyProtocolError


def config():
    return RuntimeConfig(
        dry_run=True, external_spend_limit_usd=Decimal("0"), scan_interval_seconds=300, max_concurrent_tasks=1,
        sources={"taskbounty": SourceConfig(enabled=True, base_url="https://www.task-bounty.com/api/v1", agent_native=True, read_only=True, request_timeout_seconds=20, min_poll_interval_seconds=60)},
    )


def opportunity():
    return Opportunity(
        id="tb-1", source="taskbounty", url="https://github.com/acme/repo/issues/1", category="coding",
        reward=Reward(amount=Decimal("40"), asset="USD", network=None), deadline=None,
        requirements=("Fix bug",), acceptance_criteria=("Pass verification",), competition_model="best_submission",
        agent_allowed=True, estimated_effort_minutes=30,
    )


class FakeAdapter:
    async def fetch_open(self, limit=50):
        return [opportunity()]


class FailingAdapter:
    async def fetch_open(self, limit=50):
        raise TaskBountyProtocolError("rate limited", status_code=429, error_code="rate_limited")


class RateLimitedAdapter:
    async def fetch_open(self, limit=50):
        raise TaskBountyProtocolError(
            "rate limited", status_code=429, error_code="rate_limited", retry_after_seconds=600
        )


class OutageAdapter:
    async def fetch_open(self, limit=50):
        raise TaskBountyProtocolError("unavailable", status_code=503, error_code="http_503")


@pytest.mark.asyncio
async def test_run_once_persists_ranked_read_only_opportunity(tmp_path):
    repo = StackHubRepository(tmp_path / "db.sqlite"); repo.initialize()
    result = await Scanner(config(), repo, {"taskbounty": FakeAdapter()}).run_once()
    rows = repo.list_ranked_opportunities()
    assert result.discovered == 1
    assert result.allowed == 1
    assert len(rows) == 1
    assert Decimal(rows[0]["expected_net_value_usd"]) > 0
    assert repo.conn.execute("select count(*) from claims").fetchone()[0] == 0
    assert repo.conn.execute("select count(*) from submissions").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_rate_limit_records_source_health_without_raising(tmp_path):
    repo = StackHubRepository(tmp_path / "db.sqlite"); repo.initialize()
    result = await Scanner(config(), repo, {"taskbounty": FailingAdapter()}).run_once()
    health = repo.get_source_health("taskbounty")
    assert result.errors == 1
    assert health["ok"] is False
    assert health["status_code"] == 429
    assert health["error_code"] == "rate_limited"


@pytest.mark.asyncio
async def test_run_forever_honors_retry_after(tmp_path):
    repo = StackHubRepository(tmp_path / "db.sqlite"); repo.initialize()
    stop = asyncio.Event()
    sleeps = []

    async def sleeper(seconds):
        sleeps.append(seconds)
        stop.set()

    scanner = Scanner(config(), repo, {"taskbounty": RateLimitedAdapter()}, sleeper=sleeper)
    await scanner.run_forever(stop)
    assert sleeps == [600]


@pytest.mark.asyncio
async def test_run_forever_uses_capped_exponential_outage_backoff(tmp_path):
    repo = StackHubRepository(tmp_path / "db.sqlite"); repo.initialize()
    stop = asyncio.Event()
    sleeps = []

    async def sleeper(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 5:
            stop.set()

    scanner = Scanner(config(), repo, {"taskbounty": OutageAdapter()}, sleeper=sleeper)
    await scanner.run_forever(stop)
    assert sleeps == [60, 120, 240, 480, 900]
