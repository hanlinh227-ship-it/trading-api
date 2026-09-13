from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
from typing import Any


class JsonSnapshotSink:
    def __init__(self, data_dir: Path | str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.latest_path = self.data_dir / "latest.json"
        self.history_path = self.data_dir / "minute_history.jsonl"

    def write(self, payload: dict[str, Any]) -> None:
        latest_text = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
        tmp = self.latest_path.with_name(self.latest_path.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            handle.write(latest_text)
            handle.flush()
            os.fsync(handle.fileno())
        tmp.replace(self.latest_path)

        history_line = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
        with self.history_path.open("a", encoding="utf-8") as handle:
            handle.write(history_line)
            handle.flush()
            os.fsync(handle.fileno())

    def read_latest(self) -> dict[str, Any] | None:
        if not self.latest_path.exists():
            return None
        return json.loads(self.latest_path.read_text(encoding="utf-8"))


class FileLease:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = None

    def acquire(self) -> bool:
        if self._handle is not None:
            return True
        handle = self.path.open("a+")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            return False
        self._handle = handle
        return True

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
            self._handle = None
