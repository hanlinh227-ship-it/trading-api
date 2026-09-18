"""Offline tests for bounded always-on retry helpers."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from v4.always_on.retry import (  # noqa: E402
    classify_failure,
    next_retry_delay,
    should_dead_letter,
)


def test_classify_retryable():
    assert classify_failure("timeout") == "retryable"
    assert classify_failure("  TIMEOUT ") == "retryable"
    assert classify_failure("rate_limited") == "retryable"


def test_classify_terminal():
    assert classify_failure("invalid_input") == "terminal"
    assert classify_failure("unauthorized") == "terminal"


def test_classify_fails_closed():
    assert classify_failure("unknown_kind") == "terminal"
    assert classify_failure("") == "terminal"
    assert classify_failure(None) == "terminal"
    assert classify_failure(7) == "terminal"
    assert classify_failure(True) == "terminal"


def test_backoff_is_bounded_exponential():
    assert next_retry_delay(1, base_seconds=5, cap_seconds=900) == 5
    assert next_retry_delay(2, base_seconds=5, cap_seconds=900) == 10
    assert next_retry_delay(3, base_seconds=5, cap_seconds=900) == 20
    assert next_retry_delay(4, base_seconds=5, cap_seconds=900) == 40


def test_backoff_cap_enforced():
    assert next_retry_delay(50, base_seconds=5, cap_seconds=900) == 900
    assert next_retry_delay(1000, base_seconds=5, cap_seconds=900) == 900


def test_backoff_deterministic_jitter():
    assert next_retry_delay(3, base_seconds=5, cap_seconds=900, jitter=0) == 20
    assert next_retry_delay(3, base_seconds=5, cap_seconds=900, jitter=500) == 10
    assert next_retry_delay(3, base_seconds=5, cap_seconds=900, jitter=1000) == 1
    assert next_retry_delay(3, base_seconds=5, cap_seconds=900, jitter=500) == 10


def test_backoff_fails_closed():
    assert next_retry_delay(0) == 86400
    assert next_retry_delay(-1) == 86400
    assert next_retry_delay("3") == 86400
    assert next_retry_delay(True) == 86400
    assert next_retry_delay(3, base_seconds=0) == 86400
    assert next_retry_delay(3, cap_seconds=0) == 86400
    assert next_retry_delay(3, base_seconds=900, cap_seconds=5) == 86400
    assert next_retry_delay(3, jitter=1001) == 900
    assert next_retry_delay(3, jitter=-1) == 900


def test_dead_letter():
    assert should_dead_letter(1, 3) is False
    assert should_dead_letter(2, 3) is False
    assert should_dead_letter(3, 3) is True
    assert should_dead_letter(4, 3) is True


def test_dead_letter_fails_closed():
    assert should_dead_letter(0, 3) is True
    assert should_dead_letter(1, 0) is True
    assert should_dead_letter("1", 3) is True
    assert should_dead_letter(1, None) is True
    assert should_dead_letter(True, 3) is True
