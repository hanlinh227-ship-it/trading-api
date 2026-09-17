from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


WAVE0_PATH = Path("AI_SKILL_LIBRARY/v4/control_plane/wave0.json")
_IDENTITY_FIELDS = (
    "model_id", "family", "revision", "artifact_hash", "quantization",
    "runtime", "runtime_version", "environment_fingerprint", "prompt_version", "benchmark_version",
)


def load_wave0(root: Path) -> list[dict[str, Any]]:
    data = json.loads((root / WAVE0_PATH).read_text(encoding="utf-8"))
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 12:
        raise ValueError("Wave 0 must contain exactly 12 tasks")
    if len({task.get("task_id") for task in tasks}) != 12:
        raise ValueError("Wave 0 task IDs must be unique")
    return deepcopy(tasks)


def ingest_wave0(tasks: list[dict[str, Any]], runs: list[dict[str, Any]]) -> dict[str, Any]:
    task_map = {task.get("task_id"): task for task in tasks if isinstance(task, dict)}
    run_map = {run.get("task_id"): deepcopy(run) for run in runs if isinstance(run, dict)}
    failures: list[dict[str, Any]] = []
    projected: list[dict[str, Any]] = []
    reasons: list[str] = []
    if len(task_map) != 12 or set(run_map) != set(task_map):
        reasons.append("incomplete_task_set")
    for task_id in sorted(task_map):
        run = run_map.get(task_id)
        if not run:
            continue
        row = {"schema": "benchmark_run_v1", **run}
        projected.append(row)
        if run.get("category") != task_map[task_id].get("category"):
            reasons.append("category_mismatch")
        if any(not run.get(field) for field in _IDENTITY_FIELDS):
            reasons.append("identity_or_environment_link_missing")
        if run.get("real_inference") is not True:
            reasons.append("non_real_runtime_evidence")
        if run.get("reproducible") is not True:
            reasons.append("reproducibility_gate_failed")
        if run.get("verifier_passed") is not True or run.get("failure"):
            failures.append({"task_id": task_id, "failure": deepcopy(run.get("failure")), "raw_run_ref": run.get("raw_run_ref")})
            reasons.append("verifier_or_run_failure")
        if not run.get("raw_run_ref"):
            reasons.append("raw_run_ref_missing")
    identity_sets = {field: {run.get(field) for run in projected} for field in _IDENTITY_FIELDS}
    if any(len(values) != 1 for values in identity_sets.values()):
        reasons.append("wave_identity_drift")
    return {
        "schema": "benchmark_wave_v1",
        "benchmark_version": "wave0-v1",
        "runs": projected,
        "failures": failures,
        "readiness_failures": sorted(set(reasons)),
        "ready_to_freeze": not reasons and len(projected) == 12,
    }


def freeze_baseline(report: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(report, dict) or report.get("ready_to_freeze") is not True:
        raise ValueError("Wave 0 is not ready to freeze")
    runs = report.get("runs", [])
    if len(runs) != 12:
        raise ValueError("Wave 0 is not ready to freeze")
    first = runs[0]
    return {
        "baseline_id": "PERSONAL_AI_BASELINE_001",
        **{field: first[field] for field in _IDENTITY_FIELDS},
        "wave0_results": deepcopy(runs),
        "cold_metrics": [deepcopy(run["cold_metrics"]) for run in runs],
        "warm_metrics": [deepcopy(run["warm_metrics"]) for run in runs],
        "failure_rate": sum(run.get("failure") is not None for run in runs) / len(runs),
        "verifier_results": [{"task_id": run["task_id"], "passed": run["verifier_passed"]} for run in runs],
        "raw_run_refs": [run["raw_run_ref"] for run in runs],
        "frozen": True,
    }
