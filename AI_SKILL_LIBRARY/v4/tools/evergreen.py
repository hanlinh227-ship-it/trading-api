from __future__ import annotations

REQUIRED_GATES = ("provenance", "license", "security", "authority", "evals", "canary")


def lifecycle_decision(*, promotion_class: str, gates: dict[str, bool], protected_regressions: list[str]) -> str:
    if promotion_class == "D":
        return "manual_authorization_required"
    if promotion_class not in {"A", "B", "C"}:
        return "reject"
    if protected_regressions:
        return "reject"
    if any(gates.get(name) is not True for name in REQUIRED_GATES):
        return "reject"
    if promotion_class == "C" and gates.get("second_canary") is not True:
        return "hold"
    return "promote"


def quarantine_candidate(candidate: dict) -> dict:
    return {
        "state": "quarantine",
        "routing_authority": False,
        "stable_mutation": False,
        "candidate": candidate,
    }


def promotion_record(candidate_id: str, version: str, decision: str, evidence: list[str]) -> dict:
    return {
        "candidate_id": candidate_id,
        "version": version,
        "decision": decision,
        "evidence": list(evidence),
        "inflight_stable_mutation": False,
    }
