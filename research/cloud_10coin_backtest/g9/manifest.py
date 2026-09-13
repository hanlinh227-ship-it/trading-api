from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


SCHEMA_VERSION = 1
KIND = "g9_stable_trading_evidence"
PRODUCTION_STRATEGY = "BYBIT-BTC-STATEFLOW-2.1"


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
            "production_execution_authority": False,
        }

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
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
    return payload
