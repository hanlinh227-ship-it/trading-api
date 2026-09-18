from types import SimpleNamespace

from stackhub.adapter_registry import build_adapters
from stackhub.config import SourceConfig


def cfg(base_url: str) -> SourceConfig:
    return SourceConfig(
        enabled=True,
        base_url=base_url,
        agent_native=True,
        read_only=True,
        request_timeout_seconds=20,
        min_poll_interval_seconds=60,
    )


def test_registry_builds_all_verified_read_only_job_sources():
    config = SimpleNamespace(
        sources={
            "taskbounty": cfg("https://www.task-bounty.com/api/v1"),
            "moltjobs": cfg("https://api.moltjobs.io/v1"),
            "taskforce": cfg("https://task-force.app"),
        }
    )
    adapters = build_adapters(
        config,
        {
            "TASKBOUNTY_API_KEY": "tb_placeholder",
            "MOLTJOBS_API_KEY": "mj_placeholder",
            "TASKFORCE_API_KEY": "tf_placeholder",
        },
    )
    assert set(adapters) == {"taskbounty", "moltjobs", "taskforce"}
    assert adapters["moltjobs"].api_key == "mj_placeholder"
    assert adapters["taskforce"].api_key == "tf_placeholder"
