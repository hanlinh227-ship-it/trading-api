import httpx
import pytest

from stackhub.adapters.taskforce import TaskForceAdapter, TaskForceProtocolError
from stackhub.config import SourceConfig


def _config():
    return SourceConfig(
        enabled=True,
        base_url="https://task-force.app",
        agent_native=True,
        read_only=False,
        request_timeout_seconds=20,
        min_poll_interval_seconds=60,
        capabilities={
            "source_class": "job",
            "agent_allowed": True,
            "auto_discovery": True,
            "auto_claim": True,
            "auto_execute": True,
            "auto_submit": True,
            "auto_publish": False,
            "auto_payout_observation": True,
            "requires_human_onboarding": True,
            "requires_kyc": False,
            "requires_tax_setup": False,
            "requires_manual_review": False,
            "external_spend_required": False,
            "mutation_verified_at": "2026-09-11T17:30:00+00:00",
            "terms_verified_at": "2026-09-11T17:30:00+00:00",
            "rate_limit_policy": "test",
        },
    )


@pytest.mark.asyncio
async def test_taskforce_http_error_preserves_safe_platform_code_and_message():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"error": "Already applied", "code": "ALREADY_APPLIED"}, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TaskForceAdapter(_config(), api_key="test-key", client=client)
    with pytest.raises(TaskForceProtocolError) as caught:
        await adapter.request_award("task-1", "ready")
    exc = caught.value
    assert exc.status_code == 409
    assert exc.error_code == "ALREADY_APPLIED"
    assert "Already applied" in str(exc)
    assert "test-key" not in str(exc)
    await client.aclose()
