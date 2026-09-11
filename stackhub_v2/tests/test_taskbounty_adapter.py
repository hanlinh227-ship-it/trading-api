import json
from decimal import Decimal
from pathlib import Path
import httpx
import pytest

from stackhub.adapters.taskbounty import TaskBountyAdapter, TaskBountyProtocolError
from stackhub.config import SourceConfig


def source_config():
    return SourceConfig(enabled=True, base_url="https://www.task-bounty.com/api/v1", agent_native=True, read_only=True, request_timeout_seconds=20, min_poll_interval_seconds=60)


@pytest.mark.asyncio
async def test_fetch_open_normalizes_public_task_payload():
    payload = json.loads((Path(__file__).parent / "fixtures/taskbounty_open.json").read_text())
    async def handler(request: httpx.Request):
        assert request.method == "GET"
        assert request.url.path == "/api/v1/tasks"
        assert request.url.params["state"] == "open"
        return httpx.Response(200, json=payload)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TaskBountyAdapter(source_config(), client=client)
    items = await adapter.fetch_open(limit=20)
    await client.aclose()
    assert len(items) == 1
    item = items[0]
    assert item.id.startswith("f6c0")
    assert item.agent_allowed is True
    assert item.reward.amount == Decimal("40.00")
    assert item.reward.asset == "USD"
    assert item.competition_model == "best_submission"
    assert item.estimated_effort_minutes == 30


@pytest.mark.asyncio
async def test_adapter_does_not_call_mutating_endpoints():
    seen = []
    async def handler(request: httpx.Request):
        seen.append((request.method, request.url.path))
        return httpx.Response(200, json={"tasks": []})
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TaskBountyAdapter(source_config(), client=client)
    await adapter.fetch_open(limit=5)
    await client.aclose()
    assert seen == [("GET", "/api/v1/tasks")]


@pytest.mark.asyncio
async def test_malformed_task_is_rejected_as_protocol_error():
    payload = json.loads((Path(__file__).parent / "fixtures/taskbounty_malformed.json").read_text())
    async def handler(request: httpx.Request):
        return httpx.Response(200, json=payload)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TaskBountyAdapter(source_config(), client=client)
    with pytest.raises(TaskBountyProtocolError):
        await adapter.fetch_open()
    await client.aclose()
