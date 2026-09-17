from __future__ import annotations

from copy import deepcopy


def _deny(reason: str) -> dict:
    return {"resumed": False, "reason": reason, "context": None}


def bootstrap_resume(focus: dict, authority: dict) -> dict:
    """Resolve persisted continuity focus into context for a new chat.

    This function is deliberately authority-free and side-effect-free. It never
    writes focus, changes routing, mutates project state, or grants execution
    authority. A caller must provide the current verified project authority.
    """
    if not isinstance(focus, dict):
        return _deny("invalid_focus")

    for key in (
        "authority",
        "routing_authority",
        "reasoning_authority",
        "execution_authority",
        "stable_mutation",
        "cross_project_read",
        "cross_project_write",
    ):
        if focus.get(key) is not False:
            return _deny("unsafe_focus_policy")

    active = focus.get("active")
    if not isinstance(active, dict):
        return _deny("missing_active_focus")
    if active.get("verified") is not True:
        return _deny("focus_unverified")
    if active.get("foreground") is not True:
        return _deny("focus_not_foreground")
    if active.get("resume_eligible") is not True:
        return _deny("focus_not_resume_eligible")

    if not isinstance(authority, dict) or authority.get("verified") is not True:
        return _deny("authority_unverified")

    project_id = str(active.get("project_id") or "").strip()
    domain = str(active.get("domain") or "").strip()
    authority_project = str(authority.get("project_id") or "").strip()
    authority_domain = str(authority.get("domain") or "").strip()

    if not project_id or not domain:
        return _deny("focus_scope_invalid")
    if project_id != authority_project:
        return _deny("project_authority_mismatch")
    if authority_domain and domain != authority_domain:
        return _deny("domain_authority_mismatch")

    context = deepcopy(active)
    context["authority"] = False
    context["routing_authority"] = False
    context["reasoning_authority"] = False
    context["execution_authority"] = False
    context["stable_mutation"] = False

    return {
        "resumed": True,
        "reason": None,
        "context": context,
    }
