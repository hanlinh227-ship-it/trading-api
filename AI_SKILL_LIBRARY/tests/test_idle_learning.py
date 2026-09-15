import unittest

from AI_SKILL_LIBRARY.v4.tools.idle_learning import (
    eligible_idle_jobs,
    next_idle_job,
    reserve_budget,
    yield_for_user_activity,
)


NOW = "2026-09-15T07:00:00Z"


class IdleLearningTests(unittest.TestCase):
    def _state(self):
        return {
            "active_user_work": False,
            "running_idle_jobs": 0,
            "max_concurrent_idle_jobs": 2,
            "budget": {
                "tokens_remaining": 10000,
                "api_calls_remaining": 100,
                "compute_seconds_remaining": 3600,
                "storage_mb_remaining": 500,
                "network_calls_remaining": 100,
            },
        }

    def _backlog(self):
        return [
            {"job_id": "f", "kind": "failure_analysis", "priority": 90, "cost": {"tokens": 100, "api_calls": 0, "compute_seconds": 10, "storage_mb": 1, "network_calls": 0}},
            {"job_id": "g", "kind": "capability_gap_detection", "priority": 80, "cost": {"tokens": 100, "api_calls": 0, "compute_seconds": 10, "storage_mb": 1, "network_calls": 0}},
            {"job_id": "m", "kind": "free_model_discovery", "priority": 70, "cost": {"tokens": 0, "api_calls": 2, "compute_seconds": 20, "storage_mb": 1, "network_calls": 2}},
            {"job_id": "s", "kind": "skill_mutation", "priority": 60, "mutation_budget": 4, "cost": {"tokens": 300, "api_calls": 1, "compute_seconds": 30, "storage_mb": 2, "network_calls": 1}},
            {"job_id": "bad", "kind": "live_financial_execution", "priority": 999, "cost": {"tokens": 0, "api_calls": 0, "compute_seconds": 1, "storage_mb": 0, "network_calls": 1}},
        ]

    def test_active_user_work_yields_immediately(self):
        state = self._state()
        state["active_user_work"] = True
        self.assertTrue(yield_for_user_activity(state))
        self.assertEqual(eligible_idle_jobs(state, self._backlog(), NOW), [])

    def test_only_allowed_low_risk_jobs_are_eligible(self):
        jobs = eligible_idle_jobs(self._state(), self._backlog(), NOW)
        kinds = {job["kind"] for job in jobs}
        self.assertIn("failure_analysis", kinds)
        self.assertIn("capability_gap_detection", kinds)
        self.assertIn("free_model_discovery", kinds)
        self.assertIn("skill_mutation", kinds)
        self.assertNotIn("live_financial_execution", kinds)

    def test_budget_exhaustion_blocks_job(self):
        state = self._state()
        state["budget"]["tokens_remaining"] = 50
        jobs = eligible_idle_jobs(state, self._backlog(), NOW)
        ids = {job["job_id"] for job in jobs}
        self.assertNotIn("f", ids)
        self.assertNotIn("g", ids)
        self.assertNotIn("s", ids)

    def test_reserve_budget_is_fail_closed_and_nonnegative(self):
        state = self._state()["budget"]
        job = self._backlog()[0]
        reserved = reserve_budget(job, state)
        self.assertEqual(reserved["tokens_remaining"], 9900)
        too_large = {"cost": {"tokens": 999999, "api_calls": 0, "compute_seconds": 0, "storage_mb": 0, "network_calls": 0}}
        with self.assertRaises(ValueError):
            reserve_budget(too_large, state)

    def test_mutation_budget_is_capped(self):
        backlog = self._backlog()
        backlog[3]["mutation_budget"] = 99
        jobs = eligible_idle_jobs(self._state(), backlog, NOW)
        mutation = next(job for job in jobs if job["kind"] == "skill_mutation")
        self.assertLessEqual(mutation["mutation_budget"], 6)

    def test_next_idle_job_is_deterministic_highest_priority(self):
        jobs = eligible_idle_jobs(self._state(), self._backlog(), NOW)
        chosen = next_idle_job(jobs)
        self.assertEqual(chosen["job_id"], "f")

    def test_running_concurrency_ceiling_blocks_new_work(self):
        state = self._state()
        state["running_idle_jobs"] = state["max_concurrent_idle_jobs"]
        self.assertEqual(eligible_idle_jobs(state, self._backlog(), NOW), [])


if __name__ == "__main__":
    unittest.main()
