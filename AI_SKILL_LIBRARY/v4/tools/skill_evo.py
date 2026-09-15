from __future__ import annotations

import copy
import hashlib
import json


MAX_MUTATIONS = 6


def _digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def freeze_replay(samples: list[dict], lineage_id: str) -> dict:
    frozen_samples = sorted((copy.deepcopy(sample) for sample in samples), key=lambda row: str(row.get("sample_id", "")))
    payload = {"lineage_id": lineage_id, "samples": frozen_samples}
    return {
        "lineage_id": lineage_id,
        "samples": frozen_samples,
        "sample_count": len(frozen_samples),
        "frozen": True,
        "replay_digest": _digest(payload),
    }


def compile_eval_rules(candidate: dict, replay: dict) -> list[dict]:
    lineage_id = candidate.get("lineage_id")
    replay_digest = replay.get("replay_digest")
    return [
        {"rule_id": "replay_accuracy", "binary": True, "lineage_id": lineage_id, "replay_digest": replay_digest},
        {"rule_id": "protected_regression", "binary": True, "lineage_id": lineage_id},
        {"rule_id": "permission_unchanged", "binary": True, "expected": candidate.get("permission_ceiling")},
        {"rule_id": "critical_conflicts", "binary": True, "max": 0},
        {"rule_id": "risk_not_downgraded", "binary": True, "expected_min": candidate.get("risk_class")},
    ]


def generate_mutations(champion: dict, budget: int) -> list[dict]:
    try:
        requested = int(budget)
    except (TypeError, ValueError):
        requested = 0
    count = max(0, min(requested, MAX_MUTATIONS))
    mutations: list[dict] = []
    for index in range(count):
        seed = {
            "lineage_id": champion.get("lineage_id"),
            "content_digest": champion.get("content_digest"),
            "candidate_id": champion.get("candidate_id"),
            "index": index,
        }
        digest = _digest(seed)
        mutation = copy.deepcopy(champion)
        mutation["mutation_id"] = f"mutation-{digest[:20]}"
        mutation["candidate_id"] = f"candidate-{digest[:20]}"
        mutation["parent_candidate_id"] = champion.get("candidate_id")
        mutation["mutation_index"] = index
        mutation["mutation_strategy"] = "bounded_revision"
        mutation["status"] = "incubating"
        mutation["stable_write_allowed"] = False
        mutation["permission_ceiling"] = champion.get("permission_ceiling", "read_only")
        mutation["risk_class"] = champion.get("risk_class", "A")
        mutation["content_digest"] = digest
        mutations.append(mutation)
    return mutations


def score_mutation(mutation: dict, eval_results: dict) -> float:
    score = 0.0
    if eval_results.get("eval_pass") is True:
        score += 0.25
    if eval_results.get("regression_pass") is True:
        score += 0.25
    if eval_results.get("permission_unchanged") is True:
        score += 0.15
    if int(eval_results.get("critical_conflicts", 1) or 0) == 0:
        score += 0.15
    replay_accuracy = eval_results.get("replay_accuracy")
    if isinstance(replay_accuracy, (int, float)):
        score += max(0.0, min(1.0, float(replay_accuracy))) * 0.15
    if eval_results.get("canary_required") and eval_results.get("canary_pass") is True:
        score += 0.03
    if eval_results.get("judge_preference") is True:
        score += 0.02
    return round(score, 6)


def _promotion_eligible(outcome: dict) -> bool:
    if outcome.get("eval_pass") is not True:
        return False
    if outcome.get("regression_pass") is not True:
        return False
    if outcome.get("permission_unchanged") is not True:
        return False
    try:
        conflicts = int(outcome.get("critical_conflicts", 1))
    except (TypeError, ValueError):
        return False
    if conflicts != 0:
        return False
    try:
        delta = float(outcome.get("score_delta", -1.0))
    except (TypeError, ValueError):
        return False
    if delta < 0.0:
        return False
    if outcome.get("canary_required") is True and outcome.get("canary_pass") is not True:
        return False
    return True


def select_champion(current: dict, challengers: list[dict], promotion_results: dict) -> dict:
    eligible: list[tuple[float, float, str, dict]] = []
    for challenger in challengers:
        mutation_id = challenger.get("mutation_id")
        outcome = promotion_results.get(mutation_id, {})
        if not _promotion_eligible(outcome):
            continue
        delta = float(outcome.get("score_delta", 0.0))
        measured = score_mutation(challenger, outcome)
        eligible.append((delta, measured, str(mutation_id), challenger))

    if not eligible:
        return copy.deepcopy(current)

    eligible.sort(key=lambda item: (-item[0], -item[1], item[2]))
    winner = copy.deepcopy(eligible[0][3])
    winner["status"] = "champion_candidate"
    winner["stable_write_allowed"] = False
    winner["promotion_requires_brain_gate"] = True
    return winner
