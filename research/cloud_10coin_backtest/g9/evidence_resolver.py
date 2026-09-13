from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .manifest import validate_evidence_manifest


_LIVE_FRESHNESS = {"FRESH", "DEGRADED"}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid evidence manifest: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"invalid evidence manifest: {path}")
    return payload


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


class EvidenceResolver:
    """Resolve immutable stable evidence plus the latest minute context.

    Manifest validation is delegated to the canonical G9 manifest validator. This
    adapter is read-only and never converts OOS performance into model confidence
    or live quality, nor can it grant production execution authority.
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
            errors = validate_evidence_manifest(payload)
            if not errors:
                return payload, used_fallback
            last_errors = [str(item).upper().replace("-", "_") for item in errors]
        raise ValueError("no verified G9 evidence manifest: " + ",".join(last_errors))

    def resolve_symbol(self, symbol: str, minute_snapshot: Mapping[str, Any]) -> dict[str, Any]:
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
        live_regime = str(market.get("regime") or "").upper()
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

        routes = evidence.get("routes")
        route_resolution_required = isinstance(routes, Mapping)
        matching_routes: list[dict[str, Any]] = []
        selected_route: dict[str, Any] | None = None
        if route_resolution_required:
            for route_id, route_value in sorted(routes.items()):
                if not isinstance(route_value, Mapping):
                    continue
                route_regime = str(route_value.get("regime") or "").upper()
                if live_regime and route_regime == live_regime:
                    route = dict(route_value)
                    route["route_id"] = str(route_id)
                    matching_routes.append(route)

            if not live_regime:
                reason_codes.append("MARKET_REGIME_UNKNOWN")
            elif not matching_routes:
                reason_codes.append("NO_MATCHING_RESEARCH_ROUTE")
            elif len(matching_routes) == 1:
                selected_route = matching_routes[0]
            else:
                reason_codes.append("MULTIPLE_MATCHING_ROUTES")

        model_confidence = entry.get("model_confidence")
        live_quality = entry.get("live_quality_score")
        historical_oos = _metric(oof_metrics, "win_rate", "rr2_win_rate", "oof_win_rate")

        usable_for_live_claim = freshness in _LIVE_FRESHNESS and evidence.get("status") != "QUARANTINED"
        if route_resolution_required:
            usable_for_live_claim = usable_for_live_claim and selected_route is not None
            if selected_route is not None and selected_route.get("status") == "QUARANTINED":
                usable_for_live_claim = False
                reason_codes.append("ROUTE_EVIDENCE_QUARANTINED")

        return {
            "symbol": symbol,
            "system_contract_version": manifest.get("system_contract_version"),
            "stable_plane": manifest.get("plane"),
            "stable_authority_level": manifest.get("authority_level"),
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
            "live_regime": live_regime or None,
            "matching_routes": matching_routes,
            "selected_route": selected_route,
            "used_fallback": used_fallback,
            "usable_for_live_claim": usable_for_live_claim,
            "reason_codes": reason_codes,
            "research_only": True,
            "production_execution_authority": False,
        }
