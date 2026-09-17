from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


SPECIALISTS_PATH = Path("AI_SKILL_LIBRARY/v4/control_plane/specialists.yaml")
_PROFILE_CAPS = {"FAST": 1, "STANDARD": 2, "DEEP": 4}
_ROLES = {"QUALITY_CHAMPION", "FAST_CHAMPION", "LOW_RESOURCE_CHAMPION", "CHALLENGER", "SPECIALIST", "FALLBACK"}


def load_specialists(root: Path) -> dict[str, dict[str, Any]]:
    data = yaml.safe_load((root / SPECIALISTS_PATH).read_text(encoding="utf-8"))
    defaults, groups = data.get("defaults"), data.get("groups")
    if not isinstance(defaults, dict) or not isinstance(groups, dict):
        raise ValueError("specialist registry is invalid")
    result = {}
    for name, capabilities in groups.items():
        if not isinstance(capabilities, list) or not capabilities:
            raise ValueError(f"specialist {name} lacks capabilities")
        result[name] = {"capabilities": capabilities, **deepcopy(defaults)}
    return result


def plan_execution(profile: str, selection: dict[str, Any], specialist_groups: list[str]) -> dict[str, Any]:
    normalized = str(profile).upper()
    if normalized not in _PROFILE_CAPS:
        raise ValueError("unknown execution profile")
    primary = selection.get("primary_model")
    if not isinstance(primary, dict):
        raise ValueError("primary model is required")
    candidates = [primary, *selection.get("supporting_models", [])]
    cap = _PROFILE_CAPS[normalized]
    return {
        "profile": normalized,
        "routed_by": "task_router",
        "routing_authority": False,
        "model_selection_authority": "model_mesh",
        "models": deepcopy(candidates[:cap]),
        "specialist_groups": list(specialist_groups[:cap]),
        "verifier": selection.get("verifier") if normalized != "FAST" else None,
        "max_concurrent_models": cap,
    }


def promotion_decision(champion: dict[str, Any], challenger: dict[str, Any]) -> dict[str, Any]:
    if champion.get("role") not in _ROLES or challenger.get("role") != "CHALLENGER":
        return {"promote": False, "reason": "invalid_governance_role"}
    if not challenger.get("evidence_refs"):
        return {"promote": False, "reason": "empirical_evidence_required"}
    protected_before = champion.get("protected", {})
    protected_after = challenger.get("protected", {})
    if any(protected_after.get(key) is None or protected_after.get(key) < value for key, value in protected_before.items()):
        return {"promote": False, "reason": "protected_dimension_regression"}
    if challenger.get("quality", 0) <= champion.get("quality", 0):
        return {"promote": False, "reason": "quality_not_improved"}
    if challenger.get("latency", float("inf")) > champion.get("latency", float("inf")):
        return {"promote": False, "reason": "latency_regression"}
    return {"promote": True, "reason": "measured_domain_improvement", "new_role": champion["role"]}


def compute_routing_metrics(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    if not outcomes:
        raise ValueError("outcomes are required")
    count = len(outcomes)
    rate = lambda key: sum(bool(row.get(key)) for row in outcomes) / count
    return {
        "RoutingSuccessRate": rate("success"),
        "RoutingRegret": sum(float(row.get("regret", 0)) for row in outcomes) / count,
        "OversizedModelRate": rate("oversized"),
        "FailedSelectionRate": rate("selection_failed"),
        "UnnecessaryColdStartRate": rate("unnecessary_cold_start"),
        "may_tune_model_mesh": True,
        "may_replace_task_router": False,
    }
