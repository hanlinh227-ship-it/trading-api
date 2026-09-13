import json

from g9_runtime.storage import FileLease, JsonSnapshotSink


def test_snapshot_sink_keeps_atomic_latest_and_append_only_history(tmp_path):
    sink = JsonSnapshotSink(tmp_path)
    sink.write({"event_time": "t1", "symbols": {"BTCUSDT": {"last": 1}}})
    sink.write({"event_time": "t2", "symbols": {"BTCUSDT": {"last": 2}}})

    latest = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    history = (tmp_path / "minute_history.jsonl").read_text(encoding="utf-8").splitlines()
    assert latest["event_time"] == "t2"
    assert len(history) == 2
    assert json.loads(history[0])["event_time"] == "t1"
    assert not (tmp_path / "latest.json.tmp").exists()


def test_file_lease_allows_only_one_leader(tmp_path):
    first = FileLease(tmp_path / "minute.lock")
    second = FileLease(tmp_path / "minute.lock")
    assert first.acquire() is True
    try:
        assert second.acquire() is False
    finally:
        first.release()
    assert second.acquire() is True
    second.release()
