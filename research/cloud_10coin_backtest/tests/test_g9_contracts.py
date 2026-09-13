from datetime import datetime, timezone

import pytest

from g9.contracts import (
    EntryContextSnapshot,
    FreshnessState,
    MarketStateSnapshot,
    classify_freshness,
)


def test_live_quote_over_five_seconds_is_stale_and_blocks_live_claim():
    freshness = classify_freshness(5_001)
    assert freshness is FreshnessState.STALE


def test_optional_data_can_degrade_without_becoming_current():
    assert classify_freshness(2_001) is FreshnessState.DEGRADED
    assert classify_freshness(1_999) is FreshnessState.FRESH


def test_market_snapshot_is_deterministic_research_only_and_explicit_about_semantics():
    ts = datetime(2026, 9, 13, 15, 0, tzinfo=timezone.utc)
    snap = MarketStateSnapshot(
        symbol="BTCUSDT",
        venue="BINANCE",
        instrument="USD_M_PERPETUAL",
        event_time=ts,
        ingest_time=ts,
        quote_age_ms=250,
        bid=77000.0,
        ask=77000.1,
        last=77000.05,
        regime="TREND_UP",
        regime_confidence=0.72,
        transition_probability=0.18,
        structure="HIGHER_HIGH_HIGHER_LOW",
        volatility=0.012,
        directional_efficiency=0.61,
        uncertainty=0.28,
        provenance={"price": {"source": "binance", "event_time": ts.isoformat()}},
    )
    payload = snap.to_dict()
    assert payload["symbol"] == "BTCUSDT"
    assert payload["venue"] == "BINANCE"
    assert payload["instrument"] == "USD_M_PERPETUAL"
    assert payload["research_only"] is True
    assert payload["production_execution_authority"] is False
    assert payload["snapshot_id"] == snap.to_dict()["snapshot_id"]


def test_entry_context_preserves_unknown_optional_evidence():
    ts = datetime(2026, 9, 13, 15, 0, tzinfo=timezone.utc)
    ctx = EntryContextSnapshot(
        symbol="SOLUSDT",
        event_time=ts,
        market_snapshot_id="mkt-1",
        funding=None,
        open_interest_delta=None,
        taker_imbalance=None,
        cross_asset_score=0.4,
        live_quality_score=0.7,
        model_confidence=0.66,
        historical_oos_win_rate=0.58,
        uncertainty=0.34,
    )
    payload = ctx.to_dict()
    assert payload["funding"] == "UNKNOWN"
    assert payload["open_interest_delta"] == "UNKNOWN"
    assert payload["taker_imbalance"] == "UNKNOWN"
    assert payload["live_quality_score"] != payload["historical_oos_win_rate"]
    assert payload["production_execution_authority"] is False


def test_entry_context_does_not_invent_model_confidence():
    ts = datetime(2026, 9, 13, 15, 0, tzinfo=timezone.utc)
    ctx = EntryContextSnapshot(
        symbol="BTCUSDT",
        event_time=ts,
        market_snapshot_id="mkt-1",
        funding=0.0001,
        open_interest_delta=0.01,
        taker_imbalance=0.2,
        cross_asset_score=0.5,
        live_quality_score=0.8,
        model_confidence=None,
        historical_oos_win_rate=None,
        uncertainty=0.2,
    )
    payload = ctx.to_dict()
    assert payload["model_confidence"] == "UNKNOWN"
    assert payload["historical_oos_win_rate"] == "UNKNOWN"
