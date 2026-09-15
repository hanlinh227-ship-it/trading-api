from __future__ import annotations

import json
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


V4_ROOT = Path(__file__).resolve().parents[1]
PROVIDER_SCHEMA_PATH = V4_ROOT / "schemas/model_mesh_provider.schema.json"
DOMAIN_CAPABILITIES_PATH = V4_ROOT / "model_mesh/domain_capabilities.yaml"
FREE_ONLY_POLICY_PATH = V4_ROOT / "model_mesh/free_only_policy.json"

_FREE_STATUSES = {
    "recurring",
    "limited_time",
    "trial_credit",
    "account_specific",
    "unknown",
    "paid",
    "expired",
}
_FREE_ONLY_POLICY = json.loads(FREE_ONLY_POLICY_PATH.read_text(encoding="utf-8"))
if _FREE_ONLY_POLICY.get("schema_version") != 1 or _FREE_ONLY_POLICY.get("mode") != "FREE_ONLY":
    raise ValueError("invalid canonical FREE_ONLY policy")
_ELIGIBLE_FREE_STATUSES = frozenset(_FREE_ONLY_POLICY.get("eligible_statuses", []))
_PROVIDER_CLASSES = {"F1", "F2", "F3", "Q"}
_ENDPOINT_FAMILIES = {"openai_compatible", "anthropic_compatible", "native", "other"}
_QUOTA_SCOPES = {"provider", "account", "project", "model", "unknown"}
_RESET_SEMANTICS = {"rolling", "minute", "hour", "daily", "monthly", "none", "unknown"}
_PRIVACY_CLASSES = {"public_safe", "restricted", "confidential_safe", "unknown"}
_USAGE_TERMS = {"prototyping", "evaluation", "production_allowed", "unknown"}
_HEALTH_STATES = {"healthy", "degraded", "cooldown", "unavailable"}
_ALLOWED_ROLES = {"maker", "researcher", "specialist", "critic", "checker", "grader", "summarizer"}
_PROFILE_WORKER_CAPS = {"FAST": 0, "STANDARD": 2, "DEEP": 4}
_PROVIDER_AVAILABLE_STATES = {"AVAILABLE", "LOW_HEADROOM", "DEGRADED"}


def _schema_validator() -> Draft202012Validator:
    schema = json.loads(PROVIDER_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _load_domain_capabilities() -> dict:
    data = yaml.safe_load(DOMAIN_CAPABILITIES_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("domain capability map must be a mapping")
    return data


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


def _bounded_score(value: object, *, default: float = 0.0) -> float:
    number = _nullable_number(value)
    if number is None:
        return default
    return max(0.0, min(1.0, number))


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


def required_capabilities(domain: str, primary_skill: str, *, has_image: bool = False) -> dict[str, float]:
    """Resolve execution capability weights after canonical domain/skill routing."""
    config = _load_domain_capabilities()
    domains = config.get("domains", {})
    if domain not in domains:
        raise ValueError(f"unknown model-mesh domain: {domain}")
    row = domains[domain]
    capabilities = row.get("capabilities", {}) if isinstance(row, dict) else {}
    if not isinstance(capabilities, dict) or not capabilities:
        raise ValueError(f"domain has no model-mesh capability contract: {domain}")
    result = {str(key): _bounded_score(value) for key, value in capabilities.items()}
    dimensions = set(config.get("dimensions", []))
    unknown = set(result) - dimensions
    if unknown:
        raise ValueError(f"unknown capability dimensions for {domain}: {sorted(unknown)}")
    if has_image:
        minimum = _bounded_score(config.get("policy", {}).get("image_input_min_vision_weight"), default=0.8)
        result["vision"] = max(result.get("vision", 0.0), minimum)
    return result


def _capability_fit(candidate: dict, requirements: dict[str, float]) -> float:
    capabilities = candidate.get("capabilities", {}) if isinstance(candidate, dict) else {}
    weighted = 0.0
    total = 0.0
    for name, weight_raw in requirements.items():
        weight = _bounded_score(weight_raw)
        if weight <= 0:
            continue
        row = capabilities.get(name, {}) if isinstance(capabilities, dict) else {}
        supported = row.get("supported") is True if isinstance(row, dict) else False
        score = _bounded_score(row.get("score") if isinstance(row, dict) else 0.0)
        weighted += weight * (score if supported else 0.0)
        total += weight
    return weighted / total if total > 0 else 0.0


def _measured_quality(candidate: dict) -> float:
    scores = candidate.get("quality_scores", {}) if isinstance(candidate, dict) else {}
    values = [_bounded_score(value) for value in scores.values()] if isinstance(scores, dict) else []
    if values:
        return sum(values) / len(values)
    return _bounded_score(candidate.get("success_rate_ema"), default=0.0)


def score_candidate(
    candidate: dict,
    requirements: dict[str, float],
    *,
    quota_headroom: float,
    reputation: float,
) -> float:
    """Score only candidates that already passed policy gates; quality dominates quota."""
    config = _load_domain_capabilities()
    weights = config.get("scoring", {})
    capability_fit = _capability_fit(candidate, requirements)
    measured_quality = _measured_quality(candidate)
    reliability = _bounded_score(candidate.get("success_rate_ema"), default=0.0)
    quota = _bounded_score(quota_headroom)
    rep = _bounded_score(reputation, default=0.5)
    latency = _nullable_number(candidate.get("latency_ema_ms"))
    latency_efficiency = 0.0 if latency is None else 1.0 / (1.0 + max(0.0, latency) / 1000.0)
    components = {
        "capability_fit": capability_fit,
        "measured_quality": measured_quality,
        "reputation": (rep + reliability) / 2.0,
        "quota_headroom": quota,
        "latency_efficiency": latency_efficiency,
    }
    total_weight = sum(_bounded_score(value) for value in weights.values())
    if total_weight <= 0:
        return 0.0
    score = sum(_bounded_score(weights.get(name)) * value for name, value in components.items()) / total_weight
    return round(_bounded_score(score), 6)


def _passes_capability_floor(candidate: dict, requirements: dict[str, float], config: dict) -> bool:
    policy = config.get("policy", {})
    weight_threshold = _bounded_score(policy.get("hard_capability_weight_threshold"), default=0.7)
    min_score = _bounded_score(policy.get("hard_capability_min_score"), default=0.35)
    capabilities = candidate.get("capabilities", {}) if isinstance(candidate, dict) else {}
    for name, weight_raw in requirements.items():
        weight = _bounded_score(weight_raw)
        if weight < weight_threshold:
            continue
        row = capabilities.get(name, {}) if isinstance(capabilities, dict) else {}
        if not isinstance(row, dict) or row.get("supported") is not True:
            return False
        if _bounded_score(row.get("score")) < min_score:
            return False
    return True


def _candidate_key(candidate: dict) -> str:
    return f"{candidate.get('provider_id', '')}:{candidate.get('model_id', '')}"


def select_workers(task: dict, candidates: list[dict], *, max_workers: int) -> list[dict]:
    """Filter before score, preserve model-family diversity, and return bounded execution workers."""
    if not isinstance(task, dict):
        raise TypeError("task must be a mapping")
    profile = _clean_string(task.get("profile")).upper()
    if profile not in _PROFILE_WORKER_CAPS:
        raise ValueError(f"unknown model-mesh profile: {profile}")
    if profile == "FAST":
        return []
    try:
        requested_max = max(0, int(max_workers))
    except (TypeError, ValueError):
        requested_max = 0
    cap = min(requested_max, _PROFILE_WORKER_CAPS[profile])
    if cap <= 0:
        return []

    domain = _clean_string(task.get("domain"))
    primary_skill = _clean_string(task.get("primary_skill"))
    data_class = _clean_string(task.get("data_class"), default="PUBLIC").upper()
    has_image = bool(task.get("has_image", False))
    requirements = required_capabilities(domain, primary_skill, has_image=has_image)
    config = _load_domain_capabilities()
    domains = config.get("domains", {})
    research_only = bool(domains.get(domain, {}).get("research_only", False))

    role = _clean_string(task.get("role"), default="specialist").lower()
    if role not in _ALLOWED_ROLES:
        role = "specialist"

    permission_allowed = task.get("permission_allowed", {})
    quota_headroom = task.get("quota_headroom", {})
    reputation = task.get("reputation", {})
    if not isinstance(permission_allowed, dict) or not isinstance(quota_headroom, dict) or not isinstance(reputation, dict):
        return []
    context_tokens_raw = task.get("context_tokens", 0)
    context_tokens = context_tokens_raw if isinstance(context_tokens_raw, int) and not isinstance(context_tokens_raw, bool) and context_tokens_raw > 0 else 0

    qualified: list[tuple[float, dict]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        key = _candidate_key(candidate)
        if permission_allowed.get(key) is not True:
            continue
        if not eligible_free_candidate(candidate, data_class=data_class):
            continue
        headroom = _nullable_number(quota_headroom.get(key))
        if headroom is None or headroom <= 0:
            continue
        if context_tokens:
            window = candidate.get("context_window")
            if not isinstance(window, int) or isinstance(window, bool) or window < context_tokens:
                continue
        if not _passes_capability_floor(candidate, requirements, config):
            continue
        rep = _bounded_score(reputation.get(key), default=0.5)
        score = score_candidate(candidate, requirements, quota_headroom=headroom, reputation=rep)
        qualified.append((score, candidate))

    qualified.sort(key=lambda item: (-item[0], _candidate_key(item[1])))
    by_family: dict[str, list[tuple[float, dict]]] = defaultdict(list)
    family_order: list[str] = []
    for item in qualified:
        family = model_family_key(item[1])
        if family not in by_family:
            family_order.append(family)
        by_family[family].append(item)

    family_primaries: list[tuple[float, str, dict, list[dict]]] = []
    for family in family_order:
        rows = by_family[family]
        primary_score, primary = rows[0]
        fallbacks = [
            {"provider_id": candidate["provider_id"], "model_id": candidate["model_id"]}
            for _, candidate in rows[1:]
        ]
        family_primaries.append((primary_score, family, primary, fallbacks))
    family_primaries.sort(key=lambda item: (-item[0], _candidate_key(item[2])))

    selected: list[dict] = []
    for selection_score, _, candidate, fallbacks in family_primaries[:cap]:
        worker = dict(candidate)
        worker["selection_score"] = selection_score
        worker["worker_role"] = role
        worker["fallback_provider_paths"] = fallbacks
        worker["research_only"] = research_only
        selected.append(worker)
    return selected


def _parse_timestamp(value: object) -> datetime | None:
    text = _clean_string(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _future_timestamp(now: datetime, seconds: object, *, default_seconds: int = 60) -> str:
    number = _nullable_number(seconds)
    bounded = default_seconds if number is None else max(1, min(int(number), 86400))
    return _format_timestamp(now + timedelta(seconds=bounded))


def _preferred_probe_time(event: dict, now: datetime, *, default_seconds: int = 60) -> str:
    explicit = _parse_timestamp(event.get("reset_at"))
    if explicit is not None and explicit >= now:
        return _format_timestamp(explicit)
    return _future_timestamp(now, event.get("retry_after_seconds"), default_seconds=default_seconds)


def next_probe_at(state: dict) -> str | None:
    if not isinstance(state, dict) or state.get("retry_allowed") is False:
        return None
    status = state.get("status")
    if status in {"COOLDOWN_QUOTA", "PROBE_READY"}:
        return _clean_string(state.get("reset_at")) or None
    if status in {"CIRCUIT_OPEN", "HALF_OPEN"}:
        return _clean_string(state.get("probe_at")) or None
    return None


def provider_available(state: dict, *, now: str) -> bool:
    if not isinstance(state, dict) or state.get("retry_allowed") is False:
        return False
    if _parse_timestamp(now) is None:
        return False
    return state.get("status") in _PROVIDER_AVAILABLE_STATES


def apply_quota_event(state: dict, event: dict, *, now: str) -> dict:
    """Apply a sanitized immutable provider quota/health state transition.

    The state machine never emits account/key/IP/proxy/region rotation or other quota-circumvention actions.
    """
    if not isinstance(state, dict) or not isinstance(event, dict):
        raise TypeError("state and event must be mappings")
    now_dt = _parse_timestamp(now)
    if now_dt is None:
        raise ValueError("now must be an ISO-8601 timestamp")

    result = deepcopy(state)
    result.setdefault("status", "AVAILABLE")
    result.setdefault("consecutive_failures", 0)
    result.setdefault("quota_headroom", 1.0)
    result.setdefault("reset_at", None)
    result.setdefault("probe_at", None)
    result.setdefault("retry_allowed", True)
    result.setdefault("last_failure_class", None)
    result["updated_at"] = _format_timestamp(now_dt)

    kind = _clean_string(event.get("type")).lower()

    if kind == "quota":
        remaining = _bounded_score(event.get("remaining_ratio"), default=0.0)
        result["quota_headroom"] = remaining
        if remaining <= 0.0:
            result["status"] = "COOLDOWN_QUOTA"
            reset = _preferred_probe_time(event, now_dt)
            result["reset_at"] = reset
            result["probe_at"] = reset
            result["last_failure_class"] = "quota_exhausted"
        elif remaining <= 0.15:
            result["status"] = "LOW_HEADROOM"
        elif result.get("status") in {"LOW_HEADROOM", "DEGRADED"}:
            result["status"] = "AVAILABLE"
        return result

    if kind == "http_error" and int(event.get("status_code") or 0) == 429:
        reset = _preferred_probe_time(event, now_dt)
        result["status"] = "COOLDOWN_QUOTA"
        result["quota_headroom"] = 0.0
        result["reset_at"] = reset
        result["probe_at"] = reset
        result["last_failure_class"] = "rate_limit"
        result["retry_allowed"] = True
        return result

    if kind == "invalid_credentials":
        result["status"] = "UNAVAILABLE"
        result["retry_allowed"] = False
        result["reset_at"] = None
        result["probe_at"] = None
        result["last_failure_class"] = "invalid_credentials"
        return result

    if kind == "transient_failure":
        failures = max(0, int(result.get("consecutive_failures") or 0)) + 1
        result["consecutive_failures"] = failures
        result["last_failure_class"] = "transient"
        if failures >= 3:
            result["status"] = "CIRCUIT_OPEN"
            result["probe_at"] = _preferred_probe_time(event, now_dt)
        else:
            result["status"] = "DEGRADED"
        return result

    if kind == "tick":
        if result.get("status") == "COOLDOWN_QUOTA":
            reset = _parse_timestamp(result.get("reset_at"))
            if reset is not None and now_dt >= reset:
                result["status"] = "PROBE_READY"
            return result
        if result.get("status") == "CIRCUIT_OPEN":
            probe = _parse_timestamp(result.get("probe_at"))
            if probe is not None and now_dt >= probe:
                result["status"] = "HALF_OPEN"
            return result
        return result

    if kind in {"probe_success", "success"}:
        result["status"] = "AVAILABLE"
        result["consecutive_failures"] = 0
        result["quota_headroom"] = max(_bounded_score(result.get("quota_headroom")), 0.5)
        result["reset_at"] = None
        result["probe_at"] = None
        result["retry_allowed"] = True
        result["last_failure_class"] = None
        return result

    if kind == "probe_failure":
        result["consecutive_failures"] = max(1, int(result.get("consecutive_failures") or 0) + 1)
        result["last_failure_class"] = "probe_failure"
        probe = _preferred_probe_time(event, now_dt)
        if result.get("status") == "PROBE_READY":
            result["status"] = "COOLDOWN_QUOTA"
            result["reset_at"] = probe
        else:
            result["status"] = "CIRCUIT_OPEN"
            result["probe_at"] = probe
        return result

    return result
