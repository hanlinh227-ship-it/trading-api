from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


V4_ROOT = Path(__file__).resolve().parents[1]
PROVIDER_SCHEMA_PATH = V4_ROOT / "schemas/model_mesh_provider.schema.json"

_FREE_STATUSES = {
    "recurring",
    "limited_time",
    "trial_credit",
    "account_specific",
    "unknown",
    "paid",
    "expired",
}
_ELIGIBLE_FREE_STATUSES = {"recurring", "limited_time", "trial_credit", "account_specific"}
_PROVIDER_CLASSES = {"F1", "F2", "F3", "Q"}
_ENDPOINT_FAMILIES = {"openai_compatible", "anthropic_compatible", "native", "other"}
_QUOTA_SCOPES = {"provider", "account", "project", "model", "unknown"}
_RESET_SEMANTICS = {"rolling", "minute", "hour", "daily", "monthly", "none", "unknown"}
_PRIVACY_CLASSES = {"public_safe", "restricted", "confidential_safe", "unknown"}
_USAGE_TERMS = {"prototyping", "evaluation", "production_allowed", "unknown"}
_HEALTH_STATES = {"healthy", "degraded", "cooldown", "unavailable"}


def _schema_validator() -> Draft202012Validator:
    schema = json.loads(PROVIDER_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _clean_string(value: object, *, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _enum(value: object, allowed: set[str], *, default: str) -> str:
    text = _clean_string(value, default=default).lower()
    return text if text in allowed else default


def _nullable_number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if number == number and number not in {float("inf"), float("-inf")}:
            return number
    return None


def _quality_scores(value: object) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, float] = {}
    for key, raw in value.items():
        number = _nullable_number(raw)
        if number is None or not (0.0 <= number <= 1.0):
            continue
        name = _clean_string(key)
        if name:
            result[name] = number
    return result


def _capabilities(value: object) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for key, raw in value.items():
        name = _clean_string(key)
        if not name or not isinstance(raw, dict):
            continue
        supported = raw.get("supported", "unknown")
        if supported not in {True, False, "unknown"}:
            supported = "unknown"
        score = _nullable_number(raw.get("score"))
        if score is None or not (0.0 <= score <= 1.0):
            score = 0.0
        evidence_raw = raw.get("evidence", [])
        evidence = [
            _clean_string(item)
            for item in evidence_raw
            if _clean_string(item)
        ] if isinstance(evidence_raw, list) else []
        verified_at = raw.get("verified_at")
        result[name] = {
            "supported": supported,
            "score": score,
            "evidence": evidence,
            "verified_at": _clean_string(verified_at) or None,
        }
    return result


def classify_free_status(raw: dict) -> str:
    """Classify only explicit free-status evidence; never infer free use from catalog presence."""
    if not isinstance(raw, dict):
        return "unknown"
    value = _clean_string(raw.get("free_status"), default="unknown").lower()
    return value if value in _FREE_STATUSES else "unknown"


def normalize_candidate(provider_id: str, raw: dict, *, observed_at: str) -> dict:
    """Normalize provider/model metadata into the fail-closed model-mesh contract."""
    if not isinstance(raw, dict):
        raise TypeError("raw candidate must be a mapping")
    provider = _clean_string(provider_id)
    if not provider:
        raise ValueError("provider_id is required")
    observed = _clean_string(observed_at)
    if not observed:
        raise ValueError("observed_at is required")

    provider_class = _clean_string(raw.get("provider_class"), default="Q").upper()
    if provider_class not in _PROVIDER_CLASSES:
        provider_class = "Q"

    endpoint_family = _enum(raw.get("endpoint_family"), _ENDPOINT_FAMILIES, default="other")
    quota_scope = _enum(raw.get("quota_scope"), _QUOTA_SCOPES, default="unknown")
    reset_semantics = _enum(raw.get("reset_semantics"), _RESET_SEMANTICS, default="unknown")
    privacy_class = _enum(raw.get("privacy_class"), _PRIVACY_CLASSES, default="unknown")
    usage_terms = _enum(raw.get("usage_terms"), _USAGE_TERMS, default="unknown")
    health = _enum(raw.get("health"), _HEALTH_STATES, default="unavailable")

    quota_dimensions_raw = raw.get("quota_dimensions", [])
    quota_dimensions = []
    if isinstance(quota_dimensions_raw, list):
        for item in quota_dimensions_raw:
            text = _clean_string(item)
            if text and text not in quota_dimensions:
                quota_dimensions.append(text)

    source_raw = raw.get("source_evidence", [])
    source_evidence = []
    if isinstance(source_raw, list):
        for item in source_raw:
            text = _clean_string(item)
            if text and text not in source_evidence:
                source_evidence.append(text)

    context_window_raw = raw.get("context_window")
    context_window = None
    if isinstance(context_window_raw, int) and not isinstance(context_window_raw, bool) and context_window_raw > 0:
        context_window = context_window_raw

    training_raw = raw.get("data_training_allowed_by_provider")
    training = training_raw if isinstance(training_raw, bool) else None

    candidate = {
        "provider_id": provider,
        "provider_class": provider_class,
        "model_id": _clean_string(raw.get("model_id")),
        "model_family": _clean_string(raw.get("model_family")),
        "model_variant": _clean_string(raw.get("model_variant")),
        "endpoint_family": endpoint_family,
        "free_status": classify_free_status(raw),
        "free_verified_at": _clean_string(raw.get("free_verified_at")) or None,
        "observed_at": observed,
        "quota_scope": quota_scope,
        "quota_dimensions": quota_dimensions,
        "reset_semantics": reset_semantics,
        "capabilities": _capabilities(raw.get("capabilities")),
        "context_window": context_window,
        "privacy_class": privacy_class,
        "data_training_allowed_by_provider": training,
        "retention_policy": _clean_string(raw.get("retention_policy")),
        "usage_terms": usage_terms,
        "health": health,
        "latency_ema_ms": _nullable_number(raw.get("latency_ema_ms")),
        "success_rate_ema": _nullable_number(raw.get("success_rate_ema")),
        "quality_scores": _quality_scores(raw.get("quality_scores")),
        "last_benchmark_at": _clean_string(raw.get("last_benchmark_at")) or None,
        "source_evidence": source_evidence,
    }

    errors = sorted(_schema_validator().iter_errors(candidate), key=lambda item: list(item.path))
    if errors:
        detail = "; ".join(error.message for error in errors[:4])
        raise ValueError(f"invalid normalized model candidate: {detail}")
    return candidate


def model_family_key(candidate: dict) -> str:
    """Return the explicit canonical family identity; never substring-collapse unrelated names."""
    if not isinstance(candidate, dict):
        raise TypeError("candidate must be a mapping")
    family = " ".join(_clean_string(candidate.get("model_family")).lower().split())
    if not family:
        raise ValueError("model_family is required for deduplication")
    return family


def dedupe_model_families(candidates: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for candidate in candidates:
        key = model_family_key(candidate)
        groups[key].append(candidate)
    return dict(groups)


def eligible_free_candidate(candidate: dict, *, data_class: str) -> bool:
    """Apply the FREE_ONLY and privacy gate before any scoring or provider selection."""
    if not isinstance(candidate, dict):
        return False
    classification = _clean_string(data_class).upper()
    if classification not in {"PUBLIC", "INTERNAL", "CONFIDENTIAL", "SECRET"}:
        return False
    if classification == "SECRET":
        return False
    if candidate.get("free_status") not in _ELIGIBLE_FREE_STATUSES:
        return False
    if not _clean_string(candidate.get("free_verified_at")):
        return False
    if candidate.get("health") not in {"healthy", "degraded"}:
        return False
    if candidate.get("usage_terms") == "unknown":
        return False

    privacy = candidate.get("privacy_class")
    if classification == "PUBLIC":
        return privacy in {"public_safe", "restricted", "confidential_safe"}
    return privacy == "confidential_safe"
