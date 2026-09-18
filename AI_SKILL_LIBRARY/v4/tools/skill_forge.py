from __future__ import annotations

from typing import Any

_PROTECTED = {"financial", "credential_sensitive", "destructive", "D"}


def _promotion_class(gap: dict) -> str:
    risk = str(gap.get("risk_class") or "A")
    if risk in _PROTECTED:
        return "D"
    if gap.get("changes_kernel_or_router") is True or gap.get("changes_security_authority") is True:
        return "C"
    if gap.get("requires_tool_adapter") is True or risk in {"B", "reversible_write"}:
        return "B"
    return "A"


def triage_gap(gap: dict, existing_skills: list[dict]) -> dict:
    if not isinstance(gap, dict):
        raise ValueError("gap_must_be_object")
    capability = str(gap.get("recommended_capability") or "").strip()
    domain = str(gap.get("domain") or "").strip()
    gap_id = str(gap.get("gap_id") or "").strip()
    if not gap_id or not domain or not capability:
        raise ValueError("gap_missing_required_fields")

    source_kind = str(gap.get("source_kind") or "failure").strip()
    if source_kind not in {"failure", "curriculum_gap", "competency_gap"}:
        raise ValueError("gap_source_kind_invalid")
    evidence_refs = gap.get("evidence_refs", [])
    if source_kind == "competency_gap":
        if not isinstance(evidence_refs, list) or not evidence_refs or any(
            not isinstance(ref, str) or not ref.strip() for ref in evidence_refs
        ):
            return {
                "gap_id": gap_id,
                "action": "discard",
                "target_skill_id": None,
                "promotion_class": _promotion_class(gap),
                "reason": "competency_gap_missing_evidence",
                "stable_write": False,
                "routing_authority": False,
                "source_kind": source_kind,
                "evidence_refs": sorted(set(str(x).strip() for x in evidence_refs if str(x).strip())),
            }

    for row in existing_skills if isinstance(existing_skills, list) else []:
        if not isinstance(row, dict) or str(row.get("domain") or "") != domain:
            continue
        caps = row.get("capabilities", [])
        if isinstance(caps, list) and capability in {str(x) for x in caps}:
            return {
                "gap_id": gap_id,
                "action": "improve",
                "target_skill_id": str(row.get("id") or ""),
                "promotion_class": _promotion_class(gap),
                "stable_write": False,
                "routing_authority": False,
            }

    if gap.get("distinct_contract") is not True:
        return {
            "gap_id": gap_id,
            "action": "discard",
            "target_skill_id": None,
            "promotion_class": _promotion_class(gap),
            "reason": "distinct_contract_not_proven",
            "stable_write": False,
            "routing_authority": False,
            "source_kind": source_kind,
            "evidence_refs": sorted(set(str(x).strip() for x in evidence_refs if str(x).strip())),
        }

    return {
        "gap_id": gap_id,
        "action": "create",
        "target_skill_id": None,
        "promotion_class": _promotion_class(gap),
        "stable_write": False,
        "routing_authority": False,
        "source_kind": source_kind,
        "evidence_refs": sorted(set(str(x).strip() for x in evidence_refs if str(x).strip())),
    }


def promotion_decision(candidate: dict, eval_result: dict) -> dict:
    if not isinstance(candidate, dict) or not isinstance(eval_result, dict):
        raise ValueError("candidate_and_eval_required")
    klass = str(candidate.get("promotion_class") or "D").upper()
    reasons: list[str] = []
    if klass not in {"A", "B", "C", "D"}:
        reasons.append("unknown_promotion_class")
        klass = "D"
    if candidate.get("permission_unchanged") is not True:
        reasons.append("permission_changed")
    if eval_result.get("all_gates_pass") is not True:
        reasons.append("promotion_gate_failed")
    if eval_result.get("frozen_replay") is not True:
        reasons.append("replay_not_frozen")
    if int(eval_result.get("protected_regressions", 1) or 0) != 0:
        reasons.append("protected_regression")
    if int(eval_result.get("critical_conflicts", 1) or 0) != 0:
        reasons.append("critical_conflict")
    try:
        gain = float(eval_result.get("measured_gain", 0.0))
    except (TypeError, ValueError):
        gain = -1.0
    if gain < 0.0:
        reasons.append("measured_gain_negative")
    if klass in {"B", "C"} and candidate.get("sandbox_pass") is not True:
        reasons.append("sandbox_required")

    eligible = not reasons
    automatic = eligible and klass in {"A", "B"}
    return {
        "eligible": eligible,
        "automatic": automatic,
        "explicit_authorization_required": klass in {"C", "D"},
        "promotion_class": klass,
        "reasons": sorted(set(reasons)),
        "stable_write": False,
    }
