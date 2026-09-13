from datetime import datetime, timedelta, timezone

from g9.market_state import build_market_state, normalize_optional_evidence


def _bars(start: datetime):
    values = [100.0, 100.4, 100.8, 101.3, 101.9, 102.6]
    rows = []
    for i, close in enumerate(values):
        rows.append(
            {
                "event_time": start + timedelta(minutes=i),
                "open": close - 0.2,
                "high": close + 0.3,
                "low": close - 0.4,
                "close": close,
                "volume": 1000 + i * 25,
            }
        )
    return rows


def test_closed_snapshot_is_not_changed_by_future_bars():
    start = datetime(2026, 9, 13, 15, 0, tzinfo=timezone.utc)
    cutoff = start + timedelta(minutes=5)
    ingest = cutoff + timedelta(milliseconds=250)
    base = _bars(start)
    first = build_market_state(
        symbol="BTCUSDT",
        venue="BINANCE",
        instrument="USD_M_PERPETUAL",
        bars=base,
        event_time=cutoff,
        ingest_time=ingest,
        bid=102.59,
        ask=102.61,
        last=102.60,
        quote_event_time=cutoff,
    )
    future = list(base) + [
        {
            "event_time": cutoff + timedelta(minutes=1),
            "open": 102.6,
            "high": 110.0,
            "low": 90.0,
            "close": 91.0,
            "volume": 999999,
        }
    ]
    second = build_market_state(
        symbol="BTCUSDT",
        venue="BINANCE",
        instrument="USD_M_PERPETUAL",
        bars=future,
        event_time=cutoff,
        ingest_time=ingest,
        bid=102.59,
        ask=102.61,
        last=102.60,
        quote_event_time=cutoff,
    )
    assert first.to_dict() == second.to_dict()
    assert first.regime == "TREND_UP"
    assert first.directional_efficiency > 0.5


def test_optional_evidence_stale_over_five_seconds_degrades_to_unknown():
    assert normalize_optional_evidence(0.003, age_ms=5_001) is None
    assert normalize_optional_evidence(0.003, age_ms=4_999) == 0.003
