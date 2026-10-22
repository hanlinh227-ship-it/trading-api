from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from stackhub.adapters.taskforce import TaskForceAdapter
from stackhub.config import SourceConfig


def _config() -> SourceConfig:
    return SourceConfig(
        enabled=True,
        base_url="https://www.task-force.app",
        agent_native=True,
        read_only=False,
        request_timeout_seconds=20,
        min_poll_interval_seconds=60,
        auto_discovery=True,
        auto_claim=True,
        auto_execute=True,
        auto_submit=True,
        mutation_verified_at=datetime(2026, 9, 12, tzinfo=timezone.utc),
        terms_verified_at=datetime(2026, 9, 12, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_discovery_excludes_expired_or_non_applicable_tasks_even_when_api_labels_them_active():
    async def handler(request: httpx.Request):
        return httpx.Response(
            200,
            json={
                "tasks": [
                    {
                        "id": "expired-1",
                        "title": "Old probe",
                        "category": "development",
                        "totalBudget": 1,
                        "requirements": "N/A",
                        "description": "Probe for Base escrow support",
                        "deadline": "2026-02-28T04:09:52.000Z",
                        "maxWorkers": 1,
                        "currentWorkers": 0,
                        "slotsAvailable": 1,
                    },
                    {
                        "id": "full-1",
                        "title": "Already full",
                        "category": "development",
                        "totalBudget": 10,
                        "requirements": "Return tested code",
                        "deadline": "2026-09-20T12:00:00.000Z",
                        "maxWorkers": 1,
                        "currentWorkers": 1,
                    },
                    {
                        "id": "closed-1",
                        "title": "Applications closed",
                        "category": "development",
                        "totalBudget": 10,
                        "requirements": "Return tested code",
                        "deadline": "2026-09-20T12:00:00.000Z",
                        "maxWorkers": 2,
                        "currentWorkers": 0,
                        "acceptingApplications": False,
                    },
                    {
                        "id": "live-1",
                        "title": "Current coding job",
                        "category": "development",
                        "totalBudget": 25,
                        "requirements": "Return tested code",
                        "deadline": "2026-09-20T12:00:00.000Z",
                        "maxWorkers": 1,
                        "currentWorkers": 0,
                        "slotsAvailable": 1,
                        "acceptingApplications": True,
                    },
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TaskForceAdapter(_config(), api_key="apv_test_placeholder", client=client)
    try:
        items = await adapter.discover(limit=100)
    finally:
        await client.aclose()

    assert [item.id for item in items] == ["live-1"]
