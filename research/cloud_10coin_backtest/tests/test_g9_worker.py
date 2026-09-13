from datetime import datetime, timedelta, timezone

from g9.system_contract import SYSTEM_CONTRACT_VERSION
from g9_runtime.worker import MinuteWorker


class FakeProvider:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = 0

    def fetch_minute_state(self, now):
        self.calls += 1
        if self.fail:
            raise RuntimeError("provider-down")
        return {"event_time": now.isoformat(), "symbols": {"BTCUSDT": {"last": 77000.0}}}


class MemorySink:
    def __init__(self):
        self.rows = []

    def write(self, payload):
        self.rows.append(payload)


class BusyLease:
    def acquire(self):
        return False

    def release(self):
        raise AssertionError("busy lease must not be released by non-owner")


def test_worker_ticks_monotonically_and_exposes_health():
    provider = FakeProvider()
    sink = MemorySink()
    now = datetime(2026, 9, 13, 15, 0, tzinfo=timezone.utc)
    worker = MinuteWorker(provider=provider, sink=sink, source_sha="abc123", max_failures=3)

    first = worker.run_tick(now)
    second = worker.run_tick(now + timedelta(minutes=1))

    assert first["status"] == "SUCCESS"
    assert second["tick_sequence"] == first["tick_sequence"] + 1
    assert len(sink.rows) == 2
    health = worker.health(now + timedelta(minutes=1, seconds=5))
    assert health["source_sha"] == "abc123"
    assert health["last_successful_tick"] == second["completed_at"]
    assert health["snapshot_age_seconds"] == 5.0
    assert health["production_execution_authority"] is False


def test_worker_seals_every_snapshot_with_canonical_boundary_metadata():
    sink = MemorySink()
    now = datetime(2026, 9, 13, 15, 0, tzinfo=timezone.utc)
    worker = MinuteWorker(provider=FakeProvider(), sink=sink, source_sha="source-abc")
    assert worker.run_tick(now)["status"] == "SUCCESS"

    payload = sink.rows[-1]
    assert payload["system_contract_version"] == SYSTEM_CONTRACT_VERSION
    assert payload["plane"] == "LIVE_CONTEXT"
    assert payload["authority_level"] == "LIVE_CONTEXT"
    assert payload["source_sha"] == "source-abc"
    assert payload["research_only"] is True
    assert payload["production_execution_authority"] is False


def test_worker_rejects_provider_attempt_to_escalate_execution_authority():
    class EscalatingProvider:
        def fetch_minute_state(self, now):
            return {
                "event_time": now.isoformat(),
                "symbols": {},
                "research_only": True,
                "production_execution_authority": True,
            }

    worker = MinuteWorker(provider=EscalatingProvider(), sink=MemorySink(), source_sha="abc123")
    result = worker.run_tick(datetime(2026, 9, 13, 15, 0, tzinfo=timezone.utc))
    assert result["status"] == "FAILED"
    assert "execution authority" in result["error"].lower()


def test_worker_skips_overlapping_tick():
    worker = MinuteWorker(provider=FakeProvider(), sink=MemorySink(), source_sha="abc123")
    assert worker._tick_lock.acquire(blocking=False)
    try:
        result = worker.run_tick(datetime(2026, 9, 13, 15, 0, tzinfo=timezone.utc))
    finally:
        worker._tick_lock.release()
    assert result["status"] == "SKIPPED_OVERLAP"


def test_worker_skips_tick_when_cross_process_lease_is_busy():
    provider = FakeProvider()
    worker = MinuteWorker(
        provider=provider,
        sink=MemorySink(),
        source_sha="abc123",
        lease=BusyLease(),
    )
    result = worker.run_tick(datetime(2026, 9, 13, 15, 0, tzinfo=timezone.utc))
    assert result["status"] == "SKIPPED_LEASE"
    assert provider.calls == 0


def test_worker_opens_circuit_after_bounded_provider_failures():
    provider = FakeProvider(fail=True)
    now = datetime(2026, 9, 13, 15, 0, tzinfo=timezone.utc)
    worker = MinuteWorker(
        provider=provider,
        sink=MemorySink(),
        source_sha="abc123",
        max_failures=2,
        backoff_seconds=60,
    )
    assert worker.run_tick(now)["status"] == "FAILED"
    assert worker.run_tick(now + timedelta(seconds=1))["status"] == "FAILED"
    calls_after_failures = provider.calls
    blocked = worker.run_tick(now + timedelta(seconds=2))
    assert blocked["status"] == "CIRCUIT_OPEN"
    assert provider.calls == calls_after_failures


def test_worker_logs_provider_failure_for_cloud_diagnostics(caplog):
    provider = FakeProvider(fail=True)
    worker = MinuteWorker(provider=provider, sink=MemorySink(), source_sha="abc123")
    now = datetime(2026, 9, 13, 15, 0, tzinfo=timezone.utc)

    with caplog.at_level("WARNING"):
        result = worker.run_tick(now)

    assert result["status"] == "FAILED"
    assert "g9-minute-provider-failure" in caplog.text
    assert "RuntimeError:provider-down" in caplog.text
    assert "BTCUSDT" not in caplog.text
