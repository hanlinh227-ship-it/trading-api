import unittest

from AI_SKILL_LIBRARY.v4.local_runtime.selfdev import (
    AUTOMATION_ACTORS,
    PROTECTED_BRANCHES,
    REQUIRED_GATES,
    AutoDevError,
    AutoDevState,
    GateResult,
    advance,
    approve,
    record_gate,
    reject,
    roll_back,
    start,
    valid_autodev_targets,
)


def started(run_id="run-1", branch="auto/fix-1", base_sha="a" * 40):
    return start(run_id, branch=branch, base_sha=base_sha)


def all_gates_passed(run):
    for name in REQUIRED_GATES:
        run = record_gate(run, GateResult(name=name, passed=True, evidence_ref=f"ev/{name}"))
    return run


def walk_to_review(run):
    run = advance(run, AutoDevState.PLANNING, reason="plan")
    run = advance(run, AutoDevState.BRANCH_CREATED, reason="branch")
    run = advance(run, AutoDevState.IMPLEMENTING, reason="implement")
    run = advance(run, AutoDevState.TESTING, reason="test")
    run = advance(run, AutoDevState.BENCHMARKING, reason="benchmark")
    return advance(run, AutoDevState.REVIEW, reason="review")


class BranchIsolationTests(unittest.TestCase):
    def test_a_protected_branch_is_refused(self):
        for branch in PROTECTED_BRANCHES:
            with self.subTest(branch=branch):
                with self.assertRaises(AutoDevError):
                    start("r", branch=branch, base_sha="a" * 40)

    def test_protected_branch_check_is_case_insensitive(self):
        with self.assertRaises(AutoDevError):
            start("r", branch="MAIN", base_sha="a" * 40)

    def test_an_isolated_branch_is_accepted(self):
        run = started()
        self.assertEqual(run.branch, "auto/fix-1")
        self.assertEqual(run.state, AutoDevState.IDLE)

    def test_a_base_sha_is_required_so_rollback_exists(self):
        with self.assertRaises(AutoDevError):
            start("r", branch="auto/x", base_sha="")

    def test_rollback_ref_is_recorded_at_start(self):
        self.assertEqual(started().rollback_ref, "a" * 40)


class GateTests(unittest.TestCase):
    def test_a_fresh_run_has_every_gate_outstanding(self):
        self.assertEqual(set(started().outstanding_gates), set(REQUIRED_GATES))

    def test_an_unrun_gate_blocks_exactly_like_a_failed_one(self):
        run = record_gate(started(), GateResult(name="tests", passed=None))
        self.assertIn("tests", run.outstanding_gates)
        failed = record_gate(started(), GateResult(name="tests", passed=False))
        self.assertIn("tests", failed.outstanding_gates)

    def test_all_gates_passing_allows_proposal(self):
        self.assertTrue(all_gates_passed(started()).can_propose)

    def test_a_failed_gate_cannot_be_overwritten_by_a_pass(self):
        run = record_gate(started(), GateResult(name="tests", passed=False))
        with self.assertRaises(AutoDevError):
            record_gate(run, GateResult(name="tests", passed=True))

    def test_every_required_gate_maps_to_a_producing_state(self):
        for name, state in REQUIRED_GATES.items():
            with self.subTest(name=name):
                self.assertIsInstance(state, AutoDevState)

    def test_security_and_verifier_are_both_required(self):
        self.assertIn("security", REQUIRED_GATES)
        self.assertIn("verifier", REQUIRED_GATES)


class TransitionTests(unittest.TestCase):
    def test_the_happy_path(self):
        run = all_gates_passed(walk_to_review(started()))
        run = advance(run, AutoDevState.READY_TO_MERGE, reason="all gates green")
        self.assertEqual(run.state, AutoDevState.READY_TO_MERGE)

    def test_idle_cannot_jump_to_ready(self):
        with self.assertRaises(AutoDevError):
            advance(all_gates_passed(started()), AutoDevState.READY_TO_MERGE, reason="skip")

    def test_implementation_cannot_skip_testing(self):
        run = advance(advance(advance(started(), AutoDevState.PLANNING, reason="p"),
                              AutoDevState.BRANCH_CREATED, reason="b"),
                      AutoDevState.IMPLEMENTING, reason="i")
        with self.assertRaises(AutoDevError):
            advance(run, AutoDevState.BENCHMARKING, reason="skip tests")

    def test_review_cannot_propose_with_outstanding_gates(self):
        run = walk_to_review(started())
        with self.assertRaises(AutoDevError) as caught:
            advance(run, AutoDevState.READY_TO_MERGE, reason="propose anyway")
        self.assertIn("outstanding gates", str(caught.exception))

    def test_review_cannot_propose_with_a_failed_gate(self):
        run = walk_to_review(started())
        run = all_gates_passed(run)
        run = record_gate(run, GateResult(name="extra", passed=False))
        with self.assertRaises(AutoDevError) as caught:
            advance(run, AutoDevState.READY_TO_MERGE, reason="propose anyway")
        self.assertIn("failed gates", str(caught.exception))

    def test_rolled_back_is_terminal(self):
        self.assertEqual(valid_autodev_targets(AutoDevState.ROLLED_BACK), frozenset())

    def test_ready_to_merge_does_not_transition_to_merged(self):
        # Merging is another authority's act; this machine has no such state.
        self.assertNotIn("MERGED", {s.name for s in AutoDevState})
        targets = valid_autodev_targets(AutoDevState.READY_TO_MERGE)
        self.assertEqual(targets, frozenset({AutoDevState.ROLLED_BACK, AutoDevState.REJECTED}))

    def test_a_reason_is_mandatory(self):
        with self.assertRaises(AutoDevError):
            advance(started(), AutoDevState.PLANNING, reason="   ")

    def test_history_records_each_hop(self):
        run = walk_to_review(started())
        self.assertEqual(
            [h.target for h in run.history],
            [AutoDevState.PLANNING, AutoDevState.BRANCH_CREATED, AutoDevState.IMPLEMENTING,
             AutoDevState.TESTING, AutoDevState.BENCHMARKING, AutoDevState.REVIEW],
        )

    def test_rollback_is_available_from_every_working_state(self):
        for state in (AutoDevState.BRANCH_CREATED, AutoDevState.IMPLEMENTING,
                      AutoDevState.TESTING, AutoDevState.BENCHMARKING,
                      AutoDevState.REVIEW, AutoDevState.READY_TO_MERGE):
            with self.subTest(state=state):
                self.assertIn(AutoDevState.ROLLED_BACK, valid_autodev_targets(state))

    def test_rejection_is_reachable_from_every_working_state(self):
        for state in (AutoDevState.PLANNING, AutoDevState.BRANCH_CREATED,
                      AutoDevState.IMPLEMENTING, AutoDevState.TESTING,
                      AutoDevState.BENCHMARKING, AutoDevState.REVIEW):
            with self.subTest(state=state):
                self.assertIn(AutoDevState.REJECTED, valid_autodev_targets(state))

    def test_reject_and_roll_back_helpers(self):
        run = advance(started(), AutoDevState.PLANNING, reason="p")
        self.assertEqual(reject(run, reason="bad plan").state, AutoDevState.REJECTED)
        branched = advance(run, AutoDevState.BRANCH_CREATED, reason="b")
        self.assertEqual(roll_back(branched, reason="regression").state, AutoDevState.ROLLED_BACK)


class PermissionCeilingTests(unittest.TestCase):
    def _ready(self):
        return advance(all_gates_passed(walk_to_review(started())),
                       AutoDevState.READY_TO_MERGE, reason="green")

    def test_the_automation_cannot_approve_itself(self):
        for actor in AUTOMATION_ACTORS:
            with self.subTest(actor=actor):
                with self.assertRaises(AutoDevError):
                    approve(self._ready(), actor=actor)

    def test_automation_actor_check_is_case_insensitive(self):
        with self.assertRaises(AutoDevError):
            approve(self._ready(), actor="Auto_Dev")

    def test_a_human_may_approve(self):
        run = approve(self._ready(), actor="maintainer")
        self.assertEqual(run.approved_by, "maintainer")
        self.assertTrue(run.can_merge)

    def test_an_unapproved_ready_run_may_not_merge(self):
        run = self._ready()
        self.assertTrue(run.can_propose)
        self.assertFalse(run.can_merge)

    def test_approval_requires_ready_state(self):
        with self.assertRaises(AutoDevError):
            approve(walk_to_review(started()), actor="maintainer")

    def test_an_empty_actor_is_refused(self):
        with self.assertRaises(AutoDevError):
            approve(self._ready(), actor="  ")

    def test_the_run_claims_no_merge_or_routing_authority(self):
        run = started()
        self.assertFalse(run.merge_authority)
        self.assertFalse(run.routing_authority)
        self.assertFalse(run.reasoning_authority)

    def test_run_is_json_safe(self):
        import json
        payload = approve(self._ready(), actor="maintainer").to_dict()
        decoded = json.loads(json.dumps(payload))
        self.assertEqual(decoded["state"], "AUTO_DEV_READY_TO_MERGE")
        self.assertTrue(decoded["can_merge"])
        self.assertFalse(decoded["merge_authority"])


if __name__ == "__main__":
    unittest.main()
