import inspect
from pathlib import Path

import httpx
import pytest

from stackhub.config import SourceConfig, load_runtime_config
from stackhub.worker_state import WorkerState


def source_config(base_url: str) -> SourceConfig:
    return SourceConfig(
        enabled=True,
        base_url=base_url,
        agent_native=True,
        read_only=False,
        request_timeout_seconds=20,
        min_poll_interval_seconds=60,
    )


@pytest.mark.asyncio
async def test_taskforce_already_applied_is_idempotent_pending_award():
    from stackhub.adapters.taskforce import TaskForceAdapter

    async def handler(request: httpx.Request):
        assert request.method == "POST"
        assert request.url.path == "/api/agent/tasks/tf-existing/apply"
        return httpx.Response(409, json={"error": "Already applied"}, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TaskForceAdapter(source_config("https://www.task-force.app"), api_key="apv_test_placeholder", client=client)
    receipt = await adapter.request_award("tf-existing", "ready")
    await client.aclose()

    assert receipt.status == "PENDING"
    assert receipt.external_reference == "existing:tf-existing"


@pytest.mark.asyncio
async def test_taskforce_known_permanent_rejection_has_stable_error_code():
    from stackhub.adapters.taskforce import TaskForceAdapter, TaskForceProtocolError

    async def handler(request: httpx.Request):
        return httpx.Response(400, json={"error": "Cannot apply to your own task"}, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TaskForceAdapter(source_config("https://www.task-force.app"), api_key="apv_test_placeholder", client=client)
    with pytest.raises(TaskForceProtocolError) as excinfo:
        await adapter.request_award("tf-own", "ready")
    await client.aclose()

    assert excinfo.value.status_code == 400
    assert excinfo.value.error_code == "cannot_apply_to_own_task"


def test_permanent_http_failures_do_not_loop_forever():
    from stackhub.orchestrator import _classify_failure_state

    for status in (400, 401, 403, 404, 409, 410, 422):
        assert _classify_failure_state(status_code=status, error_code=f"http_{status}") == WorkerState.FAILED_PERMANENT


def test_transient_http_failures_remain_retryable():
    from stackhub.orchestrator import _classify_failure_state

    for status in (408, 425, 429, 500, 502, 503, 504):
        assert _classify_failure_state(status_code=status, error_code=f"http_{status}") == WorkerState.FAILED_RETRYABLE
    assert _classify_failure_state(status_code=None, error_code="protocol_error") == WorkerState.FAILED_RETRYABLE


def test_scout_default_requests_max_supported_inventory():
    from stackhub.scout import Scout

    assert inspect.signature(Scout.run_once).parameters["limit"].default == 100


def test_live_runtime_uses_bounded_global_concurrency_four():
    config_path = Path(__file__).resolve().parents[1] / "config" / "sources.live.example.yaml"
    cfg = load_runtime_config(config_path)
    assert cfg.max_concurrent_tasks == 4
    assert cfg.max_active_claims == 4
