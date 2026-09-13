from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .data_contract import validate_envelope
from .manifest import KIND, PRODUCTION_STRATEGY, SCHEMA_VERSION, compute_manifest_hash


_VALID_STATUSES = {"RESEARCH_ONLY", "CERTIFIED_RESEARCH", "QUARANTINED"}
_LIVE_FRESHNESS = {"FRESH", "DEGRADED"}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid evidence manifest: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"invalid evidence manifest: {path}")
    return payload


def _embedded_contract_errors(payload: Mapping[str, Any], *, field: str) -> list[str]:
    contract = payload.get(field)
    if not isinstance(contract, Mapping):
        return [f"{field.upper()}_MISSING"]
    errors = [f"{field.upper()}:{item}" for item in validate_envelope(contract)]
    body = {key: value for key, value in payload.items() if key != field}
    if contract.get("payload") != body:
        errors.append(f"{field.upper()}:PAYLOAD_MISMATCH")
    return errors


def _manifest_errors(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("SCHEMA_VERSION_INVALID")
    if payload.get("kind") != KIND:
        errors.append("KIND_INVALID")
    if payload.get("research_only") is not True:
        errors.append("RESEARCH_ONLY_REQUIRED")
    if payload.get("production_execution_authority") is not False:
        errors.append("EXECUTION_AUTHORITY_FORBIDDEN")

    authority = payload.get("authority")
    if not isinstance(authority, Mapping):
        errors.append("AUTHORITY_INVALID")
    else:
        if authority.get("execution") != "none":
            errors.append("EXECUTION_AUTHORITY_FORBIDDEN")
        if authority.get("production_strategy") != PRODUCTION_STRATEGY:
            errors.append("PRODUCTION_STRATEGY_MISMATCH")

    source_sha = payload.get("source_sha")
    if not isinstance(source_sha, str) or not source_sha:
        errors.append("SOURCE_SHA_REQUIRED")

    symbols = payload.get("symbols")
    if not isinstance(symbols, Mapping) or not symbols:
        errors.append("SYMBOLS_REQUIRED")
    else:
        for symbol, raw_row in symbols.items():
            if not isinstance(raw_row, Mapping):
                errors.append(f"{symbol}:ROW_INVALID")
                continue
            if raw_row.get("status") not in _VALID_STATUSES:
                errors.append(f"{symbol}:STATUS_INVALID")
            if raw_row.get("production_execution_authority") is not False:
                errors.append(f"{symbol}:EXECUTION_AUTHORITY_FORBIDDEN")

    expected = payload.get("manifest_hash")
    if not isinstance(expected, str) or len(expected) != 64:
        errors.append("MANIFEST_HASH_INVALID")
    else:
        try:
            int(expected, 16)
        except ValueError:
            errors.append("MANIFEST_HASH_INVALID")
        else:
            if expected != compute_manifest_hash(payload):
                errors.append("MANIFEST_HASH_MISMATCH")
    errors.extend(_embedded_contract_errors(payload, field="data_contract"))
    return errors


def _metric(metrics: Mapping[str, Any], *names: str) -> float | None:
    for name in names:
        value = metrics.get(name)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _validate_minute_snapshot(minute_snapshot: Mapping[str, Any]) -> None:
    errors = _embedded_contract_errors(minute_snapshot, field="data_contract")
    if errors:
        raise ValueError("invalid minute data contract: " + ",".join(errors))


class EvidenceResolver:
    """Resolve immutable research evidence plus the latest minute context.

    This adapter is deliberately read-only. It never grants execution authority and
    never aliases historical OOS performance to model confidence or live quality.
    """

    def __init__(self, primary_path: str | Path, fallback_path: str | Path | None = None):
        self.primary_path = Path(primary_path)
        self.fallback_path = None if fallback_path is None else Path(fallback_path)

    def _load_verified(self) -> tuple[dict[str, Any], bool]:
        candidates = [(self.primary_path, False)]
        if self.fallback_path is not None:
            candidates.append((self.fallback_path, True))

        last_errors: list[str] = []
        for path, used_fallback in candidates:
            try:
                payload = _read_json(path)
            except ValueError:
                last_errors = ["MANIFEST_READ_FAILED"]
                continue
            errors = _manifest_errors(payload)
            if not errors:
                return payload, used_fallback
            last_errors = errors
        raise ValueError("no verified G9 evidence manifest: " + ",".join(last_errors))

    def resolve_symbol(self, symbol: str, minute_snapshot: Mapping[str, Any]) -> dict[str, Any]:
        _validate_minute_snapshot(minute_snapshot)
        manifest, used_fallback = self._load_verified()
        symbol = str(symbol).upper()
        symbols = manifest.get("symbols") or {}
        evidence = symbols.get(symbol)
        if not isinstance(evidence, Mapping):
            raise KeyError(f"symbol not present in G9 evidence: {symbol}")

        minute_symbols = minute_snapshot.get("symbols") if isinstance(minute_snapshot, Mapping) else None
        minute_row = minute_symbols.get(symbol, {}) if isinstance(minute_symbols, Mapping) else {}
        market = minute_row.get("market", {}) if isinstance(minute_row, Mapping) else {}
        entry = minute_row.get("entry", {}) if isinstance(minute_row, Mapping) else {}
        if not isinstance(market, Mapping):
            market = {}
        if not isinstance(entry, Mapping):
            entry = {}

        freshness = str(market.get("freshness") or "UNKNOWN").upper()
        oof_metrics = evidence.get("oof_metrics")
        if not isinstance(oof_metrics, Mapping):
            oof_metrics = {}
        certification_metrics = evidence.get("certification_metrics")
        if not isinstance(certification_metrics, Mapping):
            certification_metrics = {}

        reason_codes: list[str] = []
        if freshness not in _LIVE_FRESHNESS:
            reason_codes.append("STALE_MARKET_DATA" if freshness == "STALE" else "MARKET_FRESHNESS_UNKNOWN")
        if evidence.get("status") == "QUARANTINED":
            reason_codes.append("EVIDENCE_QUARANTINED")

        model_confidence = entry.get("model_confidence")
        live_quality = entry.get("live_quality_score")
        historical_oos = _metric(oof_metrics, "win_rate", "rr2_win_rate", "oof_win_rate")

        return {
            "symbol": symbol,
            "source_sha": manifest.get("source_sha"),
            "manifest_hash": manifest.get("manifest_hash"),
            "profile_hash": evidence.get("profile_hash"),
            "evidence_epoch": evidence.get("evidence_epoch"),
            "evidence_status": evidence.get("status"),
            "historical_oos_win_rate": historical_oos,
            "historical_oos_metrics": dict(oof_metrics),
            "certification_metrics": dict(certification_metrics),
            "model_confidence": model_confidence,
            "live_quality_score": live_quality,
            "market_freshness": freshness,
            "used_fallback": used_fallback,
            "usable_for_live_claim": freshness in _LIVE_FRESHNESS and evidence.get("status") != "QUARANTINED",
            "reason_codes": reason_codes,
            "research_only": True,
            "production_execution_authority": False,
        }
