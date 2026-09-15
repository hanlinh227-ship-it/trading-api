from __future__ import annotations

import copy
from pathlib import Path

import yaml


_BUDGET_FIELDS = {
    "tokens": "tokens_remaining",
    "api_calls": "api_calls_remaining",
    "compute_seconds": "compute_seconds_remaining",
    "storage_mb": "storage_mb_remaining",
    "network_calls": "network_calls_remaining",
}


def _policy() -> dict:
    root = Path(__file__).resolve().parents[3]
    return yaml.safe_load((root / "AI_SKILL_LIBRARY/v4/learning/idle.yaml").read_text(encoding="utf-8"))


def yield_for_user_activity(state: dict) -> bool:
    return bool(state.get("active_user_work", False))


def _cost_fits(job: dict, budget: dict) -> bool:
    cost = job.get("cost", {}) or {}
    for cost_key, budget_key in _BUDGET_FIELDS.items():
        try:
            requested = float(cost.get(cost_key, 0) or 0)
            remaining = float(budget.get(budget_key, 0) or 0)
        except (TypeError, ValueError):
            return False
        if requested < 0 or remaining < requested:
            return False
    return True


def eligible_idle_jobs(state: dict, backlog: list[dict], now: str) -> list[dict]:
    policy = _policy()
    if policy.get("yield_on_user_activity") and yield_for_user_activity(state):
        return []
    max_concurrent = min(
        int(state.get("max_concurrent_idle_jobs", policy.get("max_concurrent_jobs", 1))),
        int(policy.get("max_concurrent_jobs", 1)),
    )
    if int(state.get("running_idle_jobs", 0)) >= max_concurrent:
        return []

    allowed = set(policy.get("allowed_jobs", []))
    forbidden = set(policy.get("forbidden_jobs", []))
    budget = state.get("budget", {}) or {}
    eligible: list[dict] = []
    for raw in backlog:
        job = copy.deepcopy(raw)
        kind = str(job.get("kind", ""))
        if kind not in allowed or kind in forbidden:
            continue
        if not _cost_fits(job, budget):
            continue
        retries = int(job.get("retries", 0) or 0)
        if retries > int(policy.get("max_retries_per_job", 0)):
            continue
        network_calls = int((job.get("cost", {}) or {}).get("network_calls", 0) or 0)
        if network_calls > int(policy.get("max_network_calls_per_job", 0)):
            continue
        if kind == "skill_mutation":
            requested = int(job.get("mutation_budget", 1) or 1)
            job["mutation_budget"] = max(0, min(requested, int(policy.get("max_candidate_mutations", 6))))
        job["eligible_at"] = now
        job["routing_authority"] = False
        job["reasoning_authority"] = False
        eligible.append(job)
    return sorted(eligible, key=lambda item: (-int(item.get("priority", 0)), str(item.get("job_id", ""))))


def reserve_budget(job: dict, budget_state: dict) -> dict:
    if not _cost_fits(job, budget_state):
        raise ValueError("idle job exceeds remaining budget")
    result = copy.deepcopy(budget_state)
    cost = job.get("cost", {}) or {}
    for cost_key, budget_key in _BUDGET_FIELDS.items():
        remaining = float(result.get(budget_key, 0) or 0)
        requested = float(cost.get(cost_key, 0) or 0)
        value = remaining - requested
        if value < 0:
            raise ValueError(f"negative budget after reservation: {budget_key}")
        original = result.get(budget_key, 0)
        result[budget_key] = int(value) if isinstance(original, int) else value
    return result


def next_idle_job(jobs: list[dict]) -> dict | None:
    if not jobs:
        return None
    ordered = sorted(jobs, key=lambda item: (-int(item.get("priority", 0)), str(item.get("job_id", ""))))
    return copy.deepcopy(ordered[0])
