from __future__ import annotations

from datetime import datetime, timedelta
import threading
from typing import Any, Protocol


class MinuteProvider(Protocol):
    def fetch_minute_state(self, now: datetime) -> dict[str, Any]: ...


class SnapshotSink(Protocol):
    def write(self, payload: dict[str, Any]) -> None: ...


class MinuteWorker:
    def __init__(
        self,
        *,
        provider: MinuteProvider,
        sink: SnapshotSink,
        source_sha: str,
        max_failures: int = 3,
        backoff_seconds: int = 60,
    ):
        if max_failures <= 0:
            raise ValueError("max_failures must be positive")
        if backoff_seconds <= 0:
            raise ValueError("backoff_seconds must be positive")
        self.provider = provider
        self.sink = sink
        self.source_sha = str(source_sha)
        self.max_failures = int(max_failures)
        self.backoff_seconds = int(backoff_seconds)
        self._tick_lock = threading.Lock()
        self._tick_sequence = 0
        self._consecutive_failures = 0
        self._circuit_open_until: datetime | None = None
        self._last_success_time: datetime | None = None
        self._last_error: str | None = None

    def run_tick(self, now: datetime) -> dict[str, Any]:
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        if not self._tick_lock.acquire(blocking=False):
            return {
                "status": "SKIPPED_OVERLAP",
                "tick_sequence": self._tick_sequence,
                "production_execution_authority": False,
            }
        try:
            if self._circuit_open_until is not None and now < self._circuit_open_until:
                return {
                    "status": "CIRCUIT_OPEN",
                    "tick_sequence": self._tick_sequence,
                    "retry_at": self._circuit_open_until.isoformat(),
                    "production_execution_authority": False,
                }

            self._tick_sequence += 1
            sequence = self._tick_sequence
            try:
                payload = self.provider.fetch_minute_state(now)
                self.sink.write(payload)
            except Exception as exc:
                self._consecutive_failures += 1
                self._last_error = f"{type(exc).__name__}:{exc}"
                if self._consecutive_failures >= self.max_failures:
                    self._circuit_open_until = now + timedelta(seconds=self.backoff_seconds)
                return {
                    "status": "FAILED",
                    "tick_sequence": sequence,
                    "completed_at": now.isoformat(),
                    "error": self._last_error,
                    "production_execution_authority": False,
                }

            self._consecutive_failures = 0
            self._circuit_open_until = None
            self._last_error = None
            self._last_success_time = now
            return {
                "status": "SUCCESS",
                "tick_sequence": sequence,
                "completed_at": now.isoformat(),
                "production_execution_authority": False,
            }
        finally:
            self._tick_lock.release()

    def health(self, now: datetime) -> dict[str, Any]:
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        age = None
        if self._last_success_time is not None:
            age = max(0.0, (now - self._last_success_time).total_seconds())
        return {
            "status": "ok" if self._last_success_time is not None else "starting",
            "source_sha": self.source_sha,
            "tick_sequence": self._tick_sequence,
            "last_successful_tick": None if self._last_success_time is None else self._last_success_time.isoformat(),
            "snapshot_age_seconds": age,
            "consecutive_failures": self._consecutive_failures,
            "circuit_open_until": None if self._circuit_open_until is None else self._circuit_open_until.isoformat(),
            "last_error": self._last_error,
            "research_only": True,
            "production_execution_authority": False,
        }
