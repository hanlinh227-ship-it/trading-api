from __future__ import annotations

from copy import deepcopy
from typing import Any


SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "credentials",
    "password",
    "private_key",
    "secret",
    "seed_phrase",
    "session_token",
    "token",
}

REQUIRED_FIELDS = {
    "project_id",
    "domain",
    "phase",
    "last_completed",
    "next_actions",
    "canonical_refs",
    "source",
    "last_verified",
    "updated_at",
    "focus",
    "resume_eligible",
    "lifecycle",
    "verified",
}


def _contains_sensitive_data(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).strip().lower()
            if normalized in SENSITIVE_KEYS:
                return True
            if _contains_sensitive_data(nested):
                return True
    elif isinstance(value, (list, tuple, set)):
        return any(_contains_sensitive_data(item) for item in value)
    return False


def normalize_work_state(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {"accepted": False, "reason": "invalid_payload", "state": None}
    if _contains_sensitive_data(payload):
        return {"accepted": False, "reason": "sensitive_data", "state": None}

    missing = sorted(field for field in REQUIRED_FIELDS if field not in payload)
    if missing:
        return {
            "accepted": False,
            "reason": "missing_required_fields",
            "missing": missing,
            "state": None,
        }

    project_id = str(payload.get("project_id") or "").strip()
    domain = str(payload.get("domain") or "").strip()
    focus = str(payload.get("focus") or "").strip().lower()
    lifecycle = str(payload.get("lifecycle") or "").strip().lower()

    if not project_id or not domain:
        return {"accepted": False, "reason": "invalid_scope", "state": None}
    if focus not in {"primary", "background"}:
        return {"accepted": False, "reason": "invalid_focus", "state": None}

    state = deepcopy(payload)
    state["project_id"] = project_id
    state["domain"] = domain
    state["focus"] = focus
    state["lifecycle"] = lifecycle
    state["authority"] = False
    state["routing_authority"] = False
    state["reasoning_authority"] = False
    state["execution_authority"] = False
    state["stable_mutation"] = False

    return {"accepted": True, "reason": None, "state": state}


def _is_resumable(state: dict) -> bool:
    return bool(
        state.get("verified") is True
        and state.get("resume_eligible") is True
        and state.get("lifecycle") == "active"
        and not state.get("superseded_by")
    )


def select_continuation(
    states: list[dict],
    explicit_project: str | None = None,
    explicit_domain: str | None = None,
) -> dict:
    normalized: list[dict] = []
    for raw in states if isinstance(states, list) else []:
        result = normalize_work_state(raw)
        if result.get("accepted"):
            state = result["state"]
            if _is_resumable(state):
                normalized.append(state)

    project = str(explicit_project).strip() if explicit_project is not None else None
    domain = str(explicit_domain).strip() if explicit_domain is not None else None

    if project:
        matches = [row for row in normalized if row["project_id"] == project]
        if domain:
            matches = [row for row in matches if row["domain"] == domain]
        if len(matches) != 1:
            return {"selected": False, "reason": "explicit_scope_not_unique", "state": None}
        return {"selected": True, "reason": None, "state": deepcopy(matches[0])}

    primary = [row for row in normalized if row.get("focus") == "primary"]
    if domain:
        primary = [row for row in primary if row["domain"] == domain]
    if len(primary) != 1:
        return {"selected": False, "reason": "ambiguous_or_missing_focus", "state": None}
    return {"selected": True, "reason": None, "state": deepcopy(primary[0])}


def gate_against_authority(selection: dict, authority: dict) -> dict:
    if not isinstance(selection, dict) or selection.get("selected") is not True:
        return {"allowed": False, "reason": "no_selected_continuity", "context": None}
    if not isinstance(authority, dict) or authority.get("verified") is not True:
        return {"allowed": False, "reason": "authority_unverified", "context": None}

    state = selection.get("state") or {}
    authority_project = str(authority.get("project_id") or "").strip()
    authority_domain = str(authority.get("domain") or "").strip()

    if state.get("project_id") != authority_project:
        return {"allowed": False, "reason": "project_authority_mismatch", "context": None}
    if authority_domain and state.get("domain") != authority_domain:
        return {"allowed": False, "reason": "domain_authority_mismatch", "context": None}

    context = deepcopy(state)
    context["authority"] = False
    context["routing_authority"] = False
    context["reasoning_authority"] = False
    context["execution_authority"] = False
    context["stable_mutation"] = False
    return {"allowed": True, "reason": None, "context": context}
