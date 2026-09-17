import unittest

from AI_SKILL_LIBRARY.v4.local_runtime.lifecycle import ModelState
from AI_SKILL_LIBRARY.v4.local_runtime.residency import (
    GOVERNANCE_VERDICTS,
    IN_MEMORY,
    ON_DISK,
    ResidencyState,
    admit_to_residency,
    residency_transition_reason,
    to_model_state,
    valid_residency_targets,
)


class VocabularySeparationTests(unittest.TestCase):
    def test_no_governance_state_appears_in_the_residency_vocabulary(self):
        residency = {state.value for state in ResidencyState}
        for verdict in ("DISCOVERED", "REGISTERED", "APPROVED", "BLOCKED",
                        "QUARANTINED", "QUARANTINED_UPDATE", "RETIRED", "SUPERSEDED"):
            with self.subTest(verdict=verdict):
                self.assertNotIn(verdict, residency)

    def test_residency_names_what_governance_cannot(self):
        residency = {state.value for state in ResidencyState}
        for name in ("COLD", "ACQUIRING", "LOADING", "READY", "OFFLINE"):
            self.assertIn(name, residency)

    def test_every_residency_state_maps_into_the_artifact_lifecycle(self):
        for state in ResidencyState:
            with self.subTest(state=state):
                self.assertIsInstance(to_model_state(state), ModelState)

    def test_acquiring_is_not_on_disk_and_not_in_memory(self):
        self.assertNotIn(ResidencyState.ACQUIRING, ON_DISK)
        self.assertNotIn(ResidencyState.ACQUIRING, IN_MEMORY)

    def test_cold_is_not_on_disk(self):
        self.assertNotIn(ResidencyState.COLD, ON_DISK)


class GovernanceGateTests(unittest.TestCase):
    def test_blocked_does_not_project(self):
        decision = admit_to_residency("BLOCKED", artifact_admitted=True, runtime_eligible=True)
        self.assertIsNone(decision.state)
        self.assertFalse(decision.granted)

    def test_quarantined_does_not_project(self):
        self.assertIsNone(
            admit_to_residency("QUARANTINED", artifact_admitted=True, runtime_eligible=True).state
        )

    def test_quarantined_update_does_not_project(self):
        self.assertIsNone(
            admit_to_residency("QUARANTINED_UPDATE", artifact_admitted=True, runtime_eligible=True).state
        )

    def test_every_governance_verdict_refuses_even_with_perfect_evidence(self):
        for verdict in GOVERNANCE_VERDICTS:
            with self.subTest(verdict=verdict):
                decision = admit_to_residency(verdict, artifact_admitted=True, runtime_eligible=True)
                self.assertFalse(decision.granted)
                self.assertIn("verdict", decision.reasons[0])

    def test_approved_with_all_three_proofs_grants_cold(self):
        decision = admit_to_residency("APPROVED", artifact_admitted=True, runtime_eligible=True)
        self.assertEqual(decision.state, ResidencyState.COLD)

    def test_an_artifact_already_on_disk_enters_at_ready(self):
        decision = admit_to_residency(
            "APPROVED", artifact_admitted=True, runtime_eligible=True, artifact_on_disk=True
        )
        self.assertEqual(decision.state, ResidencyState.READY)

    def test_all_three_proofs_are_required(self):
        self.assertFalse(
            admit_to_residency("APPROVED", artifact_admitted=False, runtime_eligible=True).granted
        )
        self.assertFalse(
            admit_to_residency("APPROVED", artifact_admitted=True, runtime_eligible=False).granted
        )
        self.assertFalse(
            admit_to_residency("DISCOVERED", artifact_admitted=True, runtime_eligible=True).granted
        )

    def test_being_known_is_not_being_approved(self):
        for state in ("DISCOVERED", "REGISTERED"):
            with self.subTest(state=state):
                self.assertFalse(
                    admit_to_residency(state, artifact_admitted=True, runtime_eligible=True).granted
                )

    def test_every_missing_proof_is_named(self):
        decision = admit_to_residency("DISCOVERED", artifact_admitted=False, runtime_eligible=False)
        self.assertEqual(len(decision.reasons), 3)

    def test_a_missing_governance_state_is_refused(self):
        self.assertFalse(admit_to_residency("", artifact_admitted=True, runtime_eligible=True).granted)

    def test_the_decision_is_json_safe(self):
        import json
        payload = admit_to_residency("BLOCKED", artifact_admitted=True, runtime_eligible=True).to_dict()
        self.assertFalse(json.loads(json.dumps(payload))["granted"])


class ResidencyTransitionTests(unittest.TestCase):
    def test_the_cold_start_path(self):
        state = ResidencyState.COLD
        for target in (ResidencyState.ACQUIRING, ResidencyState.READY,
                       ResidencyState.LOADING, ResidencyState.WARM, ResidencyState.RUNNING):
            self.assertIsNone(residency_transition_reason(state, target), f"{state}->{target}")
            state = target

    def test_a_partial_transfer_can_never_become_loaded(self):
        for target in (ResidencyState.WARM, ResidencyState.RUNNING, ResidencyState.LOADING):
            with self.subTest(target=target):
                self.assertIsNotNone(residency_transition_reason(ResidencyState.ACQUIRING, target))

    def test_cold_cannot_jump_to_running(self):
        self.assertIsNotNone(residency_transition_reason(ResidencyState.COLD, ResidencyState.RUNNING))

    def test_an_offline_worker_re_proves_what_it_holds(self):
        self.assertEqual(valid_residency_targets(ResidencyState.OFFLINE), frozenset({ResidencyState.COLD}))

    def test_sleep_and_wake_are_both_legal(self):
        self.assertIsNone(residency_transition_reason(ResidencyState.WARM, ResidencyState.SLEEPING))
        self.assertIsNone(residency_transition_reason(ResidencyState.SLEEPING, ResidencyState.LOADING))

    def test_any_state_can_go_offline(self):
        for state in ResidencyState:
            if state is ResidencyState.OFFLINE:
                continue
            with self.subTest(state=state):
                self.assertIn(ResidencyState.OFFLINE, valid_residency_targets(state))

    def test_self_transition_is_refused(self):
        self.assertIsNotNone(residency_transition_reason(ResidencyState.WARM, ResidencyState.WARM))


if __name__ == "__main__":
    unittest.main()
