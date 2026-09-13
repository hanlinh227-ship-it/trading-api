import json
import threading
from datetime import datetime, timedelta, timezone
from urllib.request import urlopen

from g9_runtime.app import create_http_server, seconds_until_next_minute
from g9_runtime.storage import JsonSnapshotSink
from g9_runtime.worker import MinuteWorker


class OneShotProvider:
    def fetch_minute_state(self, now):
        return {
            "schema_version": 1,
            "kind": "g9_minute_intelligence",
            "event_time": now.isoformat(),
            "symbols": {"BTCUSDT": {"market": {"last": 77000.0}}},
            "research_only": True,
            "production_execution_authority": False,
        }


def test_seconds_until_next_minute_is_bounded_and_aligned():
    now = datetime(2026, 9, 13, 15, 0, 15, 250000, tzinfo=timezone.utc)
    assert seconds_until_next_minute(now) == 44.75


def test_http_runtime_exposes_health_ready_and_latest(tmp_path):
    tick_time = datetime(2026, 9, 13, 15, 0, tzinfo=timezone.utc)
    observed_time = tick_time + timedelta(seconds=5)
    sink = JsonSnapshotSink(tmp_path)
    worker = MinuteWorker(provider=OneShotProvider(), sink=sink, source_sha="sha-123")
    assert worker.run_tick(tick_time)["status"] == "SUCCESS"

    server = create_http_server(
        worker=worker,
        sink=sink,
        host="127.0.0.1",
        port=0,
        clock=lambda: observed_time,
        ready_max_age_seconds=90,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        with urlopen(f"http://{host}:{port}/healthz") as response:
            health = json.loads(response.read())
        with urlopen(f"http://{host}:{port}/readyz") as response:
            ready = json.loads(response.read())
        with urlopen(f"http://{host}:{port}/latest") as response:
            latest = json.loads(response.read())
        assert health["source_sha"] == "sha-123"
        assert health["snapshot_age_seconds"] == 5.0
        assert ready["ready"] is True
        assert latest["event_time"] == tick_time.isoformat()
        assert latest["production_execution_authority"] is False
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
