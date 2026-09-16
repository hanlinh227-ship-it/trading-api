from __future__ import annotations

from copy import deepcopy

REQUIRED_FIELDS = {
    "id", "version", "domain", "triggers", "excludes", "requires", "conflicts_with", "bridges",
    "tools", "sources", "permissions", "risk_class", "output_contract", "evals", "provenance",
    "license", "compatibility",
}
ALLOWED_LICENSES = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "CC0-1.0", "Unlicense"}
PRIVILEGED = {"credential_sensitive", "financial", "destructive", "secret_read", "secret_export"}
# The only permissions a learned candidate may declare. Anything else is a permission
# expansion and fails closed (harmonization.yaml unknown_write_capability: fail_closed;
# kernel.yaml no_permission_expansion_by_learning).
ALLOWED_PERMISSIONS = {"read_only", "reversible_write", "sandbox_execute"}
INJECTION_MARKERS = (
    "ignore system", "ignore previous", "override authority", "bypass policy", "reveal secret",
    "disable security", "act as system",
)


def _norm_term(value: object) -> str:
    return " ".join(str(value or "").lower().split())


def _promotion_class(skill: dict) -> str:
    risk = skill.get("risk_class")
    permissions = set(skill.get("permissions", []))
    if risk in {"financial", "credential_sensitive", "destructive"} or permissions & PRIVILEGED:
        return "D"
    if risk == "reversible_write" or "reversible_write" in permissions or skill.get("tools"):
        return "B"
    return "A"


def admit_skill(skill: dict, *, existing_skills: list[dict]) -> dict:
    candidate = deepcopy(skill)
    reasons: list[str] = []
    missing = sorted(REQUIRED_FIELDS - set(candidate))
    if missing:
        reasons.append("missing_fields")
    identifiers = {row.get("id") for row in existing_skills if isinstance(row, dict)}
    if candidate.get("id") in identifiers:
        reasons.append("duplicate_id")
    # One trigger term has exactly one owner: a candidate may not claim a trigger that a
    # canonical skill already owns, or two reasoning authorities would share one purpose.
    owned_triggers = {
        _norm_term(term)
        for row in existing_skills if isinstance(row, dict)
        for term in (row.get("triggers") or []) if isinstance(term, str)
    }
    candidate_triggers = candidate.get("triggers") if isinstance(candidate.get("triggers"), list) else []
    if any(_norm_term(term) in owned_triggers for term in candidate_triggers if isinstance(term, str)):
        reasons.append("trigger_owner_conflict")
    provenance = candidate.get("provenance")
    if not isinstance(provenance, dict) or provenance.get("verified") is not True or not provenance.get("source"):
        reasons.append("unverified_provenance")
    if candidate.get("license") not in ALLOWED_LICENSES:
        reasons.append("license_not_allowed")
    permissions = set(candidate.get("permissions", [])) if isinstance(candidate.get("permissions"), list) else set()
    if permissions & PRIVILEGED or candidate.get("risk_class") in {"financial", "credential_sensitive", "destructive"}:
        reasons.append("privileged_permission")
    if permissions - ALLOWED_PERMISSIONS - PRIVILEGED:
        reasons.append("unknown_permission")
    text = " ".join(str(candidate.get(key, "")) for key in ("output_contract", "id")).lower()
    if any(marker in text for marker in INJECTION_MARKERS):
        reasons.append("instruction_override")
    if candidate.get("id") in set(candidate.get("conflicts_with", [])):
        reasons.append("self_conflict")
    if candidate.get("id") in set(candidate.get("requires", [])):
        reasons.append("require_cycle")
    promotion_class = _promotion_class(candidate)
    return {
        "admitted": not reasons,
        "promotion_class": promotion_class,
        "reasons": reasons,
        "quarantine_required": True,
    }
