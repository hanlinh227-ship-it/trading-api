import httpx
import pytest

from stackhub.adapters.taskbounty import TaskBountyAdapter, TaskBountyProtocolError
from stackhub.config import SourceConfig


def source_config(*, read_only: bool = False):
    return SourceConfig(
        enabled=True,
        base_url="https://www.task-bounty.com/api/v1",
        agent_native=True,
        read_only=read_only,
        request_timeout_seconds=20,
        min_poll_interval_seconds=60,
    )


@pytest.mark.asyncio
async def test_access_task_posts_to_documented_endpoint_and_parses_clone_url():
    seen = []

    async def handler(request: httpx.Request):
        seen.append((request.method, request.url.path, request.headers.get("Authorization")))
        assert request.method == "POST"
        assert request.url.path == "/api/v1/tasks/tb-123/access"
        return httpx.Response(200, json={"clone_url": "https://example.invalid/clone", "expires_at": "2026-09-11T21:00:00Z"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TaskBountyAdapter(source_config(), client=client, api_key="tb_live_SECRET")
    result = await adapter.access_task("tb-123")
    await client.aclose()

    assert result.task_id == "tb-123"
    assert result.clone_url == "https://example.invalid/clone"
    assert result.expires_at == "2026-09-11T21:00:00Z"
    assert seen == [("POST", "/api/v1/tasks/tb-123/access", "Bearer tb_live_SECRET")]


@pytest.mark.asyncio
async def test_submit_pr_posts_task_and_external_link():
    async def handler(request: httpx.Request):
        assert request.method == "POST"
        assert request.url.path == "/api/v1/submissions"
        assert request.headers.get("Authorization") == "Bearer tb_live_SECRET"
        payload = __import__("json").loads(request.content)
        assert payload == {
            "task_id": "tb-123",
            "external_link": "https://github.com/acme/repo/pull/7",
        }
        return httpx.Response(
            200,
            json={
                "id": "sub-1",
                "task_id": "tb-123",
                "status": "verifying",
                "external_link": "https://github.com/acme/repo/pull/7",
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TaskBountyAdapter(source_config(), client=client, api_key="tb_live_SECRET")
    result = await adapter.submit_pr("tb-123", "https://github.com/acme/repo/pull/7")
    await client.aclose()

    assert result.id == "sub-1"
    assert result.task_id == "tb-123"
    assert result.status == "verifying"


@pytest.mark.asyncio
async def test_mutation_requires_api_key():
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(500)))
    adapter = TaskBountyAdapter(source_config(), client=client)
    with pytest.raises(TaskBountyProtocolError) as caught:
        await adapter.access_task("tb-123")
    await client.aclose()
    assert caught.value.error_code == "auth_required"


@pytest.mark.asyncio
async def test_mutation_is_blocked_for_read_only_config():
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(500)))
    adapter = TaskBountyAdapter(source_config(read_only=True), client=client, api_key="tb_live_SECRET")
    with pytest.raises(TaskBountyProtocolError) as caught:
        await adapter.submit_pr("tb-123", "https://github.com/acme/repo/pull/7")
    await client.aclose()
    assert caught.value.error_code == "mutation_disabled"


@pytest.mark.asyncio
async def test_http_error_never_leaks_api_key():
    async def handler(request: httpx.Request):
        return httpx.Response(401, json={"error": "invalid"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TaskBountyAdapter(source_config(), client=client, api_key="tb_live_SUPERSECRET")
    with pytest.raises(TaskBountyProtocolError) as caught:
        await adapter.access_task("tb-123")
    await client.aclose()

    assert caught.value.error_code == "auth_invalid"
    assert "tb_live_SUPERSECRET" not in str(caught.value)
