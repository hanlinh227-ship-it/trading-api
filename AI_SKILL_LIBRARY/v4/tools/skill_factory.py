from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator


_PERMISSION_RANK = {"read_only": 0, "bounded_write": 1, "sandbox_execute": 2}
_RISK_RANK = {"A": 0, "B": 1, "C": 2, "D": 3}
_ALLOWED_LAYERS = {"experience", "curated", "exploration"}


def _canonical_payload(items: list[dict], domain: str) -> str:
    normalized = [
        {
            "claim_id": str(item.get("claim_id", "")),
            "learning_layer": str(item.get("learning_layer", "")),
            "content": str(item.get("content", "")),
        }
        for item in items
    ]
    return json.dumps({"domain": domain, "items": normalized}, sort_keys=True, separators=(",", ":"))


def _digest(items: list[dict], domain: str) -> str:
    return hashlib.sha256(_canonical_payload(items, domain).encode("utf-8")).hexdigest()


def triage_experience(item: dict, existing_skills: list[dict]) -> str:
    if not item.get("reusable", False):
        return "discard"
    skill_id = item.get("skill_id")
    if skill_id and item.get("is_correction") and any(s.get("skill_id") == skill_id for s in existing_skills):
        return "improve"
    signature = item.get("signature")
    domain = item.get("domain")
    if signature and any(s.get("signature") == signature and s.get("domain") == domain for s in existing_skills):
        return "merge"
    return "create"


def create_skill_candidate(items: list[dict], domain: str) -> dict:
    if not items:
        raise ValueError("skill candidate requires at least one source item")
    claims = [str(item.get("claim_id", "")).strip() for item in items]
    if any(not claim for claim in claims):
        raise ValueError("each source item requires claim_id")
    layers = sorted({str(item.get("learning_layer", "")) for item in items})
    if not set(layers).issubset(_ALLOWED_LAYERS) or not layers:
        raise ValueError("invalid learning layer")
    digest = _digest(items, domain)
    observed = sorted(str(item.get("observed_at")) for item in items if item.get("observed_at"))
    created_at = observed[-1] if observed else "1970-01-01T00:00:00Z"
    candidate = {
        "candidate_id": f"candidate-{digest[:20]}",
        "skill_id": f"skill-{domain}-{digest[:12]}",
        "lineage_id": f"lineage-{domain}-{digest[:16]}",
        "parent_version": None,
        "domain": domain,
        "source_claims": sorted(set(claims), key=claims.index),
        "learning_layers": layers,
        "risk_class": "A",
        "permission_ceiling": "read_only",
        "eval_plan": ["replay", "protected_regression", "permission_ceiling", "provenance"],
        "status": "incubating",
        "created_at": created_at,
        "stable_write_allowed": False,
        "content_digest": digest,
    }
    errors = validate_skill_lineage(candidate)
    if errors:
        raise ValueError("invalid generated skill candidate: " + "; ".join(errors))
    return candidate


def merge_skill_candidate(base: dict, candidate: dict) -> dict:
    merged = copy.deepcopy(base)
    merged["source_claims"] = sorted(set(base.get("source_claims", [])) | set(candidate.get("source_claims", [])))
    merged["learning_layers"] = sorted(set(base.get("learning_layers", [])) | set(candidate.get("learning_layers", [])))
    base_perm = base.get("permission_ceiling", "read_only")
    candidate_perm = candidate.get("permission_ceiling", "read_only")
    merged["permission_ceiling"] = min((base_perm, candidate_perm), key=lambda value: _PERMISSION_RANK.get(value, -1))
    base_risk = base.get("risk_class", "A")
    candidate_risk = candidate.get("risk_class", "A")
    merged["risk_class"] = max((base_risk, candidate_risk), key=lambda value: _RISK_RANK.get(value, 99))
    merged["status"] = "incubating"
    merged["stable_write_allowed"] = False
    merged["parent_version"] = base.get("parent_version")
    merged["eval_plan"] = sorted(set(base.get("eval_plan", [])) | set(candidate.get("eval_plan", [])))
    digest = hashlib.sha256(json.dumps({
        "lineage_id": merged.get("lineage_id"),
        "source_claims": merged["source_claims"],
        "learning_layers": merged["learning_layers"],
        "risk_class": merged["risk_class"],
        "permission_ceiling": merged["permission_ceiling"],
    }, sort_keys=True).encode("utf-8")).hexdigest()
    merged["candidate_id"] = f"candidate-{digest[:20]}"
    merged["content_digest"] = digest
    return merged


def validate_skill_lineage(candidate: dict) -> list[str]:
    root = Path(__file__).resolve().parents[3]
    schema = json.loads((root / "AI_SKILL_LIBRARY/v4/schemas/skill_candidate.schema.json").read_text(encoding="utf-8"))
    errors = [
        f"{'.'.join(map(str, error.path)) or '<root>'}: {error.message}"
        for error in Draft202012Validator(schema).iter_errors(candidate)
    ]
    if candidate.get("status") != "incubating":
        errors.append("status must remain incubating in Skill Factory")
    if candidate.get("stable_write_allowed") is not False:
        errors.append("stable_write_allowed must be false")
    if not candidate.get("source_claims"):
        errors.append("source_claims provenance is required")
    if not candidate.get("lineage_id"):
        errors.append("lineage_id is required")
    if set(candidate.get("learning_layers", [])) - _ALLOWED_LAYERS:
        errors.append("unknown learning layer")
    return sorted(set(errors))
