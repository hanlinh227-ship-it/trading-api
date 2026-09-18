from decimal import Decimal

import httpx
import pytest

from stackhub.adapters.taskbounty import TaskBountyAdapter, TaskBountyProtocolError
from stackhub.config import SourceConfig


def source_config():
    return SourceConfig(enabled=True, base_url="https://www.task-bounty.com/api/v1", agent_native=True, read_only=True, request_timeout_seconds=20, min_poll_interval_seconds=60)


def task_payload():
    return {
        "id": "tb-123",
        "title": "Fix regression",
        "bounty_cents": 5000,
        "github_repo_url": "https://github.com/acme/repo",
        "github_issue_url": "https://github.com/acme/repo/issues/7",
        "complexity_tag": "small",
        "language": "python",
    }


@pytest.mark.asyncio
async def test_fetch_open_uses_current_tasks_endpoint_without_auth_when_public():
    task = task_payload()
    seen = []

    async def handler(request: httpx.Request):
        seen.append((request.method, request.url.path, request.url.params.get("state"), request.url.params.get("limit"), request.headers.get("Authorization")))
        assert request.method == "GET"
        assert request.url.path == "/api/v1/tasks"
        return httpx.Response(200, json={"tasks": [task]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TaskBountyAdapter(source_config(), client=client)
    items = await adapter.fetch_open(limit=20)
    await client.aclose()

    assert seen == [("GET", "/api/v1/tasks", "open", "20", None)]
    assert len(items) == 1
    item = items[0]
    assert item.id == task["id"]
    assert item.agent_allowed is True
    assert item.reward.amount == Decimal("40.00")
    assert item.reward.asset == "USD"
    assert item.competition_model == "best_submission"
    assert item.estimated_effort_minutes == 30
    assert f"Issue: {task['github_issue_url']}" in item.requirements


@pytest.mark.asyncio
async def test_empty_current_tasks_response_is_healthy_and_returns_no_opportunities():
    seen = []

    async def handler(request: httpx.Request):
        seen.append((request.method, request.url.path))
        return httpx.Response(200, json={"tasks": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TaskBountyAdapter(source_config(), client=client)
    items = await adapter.fetch_open(limit=5)
    await client.aclose()

    assert items == []
    assert seen == [("GET", "/api/v1/tasks")]


@pytest.mark.asyncio
async def test_optional_api_key_is_sent_when_configured_but_not_required_for_discovery():
    seen = []

    async def handler(request: httpx.Request):
        seen.append((request.method, request.url.path, request.headers.get("Authorization")))
        return httpx.Response(200, json={"tasks": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TaskBountyAdapter(source_config(), client=client, api_key="tb_live_SECRETSECRETSECRET")
    assert await adapter.fetch_open(limit=5) == []
    await client.aclose()
    assert seen == [("GET", "/api/v1/tasks", "Bearer tb_live_SECRETSECRETSECRET")]


@pytest.mark.asyncio
async def test_malformed_task_is_rejected_as_protocol_error():
    async def handler(request: httpx.Request):
        return httpx.Response(200, json={"tasks": [{"title": "missing id"}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TaskBountyAdapter(source_config(), client=client)
    with pytest.raises(TaskBountyProtocolError) as caught:
        await adapter.fetch_open()
    await client.aclose()
    assert caught.value.error_code == "validation_error"


@pytest.mark.asyncio
async def test_rate_limit_parses_retry_after_header():
    async def handler(request: httpx.Request):
        assert request.url.path == "/api/v1/tasks"
        return httpx.Response(429, headers={"Retry-After": "600"}, json={"error": "rate_limited"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TaskBountyAdapter(source_config(), client=client)
    with pytest.raises(TaskBountyProtocolError) as caught:
        await adapter.fetch_open()
    await client.aclose()
    assert caught.value.status_code == 429
    assert caught.value.error_code == "rate_limited"
    assert caught.value.retry_after_seconds == 600
