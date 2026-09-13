from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Any


SCHEMA_VERSION = 1
KIND = "g9_stable_trading_evidence"
PRODUCTION_STRATEGY = "BYBIT-BTC-STATEFLOW-2.1"
ALLOWED_STATUSES = {"RESEARCH_ONLY", "CERTIFIED_RESEARCH", "QUARANTINED"}
ALLOWED_FRESHNESS = {"FRESH", "DEGRADED", "STALE", "UNKNOWN"}


def _canonical_without_hash(payload: dict[str, Any]) -> dict[str, Any]:
    clean = dict(payload)
    clean.pop("manifest_hash", None)
    clean.pop("data_contract", None)
    return clean


def compute_manifest_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(
        _canonical_without_hash(payload),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _payload_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _validate_data_contract(payload: dict[str, Any]) -> list[str]:
    contract = payload.get("data_contract")
    if not isinstance(contract, dict):
        return ["data-contract:missing"]
    errors: list[str] = []
    if contract.get("contract_version") != 1:
        errors.append("data-contract:version-invalid")
    if contract.get("research_only") is not True:
        errors.append("data-contract:research-only-required")
    if contract.get("production_execution_authority") is not False:
        errors.append("data-contract:production-execution-authority-forbidden")
    if contract.get("freshness") not in ALLOWED_FRESHNESS:
        errors.append("data-contract:freshness-invalid")
    authority = contract.get("authority")
    if not isinstance(authority, dict):
        errors.append("data-contract:authority-invalid")
    else:
        if authority.get("scope") != "research_evidence":
            errors.append("data-contract:authority-scope-invalid")
        if authority.get("execution") != "none":
            errors.append("data-contract:execution-authority-forbidden")
    event_time = _parse_time(contract.get("event_time"))
    ingest_time = _parse_time(contract.get("ingest_time"))
    if event_time is None:
        errors.append("data-contract:event-time-invalid")
    if ingest_time is None:
        errors.append("data-contract:ingest-time-invalid")
    if event_time is not None and ingest_time is not None and event_time > ingest_time:
        errors.append("data-contract:event-after-ingest")
    if not isinstance(contract.get("provenance"), dict):
        errors.append("data-contract:provenance-invalid")
    expected = contract.get("payload_hash")
    body = {key: value for key, value in payload.items() if key != "data_contract"}
    if not isinstance(expected, str) or len(expected) != 64:
        errors.append("data-contract:payload-hash-invalid")
    else:
        try:
            actual = _payload_hash(contract.get("payload"))
        except (TypeError, ValueError):
            errors.append("data-contract:payload-invalid")
        else:
            if actual != expected:
                errors.append("data-contract:payload-hash-mismatch")
    if contract.get("payload") != body:
        errors.append("data-contract:payload-mismatch")
    return errors


def validate_snapshot(payload: dict[str, Any]) -> list[str]:
    if not isinstance(payload, dict):
        return ["snapshot-must-be-object"]

    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema-version-invalid")
    if payload.get("kind") != KIND:
        errors.append("kind-invalid")
    if payload.get("research_only") is not True:
        errors.append("research-only-required")
    if payload.get("production_execution_authority") is not False:
        errors.append("production-execution-authority-forbidden")

    authority = payload.get("authority")
    if not isinstance(authority, dict):
        errors.append("authority-invalid")
    else:
        if authority.get("execution") != "none":
            errors.append("execution-authority-forbidden")
        if authority.get("production_strategy") != PRODUCTION_STRATEGY:
            errors.append("production-strategy-mismatch")

    source_sha = payload.get("source_sha")
    if not isinstance(source_sha, str) or not source_sha:
        errors.append("source-sha-required")

    parent_hash = payload.get("parent_snapshot_hash")
    if not isinstance(parent_hash, str) or len(parent_hash) != 64:
        errors.append("parent-snapshot-hash-invalid")

    symbols = payload.get("symbols")
    if not isinstance(symbols, dict) or not symbols:
        errors.append("symbols-required")
    else:
        for symbol, row in sorted(symbols.items()):
            if not isinstance(row, dict):
                errors.append(f"{symbol}:row-invalid")
                continue
            if row.get("status") not in ALLOWED_STATUSES:
                errors.append(f"{symbol}:status-invalid")
            if row.get("production_execution_authority") is not False:
                errors.append(f"{symbol}:production-execution-authority-forbidden")
            epoch = row.get("evidence_epoch")
            if epoch is not None and not isinstance(epoch, str):
                errors.append(f"{symbol}:evidence-epoch-invalid")

    expected = payload.get("manifest_hash")
    if not isinstance(expected, str) or len(expected) != 64:
        errors.append("manifest-hash-invalid")
    else:
        try:
            int(expected, 16)
        except ValueError:
            errors.append("manifest-hash-invalid")
        else:
            if expected != compute_manifest_hash(payload):
                errors.append("manifest-hash-mismatch")
    errors.extend(_validate_data_contract(payload))
    return errors


def validate_manifest(payload: dict[str, Any]) -> list[str]:
    """Semantic alias used by G9 aggregation workflows."""
    return validate_snapshot(payload)
