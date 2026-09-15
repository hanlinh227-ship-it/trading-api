from __future__ import annotations

from copy import deepcopy


def normalize_graphify_graph(payload: dict, *, source_sha: str, expected_sha: str, max_nodes: int = 500) -> dict:
    max_nodes = max(0, int(max_nodes))
    nodes = payload.get("nodes", []) if isinstance(payload, dict) else []
    edges = payload.get("edges", []) if isinstance(payload, dict) else []
    nodes = [deepcopy(row) for row in nodes if isinstance(row, dict)][:max_nodes]
    allowed_ids = {str(row.get("id")) for row in nodes if row.get("id") is not None}
    bounded_edges = []
    for row in edges if isinstance(edges, list) else []:
        if not isinstance(row, dict):
            continue
        if str(row.get("source")) in allowed_ids and str(row.get("target")) in allowed_ids:
            bounded_edges.append(deepcopy(row))
        if len(bounded_edges) >= max_nodes * 4:
            break
    return {
        "derived": True,
        "authority": False,
        "routing_authority": False,
        "reasoning_authority": False,
        "source_sha": str(source_sha),
        "expected_sha": str(expected_sha),
        "stale": str(source_sha) != str(expected_sha),
        "nodes": nodes,
        "edges": bounded_edges,
    }


def ponytail_policy() -> dict:
    return {
        "mode": "advisory_simplicity_critic",
        "routing_authority": False,
        "reasoning_authority": False,
        "stable_mutation": False,
        "may_weaken_security": False,
        "may_remove_required_tests": False,
        "may_remove_acceptance_criteria": False,
    }


def apply_simplicity_advice(advice: dict, *, required_constraints: list[str]) -> dict:
    required = [str(value) for value in required_constraints]
    requested = advice.get("remove", []) if isinstance(advice, dict) else []
    requested = [str(value) for value in requested if str(value)] if isinstance(requested, list) else []
    required_set = set(required)
    return {
        "preserved_constraints": required,
        "accepted_removals": [value for value in requested if value not in required_set],
        "rejected_removals": [value for value in requested if value in required_set],
        "advisory_only": True,
    }


def omniroute_policy() -> dict:
    return {
        "enabled_by_default": False,
        "sandbox_only": True,
        "routing_authority": False,
        "reasoning_authority": False,
        "stable_mutation": False,
        "fusion_enabled": False,
        "pipeline_enabled": False,
        "autonomous_orchestration": False,
        "paid_fallback": False,
        "auto_purchase": False,
        "brain_policy_wins": True,
    }


def normalize_omniroute_candidate(row: dict) -> dict:
    row = row if isinstance(row, dict) else {}
    free_status = str(row.get("free_status") or "unknown").strip().lower()
    prohibited = free_status in {"paid", "trial", "promo", "promotional", "credit"}
    free_claim = free_status == "free"
    entitlement = row.get("entitlement_verified") is True
    health = row.get("health_fresh") is True
    quota = row.get("quota_available") is True
    privacy = row.get("privacy_verified") is True
    terms = row.get("terms_verified") is True
    eligible = bool(free_claim and entitlement and health and quota and privacy and terms and not prohibited)
    return {
        "provider_id": str(row.get("provider_id") or ""),
        "model_id": str(row.get("model_id") or ""),
        "family": str(row.get("family") or "unknown"),
        "free_status": free_status,
        "eligible": eligible,
        "state": "quarantine",
        "routing_authority": False,
        "reasoning_authority": False,
        "stable_mutation": False,
        "exclusion_reason": "paid_or_temporary_free" if prohibited else (None if eligible else "verification_incomplete"),
    }
