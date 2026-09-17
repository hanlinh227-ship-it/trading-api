import unittest

from AI_SKILL_LIBRARY.v4.control_plane.self_development import AutoDevRun, evaluate_merge_readiness


class AutoDevelopmentTests(unittest.TestCase):
    def test_full_state_machine_reaches_ready_only_through_all_gates(self):
        run = AutoDevRun("work/improve-router", "base-sha", "rollback-sha")
        for state in ("AUTO_DEV_PLANNING", "AUTO_DEV_BRANCH_CREATED", "AUTO_DEV_IMPLEMENTING", "AUTO_DEV_TESTING", "AUTO_DEV_BENCHMARKING", "AUTO_DEV_REVIEW"):
            run.transition(state)
        run.record_gate("tests", True, "run:tests")
        run.record_gate("benchmark", True, "run:bench")
        run.record_gate("security", True, "run:security")
        run.record_gate("authority", True, "run:authority")
        run.record_gate("pr", True, "pr:1")
        run.transition("AUTO_DEV_READY_TO_MERGE")
        self.assertEqual(run.state, "AUTO_DEV_READY_TO_MERGE")

    def test_protected_branch_and_direct_main_are_refused(self):
        with self.assertRaisesRegex(ValueError, "protected"):
            AutoDevRun("main", "base", "rollback")

    def test_unrun_or_failed_gate_blocks_and_failure_is_terminal(self):
        run = AutoDevRun("work/x", "base", "rollback")
        with self.assertRaisesRegex(ValueError, "gates"):
            run.transition("AUTO_DEV_READY_TO_MERGE")
        run.record_gate("tests", False, "run:1")
        self.assertEqual(run.state, "AUTO_DEV_REJECTED")
        with self.assertRaisesRegex(ValueError, "terminal"):
            run.transition("AUTO_DEV_IMPLEMENTING")

    def test_scorecard_requires_baseline_no_protected_or_resource_regression(self):
        before = {"quality": .8, "latency": 100, "resource_use": 100, "reliability": .9, "security": 1, "vietnamese_retention": .9, "instruction_adherence": .9}
        after = {**before, "quality": .85, "latency": 90}
        self.assertTrue(evaluate_merge_readiness(before, after, "rollback-sha")["passed"])
        self.assertFalse(evaluate_merge_readiness({}, after, "rollback-sha")["passed"])
        self.assertFalse(evaluate_merge_readiness(before, {**after, "security": .9}, "rollback-sha")["passed"])
        self.assertFalse(evaluate_merge_readiness(before, {**after, "resource_use": 110}, "rollback-sha")["passed"])
        self.assertFalse(evaluate_merge_readiness(before, after, "")["passed"])

    def test_forbidden_actions_are_never_authorized(self):
        run = AutoDevRun("work/x", "base", "rollback")
        for action in ("bypass_ci", "disable_security", "change_router_authority", "expose_secrets", "enable_paid_api", "execute_trade", "mutate_main", "self_approve"):
            self.assertFalse(run.authorizes(action))
        for action in ("edit_branch", "add_tests", "run_tests", "benchmark", "open_pr", "prepare_rollback"):
            self.assertTrue(run.authorizes(action))


if __name__ == "__main__": unittest.main()
