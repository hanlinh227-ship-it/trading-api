"""Wave 0: the benchmark harness, and the rule that a score must be earned.

Two things are under test and they guard different failures. The harness has to
count honestly - a partial run must not pass for a whole one, and a suite must
not be editable without the score noticing. The registry rule has to make a
fabricated number impossible to write down, because the Model Mesh admits a
worker by comparing that number against a floor: an unearned score is not an
optimistic estimate, it is the gate itself, bypassed.
"""

import copy
import json
import unittest
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.local_runtime.benchmark import (
    BENCHMARKS_DIR,
    BenchmarkError,
    BenchmarkItem,
    BenchmarkSuite,
    STATUS_COMPLETE,
    STATUS_DEGRADED,
    extract_choice,
    load_suite,
    run_suite,
    score_item,
)
from AI_SKILL_LIBRARY.v4.tools.validate_open_model_universe import _capability_refusals

ROOT = Path(__file__).resolve().parents[2]
SUITE_PATH = BENCHMARKS_DIR / "local_core_reasoning_v1.json"
NOW = "2026-09-17T00:00:00+00:00"


def suite() -> BenchmarkSuite:
    return load_suite(SUITE_PATH)


def live_record() -> dict:
    registry = yaml.safe_load(
        (ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml").read_text(encoding="utf-8")
    )
    return registry["models"][0]


class SuiteIntegrityTests(unittest.TestCase):
    def test_the_shipped_suite_loads_and_is_self_consistent(self):
        s = suite()
        self.assertTrue(s.items)
        for item in s.items:
            if item.multiple_choice:
                self.assertIn(item.answer, {label for label, _ in item.choices})

    def test_no_single_letter_answer_can_clear_the_mesh_floor(self):
        """A degenerate answerer must fail, or the suite measures nothing.

        If one letter were correct often enough, a model that emits that letter
        every time would clear the capability floor without reasoning at all.
        The labels are balanced so the best constant strategy scores well under
        it.
        """
        from AI_SKILL_LIBRARY.v4.tools.local_runtime_wave0 import mesh_capability_floor

        s = suite()
        for label in "ABCD":
            constant = sum(
                1 for item in s.items if item.multiple_choice and item.answer.upper() == label
            )
            self.assertLess(constant / len(s.items), mesh_capability_floor())

    def test_editing_the_suite_changes_its_hash(self):
        """A score is bound to the exact suite that produced it."""
        s = suite()
        before = s.content_hash
        reworded = BenchmarkSuite(
            suite_id=s.suite_id, version=s.version, capability=s.capability,
            description=s.description, prefix=s.prefix + " Think carefully.",
            max_tokens=s.max_tokens, items=s.items, decoding=s.decoding,
        )
        self.assertNotEqual(before, reworded.content_hash)

        dropped = BenchmarkSuite(
            suite_id=s.suite_id, version=s.version, capability=s.capability,
            description=s.description, prefix=s.prefix, max_tokens=s.max_tokens,
            items=s.items[:-1], decoding=s.decoding,
        )
        self.assertNotEqual(before, dropped.content_hash)

    def test_the_hash_is_stable_across_loads(self):
        self.assertEqual(suite().content_hash, suite().content_hash)

    def test_a_suite_with_no_items_is_refused(self):
        with self.assertRaises(BenchmarkError):
            BenchmarkSuite(suite_id="x", version="1", capability="c", description="",
                           prefix="p", max_tokens=4, items=())

    def test_duplicate_item_ids_are_refused(self):
        item = BenchmarkItem(item_id="a", capability="c", question="q", answer="A",
                             choices=(("A", "x"), ("B", "y")))
        with self.assertRaises(BenchmarkError):
            BenchmarkSuite(suite_id="x", version="1", capability="c", description="",
                           prefix="p", max_tokens=4, items=(item, item))

    def test_an_answer_outside_the_choices_is_refused(self):
        item = BenchmarkItem(item_id="a", capability="c", question="q", answer="D",
                             choices=(("A", "x"), ("B", "y")))
        with self.assertRaises(BenchmarkError):
            BenchmarkSuite(suite_id="x", version="1", capability="c", description="",
                           prefix="p", max_tokens=4, items=(item,))


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.mcq = BenchmarkItem(item_id="m", capability="c", question="q", answer="B",
                                 choices=(("A", "x"), ("B", "y")))
        self.short = BenchmarkItem(item_id="s", capability="c", question="q", answer="Paris")

    def test_the_first_letter_is_the_answer(self):
        self.assertTrue(score_item(self.mcq, " B"))
        self.assertTrue(score_item(self.mcq, "B) y"))
        self.assertFalse(score_item(self.mcq, " A, though B is also plausible"))

    def test_an_empty_generation_scores_nothing(self):
        self.assertIsNone(extract_choice(""))
        self.assertFalse(score_item(self.mcq, ""))
        self.assertFalse(score_item(self.short, ""))

    def test_short_answers_match_on_word_boundaries(self):
        self.assertTrue(score_item(self.short, " Paris"))
        self.assertTrue(score_item(self.short, "paris.\n"))
        self.assertFalse(score_item(self.short, " Parisian"))

    def test_naming_a_banned_distractor_fails_the_item(self):
        item = BenchmarkItem(item_id="s", capability="c", question="q", answer="Paris",
                             must_not_contain=("Lyon",))
        self.assertTrue(score_item(item, " Paris"))
        self.assertFalse(score_item(item, " Paris or Lyon"))


class RunTests(unittest.TestCase):
    def small(self) -> BenchmarkSuite:
        return BenchmarkSuite(
            suite_id="t", version="1", capability="text_reasoning", description="",
            prefix="p", max_tokens=4,
            items=(
                BenchmarkItem("i1", "text_reasoning", "q1", "A", (("A", "x"), ("B", "y"))),
                BenchmarkItem("i2", "text_reasoning", "q2", "B", (("A", "x"), ("B", "y"))),
            ),
        )

    def run_with(self, generate):
        return run_suite(self.small(), generate, model_id="m", artifact_sha256="0" * 64,
                         backend_version="test", started_at=NOW)

    def test_a_clean_run_is_complete_and_promotable(self):
        run = self.run_with(lambda prompt, n, d: "A" if "q1" in prompt else "B")
        self.assertEqual(run.status, STATUS_COMPLETE)
        self.assertEqual(run.score, 1.0)
        self.assertTrue(run.promotable)

    def test_every_raw_generation_is_kept(self):
        run = self.run_with(lambda prompt, n, d: "A")
        self.assertEqual([r.generation for r in run.results], ["A", "A"])
        self.assertEqual(run.score, 0.5)

    def test_an_erroring_item_does_not_abort_the_run(self):
        def flaky(prompt, n, d):
            if "q1" in prompt:
                raise RuntimeError("engine died")
            return "B"

        run = self.run_with(flaky)
        self.assertEqual(run.attempted, 2)
        self.assertEqual(run.errors, 1)
        self.assertIn("engine died", run.results[0].error)

    def test_a_degraded_run_cannot_be_promoted(self):
        """The failure this exists to stop.

        One item crashing and one passing is 50% of the items that ran, and
        looks identical to a model that genuinely got half of them right. The
        score divides by attempted, and the run refuses promotion outright.
        """
        def flaky(prompt, n, d):
            if "q1" in prompt:
                raise RuntimeError("boom")
            return "B"

        run = self.run_with(flaky)
        self.assertEqual(run.status, STATUS_DEGRADED)
        self.assertEqual(run.score, 0.5)
        self.assertFalse(run.promotable)

    def test_the_run_records_which_suite_it_measured(self):
        run = self.run_with(lambda prompt, n, d: "A")
        self.assertEqual(run.suite_hash, self.small().content_hash)
        self.assertFalse(run.to_dict()["is_public_benchmark"])


class RegistryEvidenceRuleTests(unittest.TestCase):
    """A declared score above zero must be backed by a matching measurement."""

    def setUp(self):
        self.record = live_record()

    def test_the_live_record_satisfies_its_own_rule(self):
        self.assertEqual(_capability_refusals(self.record, 0), [])

    def test_a_score_with_no_evidence_is_refused(self):
        record = copy.deepcopy(self.record)
        record.pop("capability_evidence", None)
        self.assertTrue(_capability_refusals(record, 0))

    def test_a_score_inflated_above_its_evidence_is_refused(self):
        record = copy.deepcopy(self.record)
        record["capabilities"]["text_reasoning"] = 0.95
        refusals = _capability_refusals(record, 0)
        self.assertTrue(any("declares 0.95" in r for r in refusals), refusals)

    def test_evidence_from_a_partial_run_is_refused(self):
        record = copy.deepcopy(self.record)
        record["capability_evidence"]["text_reasoning"]["errors"] = 2
        refusals = _capability_refusals(record, 0)
        self.assertTrue(any("partial run" in r for r in refusals), refusals)

    def test_evidence_measured_on_other_bytes_is_refused(self):
        """A capability cannot be inherited by a different artifact.

        This is the rule that stops one admitted model's score being pasted
        onto the next one to skip benchmarking it.
        """
        record = copy.deepcopy(self.record)
        record["capability_evidence"]["text_reasoning"]["artifact_sha256"] = "1" * 64
        refusals = _capability_refusals(record, 0)
        self.assertTrue(any("different artifact bytes" in r for r in refusals), refusals)

    def test_a_newly_declared_capability_needs_its_own_measurement(self):
        record = copy.deepcopy(self.record)
        record["capabilities"]["planning"] = 0.8
        refusals = _capability_refusals(record, 0)
        self.assertTrue(any("planning" in r for r in refusals), refusals)

    def test_declaring_zero_needs_no_evidence(self):
        """Otherwise a newly discovered model could not be registered at all."""
        record = copy.deepcopy(self.record)
        record["capabilities"] = {"text_reasoning": 0.0}
        record.pop("capability_evidence", None)
        self.assertEqual(_capability_refusals(record, 0), [])


class WaveZeroEvidenceTests(unittest.TestCase):
    """The committed evidence must actually support what the registry claims."""

    def setUp(self):
        path = ROOT / "CHECKPOINTS/evidence/WAVE0_CAPABILITY_EVIDENCE.json"
        if not path.is_file():
            self.skipTest("no Wave 0 evidence committed")
        self.evidence = json.loads(path.read_text(encoding="utf-8"))
        self.record = live_record()

    def test_the_registry_score_is_the_measured_score(self):
        run = self.evidence["benchmark_run"]
        self.assertEqual(self.record["capabilities"]["text_reasoning"], run["score"])

    def test_the_score_is_the_count_of_the_raw_results(self):
        """Recomputed from the generations, not taken on trust."""
        run = self.evidence["benchmark_run"]
        recounted = sum(1 for r in run["results"] if r["passed"]) / len(run["results"])
        self.assertAlmostEqual(run["score"], recounted, places=6)

    def test_every_item_kept_its_generation(self):
        for row in self.evidence["benchmark_run"]["results"]:
            self.assertTrue(row["generation"] or row["error"], row)

    def test_the_run_measured_the_suite_that_is_checked_in(self):
        self.assertEqual(self.evidence["benchmark_run"]["suite_hash"], suite().content_hash)

    def test_the_evidence_is_bound_to_the_registered_artifact(self):
        self.assertEqual(
            self.evidence["artifact_identity"]["artifact_sha256"],
            self.record["artifact_identity"]["sha256"],
        )

    def test_it_is_not_claimed_as_a_public_benchmark(self):
        self.assertFalse(self.evidence["benchmark_run"]["is_public_benchmark"])
        self.assertEqual(self.record["quality_class"], "locally_measured")


if __name__ == "__main__":
    unittest.main()
