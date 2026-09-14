from datetime import datetime, timedelta, timezone

import pytest

from money_ecosystem.render_gateway.worker_registry import (
    LeaseConflict,
    WorkerCapabilities,
    WorkerRegistry,
)


def _now():
    return datetime(2026, 9, 14, 13, 0, tzinfo=timezone.utc)


def _caps(worker_id="win1650-01"):
    return WorkerCapabilities(
        worker_id=worker_id,
        gpu="GTX 1650 4GB",
        engines=("comfyui", "ffmpeg"),
        capabilities=("image_local_draft", "video_ffmpeg"),
        runner_build="worker-reliability-v4",
        runtime_build="image-render-v1",
    )


def test_two_workers_cannot_acquire_same_active_lease():
    registry = WorkerRegistry(heartbeat_ttl=timedelta(seconds=60), lease_ttl=timedelta(seconds=90))
    now = _now()
    registry.heartbeat(_caps("w1"), now)
    registry.heartbeat(_caps("w2"), now)
    registry.acquire_lease("job-1", "a1", "w1", now)
    with pytest.raises(LeaseConflict):
        registry.acquire_lease("job-1", "a1", "w2", now + timedelta(seconds=10))


def test_expired_lease_can_be_reacquired():
    registry = WorkerRegistry(heartbeat_ttl=timedelta(minutes=5), lease_ttl=timedelta(seconds=30))
    now = _now()
    registry.heartbeat(_caps("w1"), now)
    registry.heartbeat(_caps("w2"), now)
    registry.acquire_lease("job-1", "a1", "w1", now)
    lease = registry.acquire_lease("job-1", "a1", "w2", now + timedelta(seconds=31))
    assert lease.worker_id == "w2"


def test_stale_heartbeat_marks_worker_offline():
    registry = WorkerRegistry(heartbeat_ttl=timedelta(seconds=30), lease_ttl=timedelta(seconds=60))
    now = _now()
    registry.heartbeat(_caps(), now)
    assert registry.is_online("win1650-01", now + timedelta(seconds=29))
    assert not registry.is_online("win1650-01", now + timedelta(seconds=31))
