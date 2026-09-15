from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


_AUTHORITY = {
    "official_spec": 1.0,
    "verified_project_authority": 0.95,
    "benchmark": 0.85,
    "peer_reviewed": 0.85,
    "verified_internal_experience": 0.75,
    "public_source": 0.55,
    "anecdotal": 0.35,
}
_REPRO = {"unknown": 0.35, "not_reproduced": 0.0, "reproduced": 1.0}
_VERIFY = {"unverified": 0.25, "verified": 1.0, "rejected": 0.0}


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _validate(claim: dict) -> None:
    schema = json.loads((_root() / "AI_SKILL_LIBRARY/v4/schemas/intelligence_claim.schema.json").read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(claim), key=lambda e: list(e.path))
    if errors:
        message = "; ".join(f"{'.'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors)
        raise ValueError(message)


def normalize_claim(raw: dict) -> dict:
    claim = copy.deepcopy(raw)
    statement = str(claim.get("statement", "")).strip()
    if not statement:
        raise ValueError("statement is required")
    claim["statement"] = statement
    claim["statement_hash"] = hashlib.sha256(statement.encode("utf-8")).hexdigest()
    claim.setdefault("freshness_deadline", None)
    claim.setdefault("conflict_key", None)
    claim.setdefault("reproducibility", "unknown")
    claim.setdefault("benchmark_refs", [])
    claim.setdefault("confidence", 0.5)
    claim.setdefault("contradiction_ids", [])
    claim.setdefault("verification_state", "unverified")
    claim.setdefault("source_integrity", 0.5)
    _validate(claim)
    return claim


def score_claim_evidence(claim: dict, *, now: str) -> float:
    # Learning layer is intentionally absent. Peer layer identity is not evidence.
    authority = _AUTHORITY.get(str(claim.get("authority_type")), 0.25)
    deadline = _parse_time(claim.get("freshness_deadline"))
    current = _parse_time(now)
    freshness = 1.0 if deadline is None or (current is not None and deadline >= current) else 0.0
    reproducibility = _REPRO.get(str(claim.get("reproducibility")), 0.0)
    refs = [x for x in claim.get("benchmark_refs", []) if x]
    benchmark = min(1.0, len(refs) / 1.0) if refs else 0.0
    verification = _VERIFY.get(str(claim.get("verification_state")), 0.0)
    integrity = max(0.0, min(1.0, float(claim.get("source_integrity", 0.0))))
    score = (
        authority * 0.22
        + freshness * 0.14
        + reproducibility * 0.20
        + benchmark * 0.14
        + verification * 0.20
        + integrity * 0.10
    )
    return round(score, 6)


def link_contradictions(claims: list[dict]) -> list[dict]:
    linked = [copy.deepcopy(c) for c in claims]
    groups: dict[str, list[dict]] = {}
    for claim in linked:
        key = claim.get("conflict_key")
        if key:
            groups.setdefault(str(key), []).append(claim)
    for group in groups.values():
        for claim in group:
            contradictions = {
                other["claim_id"]
                for other in group
                if other["claim_id"] != claim["claim_id"]
                and other.get("statement_hash") != claim.get("statement_hash")
            }
            claim["contradiction_ids"] = sorted(set(claim.get("contradiction_ids", [])) | contradictions)
    return linked


def resolve_claim_set(claims: list[dict], verification: dict) -> dict:
    normalized = [copy.deepcopy(c) for c in claims]
    for claim in normalized:
        override = verification.get(claim["claim_id"])
        if override in _VERIFY:
            claim["verification_state"] = override

    # Resolve against the newest observed time in the set so scoring remains deterministic.
    now = max((c.get("observed_at", "1970-01-01T00:00:00Z") for c in normalized), default="1970-01-01T00:00:00Z")
    scores = {c["claim_id"]: score_claim_evidence(c, now=now) for c in normalized}

    by_conflict: dict[str, list[dict]] = {}
    standalone: list[dict] = []
    for claim in normalized:
        key = claim.get("conflict_key")
        if key:
            by_conflict.setdefault(str(key), []).append(claim)
        else:
            standalone.append(claim)

    accepted: list[str] = []
    rejected: list[str] = []
    unresolved: list[str] = []

    for claim in standalone:
        if claim.get("verification_state") == "rejected":
            rejected.append(claim["claim_id"])
        else:
            accepted.append(claim["claim_id"])

    for group in by_conflict.values():
        statements = {c.get("statement_hash") for c in group}
        if len(statements) <= 1:
            eligible = [c for c in group if c.get("verification_state") != "rejected"]
            accepted.extend(c["claim_id"] for c in eligible)
            rejected.extend(c["claim_id"] for c in group if c.get("verification_state") == "rejected")
            continue

        ranked = sorted(group, key=lambda c: (-scores[c["claim_id"]], c["claim_id"]))
        top = ranked[0]
        runner = ranked[1]
        top_score = scores[top["claim_id"]]
        margin = top_score - scores[runner["claim_id"]]
        decisive = (
            top.get("verification_state") == "verified"
            and top.get("reproducibility") == "reproduced"
            and margin >= 0.15
        )
        if decisive:
            accepted.append(top["claim_id"])
            rejected.extend(c["claim_id"] for c in ranked[1:])
        else:
            unresolved.extend(c["claim_id"] for c in group if c.get("verification_state") != "rejected")
            rejected.extend(c["claim_id"] for c in group if c.get("verification_state") == "rejected")

    return {
        "accepted_claim_ids": sorted(set(accepted)),
        "rejected_claim_ids": sorted(set(rejected)),
        "unresolved_claim_ids": sorted(set(unresolved)),
        "scores": scores,
        "promotion_blocked": bool(unresolved),
        "majority_vote_used": False,
        "routing_authority": False,
        "reasoning_authority": False,
    }
