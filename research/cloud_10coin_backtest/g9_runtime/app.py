from __future__ import annotations

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from typing import Callable
from urllib.parse import urlparse

from .storage import JsonSnapshotSink
from .worker import MinuteWorker


def seconds_until_next_minute(now: datetime) -> float:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    elapsed = now.second + now.microsecond / 1_000_000.0
    return round(60.0 - elapsed, 6)


def create_http_server(
    *,
    worker: MinuteWorker,
    sink: JsonSnapshotSink,
    host: str,
    port: int,
    clock: Callable[[], datetime] | None = None,
    ready_max_age_seconds: float = 90.0,
) -> ThreadingHTTPServer:
    clock = clock or (lambda: datetime.now(timezone.utc))

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, payload: dict) -> None:
            raw = json.dumps(payload, sort_keys=True, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            path = urlparse(self.path).path
            if path == "/healthz":
                self._send(200, worker.health(clock()))
                return
            if path == "/readyz":
                health = worker.health(clock())
                age = health.get("snapshot_age_seconds")
                ready = (
                    health.get("status") == "ok"
                    and isinstance(age, (int, float))
                    and age <= float(ready_max_age_seconds)
                    and health.get("production_execution_authority") is False
                )
                self._send(200 if ready else 503, {"ready": ready, **health})
                return
            if path == "/latest":
                latest = sink.read_latest()
                if latest is None:
                    self._send(404, {"error": "snapshot-not-ready"})
                else:
                    self._send(200, latest)
                return
            self._send(404, {"error": "not-found"})

        def log_message(self, format: str, *args) -> None:
            return

    return ThreadingHTTPServer((host, int(port)), Handler)
