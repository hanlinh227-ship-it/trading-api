from __future__ import annotations

import httpx
import pytest

from stackhub.adapters.moltjobs import MoltJobsAdapter
from stackhub.config import SourceConfig


def _config() -> SourceConfig:
    return SourceConfig(
        enabled=True,
        base_url="https://api.moltjobs.io/v1",
        agent_native=True,
        read_only=True,
        request_timeout_seconds=20,
        min_poll_interval_seconds=60,
    )


@pytest.mark.asyncio
async def test_discovery_follows_next_cursor_until_requested_limit():
    seen_cursors: list[str | None] = []

    async def handler(request: httpx.Request):
        cursor = request.url.params.get("cursor")
        seen_cursors.append(cursor)
        if cursor is None:
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "job-1", "title": "One", "vertical": "DATA", "budgetUsdc": "2"},
                        {"id": "job-2", "title": "Two", "vertical": "DEV", "budgetUsdc": "3"},
                    ],
                    "meta": {"nextCursor": "cursor-2"},
                },
            )
        assert cursor == "cursor-2"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "job-3", "title": "Three", "vertical": "RESEARCH", "budgetUsdc": "4"},
                    {"id": "job-4", "title": "Four", "vertical": "DEV", "budgetUsdc": "5"},
                ],
                "meta": {"nextCursor": None},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = MoltJobsAdapter(_config(), api_key="mj_test_placeholder", client=client)
    try:
        items = await adapter.discover(limit=4)
    finally:
        await client.aclose()

    assert seen_cursors == [None, "cursor-2"]
    assert [item.id for item in items] == ["job-1", "job-2", "job-3", "job-4"]
