from datetime import datetime, timezone

from g9.data_contract import build_envelope
from g9_runtime.main import build_runtime


class FakeProvider:
    def fetch_minute_state(self, now):
        payload = {
            "schema_version": 1,
            "kind": "g9_minute_intelligence",
            "event_time": now.isoformat(),
            "symbols": {},
            "research_only": True,
            "production_execution_authority": False,
        }
        return {
            **payload,
            "data_contract": build_envelope(
                kind="g9_minute_intelligence",
                source="test-runtime-provider",
                source_sha="test-sha",
                event_time=now,
                ingest_time=now,
                freshness="FRESH",
                payload=payload,
                provenance={"test": True},
            ),
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
    latest = runtime.sink.read_latest()
    assert latest["event_time"] == now.isoformat()
    assert latest["data_contract"]["production_execution_authority"] is False
    runtime.server.server_close()
