from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import json
from typing import Any, Mapping


class FreshnessState(str, Enum):
    FRESH = "FRESH"
    DEGRADED = "DEGRADED"
    STALE = "STALE"


def classify_freshness(quote_age_ms: int) -> FreshnessState:
    if quote_age_ms < 0:
        raise ValueError("quote_age_ms must be non-negative")
    if quote_age_ms <= 2_000:
        return FreshnessState.FRESH
    if quote_age_ms <= 5_000:
        return FreshnessState.DEGRADED
    return FreshnessState.STALE


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.isoformat()


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"{prefix}-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:24]}"


def _unknown(value: Any) -> Any:
    return "UNKNOWN" if value is None else value


@dataclass(frozen=True)
class MarketStateSnapshot:
    symbol: str
    venue: str
    instrument: str
    event_time: datetime
    ingest_time: datetime
    quote_age_ms: int
    bid: float
    ask: float
    last: float
    regime: str
    regime_confidence: float
    transition_probability: float
    structure: str
    volatility: float
    directional_efficiency: float
    uncertainty: float
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        base = {
            "symbol": self.symbol,
            "venue": self.venue,
            "instrument": self.instrument,
            "event_time": _iso(self.event_time),
            "ingest_time": _iso(self.ingest_time),
            "quote_age_ms": int(self.quote_age_ms),
            "freshness": classify_freshness(int(self.quote_age_ms)).value,
            "bid": float(self.bid),
            "ask": float(self.ask),
            "last": float(self.last),
            "spread": float(self.ask - self.bid),
            "regime": self.regime,
            "regime_confidence": float(self.regime_confidence),
            "transition_probability": float(self.transition_probability),
            "structure": self.structure,
            "volatility": float(self.volatility),
            "directional_efficiency": float(self.directional_efficiency),
            "uncertainty": float(self.uncertainty),
            "provenance": dict(self.provenance),
            "research_only": True,
            "production_execution_authority": False,
        }
        base["snapshot_id"] = _stable_id("mkt", base)
        return base


@dataclass(frozen=True)
class EntryContextSnapshot:
    symbol: str
    event_time: datetime
    market_snapshot_id: str
    funding: float | None
    open_interest_delta: float | None
    taker_imbalance: float | None
    cross_asset_score: float | None
    live_quality_score: float
    model_confidence: float | None
    historical_oos_win_rate: float | None
    uncertainty: float
    mark_index_premium: float | None = None

    def to_dict(self) -> dict[str, Any]:
        base = {
            "symbol": self.symbol,
            "event_time": _iso(self.event_time),
            "market_snapshot_id": self.market_snapshot_id,
            "funding": _unknown(self.funding),
            "open_interest_delta": _unknown(self.open_interest_delta),
            "taker_imbalance": _unknown(self.taker_imbalance),
            "cross_asset_score": _unknown(self.cross_asset_score),
            "mark_index_premium": _unknown(self.mark_index_premium),
            "live_quality_score": float(self.live_quality_score),
            "model_confidence": _unknown(self.model_confidence),
            "historical_oos_win_rate": _unknown(self.historical_oos_win_rate),
            "uncertainty": float(self.uncertainty),
            "research_only": True,
            "production_execution_authority": False,
        }
        base["context_id"] = _stable_id("entry", base)
        return base
