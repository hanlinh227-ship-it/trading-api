from __future__ import annotations

from datetime import datetime, timedelta
import logging
import threading
from typing import Any, Mapping, Protocol

from g9.data_contract import validate_envelope


logger = logging.getLogger(__name__)


class MinuteProvider(Protocol):
    def fetch_minute_state(self, now: datetime) -> dict[str, Any]: ...


class SnapshotSink(Protocol):
    def write(self, payload: dict[str, Any]) -> None: ...


class Lease(Protocol):
    def acquire(self) -> bool: ...
    def release(self) -> None: ...


class MinuteWorker:
    def __init__(
        self,
        *,
        provider: MinuteProvider,
        sink: SnapshotSink,
        source_sha: str,
        max_failures: int = 3,
        backoff_seconds: int = 60,
        lease: Lease | None = None,
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
        self.lease = lease
        self._tick_lock = threading.Lock()
        self._tick_sequence = 0
        self._consecutive_failures = 0
        self._circuit_open_until: datetime | None = None
        self._last_success_time: datetime | None = None
        self._last_error: str | None = None

    @staticmethod
    def _validate_payload_contract(payload: Mapping[str, Any]) -> None:
        contract = payload.get("data_contract")
        if not isinstance(contract, Mapping):
            raise RuntimeError("minute-data-contract-missing")
        errors = validate_envelope(contract)
        if errors:
            raise RuntimeError("minute-data-contract-invalid:" + ",".join(errors))
        body = {key: value for key, value in payload.items() if key != "data_contract"}
        if contract.get("payload") != body:
            raise RuntimeError("minute-data-contract-payload-mismatch")

    def run_tick(self, now: datetime) -> dict[str, Any]:
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        if not self._tick_lock.acquire(blocking=False):
            return {
                "status": "SKIPPED_OVERLAP",
                "tick_sequence": self._tick_sequence,
                "production_execution_authority": False,
            }
        lease_acquired = False
        try:
            if self.lease is not None:
                lease_acquired = self.lease.acquire()
                if not lease_acquired:
                    return {
                        "status": "SKIPPED_LEASE",
                        "tick_sequence": self._tick_sequence,
                        "production_execution_authority": False,
                    }

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
                self._validate_payload_contract(payload)
                self.sink.write(payload)
            except Exception as exc:
                self._consecutive_failures += 1
                self._last_error = f"{type(exc).__name__}:{exc}"
                logger.warning("g9-minute-provider-failure %s", self._last_error)
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
            if lease_acquired and self.lease is not None:
                self.lease.release()
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
