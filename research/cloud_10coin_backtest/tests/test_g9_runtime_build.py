from datetime import datetime, timezone

from g9_runtime.main import build_runtime


class FakeProvider:
    def fetch_minute_state(self, now):
        return {
            "schema_version": 1,
            "kind": "g9_minute_intelligence",
            "event_time": now.isoformat(),
            "symbols": {},
            "research_only": True,
            "production_execution_authority": False,
        }


def test_runtime_builds_from_environment_and_can_tick(tmp_path):
    provider = FakeProvider()
    runtime = build_runtime(
        {
            "G9_SYMBOLS": "BTCUSDT,ETHUSDT",
            "G9_DATA_DIR": str(tmp_path),
            "DEPLOYMENT_SOURCE_SHA": "source-789",
            "HOST": "127.0.0.1",
            "PORT": "0",
        },
        provider=provider,
    )
    assert runtime.worker.source_sha == "source-789"
    assert runtime.symbols == ("BTCUSDT", "ETHUSDT")
    assert runtime.sink.data_dir == tmp_path
    now = datetime(2026, 9, 13, 15, 0, tzinfo=timezone.utc)
    assert runtime.tick_once(now)["status"] == "SUCCESS"
    assert runtime.sink.read_latest()["event_time"] == now.isoformat()
    runtime.server.server_close()
