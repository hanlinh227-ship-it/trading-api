"""Residency tiers: a commitment of real memory, so it must be earned.

The tier is a policy target, not a lifecycle state - `ResidencyState` already
owns where an artifact physically is, and these tests pin that no second
lifecycle was introduced. The rest are the ways memory could be committed to a
model that has not earned it.
"""

import json
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.local_runtime.residency import ResidencyState
from AI_SKILL_LIBRARY.v4.local_runtime.residency_policy import (
    ARCHIVED,
    COLD,
    HOT,
    TARGET_STATE,
    WARM,
    ResidencyCandidate,
    hot_budget_mb,
    plan_residency,
)
from AI_SKILL_LIBRARY.v4.local_runtime.resources import PRESSURE_THRESHOLD

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "CHECKPOINTS/evidence/RESIDENCY_PLAN.json"


def candidate(model_id, ram, capability, warm_ms, cold_ms=1000.0):
    return ResidencyCandidate(model_id=model_id, family="f", peak_ram_mb=ram,
                              capability=capability, warm_inference_ms=warm_ms,
                              cold_load_ms=cold_ms)


class VocabularyTests(unittest.TestCase):
    def test_every_tier_targets_an_existing_residency_state(self):
        """No second lifecycle: each tier names a state that already exists."""
        for tier, state in TARGET_STATE.items():
            with self.subTest(tier=tier):
                self.assertIn(state, {s.value for s in ResidencyState})

    def test_all_four_tiers_are_mapped(self):
        self.assertEqual(set(TARGET_STATE), {HOT, WARM, COLD, ARCHIVED})


class BudgetTests(unittest.TestCase):
    def test_the_budget_is_the_existing_pressure_watermark(self):
        """Not a fresh constant - the scheduler already refuses past this."""
        self.assertEqual(hot_budget_mb(1000.0), round(1000.0 * PRESSURE_THRESHOLD, 2))

    def test_unknown_host_memory_yields_no_budget(self):
        self.assertIsNone(hot_budget_mb(None))
        self.assertIsNone(hot_budget_mb(0))

    def test_nothing_is_made_hot_when_host_memory_is_unknown(self):
        """Committing memory you cannot measure is guessing."""
        plan = plan_residency([candidate("m", 100.0, 0.9, 100.0)], host_ram_mb=None)
        self.assertEqual(plan.hot, ())
        self.assertEqual(plan.tier("m"), COLD)


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.fast = candidate("fast", 1000.0, 0.70, 100.0)
        self.strong = candidate("strong", 2000.0, 0.95, 900.0)
        self.middle = candidate("middle", 1500.0, 0.80, 400.0)

    def test_hot_holds_a_fast_worker_and_a_strong_one(self):
        """The trade the measurements expose: the best model is the slowest."""
        plan = plan_residency([self.middle, self.strong, self.fast], host_ram_mb=16000.0)
        self.assertEqual(set(plan.hot), {"fast", "strong"})
        self.assertEqual(plan.tier("middle"), WARM)

    def test_a_model_that_would_exceed_the_budget_is_not_promoted(self):
        huge = candidate("huge", 100000.0, 0.99, 50.0)
        plan = plan_residency([huge, self.fast], host_ram_mb=4000.0)
        self.assertNotIn("huge", plan.hot)
        self.assertLessEqual(plan.committed_mb, plan.hot_budget_mb)

    def test_the_committed_total_never_exceeds_the_budget(self):
        models = [candidate(f"m{i}", 3000.0, 0.5 + i / 20, 100.0 * (i + 1)) for i in range(6)]
        plan = plan_residency(models, host_ram_mb=8000.0)
        self.assertLessEqual(plan.committed_mb, plan.hot_budget_mb)

    def test_an_unmeasured_model_is_never_promoted(self):
        """Residency spends real memory; an unmeasured model has earned none."""
        unmeasured = ResidencyCandidate("unknown", "f", None, None, None, None)
        plan = plan_residency([unmeasured, self.fast], host_ram_mb=16000.0)
        self.assertEqual(plan.tier("unknown"), COLD)
        self.assertIn("no digest-bound capability measurement", 
                      next(a.reason for a in plan.assignments if a.model_id == "unknown"))

    def test_a_model_measured_but_missing_ram_is_not_promoted(self):
        partial = ResidencyCandidate("partial", "f", None, 0.99, 10.0, None)
        plan = plan_residency([partial, self.fast], host_ram_mb=16000.0)
        self.assertEqual(plan.tier("partial"), COLD)

    def test_every_assignment_explains_itself(self):
        plan = plan_residency([self.fast, self.strong, self.middle], host_ram_mb=16000.0)
        for assignment in plan.assignments:
            with self.subTest(model_id=assignment.model_id):
                self.assertTrue(assignment.reason.strip())

    def test_a_held_back_model_says_which_reason_applies(self):
        """Budget-limited and not-worth-it are different, and recoverable
        differently: freeing memory promotes the first, never the second."""
        plan = plan_residency([self.fast, self.strong, self.middle], host_ram_mb=16000.0)
        reason = next(a.reason for a in plan.assignments if a.model_id == "middle")
        self.assertIn("neither the fastest nor the strongest", reason)
        self.assertNotIn("budget", reason)

    def test_planning_loads_nothing(self):
        plan = plan_residency([self.fast], host_ram_mb=16000.0)
        self.assertTrue(plan.to_dict()["plan_only_nothing_loaded"])


class CommittedPlanTests(unittest.TestCase):
    def setUp(self):
        if not PLAN.is_file():
            self.skipTest("no residency plan committed")
        self.plan = json.loads(PLAN.read_text(encoding="utf-8"))

    def test_the_committed_plan_fits_its_own_budget(self):
        self.assertLessEqual(self.plan["committed_mb"], self.plan["hot_budget_mb"])

    def test_hot_is_bounded(self):
        """Hundreds of models may be admitted; two may be resident."""
        self.assertLessEqual(len(self.plan["hot"]), 2)

    def test_every_hot_model_was_measured(self):
        for assignment in self.plan["assignments"]:
            if assignment["tier"] == HOT:
                with self.subTest(model_id=assignment["model_id"]):
                    self.assertIsNotNone(assignment["measured_capability"])
                    self.assertIsNotNone(assignment["peak_ram_mb"])

    def test_all_models_together_would_not_fit(self):
        """The constraint that makes tiering necessary rather than tidy."""
        total = sum(a["peak_ram_mb"] or 0 for a in self.plan["assignments"])
        self.assertGreater(total, self.plan["hot_budget_mb"])


if __name__ == "__main__":
    unittest.main()
