from __future__ import annotations

from datetime import datetime
import math
import statistics
from typing import Any, Iterable, Mapping

from .contracts import MarketStateSnapshot, FreshnessState, classify_freshness


def normalize_optional_evidence(value: Any, *, age_ms: int) -> Any | None:
    """Return UNKNOWN-compatible None when optional evidence is too stale."""
    if classify_freshness(age_ms) is FreshnessState.STALE:
        return None
    return value


def _as_time(value: Any) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("bar event_time must be a timezone-aware datetime")
    return value


def _closed_bars(bars: Iterable[Mapping[str, Any]], event_time: datetime) -> list[Mapping[str, Any]]:
    rows = [row for row in bars if _as_time(row["event_time"]) <= event_time]
    rows.sort(key=lambda row: _as_time(row["event_time"]))
    if len(rows) < 3:
        raise ValueError("at least three closed bars are required")
    return rows


def _directional_efficiency(closes: list[float]) -> float:
    path = sum(abs(b - a) for a, b in zip(closes, closes[1:]))
    if path <= 0:
        return 0.0
    return min(1.0, abs(closes[-1] - closes[0]) / path)


def _realized_volatility(closes: list[float]) -> float:
    returns = []
    for previous, current in zip(closes, closes[1:]):
        if previous <= 0 or current <= 0:
            continue
        returns.append(math.log(current / previous))
    if len(returns) < 2:
        return 0.0
    return float(statistics.pstdev(returns))


def _structure(rows: list[Mapping[str, Any]]) -> str:
    tail = rows[-3:]
    highs = [float(row["high"]) for row in tail]
    lows = [float(row["low"]) for row in tail]
    if highs[0] < highs[1] < highs[2] and lows[0] < lows[1] < lows[2]:
        return "HIGHER_HIGH_HIGHER_LOW"
    if highs[0] > highs[1] > highs[2] and lows[0] > lows[1] > lows[2]:
        return "LOWER_HIGH_LOWER_LOW"
    return "MIXED"


def _regime(closes: list[float], efficiency: float, volatility: float) -> tuple[str, float, float]:
    net = closes[-1] - closes[0]
    if efficiency >= 0.55 and net > 0:
        regime = "TREND_UP"
        confidence = efficiency
    elif efficiency >= 0.55 and net < 0:
        regime = "TREND_DOWN"
        confidence = efficiency
    elif volatility <= 0.0005:
        regime = "COMPRESSION"
        confidence = max(0.5, 1.0 - min(1.0, volatility / 0.0005))
    else:
        regime = "RANGE"
        confidence = max(0.5, 1.0 - efficiency)
    transition_probability = min(1.0, max(0.0, 1.0 - confidence))
    return regime, float(confidence), float(transition_probability)


def build_market_state(
    *,
    symbol: str,
    venue: str,
    instrument: str,
    bars: Iterable[Mapping[str, Any]],
    event_time: datetime,
    ingest_time: datetime,
    bid: float,
    ask: float,
    last: float,
    quote_event_time: datetime,
) -> MarketStateSnapshot:
    if event_time.tzinfo is None or ingest_time.tzinfo is None or quote_event_time.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    if ask < bid:
        raise ValueError("ask must be greater than or equal to bid")

    rows = _closed_bars(bars, event_time)
    closes = [float(row["close"]) for row in rows]
    efficiency = _directional_efficiency(closes)
    volatility = _realized_volatility(closes)
    regime, confidence, transition_probability = _regime(closes, efficiency, volatility)
    quote_age_ms = max(0, int((ingest_time - quote_event_time).total_seconds() * 1_000))

    return MarketStateSnapshot(
        symbol=symbol,
        venue=venue,
        instrument=instrument,
        event_time=event_time,
        ingest_time=ingest_time,
        quote_age_ms=quote_age_ms,
        bid=float(bid),
        ask=float(ask),
        last=float(last),
        regime=regime,
        regime_confidence=confidence,
        transition_probability=transition_probability,
        structure=_structure(rows),
        volatility=volatility,
        directional_efficiency=efficiency,
        uncertainty=float(1.0 - confidence),
        provenance={
            "price": {
                "source": venue.lower(),
                "event_time": quote_event_time.isoformat(),
            },
            "bars": {
                "last_closed_event_time": _as_time(rows[-1]["event_time"]).isoformat(),
                "count": len(rows),
            },
        },
    )
