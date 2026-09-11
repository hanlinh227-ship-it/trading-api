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
async def test_fetch_open_uses_public_json_feed_then_normalizes_task_detail_without_auth():
    old_payload = json.loads((Path(__file__).parent / "fixtures/taskbounty_open.json").read_text())
    task = old_payload["tasks"][0]
    feed = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": "TaskBounty open bounties",
        "items": [
            {
                "id": task["id"],
                "url": task["github_issue_url"],
                "title": task["title"],
                "content_text": "Funded coding bounty",
            }
        ],
    }
    seen = []

    async def handler(request: httpx.Request):
        seen.append((request.method, request.url.path, request.headers.get("Authorization")))
        assert request.method == "GET"
        if request.url.path == "/api/v1/bounties.json":
            assert request.url.params["limit"] == "20"
            assert "state" not in request.url.params
            return httpx.Response(200, json=feed, headers={"Content-Type": "application/feed+json"})
        if request.url.path == f"/api/v1/tasks/{task['id']}":
            return httpx.Response(200, json=task)
        raise AssertionError(f"unexpected request: {request.url}")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TaskBountyAdapter(source_config(), client=client)
    items = await adapter.fetch_open(limit=20)
    await client.aclose()

    assert seen == [
        ("GET", "/api/v1/bounties.json", None),
        ("GET", f"/api/v1/tasks/{task['id']}", None),
    ]
    assert len(items) == 1
    item = items[0]
    assert item.id == task["id"]
    assert item.agent_allowed is True
    assert item.reward.amount == Decimal("40.00")
    assert item.reward.asset == "USD"
    assert item.competition_model == "best_submission"
    assert item.estimated_effort_minutes == 30


@pytest.mark.asyncio
async def test_empty_public_json_feed_is_healthy_and_returns_no_opportunities():
    seen = []

    async def handler(request: httpx.Request):
        seen.append((request.method, request.url.path, request.headers.get("Authorization")))
        return httpx.Response(
            200,
            json={
                "version": "https://jsonfeed.org/version/1.1",
                "title": "TaskBounty open bounties",
                "items": [],
            },
            headers={"Content-Type": "application/feed+json"},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TaskBountyAdapter(source_config(), client=client)
    items = await adapter.fetch_open(limit=5)
    await client.aclose()

    assert items == []
    assert seen == [("GET", "/api/v1/bounties.json", None)]


@pytest.mark.asyncio
async def test_optional_api_key_is_sent_when_configured_but_not_required_for_discovery():
    seen = []

    async def handler(request: httpx.Request):
        seen.append((request.method, request.url.path, request.headers.get("Authorization")))
        return httpx.Response(200, json={"version": "https://jsonfeed.org/version/1.1", "items": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TaskBountyAdapter(source_config(), client=client, api_key="tb_live_SECRETSECRETSECRET")
    assert await adapter.fetch_open(limit=5) == []
    await client.aclose()
    assert seen == [("GET", "/api/v1/bounties.json", "Bearer tb_live_SECRETSECRETSECRET")]


@pytest.mark.asyncio
async def test_malformed_feed_item_is_rejected_as_protocol_error():
    async def handler(request: httpx.Request):
        return httpx.Response(200, json={"version": "https://jsonfeed.org/version/1.1", "items": [{"title": "missing id"}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TaskBountyAdapter(source_config(), client=client)
    with pytest.raises(TaskBountyProtocolError) as caught:
        await adapter.fetch_open()
    await client.aclose()
    assert caught.value.error_code in {"validation_error", "protocol_error"}


@pytest.mark.asyncio
async def test_rate_limit_parses_retry_after_header():
    async def handler(request: httpx.Request):
        assert request.url.path == "/api/v1/bounties.json"
        return httpx.Response(429, headers={"Retry-After": "600"}, json={"error": "rate_limited"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TaskBountyAdapter(source_config(), client=client)
    with pytest.raises(TaskBountyProtocolError) as caught:
        await adapter.fetch_open()
    await client.aclose()
    assert caught.value.status_code == 429
    assert caught.value.error_code == "rate_limited"
    assert caught.value.retry_after_seconds == 600
