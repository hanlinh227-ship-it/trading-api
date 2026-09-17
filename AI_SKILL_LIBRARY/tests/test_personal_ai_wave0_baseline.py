import json
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.control_plane.benchmark import freeze_baseline, ingest_wave0, load_wave0


ROOT = Path(__file__).resolve().parents[2]


def run(task, *, real=True, passed=True):
    return {
        "task_id": task["task_id"], "category": task["category"],
        "model_id": "m", "family": "f", "revision": "a" * 40,
        "artifact_hash": "b" * 64, "quantization": "Q8_0",
        "runtime": "llama.cpp", "runtime_version": "1",
        "environment_fingerprint": "env:1", "prompt_version": "p1", "benchmark_version": "wave0-v1",
        "real_inference": real, "verifier_passed": passed, "reproducible": True,
        "cold_metrics": {"latency_ms": 100}, "warm_metrics": {"latency_ms": 50},
        "failure": None if passed else {"code": "VERIFY"}, "raw_run_ref": "run:" + task["task_id"],
    }


class Wave0Tests(unittest.TestCase):
    def test_composition_is_exactly_existing_twelve_tasks(self):
        tasks = load_wave0(ROOT)
        counts = {}
        for task in tasks: counts[task["category"]] = counts.get(task["category"], 0) + 1
        self.assertEqual(counts, {"GENERAL_REASONING": 3, "VIETNAMESE": 3, "STRUCTURED_OUTPUT": 2, "CODING": 2, "MATH": 2})

    def test_ingestion_links_environment_and_retains_failures(self):
        tasks = load_wave0(ROOT); runs = [run(task) for task in tasks]
        runs[0] = run(tasks[0], passed=False)
        report = ingest_wave0(tasks, runs)
        self.assertFalse(report["ready_to_freeze"])
        self.assertEqual(report["failures"][0]["raw_run_ref"], "run:" + tasks[0]["task_id"])

    def test_fake_or_nonreproducible_run_blocks_freeze(self):
        tasks = load_wave0(ROOT); runs = [run(task) for task in tasks]
        runs[0]["real_inference"] = False
        with self.assertRaisesRegex(ValueError, "not ready"):
            freeze_baseline(ingest_wave0(tasks, runs))
        runs[0] = run(tasks[0]); runs[0]["reproducible"] = False
        with self.assertRaisesRegex(ValueError, "not ready"):
            freeze_baseline(ingest_wave0(tasks, runs))

    def test_full_real_wave_freezes_complete_baseline(self):
        tasks = load_wave0(ROOT); report = ingest_wave0(tasks, [run(task) for task in tasks])
        baseline = freeze_baseline(report)
        self.assertEqual(baseline["baseline_id"], "PERSONAL_AI_BASELINE_001")
        self.assertEqual(len(baseline["wave0_results"]), 12)
        self.assertEqual(baseline["failure_rate"], 0.0)
        for field in ("model_id", "family", "revision", "artifact_hash", "quantization", "runtime", "runtime_version", "environment_fingerprint", "prompt_version", "benchmark_version", "cold_metrics", "warm_metrics", "verifier_results", "raw_run_refs"):
            self.assertIn(field, baseline)


if __name__ == "__main__": unittest.main()
