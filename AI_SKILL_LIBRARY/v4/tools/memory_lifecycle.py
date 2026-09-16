from __future__ import annotations

from copy import deepcopy
from typing import Any

_FORBIDDEN_FIELDS = {
    "raw_private_chat", "hidden_reasoning", "chain_of_thought", "secrets", "credentials",
    "api_keys", "private_keys", "authentication_tokens", "seed_phrases", "raw_private_tool_payload",
}
_SENSITIVE_MARKERS = (
    "api_key=", "api key:", "private_key", "private key:", "bearer ",
    "seed phrase", "authentication_token", "authorization: bearer",
)
_ALLOWED_STATES = {"candidate", "pending", "confirmed", "active", "superseded", "archived", "tombstoned"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _sensitive(candidate: dict) -> bool:
    if any(key in candidate for key in _FORBIDDEN_FIELDS):
        return True
    content = _text(candidate.get("content")).casefold()
    return any(marker.casefold() in content for marker in _SENSITIVE_MARKERS)


def evaluate_candidate(candidate: dict, active_records: list[dict]) -> dict:
    if not isinstance(candidate, dict):
        raise ValueError("candidate_must_be_object")
    row = deepcopy(candidate)
    reasons: list[str] = []
    required = ("candidate_id", "domain", "scope", "content", "source", "confidence", "created_at", "evidence_refs")
    for key in required:
        value = row.get(key)
        if value is None or value == "" or (key == "evidence_refs" and not isinstance(value, list)):
            reasons.append(f"missing_{key}")
    evidence = row.get("evidence_refs", [])
    if not isinstance(evidence, list) or not [item for item in evidence if _text(item)]:
        reasons.append("missing_evidence")
    try:
        confidence = float(row.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = -1
    if confidence < 0 or confidence > 1:
        reasons.append("invalid_confidence")
    if any(key in row for key in _FORBIDDEN_FIELDS):
        reasons.append("forbidden_field")
    if _sensitive(row):
        reasons.append("sensitive_content")
    if row.get("non_sensitive") is not True:
        reasons.append("non_sensitive_not_verified")
    if row.get("reusable") is not True:
        reasons.append("not_reusable")
    if row.get("verified") is not True:
        reasons.append("not_verified")
    if not _text(row.get("domain")) or not _text(row.get("scope")):
        reasons.append("unscoped")

    active_by_id = {
        _text(record.get("memory_id") or record.get("candidate_id")): record
        for record in active_records if isinstance(record, dict) and record.get("state") == "active"
    }
    conflicts = row.get("conflicts_with", [])
    if not isinstance(conflicts, list):
        reasons.append("invalid_conflicts")
        conflicts = []
    if any(_text(conflict) in active_by_id for conflict in conflicts):
        reasons.append("unresolved_conflict")

    reasons = sorted(set(reasons))
    return {
        "candidate_id": _text(row.get("candidate_id")),
        "state": "candidate",
        "active": False,
        "eligible_for_review": not reasons,
        "reasons": reasons,
    }


def transition(record: dict, target_state: str, evidence: dict) -> dict:
    if not isinstance(record, dict) or not isinstance(evidence, dict):
        raise ValueError("record_and_evidence_required")
    current = _text(record.get("state") or "candidate")
    target = _text(target_state)
    if current not in _ALLOWED_STATES or target not in _ALLOWED_STATES:
        raise ValueError("invalid_memory_state")

    allowed = {
        "candidate": {"pending", "confirmed", "active", "archived", "tombstoned"},
        "pending": {"confirmed", "active", "archived", "tombstoned"},
        "confirmed": {"active", "archived", "tombstoned"},
        "active": {"superseded", "archived", "tombstoned"},
        "superseded": {"archived", "tombstoned"},
        "archived": {"tombstoned"},
        "tombstoned": set(),
    }
    if target not in allowed[current]:
        raise ValueError(f"memory_transition_forbidden:{current}->{target}")

    if target == "active":
        required = ("verified", "scoped", "reusable", "non_sensitive", "conflict_free")
        if any(evidence.get(key) is not True for key in required):
            raise ValueError("active_memory_gate_failed")
        if _sensitive(record):
            raise ValueError("active_memory_sensitive_content")
    if target == "superseded":
        if evidence.get("verified") is not True or not _text(evidence.get("superseded_by")):
            raise ValueError("supersession_gate_failed")

    out = deepcopy(record)
    out["state"] = target
    if target == "active":
        out["memory_id"] = _text(out.get("memory_id") or out.get("candidate_id"))
        out["last_verified"] = _text(evidence.get("verified_at")) or _text(out.get("last_verified"))
        out["verified"] = True
    if target == "superseded":
        out["superseded_by"] = _text(evidence.get("superseded_by"))
        out["last_verified"] = _text(evidence.get("verified_at")) or _text(out.get("last_verified"))
    return out
