from __future__ import annotations

from copy import deepcopy
from typing import Any


_FIELDS = (
    "request_id", "source", "request", "project_context", "conversation_context",
    "attachments", "constraints", "privacy_class", "desired_depth",
)


def prepare_ingress(envelope: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(envelope, dict):
        raise TypeError("ingress envelope must be a mapping")
    missing = [field for field in _FIELDS if field not in envelope]
    if missing:
        raise ValueError("missing ingress fields: " + ", ".join(missing))
    if not isinstance(route, dict) or route.get("routed_by") != "task_router":
        raise ValueError("task_router route evidence is required")
    if route.get("profile") not in {"FAST", "STANDARD", "DEEP"}:
        raise ValueError("route profile is invalid")
    constraints = envelope["constraints"]
    if not isinstance(constraints, dict) or constraints.get("FREE_ONLY") is not True:
        raise ValueError("FREE_ONLY constraint is mandatory")
    permissions = constraints.get("permissions")
    if not isinstance(permissions, list):
        raise ValueError("permission ceiling is required")
    token_count = envelope.get("conversation_context", {}).get("tokens", 0)
    selection_request = {
        "task_id": envelope["request_id"],
        "domain": route.get("domain"),
        "required_capabilities": [route.get("primary_skill")],
        "privacy": envelope["privacy_class"],
        "context": {"tokens": token_count, "project": deepcopy(envelope["project_context"])},
        "latency_budget": deepcopy(constraints.get("latency_budget", {"max_ms": None})),
        "resource_budget": deepcopy(constraints.get("resource_budget", {"ram_mb": 0, "vram_mb": 0})),
        "execution_profile": route["profile"],
        "verifier_requirement": route.get("domain"),
    }
    return {
        "request_id": envelope["request_id"],
        "request": envelope["request"],
        "source": envelope["source"],
        "route": deepcopy(route),
        "bounded_context": {
            "project": deepcopy(envelope["project_context"]),
            "conversation": deepcopy(envelope["conversation_context"]),
            "attachments": deepcopy(envelope["attachments"]),
        },
        "policy_ceiling": {"FREE_ONLY": True, "privacy": envelope["privacy_class"], "permissions": deepcopy(permissions)},
        "selection_request": selection_request,
    }

