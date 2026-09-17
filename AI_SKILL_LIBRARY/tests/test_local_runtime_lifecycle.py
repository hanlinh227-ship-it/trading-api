import unittest

from AI_SKILL_LIBRARY.v4.local_runtime.lifecycle import (
    LifecycleError,
    ModelLifecycle,
    ModelState,
    is_terminal,
    transition_reason,
    valid_targets,
)


class LifecycleGraphTests(unittest.TestCase):
    def test_every_state_except_retired_has_an_exit(self):
        for state in ModelState:
            if state is ModelState.RETIRED:
                self.assertEqual(valid_targets(state), frozenset())
            else:
                self.assertTrue(valid_targets(state), state)

    def test_every_state_except_discovered_is_reachable(self):
        reached = {ModelState.DISCOVERED}
        frontier = [ModelState.DISCOVERED]
        while frontier:
            for target in valid_targets(frontier.pop()):
                if target not in reached:
                    reached.add(target)
                    frontier.append(target)
        self.assertEqual(reached, set(ModelState))

    def test_retired_is_the_only_terminal_state(self):
        self.assertTrue(is_terminal(ModelState.RETIRED))
        for state in ModelState:
            if state is not ModelState.RETIRED:
                self.assertFalse(is_terminal(state), state)


class ValidLifecycleTests(unittest.TestCase):
    def test_canonical_cold_start_path(self):
        lifecycle = ModelLifecycle("qwen3-8b")
        for target in (
            ModelState.REGISTERED,
            ModelState.APPROVED,
            ModelState.AVAILABLE,
            ModelState.DOWNLOADING,
            ModelState.CACHED,
            ModelState.WARM,
            ModelState.RUNNING,
        ):
            lifecycle.transition(target, reason="test")
        self.assertIs(lifecycle.state, ModelState.RUNNING)
        self.assertTrue(lifecycle.is_loaded)
        self.assertTrue(lifecycle.has_local_artifact)

    def test_sleep_then_wake_cycle(self):
        lifecycle = ModelLifecycle("qwen3-8b", state=ModelState.RUNNING)
        lifecycle.transition(ModelState.WARM, reason="idle")
        lifecycle.transition(ModelState.SLEEPING, reason="idle_timeout")
        self.assertFalse(lifecycle.is_loaded)
        self.assertTrue(lifecycle.has_local_artifact)
        lifecycle.transition(ModelState.WARM, reason="wake")
        lifecycle.transition(ModelState.RUNNING, reason="task")
        self.assertIs(lifecycle.state, ModelState.RUNNING)

    def test_broken_may_degrade_or_quarantine_per_policy(self):
        self.assertIn(ModelState.DEGRADED, valid_targets(ModelState.BROKEN))
        self.assertIn(ModelState.QUARANTINED, valid_targets(ModelState.BROKEN))

    def test_evicted_model_must_be_reacquired_not_resumed(self):
        lifecycle = ModelLifecycle("qwen3-8b", state=ModelState.EVICTED)
        self.assertFalse(lifecycle.has_local_artifact)
        with self.assertRaises(LifecycleError):
            lifecycle.transition(ModelState.WARM, reason="shortcut")
        lifecycle.transition(ModelState.AVAILABLE, reason="reacquire")
        lifecycle.transition(ModelState.DOWNLOADING, reason="reacquire")

    def test_history_records_every_accepted_hop(self):
        lifecycle = ModelLifecycle("qwen3-8b")
        lifecycle.transition(ModelState.REGISTERED, reason="registry sync")
        lifecycle.transition(ModelState.APPROVED, reason="license verified")
        self.assertEqual(
            [(entry.source, entry.target) for entry in lifecycle.history],
            [
                (ModelState.DISCOVERED, ModelState.REGISTERED),
                (ModelState.REGISTERED, ModelState.APPROVED),
            ],
        )
        self.assertEqual(lifecycle.history[-1].reason, "license verified")


class InvalidTransitionTests(unittest.TestCase):
    def test_discovered_cannot_run(self):
        lifecycle = ModelLifecycle("rogue")
        with self.assertRaises(LifecycleError):
            lifecycle.transition(ModelState.RUNNING, reason="hardcoded enable")
        self.assertIs(lifecycle.state, ModelState.DISCOVERED)
        self.assertEqual(lifecycle.history, ())

    def test_unapproved_model_cannot_download(self):
        for state in (ModelState.DISCOVERED, ModelState.REGISTERED):
            with self.subTest(state=state):
                lifecycle = ModelLifecycle("rogue", state=state)
                with self.assertRaises(LifecycleError):
                    lifecycle.transition(ModelState.DOWNLOADING, reason="jump the gate")

    def test_partial_download_is_never_usable(self):
        lifecycle = ModelLifecycle("qwen3-8b", state=ModelState.DOWNLOADING)
        self.assertFalse(lifecycle.has_local_artifact)
        self.assertFalse(lifecycle.is_loaded)
        for target in (ModelState.WARM, ModelState.RUNNING, ModelState.SLEEPING):
            with self.subTest(target=target):
                with self.assertRaises(LifecycleError):
                    lifecycle.transition(target, reason="use partial artifact")

    def test_blocked_model_cannot_be_woken_directly(self):
        lifecycle = ModelLifecycle("blocked-model", state=ModelState.BLOCKED)
        for target in (ModelState.RUNNING, ModelState.WARM, ModelState.CACHED):
            with self.subTest(target=target):
                with self.assertRaises(LifecycleError):
                    lifecycle.transition(target, reason="ignore the block")
        lifecycle.transition(ModelState.REGISTERED, reason="re-review cleared")

    def test_retired_is_final(self):
        lifecycle = ModelLifecycle("old", state=ModelState.RETIRED)
        for target in ModelState:
            with self.subTest(target=target):
                with self.assertRaises(LifecycleError):
                    lifecycle.transition(target, reason="resurrect")

    def test_self_transition_rejected(self):
        lifecycle = ModelLifecycle("qwen3-8b", state=ModelState.RUNNING)
        with self.assertRaises(LifecycleError):
            lifecycle.transition(ModelState.RUNNING, reason="noop")

    def test_reason_is_mandatory(self):
        lifecycle = ModelLifecycle("qwen3-8b")
        with self.assertRaises(LifecycleError):
            lifecycle.transition(ModelState.REGISTERED, reason="  ")

    def test_error_names_the_legal_targets(self):
        lifecycle = ModelLifecycle("rogue")
        with self.assertRaises(LifecycleError) as caught:
            lifecycle.transition(ModelState.RUNNING, reason="x")
        self.assertIn("REGISTERED", str(caught.exception))

    def test_transition_reason_explains_rejection_without_mutating(self):
        self.assertIsNone(transition_reason(ModelState.CACHED, ModelState.WARM))
        self.assertIsInstance(transition_reason(ModelState.DISCOVERED, ModelState.RUNNING), str)


class BlockedPrecedenceTests(unittest.TestCase):
    def test_any_live_state_can_be_blocked(self):
        for state in ModelState:
            if state in (ModelState.BLOCKED, ModelState.RETIRED):
                continue
            with self.subTest(state=state):
                self.assertIn(ModelState.BLOCKED, valid_targets(state))

    def test_policy_block_is_accepted_from_running(self):
        lifecycle = ModelLifecycle("qwen3-8b", state=ModelState.RUNNING)
        lifecycle.transition(ModelState.BLOCKED, reason="license revoked")
        self.assertIs(lifecycle.state, ModelState.BLOCKED)
        self.assertFalse(lifecycle.is_loaded)


if __name__ == "__main__":
    unittest.main()
