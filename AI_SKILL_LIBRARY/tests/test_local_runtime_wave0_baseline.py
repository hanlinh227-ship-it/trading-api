"""Wave 0 baseline: the verifiers, and the refusal to freeze on a partial pass.

Every verifier here is one a lazy implementation would have returned True from.
The tests are written the other way round - each one is a specific wrong answer
that must be caught - because twelve verifiers that cannot fail would freeze a
baseline measuring nothing, and the freeze is meant to be the hard part.
"""

import json
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.control_plane.benchmark import freeze_baseline, ingest_wave0, load_wave0
from AI_SKILL_LIBRARY.v4.local_runtime.wave0_baseline import (
    load_prompts,
    prompts_hash,
    safe_arithmetic_value,
    verify,
)

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "CHECKPOINTS/evidence/WAVE0_BASELINE_EVIDENCE.json"


class PromptSetTests(unittest.TestCase):
    def test_every_canonical_task_has_a_prompt(self):
        ids = {task["task_id"] for task in load_wave0(ROOT)}
        self.assertEqual(set(load_prompts()["prompts"]), ids)

    def test_the_prompt_set_is_hash_stable(self):
        self.assertEqual(prompts_hash(load_prompts()), prompts_hash(load_prompts()))

    def test_editing_a_prompt_changes_the_hash(self):
        data = load_prompts()
        before = prompts_hash(data)
        data["prompts"]["gr-01"]["prompt"] += " Think step by step."
        self.assertNotEqual(before, prompts_hash(data))

    def test_the_vietnamese_prompts_are_actually_in_vietnamese(self):
        """v1's were diacritic-stripped, which is not Vietnamese text.

        That made the Vietnamese tasks an unfair test rather than a
        measurement, since the verifier requires a Vietnamese answer.
        """
        prompts = load_prompts()["prompts"]
        for task_id in ("vi-01", "vi-02", "vi-03"):
            text = prompts[task_id]["prompt"]
            self.assertTrue(any(not ch.isascii() for ch in text), task_id)


class SafeExpressionTests(unittest.TestCase):
    """Model output is text. This is the one place it would be run."""

    def test_arithmetic_evaluates(self):
        self.assertEqual(safe_arithmetic_value("12 + 30")[0], 42)
        self.assertEqual(safe_arithmetic_value("100 - 45")[0], 55)

    def test_a_call_is_refused_without_evaluation(self):
        value, why = safe_arithmetic_value('__import__("os").system("id")')
        self.assertIsNone(value)
        self.assertIn("Call", why)

    def test_a_bare_name_is_refused(self):
        value, why = safe_arithmetic_value("open")
        self.assertIsNone(value)
        self.assertIn("Name", why)

    def test_an_attribute_access_is_refused(self):
        self.assertIsNone(safe_arithmetic_value("(1).__class__")[0])

    def test_nonsense_is_refused_rather_than_raising(self):
        value, why = safe_arithmetic_value("this is not python")
        self.assertIsNone(value)
        self.assertTrue(why)

    def test_an_overlong_expression_is_refused(self):
        self.assertIsNone(safe_arithmetic_value("1+" * 200 + "1")[0])

    def test_division_by_zero_is_a_refusal_not_a_crash(self):
        value, why = safe_arithmetic_value("1/0")
        self.assertIsNone(value)
        self.assertIn("evaluation_failed", why)


class VerifierTests(unittest.TestCase):
    def test_math_checks_the_number(self):
        self.assertTrue(verify("MATH", {"expected_number": 60}, " 60")["passed"])
        self.assertFalse(verify("MATH", {"expected_number": 60}, " 59")["passed"])
        self.assertFalse(verify("MATH", {"expected_number": 60}, " sixty-ish")["passed"])

    def test_coding_computes_rather_than_reads(self):
        self.assertTrue(verify("CODING", {"expected_value": 42}, " 12 + 30")["passed"])
        self.assertFalse(verify("CODING", {"expected_value": 42}, " 12 + 31")["passed"])

    def test_coding_does_not_accept_the_answer_restated(self):
        """"42" as prose is not an expression that computes 42."""
        self.assertTrue(verify("CODING", {"expected_value": 42}, "42")["passed"])
        self.assertFalse(verify("CODING", {"expected_value": 42}, " the answer is 42")["passed"])

    def test_structured_output_must_parse(self):
        spec = {"required_keys": ["name", "age"]}
        self.assertTrue(verify("STRUCTURED_OUTPUT", spec, ' {"name": "Bob", "age": 41}')["passed"])
        self.assertIn("missing_key:age",
                      verify("STRUCTURED_OUTPUT", spec, ' {"name": "Bob"}')["failures"])
        self.assertFalse(verify("STRUCTURED_OUTPUT", spec, ' {"name": }')["passed"])
        self.assertFalse(verify("STRUCTURED_OUTPUT", spec, " name Bob age 41")["passed"])

    def test_a_vietnamese_task_is_not_passed_by_an_english_answer(self):
        spec = {"any_of": ["bảy", "7"]}
        self.assertIn("answer_is_not_in_vietnamese",
                      verify("VIETNAMESE", spec, " 7 days a week")["failures"])
        self.assertTrue(verify("VIETNAMESE", spec, " Một tuần có bảy ngày.")["passed"])

    def test_asserting_both_an_answer_and_its_contradiction_fails(self):
        spec = {"any_of": ["Tokyo"], "must_not_contain": ["Kyoto"]}
        self.assertTrue(verify("GENERAL_REASONING", spec, " Tokyo")["passed"])
        self.assertFalse(verify("GENERAL_REASONING", spec, " Tokyo or Kyoto")["passed"])

    def test_an_empty_answer_never_passes_any_category(self):
        for category in ("MATH", "CODING", "STRUCTURED_OUTPUT", "VIETNAMESE", "GENERAL_REASONING"):
            self.assertFalse(verify(category, {}, "   ")["passed"], category)

    def test_an_unknown_category_fails_closed(self):
        self.assertFalse(verify("ASTROLOGY", {}, "anything")["passed"])


class FreezeGateTests(unittest.TestCase):
    """A partial pass must not freeze a baseline."""

    def rows(self, **override):
        tasks = load_wave0(ROOT)
        base = {
            "model_id": "m", "family": "f", "revision": "a" * 40, "artifact_hash": "b" * 64,
            "quantization": "Q8_0", "runtime": "llama.cpp", "runtime_version": "1",
            "environment_fingerprint": "e", "prompt_version": "p", "benchmark_version": "wave0-v1",
            "real_inference": True, "reproducible": True, "verifier_passed": True,
            "failure": None, "raw_run_ref": "r", "cold_metrics": {}, "warm_metrics": {},
        }
        return tasks, [{**base, "task_id": t["task_id"], "category": t["category"], **override}
                       for t in tasks]

    def test_a_clean_wave_is_ready(self):
        tasks, runs = self.rows()
        self.assertTrue(ingest_wave0(tasks, runs)["ready_to_freeze"])

    def test_one_failed_verifier_blocks_the_freeze(self):
        tasks, runs = self.rows()
        runs[0]["verifier_passed"] = False
        report = ingest_wave0(tasks, runs)
        self.assertFalse(report["ready_to_freeze"])
        with self.assertRaises(ValueError):
            freeze_baseline(report)

    def test_a_non_reproducible_run_blocks_the_freeze(self):
        tasks, runs = self.rows()
        runs[3]["reproducible"] = False
        self.assertFalse(ingest_wave0(tasks, runs)["ready_to_freeze"])


class CommittedBaselineEvidenceTests(unittest.TestCase):
    def setUp(self):
        if not EVIDENCE.is_file():
            self.skipTest("no baseline evidence committed")
        self.evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))

    def test_all_twelve_canonical_tasks_were_run(self):
        ids = {run["task_id"] for run in self.evidence["wave_report"]["runs"]}
        self.assertEqual(ids, {task["task_id"] for task in load_wave0(ROOT)})

    def test_every_run_was_reproducible_after_the_cache_reset_fix(self):
        """Two of twelve diverged before the KV cache was cleared between runs."""
        self.assertEqual(self.evidence["reproducible"], self.evidence["total"])

    def test_the_status_matches_the_count_rather_than_being_asserted(self):
        report = self.evidence["wave_report"]
        expected = "READY" if report["ready_to_freeze"] else "NOT_READY"
        self.assertEqual(self.evidence["baseline_status"], expected)

    def test_no_baseline_is_frozen_while_any_task_fails(self):
        if self.evidence["passed"] < self.evidence["total"]:
            self.assertNotIn("baseline", self.evidence)
            self.assertEqual(self.evidence["baseline_status"], "NOT_READY")

    def test_failures_are_retained_with_their_reasons(self):
        for run in self.evidence["wave_report"]["runs"]:
            if not run["verifier_passed"]:
                self.assertTrue(run["failure"]["verifier_failures"], run["task_id"])


if __name__ == "__main__":
    unittest.main()
