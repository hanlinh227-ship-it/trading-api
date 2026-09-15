import copy
import unittest

from AI_SKILL_LIBRARY.v4.tools.model_mesh import apply_quota_event, next_probe_at, provider_available


class AdaptiveFreeModelMeshQuotaTests(unittest.TestCase):
    def setUp(self):
        self.now = "2026-09-15T05:30:00Z"
        self.base = {
            "provider_id": "groq",
            "model_id": "gpt-oss-120b",
            "status": "AVAILABLE",
            "consecutive_failures": 0,
            "quota_headroom": 1.0,
            "reset_at": None,
            "probe_at": None,
            "retry_allowed": True,
            "last_failure_class": None,
        }

    def test_low_headroom_then_429_enters_cooldown_and_honors_retry_after(self):
        low = apply_quota_event(self.base, {"type": "quota", "remaining_ratio": 0.08}, now=self.now)
        self.assertEqual(low["status"], "LOW_HEADROOM")
        before = copy.deepcopy(low)
        cooled = apply_quota_event(low, {"type": "http_error", "status_code": 429, "retry_after_seconds": 120}, now=self.now)
        self.assertEqual(low, before, "state transitions must not mutate input")
        self.assertEqual(cooled["status"], "COOLDOWN_QUOTA")
        self.assertEqual(cooled["reset_at"], "2026-09-15T05:32:00Z")
        self.assertFalse(provider_available(cooled, now="2026-09-15T05:31:59Z"))
        self.assertEqual(next_probe_at(cooled), "2026-09-15T05:32:00Z")

        probe_ready = apply_quota_event(cooled, {"type": "tick"}, now="2026-09-15T05:32:00Z")
        self.assertEqual(probe_ready["status"], "PROBE_READY")
        recovered = apply_quota_event(probe_ready, {"type": "probe_success"}, now="2026-09-15T05:32:01Z")
        self.assertEqual(recovered["status"], "AVAILABLE")
        self.assertTrue(provider_available(recovered, now="2026-09-15T05:32:01Z"))

    def test_provider_reset_at_metadata_outranks_static_backoff(self):
        cooled = apply_quota_event(
            self.base,
            {
                "type": "http_error",
                "status_code": 429,
                "retry_after_seconds": 600,
                "reset_at": "2026-09-15T05:35:00Z",
            },
            now=self.now,
        )
        self.assertEqual(cooled["reset_at"], "2026-09-15T05:35:00Z")
        self.assertEqual(next_probe_at(cooled), "2026-09-15T05:35:00Z")

    def test_invalid_credentials_are_unavailable_and_never_retried(self):
        failed = apply_quota_event(self.base, {"type": "invalid_credentials"}, now=self.now)
        self.assertEqual(failed["status"], "UNAVAILABLE")
        self.assertFalse(failed["retry_allowed"])
        self.assertFalse(provider_available(failed, now=self.now))
        self.assertIsNone(next_probe_at(failed))
        self.assertEqual(failed["last_failure_class"], "invalid_credentials")

    def test_three_transient_failures_open_circuit_then_half_open_probe(self):
        state = self.base
        state = apply_quota_event(state, {"type": "transient_failure"}, now=self.now)
        self.assertEqual(state["status"], "DEGRADED")
        state = apply_quota_event(state, {"type": "transient_failure"}, now="2026-09-15T05:30:01Z")
        self.assertEqual(state["status"], "DEGRADED")
        state = apply_quota_event(state, {"type": "transient_failure", "retry_after_seconds": 60}, now="2026-09-15T05:30:02Z")
        self.assertEqual(state["status"], "CIRCUIT_OPEN")
        self.assertEqual(state["consecutive_failures"], 3)
        self.assertFalse(provider_available(state, now="2026-09-15T05:30:30Z"))
        self.assertEqual(next_probe_at(state), "2026-09-15T05:31:02Z")

        half_open = apply_quota_event(state, {"type": "tick"}, now="2026-09-15T05:31:02Z")
        self.assertEqual(half_open["status"], "HALF_OPEN")
        recovered = apply_quota_event(half_open, {"type": "probe_success"}, now="2026-09-15T05:31:03Z")
        self.assertEqual(recovered["status"], "AVAILABLE")
        self.assertEqual(recovered["consecutive_failures"], 0)

    def test_no_transition_emits_quota_circumvention_actions(self):
        events = [
            {"type": "quota", "remaining_ratio": 0.01},
            {"type": "http_error", "status_code": 429, "retry_after_seconds": 60},
            {"type": "transient_failure"},
            {"type": "invalid_credentials"},
        ]
        forbidden = {"rotate_ip", "new_account", "new_key", "proxy_hop", "region_hop", "bypass"}
        for event in events:
            state = apply_quota_event(self.base, event, now=self.now)
            self.assertTrue(forbidden.isdisjoint(state), event)
            self.assertTrue(forbidden.isdisjoint(state.values()), event)


if __name__ == "__main__":
    unittest.main()
