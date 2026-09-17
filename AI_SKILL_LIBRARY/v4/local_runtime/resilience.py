"""Failure classification, circuit breaking and failover.

One worker dying must not take the canonical Brain with it. That requires
knowing *what kind* of failure happened, because the right response differs
sharply: a timeout is worth retrying on the same runtime, an OOM is not - it
will reproduce exactly - and a quota exhaustion is worth neither, only a move
to a different candidate.

The breaker exists so a runtime that is reliably broken stops being asked. It
opens on a run of failures (or immediately on a fatal one), refuses calls for a
cooldown that doubles each time the probe fails again, and closes on the first
probe that succeeds.

What is deliberately absent: any path that answers a free-tier failure by
reaching for a paid one. Failover rotates to the next zero-cost candidate or it
reports that there is none.
"""

from __future__ import annotations

import errno
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class FailureKind(str, Enum):
    TIMEOUT = "TIMEOUT"          # deadline passed; may be load, may be luck
    NETWORK = "NETWORK"          # unreachable, reset, DNS, offline
    CRASH = "CRASH"              # the runtime process died
    OOM = "OOM"                  # out of RAM or VRAM
    DISK_FULL = "DISK_FULL"      # no space to write
    QUOTA = "QUOTA"              # free entitlement exhausted for now
    PROTOCOL = "PROTOCOL"        # the contract itself is malformed
    UNSUPPORTED = "UNSUPPORTED"  # this runtime cannot serve this contract
    WORKER_LOST = "WORKER_LOST"  # the worker stopped answering healthchecks
    UNKNOWN = "UNKNOWN"          # unclassified; never guessed into another kind


#: Failures that will reproduce on the very next call, so one is enough
#: evidence to stop asking.
FATAL_KINDS = frozenset({FailureKind.OOM, FailureKind.DISK_FULL})

#: Failures where a second attempt on the same runtime is plausible.
RETRYABLE_KINDS = frozenset({FailureKind.TIMEOUT, FailureKind.NETWORK, FailureKind.CRASH,
                             FailureKind.WORKER_LOST, FailureKind.UNKNOWN})

#: A malformed contract fails identically everywhere; moving it to another
#: runtime just spends someone else's quota on the same error.
NO_FAILOVER_KINDS = frozenset({FailureKind.PROTOCOL})


class BreakerState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


def classify_exception(exc: BaseException) -> FailureKind:
    """Map an exception to a failure kind, or to UNKNOWN.

    UNKNOWN is a real answer. Guessing a specific kind would hand the caller a
    retry policy chosen from a coin flip.
    """
    text = str(exc).lower()
    if isinstance(exc, MemoryError) or "out of memory" in text or "oom" in text.split():
        return FailureKind.OOM
    if isinstance(exc, TimeoutError) or "timed out" in text or "deadline exceeded" in text:
        return FailureKind.TIMEOUT
    if isinstance(exc, ConnectionError):
        return FailureKind.NETWORK
    if isinstance(exc, OSError):
        if exc.errno == errno.ENOSPC:
            return FailureKind.DISK_FULL
        if exc.errno in (errno.ECONNREFUSED, errno.EHOSTUNREACH, errno.ENETUNREACH, errno.ECONNRESET):
            return FailureKind.NETWORK
    return FailureKind.UNKNOWN


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    backoff_base_seconds: float = 0.5
    max_backoff_seconds: float = 30.0

    def should_retry(self, kind: FailureKind, attempt: int) -> bool:
        """Retry this failure on the same runtime?"""
        if attempt >= self.max_attempts:
            return False
        return kind in RETRYABLE_KINDS

    def should_failover(self, kind: FailureKind) -> bool:
        """Move to the next zero-cost candidate? Never to a paid one."""
        return kind not in NO_FAILOVER_KINDS

    def backoff_seconds(self, attempt: int) -> float:
        return min(self.max_backoff_seconds, self.backoff_base_seconds * (2 ** max(0, attempt - 1)))


class CircuitBreaker:
    """Per-runtime breaker. Time is passed in, never read from the clock."""

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        cooldown_seconds: float = 30.0,
        max_cooldown_seconds: float = 600.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self.failure_threshold = max(1, failure_threshold)
        self.cooldown_seconds = cooldown_seconds
        self.max_cooldown_seconds = max_cooldown_seconds
        self.half_open_max_calls = max(1, half_open_max_calls)
        self._state = BreakerState.CLOSED
        self._consecutive_failures = 0
        self._open_count = 0
        self._opened_at: float | None = None
        self._probes_in_flight = 0
        self._last_failure_kind: FailureKind | None = None

    @property
    def state(self) -> BreakerState:
        return self._state

    @property
    def last_failure_kind(self) -> FailureKind | None:
        return self._last_failure_kind

    def _current_cooldown(self) -> float:
        if self._open_count <= 0:
            return self.cooldown_seconds
        return min(self.max_cooldown_seconds, self.cooldown_seconds * (2 ** (self._open_count - 1)))

    def cooldown_remaining(self, *, now: float) -> float:
        if self._state is not BreakerState.OPEN or self._opened_at is None:
            return 0.0
        return max(0.0, self._opened_at + self._current_cooldown() - now)

    def allow(self, *, now: float) -> bool:
        """May a call go out right now? Transitions OPEN -> HALF_OPEN when due."""
        if self._state is BreakerState.CLOSED:
            return True
        if self._state is BreakerState.OPEN:
            if self.cooldown_remaining(now=now) > 0:
                return False
            self._state = BreakerState.HALF_OPEN
            self._probes_in_flight = 0
        # HALF_OPEN: let a bounded number of probes through, not the whole
        # backlog - a runtime that just came back should not be stampeded.
        if self._probes_in_flight >= self.half_open_max_calls:
            return False
        self._probes_in_flight += 1
        return True

    def record_success(self, *, now: float) -> None:
        self._state = BreakerState.CLOSED
        self._consecutive_failures = 0
        self._open_count = 0
        self._opened_at = None
        self._probes_in_flight = 0

    def record_failure(self, kind: FailureKind, *, now: float) -> None:
        self._last_failure_kind = kind
        self._consecutive_failures += 1
        self._probes_in_flight = 0
        if kind in FATAL_KINDS or self._consecutive_failures >= self.failure_threshold \
                or self._state is BreakerState.HALF_OPEN:
            self._state = BreakerState.OPEN
            self._open_count += 1
            self._opened_at = now

    def to_dict(self, *, now: float) -> Mapping[str, Any]:
        return {
            "state": self._state.value,
            "consecutive_failures": self._consecutive_failures,
            "open_count": self._open_count,
            "cooldown_remaining_s": round(self.cooldown_remaining(now=now), 3),
            "last_failure_kind": self._last_failure_kind.value if self._last_failure_kind else None,
        }
