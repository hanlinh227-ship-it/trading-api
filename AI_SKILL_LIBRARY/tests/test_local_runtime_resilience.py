import unittest

from AI_SKILL_LIBRARY.v4.local_runtime.resilience import (
    BreakerState,
    CircuitBreaker,
    FailureKind,
    RetryPolicy,
    classify_exception,
)


class BreakerTests(unittest.TestCase):
    def test_starts_closed_and_allows_calls(self):
        breaker = CircuitBreaker()
        self.assertEqual(breaker.state, BreakerState.CLOSED)
        self.assertTrue(breaker.allow(now=0.0))

    def test_opens_after_the_failure_threshold(self):
        breaker = CircuitBreaker(failure_threshold=3)
        for step in range(3):
            self.assertTrue(breaker.allow(now=float(step)))
            breaker.record_failure(FailureKind.TIMEOUT, now=float(step))
        self.assertEqual(breaker.state, BreakerState.OPEN)
        self.assertFalse(breaker.allow(now=3.0))

    def test_a_success_resets_the_failure_run(self):
        breaker = CircuitBreaker(failure_threshold=3)
        breaker.record_failure(FailureKind.TIMEOUT, now=0.0)
        breaker.record_failure(FailureKind.TIMEOUT, now=1.0)
        breaker.record_success(now=2.0)
        breaker.record_failure(FailureKind.TIMEOUT, now=3.0)
        self.assertEqual(breaker.state, BreakerState.CLOSED)

    def test_fatal_failures_open_immediately(self):
        for kind in (FailureKind.OOM, FailureKind.DISK_FULL):
            with self.subTest(kind=kind):
                breaker = CircuitBreaker(failure_threshold=10)
                breaker.record_failure(kind, now=0.0)
                self.assertEqual(breaker.state, BreakerState.OPEN)

    def test_half_opens_after_the_cooldown(self):
        breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=30.0)
        breaker.record_failure(FailureKind.TIMEOUT, now=0.0)
        self.assertFalse(breaker.allow(now=29.0))
        self.assertTrue(breaker.allow(now=31.0))
        self.assertEqual(breaker.state, BreakerState.HALF_OPEN)

    def test_half_open_admits_one_probe_at_a_time(self):
        breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=10.0)
        breaker.record_failure(FailureKind.CRASH, now=0.0)
        self.assertTrue(breaker.allow(now=20.0))
        self.assertFalse(breaker.allow(now=20.1))

    def test_a_successful_probe_closes_the_breaker(self):
        breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=10.0)
        breaker.record_failure(FailureKind.CRASH, now=0.0)
        breaker.allow(now=20.0)
        breaker.record_success(now=20.5)
        self.assertEqual(breaker.state, BreakerState.CLOSED)
        self.assertTrue(breaker.allow(now=21.0))

    def test_a_failed_probe_reopens_with_a_longer_cooldown(self):
        breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=10.0)
        breaker.record_failure(FailureKind.CRASH, now=0.0)
        breaker.allow(now=11.0)
        breaker.record_failure(FailureKind.CRASH, now=11.0)
        self.assertEqual(breaker.state, BreakerState.OPEN)
        self.assertFalse(breaker.allow(now=18.0))
        self.assertTrue(breaker.allow(now=35.0))

    def test_cooldown_backoff_is_capped(self):
        breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=10.0, max_cooldown_seconds=40.0)
        now = 0.0
        for _ in range(8):
            breaker.record_failure(FailureKind.CRASH, now=now)
            now += 1000.0
            breaker.allow(now=now)
        self.assertLessEqual(breaker.cooldown_remaining(now=now), 40.0)

    def test_snapshot_is_json_safe(self):
        import json
        breaker = CircuitBreaker(failure_threshold=1)
        breaker.record_failure(FailureKind.OOM, now=0.0)
        payload = breaker.to_dict(now=1.0)
        self.assertEqual(json.loads(json.dumps(payload))["state"], "OPEN")
        self.assertEqual(payload["last_failure_kind"], "OOM")


class RetryPolicyTests(unittest.TestCase):
    def test_transient_failures_are_retried_within_the_attempt_budget(self):
        policy = RetryPolicy(max_attempts=3)
        self.assertTrue(policy.should_retry(FailureKind.TIMEOUT, attempt=1))
        self.assertTrue(policy.should_retry(FailureKind.NETWORK, attempt=2))
        self.assertFalse(policy.should_retry(FailureKind.TIMEOUT, attempt=3))

    def test_deterministic_failures_are_never_retried_on_the_same_runtime(self):
        policy = RetryPolicy()
        for kind in (FailureKind.OOM, FailureKind.DISK_FULL, FailureKind.PROTOCOL,
                     FailureKind.UNSUPPORTED):
            with self.subTest(kind=kind):
                self.assertFalse(policy.should_retry(kind, attempt=1))

    def test_quota_exhaustion_fails_over_rather_than_retrying(self):
        policy = RetryPolicy()
        self.assertFalse(policy.should_retry(FailureKind.QUOTA, attempt=1))
        self.assertTrue(policy.should_failover(FailureKind.QUOTA))

    def test_backoff_grows_and_is_capped(self):
        policy = RetryPolicy(backoff_base_seconds=1.0, max_backoff_seconds=8.0)
        delays = [policy.backoff_seconds(attempt) for attempt in range(1, 8)]
        self.assertEqual(delays[:4], [1.0, 2.0, 4.0, 8.0])
        self.assertTrue(all(delay <= 8.0 for delay in delays))

    def test_every_failure_kind_has_a_declared_disposition(self):
        policy = RetryPolicy()
        for kind in FailureKind:
            with self.subTest(kind=kind):
                self.assertIsInstance(policy.should_retry(kind, attempt=1), bool)
                self.assertIsInstance(policy.should_failover(kind), bool)


class ClassificationTests(unittest.TestCase):
    def test_memory_error_is_oom(self):
        self.assertEqual(classify_exception(MemoryError("cuda out of memory")), FailureKind.OOM)

    def test_enospc_is_disk_full(self):
        self.assertEqual(classify_exception(OSError(28, "No space left on device")), FailureKind.DISK_FULL)

    def test_timeout_is_timeout(self):
        self.assertEqual(classify_exception(TimeoutError("deadline exceeded")), FailureKind.TIMEOUT)

    def test_connection_error_is_network(self):
        self.assertEqual(classify_exception(ConnectionResetError("reset by peer")), FailureKind.NETWORK)

    def test_an_unrecognised_exception_is_unknown_not_a_guess(self):
        self.assertEqual(classify_exception(ValueError("who knows")), FailureKind.UNKNOWN)

    def test_cuda_oom_reported_as_a_runtime_error_is_still_oom(self):
        self.assertEqual(classify_exception(RuntimeError("CUDA out of memory")), FailureKind.OOM)


if __name__ == "__main__":
    unittest.main()
