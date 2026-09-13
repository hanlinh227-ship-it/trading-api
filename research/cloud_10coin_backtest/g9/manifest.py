from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .system_contract import SYSTEM_CONTRACT_VERSION


SCHEMA_VERSION = 1
KIND = "g9_stable_trading_evidence"
PRODUCTION_STRATEGY = "BYBIT-BTC-STATEFLOW-2.1"
PLANE = "STABLE_EVIDENCE"
AUTHORITY_LEVEL = "STABLE_EVIDENCE"
ALLOWED_STATUSES = {"RESEARCH_ONLY", "CERTIFIED_RESEARCH", "QUARANTINED"}


def _canonical_without_hash(payload: Mapping[str, Any]) -> dict[str, Any]:
    clean = dict(payload)
    clean.pop("manifest_hash", None)
    return clean


def compute_manifest_hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(
        _canonical_without_hash(payload),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_evidence_manifest(payload: Mapping[str, Any]) -> list[str]:
    if not isinstance(payload, Mapping):
        return ["snapshot-must-be-object"]
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema-version-invalid")
    if payload.get("kind") != KIND:
        errors.append("kind-invalid")
    if payload.get("system_contract_version") != SYSTEM_CONTRACT_VERSION:
        errors.append("system-contract-version-invalid")
    if payload.get("plane") != PLANE:
        errors.append("plane-invalid")
    if payload.get("authority_level") != AUTHORITY_LEVEL:
        errors.append("authority-level-invalid")
    if payload.get("research_only") is not True:
        errors.append("research-only-required")
    if payload.get("production_execution_authority") is not False:
        errors.append("production-execution-authority-forbidden")

    authority = payload.get("authority")
    if not isinstance(authority, Mapping):
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
    if not isinstance(symbols, Mapping) or not symbols:
        errors.append("symbols-required")
    else:
        for symbol, row in sorted(symbols.items()):
            if not isinstance(row, Mapping):
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


def build_evidence_manifest(
    g8_snapshot: Mapping[str, Any],
    *,
    source_sha: str,
    evidence_epochs: Mapping[str, str],
) -> dict[str, Any]:
    source_sha = str(source_sha)
    if not source_sha:
        raise ValueError("source_sha is required")
    if g8_snapshot.get("research_only") is not True:
        raise ValueError("parent G8 snapshot must be research-only")
    parent_authority = g8_snapshot.get("authority")
    if not isinstance(parent_authority, Mapping) or parent_authority.get("execution") != "none":
        raise ValueError("parent G8 snapshot execution authority is forbidden")

    parent_hash = str(g8_snapshot.get("snapshot_hash") or "")
    if len(parent_hash) != 64:
        raise ValueError("parent snapshot hash is required")

    symbols_payload = g8_snapshot.get("symbols")
    if not isinstance(symbols_payload, Mapping) or not symbols_payload:
        raise ValueError("parent G8 symbols are required")

    symbols: dict[str, dict[str, Any]] = {}
    for symbol, row_value in sorted(symbols_payload.items()):
        row = dict(row_value)
        if row.get("production_execution_authority") is not False:
            raise ValueError(f"{symbol}: parent execution authority is forbidden")
        normalized = str(symbol).upper()
        symbols[normalized] = {
            "profile_hash": row.get("profile_hash"),
            "status": row.get("status", "QUARANTINED"),
            "evidence_epoch": evidence_epochs.get(normalized),
            "oof_metrics": dict(row.get("oof_metrics") or {}),
            "certification_metrics": dict(row.get("certification_metrics") or {}),
            "production_execution_authority": False,
        }

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "system_contract_version": SYSTEM_CONTRACT_VERSION,
        "plane": PLANE,
        "authority_level": AUTHORITY_LEVEL,
        "research_only": True,
        "production_execution_authority": False,
        "authority": {
            "execution": "none",
            "production_strategy": PRODUCTION_STRATEGY,
        },
        "source_sha": source_sha,
        "parent_snapshot_hash": parent_hash,
        "data_cutoff": g8_snapshot.get("data_cutoff"),
        "symbols": symbols,
    }
    payload["manifest_hash"] = compute_manifest_hash(payload)
    errors = validate_evidence_manifest(payload)
    if errors:
        raise ValueError("invalid G9 stable evidence manifest: " + ",".join(errors))
    return payload
