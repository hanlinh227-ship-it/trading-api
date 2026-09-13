from __future__ import annotations

import hashlib
import json
from typing import Any


SCHEMA_VERSION = 1
KIND = "g9_stable_trading_evidence"
PRODUCTION_STRATEGY = "BYBIT-BTC-STATEFLOW-2.1"
ALLOWED_STATUSES = {"RESEARCH_ONLY", "CERTIFIED_RESEARCH", "QUARANTINED"}


def _canonical_without_hash(payload: dict[str, Any]) -> dict[str, Any]:
    clean = dict(payload)
    clean.pop("manifest_hash", None)
    return clean


def compute_manifest_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(
        _canonical_without_hash(payload),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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
    return errors


def validate_manifest(payload: dict[str, Any]) -> list[str]:
    """Semantic alias used by G9 aggregation workflows."""
    return validate_snapshot(payload)
