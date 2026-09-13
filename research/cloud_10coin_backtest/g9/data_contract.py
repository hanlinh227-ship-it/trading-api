from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Any, Mapping


CONTRACT_VERSION = 1
ALLOWED_FRESHNESS = {"FRESH", "DEGRADED", "STALE", "UNKNOWN"}
AUTHORITY_SCOPE = "research_evidence"


def _iso(value: datetime | str) -> str:
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return parsed.isoformat()
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.isoformat()


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def compute_payload_hash(payload: Any) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def build_envelope(
    *,
    kind: str,
    source: str,
    source_sha: str,
    event_time: datetime | str,
    ingest_time: datetime | str,
    freshness: str,
    payload: Mapping[str, Any] | list[Any],
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_freshness = str(freshness).upper()
    envelope = {
        "contract_version": CONTRACT_VERSION,
        "kind": str(kind),
        "source": str(source),
        "source_sha": str(source_sha),
        "event_time": _iso(event_time),
        "ingest_time": _iso(ingest_time),
        "freshness": normalized_freshness,
        "authority": {
            "scope": AUTHORITY_SCOPE,
            "execution": "none",
        },
        "research_only": True,
        "production_execution_authority": False,
        "provenance": dict(provenance),
        "payload": payload,
    }
    envelope["payload_hash"] = compute_payload_hash(payload)
    return envelope


def validate_envelope(payload: Mapping[str, Any]) -> list[str]:
    if not isinstance(payload, Mapping):
        return ["ENVELOPE_INVALID"]
    errors: list[str] = []

    if payload.get("contract_version") != CONTRACT_VERSION:
        errors.append("CONTRACT_VERSION_INVALID")
    if not isinstance(payload.get("kind"), str) or not payload.get("kind"):
        errors.append("KIND_REQUIRED")
    if not isinstance(payload.get("source"), str) or not payload.get("source"):
        errors.append("SOURCE_REQUIRED")
    if not isinstance(payload.get("source_sha"), str) or not payload.get("source_sha"):
        errors.append("SOURCE_SHA_REQUIRED")
    if str(payload.get("freshness") or "").upper() not in ALLOWED_FRESHNESS:
        errors.append("FRESHNESS_INVALID")

    event_time = _parse_time(payload.get("event_time"))
    ingest_time = _parse_time(payload.get("ingest_time"))
    if event_time is None:
        errors.append("EVENT_TIME_INVALID")
    if ingest_time is None:
        errors.append("INGEST_TIME_INVALID")
    if event_time is not None and ingest_time is not None and event_time > ingest_time:
        errors.append("EVENT_AFTER_INGEST")

    authority = payload.get("authority")
    if not isinstance(authority, Mapping):
        errors.append("AUTHORITY_INVALID")
    else:
        if authority.get("scope") != AUTHORITY_SCOPE:
            errors.append("AUTHORITY_SCOPE_INVALID")
        if authority.get("execution") != "none":
            errors.append("EXECUTION_AUTHORITY_FORBIDDEN")
    if payload.get("research_only") is not True:
        errors.append("RESEARCH_ONLY_REQUIRED")
    if payload.get("production_execution_authority") is not False:
        errors.append("PRODUCTION_EXECUTION_AUTHORITY_FORBIDDEN")
    if not isinstance(payload.get("provenance"), Mapping):
        errors.append("PROVENANCE_INVALID")

    body = payload.get("payload")
    expected = payload.get("payload_hash")
    if not isinstance(expected, str) or len(expected) != 64:
        errors.append("PAYLOAD_HASH_INVALID")
    else:
        try:
            actual = compute_payload_hash(body)
        except (TypeError, ValueError):
            errors.append("PAYLOAD_INVALID")
        else:
            if actual != expected:
                errors.append("PAYLOAD_HASH_MISMATCH")
    return errors
