"""Bounded retry classification and backoff for always-on execution.

Non-authoritative helper module. It performs no I/O, no network access, no
scheduling, no routing, and no model/provider selection. It only computes
retry decisions and delays for callers that already own execution authority.
"""

from __future__ import annotations

RETRYABLE = "retryable"
TERMINAL = "terminal"

_RETRYABLE_KINDS = frozenset(
    {
        "timeout",
        "transient",
        "rate_limited",
        "throttled",
        "connection_error",
        "connection_reset",
        "unavailable",
        "lease_expired",
        "provider_error",
        "server_error",
    }
)

_TERMINAL_KINDS = frozenset(
    {
        "invalid_input",
        "validation_error",
        "unauthorized",
        "forbidden",
        "not_found",
        "conflict",
        "unsupported",
        "policy_violation",
        "quota_exhausted",
        "terminal",
    }
)

_MAX_ATTEMPT = 1_000_000
_MAX_SECONDS = 86_400


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def classify_failure(kind: object) -> str:
    """Classify a failure kind as retryable or terminal.

    Fail closed: unknown, malformed, or non-string kinds are terminal.
    """
    if not isinstance(kind, str):
        return TERMINAL
    normalized = kind.strip().lower()
    if not normalized:
        return TERMINAL
    if normalized in _RETRYABLE_KINDS:
        return RETRYABLE
    if normalized in _TERMINAL_KINDS:
        return TERMINAL
    return TERMINAL


def next_retry_delay(
    attempt: object,
    base_seconds: object = 5,
    cap_seconds: object = 900,
    jitter: object = None,
) -> int:
    """Return a bounded exponential backoff delay in whole seconds.

    attempt is 1-based. Invalid inputs fail closed to the cap so that no
    unbounded or negative delay can be produced. jitter, when supplied, must
    be a deterministic integer in [0, 1000] representing a fraction of the
    computed delay; it exists only for deterministic tests.
    """
    if not _is_int(attempt) or attempt < 1 or attempt > _MAX_ATTEMPT:
        return _MAX_SECONDS
    if not _is_int(base_seconds) or base_seconds < 1 or base_seconds > _MAX_SECONDS:
        return _MAX_SECONDS
    if not _is_int(cap_seconds) or cap_seconds < 1 or cap_seconds > _MAX_SECONDS:
        return _MAX_SECONDS
    if cap_seconds < base_seconds:
        return _MAX_SECONDS

    exponent = attempt - 1
    if exponent > 62:
        delay = cap_seconds
    else:
        delay = base_seconds * (2 ** exponent)
        if delay > cap_seconds:
            delay = cap_seconds

    if jitter is None:
        return int(delay)
    if not _is_int(jitter) or jitter < 0 or jitter > 1000:
        return int(cap_seconds)
    jittered = delay - (delay * jitter // 1000)
    if jittered < 1:
        jittered = 1
    if jittered > cap_seconds:
        jittered = cap_seconds
    return int(jittered)


def should_dead_letter(attempt: object, max_attempts: object) -> bool:
    """Return True when the attempt budget is exhausted.

    Fail closed: invalid values dead-letter rather than retrying forever.
    """
    if not _is_int(attempt) or attempt < 1 or attempt > _MAX_ATTEMPT:
        return True
    if not _is_int(max_attempts) or max_attempts < 1 or max_attempts > _MAX_ATTEMPT:
        return True
    return attempt >= max_attempts
