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
    "verified",
    "foreground",
    "resume_eligible",
}


def _contains_sensitive_data(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).strip().lower() in SENSITIVE_KEYS:
                return True
            if _contains_sensitive_data(nested):
                return True
    elif isinstance(value, (list, tuple, set)):
        return any(_contains_sensitive_data(item) for item in value)
    return False


def _base_focus(active: dict | None = None) -> dict:
    return {
        "version": 1,
        "authority": False,
        "routing_authority": False,
        "reasoning_authority": False,
        "execution_authority": False,
        "stable_mutation": False,
        "active": deepcopy(active) if isinstance(active, dict) else None,
        "on_missing_focus": "no_resume",
        "on_ambiguous_focus": "no_resume",
        "write_mode": "candidate_only",
        "cross_project_read": False,
        "cross_project_write": False,
        "requires_verified_project_handoff": True,
        "current_project_authority_wins": True,
    }


def build_focus_update(handoff: dict, current_active: dict | None = None) -> dict:
    """Build a safe foreground-focus payload from a verified project handoff.

    This function never writes to GitHub or any runtime state. The caller may persist
    the returned focus only when ``accepted`` is true and after its own current
    project-authority check. Background work and a different protected running
    project fail closed.
    """
    focus = _base_focus(current_active)
    if not isinstance(handoff, dict):
        return {"accepted": False, "reason": "invalid_handoff", "focus": focus}
    if _contains_sensitive_data(handoff):
        return {"accepted": False, "reason": "sensitive_data", "focus": focus}

    missing = sorted(field for field in REQUIRED_FIELDS if field not in handoff)
    if missing:
        return {
            "accepted": False,
            "reason": "missing_required_fields",
            "missing": missing,
            "focus": focus,
        }
    if handoff.get("verified") is not True:
        return {"accepted": False, "reason": "handoff_unverified", "focus": focus}
    if handoff.get("resume_eligible") is not True:
        return {"accepted": False, "reason": "not_resume_eligible", "focus": focus}
    if handoff.get("foreground") is not True:
        return {
            "accepted": False,
            "reason": "background_work_cannot_take_focus",
            "focus": focus,
        }

    project_id = str(handoff.get("project_id") or "").strip()
    domain = str(handoff.get("domain") or "").strip()
    if not project_id or not domain:
        return {"accepted": False, "reason": "invalid_scope", "focus": focus}

    if isinstance(current_active, dict) and current_active.get("protected_running") is True:
        current_project = str(current_active.get("project_id") or "").strip()
        current_domain = str(current_active.get("domain") or "").strip()
        if current_project != project_id or (current_domain and current_domain != domain):
            return {
                "accepted": False,
                "reason": "protected_running_project",
                "focus": focus,
            }

    active = {
        "project_id": project_id,
        "domain": domain,
        "phase": handoff.get("phase"),
        "last_completed": handoff.get("last_completed"),
        "next_actions": deepcopy(handoff.get("next_actions")),
        "canonical_refs": deepcopy(handoff.get("canonical_refs")),
        "source": handoff.get("source"),
        "last_verified": handoff.get("last_verified"),
        "updated_at": handoff.get("updated_at"),
        "verified": True,
        "foreground": True,
        "resume_eligible": True,
        "authority": False,
        "routing_authority": False,
        "reasoning_authority": False,
        "execution_authority": False,
    }
    if isinstance(current_active, dict) and current_active.get("protected_running") is True:
        active["protected_running"] = True

    focus = _base_focus(active)
    return {"accepted": True, "reason": None, "focus": focus}
