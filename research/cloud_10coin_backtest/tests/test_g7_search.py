import numpy as np
import pandas as pd
import pytest

from config import DEFAULT_CONFIG
from engine.execution import OrderCandidate
from optimize.search_g7 import (
    _fit_route_profile,
    dedupe_scored_candidates,
    filter_locked_geometry,
    lock_g7_profile,
    search_coin_g7,
)


def _features(n=500):
    close = np.linspace(100.0, 101.0, n)
    return pd.DataFrame({
        "open": close - 0.05,
        "high": close + 0.20,
        "low": close - 0.20,
        "close": close,
        "atr14": np.ones(n),
        "body_atr": np.full(n, 0.20),
        "close_loc": np.full(n, 0.50),
        "rel_volume": np.ones(n),
        "rel_trades": np.ones(n),
        "taker_buy_ratio": np.full(n, 0.50),
        "flow_delta": np.zeros(n),
        "flow_ema12": np.zeros(n),
        "vol_regime": np.ones(n),
        "z_ema20": np.zeros(n),
        "h1_trend": np.zeros(n),
        "h4_trend": np.zeros(n),
        "trend_strength": np.full(n, 0.20),
        "prior_high_12": close + 2.0,
        "prior_low_12": close - 2.0,
        "prior_high_24": close + 3.0,
        "prior_low_24": close - 3.0,
        "recent_sweep_low_3": np.zeros(n),
        "recent_sweep_high_3": np.zeros(n),
        "h1_ma20": close,
        "h4_ma20": close,
    })


def _candidate(risk_atr, hold_bars, quality=0.0, signal_index=20):
    return OrderCandidate(
        signal_index,
        "LONG",
        100.0,
        100.0 - float(risk_atr),
        1,
        int(hold_bars),
        float(quality),
        "setup_breakout",
    )


def test_filter_locked_geometry_keeps_only_exact_route_geometry():
    f = _features(60)
    candidates = [_candidate(0.8, 72), _candidate(1.2, 72), _candidate(1.2, 144)]
    kept = filter_locked_geometry(candidates, f, risk_atr=1.2, hold_bars=144)
    assert len(kept) == 1
    assert kept[0].max_hold_bars == 144
    assert abs(kept[0].entry - kept[0].stop) == pytest.approx(1.2)


def test_dedupe_scored_candidates_keeps_highest_quality_per_signal():
    low = _candidate(1.2, 72, quality=0.61, signal_index=20)
    high = _candidate(1.2, 72, quality=0.84, signal_index=20)
    other = _candidate(1.2, 72, quality=0.70, signal_index=30)
    kept = dedupe_scored_candidates([low, high, other])
    assert [c.signal_index for c in kept] == [20, 30]
    assert kept[0].quality == 0.84


def test_profile_lock_is_deterministic_and_has_one_geometry_per_route():
    specs = [{
        "regime": "TREND_UP",
        "family": "setup_breakout",
        "side": "LONG",
        "risk_atr": 1.2,
        "hold_bars": 72,
        "threshold": 0.8,
        "qualified": True,
    }]
    a = lock_g7_profile(specs)
    b = lock_g7_profile(list(reversed(specs)))
    assert a.profile_hash == b.profile_hash
    assert a.params["routes"][0]["risk_atr"] == 1.2
    assert a.params["routes"][0]["hold_bars"] == 72


def test_fit_route_profile_does_not_accept_validation_data():
    with pytest.raises(TypeError):
        _fit_route_profile(_features(100), ("TREND_UP", "setup_breakout", "LONG"), DEFAULT_CONFIG, validation_x=np.ones((2, 2)))


def test_flat_market_fails_closed_without_target_qualified_route():
    result = search_coin_g7("BTCUSDT", _features(), DEFAULT_CONFIG)
    assert result.status == "FAIL"
    assert "g7-no-target-qualified-route" in result.bottlenecks
    assert result.evaluation.completed_trades == 0
