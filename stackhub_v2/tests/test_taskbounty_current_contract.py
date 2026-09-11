from __future__ import annotations

from decimal import Decimal

import httpx
import pytest

from stackhub.adapters.taskbounty import TaskBountyAdapter
from stackhub.config import SourceConfig


def _config() -> SourceConfig:
    return SourceConfig(
        enabled=True,
        base_url="https://www.task-bounty.com/api/v1",
        agent_native=True,
        read_only=False,
        request_timeout_seconds=20,
        min_poll_interval_seconds=60,
    )


@pytest.mark.asyncio
async def test_discovery_uses_current_tasks_endpoint_and_open_state():
    seen: list[tuple[str, str, str | None, str | None]] = []

    async def handler(request: httpx.Request):
        seen.append((
            request.method,
            request.url.path,
            request.url.params.get("state"),
            request.url.params.get("limit"),
        ))
        assert request.method == "GET"
        assert request.url.path == "/api/v1/tasks"
        return httpx.Response(
            200,
            json={
                "tasks": [
                    {
                        "id": "tb_live_1",
                        "title": "Fix pagination regression",
                        "bounty_cents": 5000,
                        "github_repo_url": "https://github.com/example/project",
                        "github_issue_url": "https://github.com/example/project/issues/42",
                        "complexity_tag": "small",
                        "language": "python",
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TaskBountyAdapter(_config(), client=client, api_key="tb_live_placeholder")
    try:
        items = await adapter.discover(limit=25)
    finally:
        await client.aclose()

    assert seen == [("GET", "/api/v1/tasks", "open", "25")]
    assert len(items) == 1
    assert items[0].id == "tb_live_1"
    assert items[0].reward.amount == Decimal("40.00")
    assert items[0].competition_model == "best_submission"
