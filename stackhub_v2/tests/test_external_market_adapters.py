from decimal import Decimal

import httpx
import pytest

from stackhub.config import SourceConfig


def source_config(base_url: str) -> SourceConfig:
    return SourceConfig(
        enabled=True,
        base_url=base_url,
        agent_native=True,
        read_only=True,
        request_timeout_seconds=20,
        min_poll_interval_seconds=60,
    )


@pytest.mark.asyncio
async def test_moltjobs_discovery_normalizes_open_jobs_and_uses_bearer_auth():
    from stackhub.adapters.moltjobs import MoltJobsAdapter

    seen = []

    async def handler(request: httpx.Request):
        seen.append((request.method, request.url.path, request.headers.get("Authorization")))
        assert request.url.params["status"] == "OPEN"
        assert request.url.params["limit"] == "25"
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": "mj-1",
                        "title": "Clean product catalog",
                        "vertical": "DATA",
                        "budgetUsdc": "12.50",
                        "deadline": "2026-09-20T00:00:00Z",
                        "requirements": ["Return CSV", "No duplicates"],
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = MoltJobsAdapter(
        source_config("https://api.moltjobs.io/v1"),
        api_key="mj_test_placeholder",
        client=client,
    )
    items = await adapter.discover(limit=25)
    await client.aclose()

    assert seen == [("GET", "/v1/jobs", "Bearer mj_test_placeholder")]
    assert len(items) == 1
    item = items[0]
    assert item.id == "mj-1"
    assert item.source == "moltjobs"
    assert item.reward.amount == Decimal("12.50")
    assert item.reward.asset == "USDC"
    assert item.reward.network == "Base"
    assert item.agent_allowed is True
    assert item.category == "data"
    assert item.competition_model == "bid"


@pytest.mark.asyncio
async def test_taskforce_discovery_normalizes_active_tasks_and_uses_api_key():
    from stackhub.adapters.taskforce import TaskForceAdapter

    seen = []

    async def handler(request: httpx.Request):
        seen.append((request.method, request.url.path, request.headers.get("X-API-Key")))
        assert request.url.params["status"] == "ACTIVE"
        assert request.url.params["limit"] == "30"
        return httpx.Response(
            200,
            json={
                "tasks": [
                    {
                        "id": "tf-1",
                        "title": "Research public datasets",
                        "category": "research",
                        "totalBudget": 40,
                        "requirements": "Return a sourced CSV and short summary",
                        "deadline": "2026-09-22T12:00:00Z",
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TaskForceAdapter(
        source_config("https://task-force.app"),
        api_key="apv_test_placeholder",
        client=client,
    )
    items = await adapter.discover(limit=30)
    await client.aclose()

    assert seen == [("GET", "/api/agent/tasks", "apv_test_placeholder")]
    assert len(items) == 1
    item = items[0]
    assert item.id == "tf-1"
    assert item.source == "taskforce"
    assert item.reward.amount == Decimal("40")
    assert item.reward.asset == "USDC"
    assert item.reward.network == "Solana"
    assert item.agent_allowed is True
    assert item.category == "research"
    assert item.competition_model == "application"
