import numpy as np
import pandas as pd

from strategies.sweep_mss_ote_g2 import generate_candidates


def _features():
    n = 20
    f = pd.DataFrame({
        "open": np.full(n, 100.0),
        "high": np.full(n, 100.4),
        "low": np.full(n, 99.6),
        "close": np.full(n, 100.0),
        "atr14": np.ones(n),
        "body_atr": np.full(n, 0.2),
        "close_loc": np.full(n, 0.5),
        "rel_volume": np.full(n, 1.0),
        "rel_trades": np.full(n, 1.0),
        "taker_buy_ratio": np.full(n, 0.5),
        "flow_delta": np.zeros(n),
        "trend_strength": np.full(n, 1.0),
        "h1_trend": np.ones(n),
        "h4_trend": np.ones(n),
        "regime": ["normal"] * n,
        "sweep_low": [False] * n,
        "sweep_high": [False] * n,
        "prior_swing_high_6": np.full(n, 100.5),
        "prior_swing_low_6": np.full(n, 99.5),
    })
    return f


def _params():
    return {
        "side": "LONG", "r": 0.79, "confirm_window": 4,
        "displacement_min": 0.8, "flow_min": 0.55,
        "rel_volume_min": 1.1, "min_risk_atr": 0.2,
        "stop_buffer_atr": 0.03, "max_cost_r": 0.20,
        "roundtrip_cost_bps": 12.0, "regime": "normal",
    }


def test_mss_before_sweep_is_not_valid():
    f = _features()
    f.loc[8, ["open", "close", "high", "low", "body_atr", "close_loc", "rel_volume", "rel_trades", "taker_buy_ratio", "flow_delta"]] = [100.0, 101.0, 101.2, 99.9, 1.0, 0.85, 1.4, 1.3, 0.62, 0.24]
    f.loc[10, "sweep_low"] = True
    f.loc[10, "low"] = 99.0
    assert generate_candidates(f, _params()) == []


def test_ordered_sweep_then_displacement_mss_produces_ote_candidate():
    f = _features()
    f.loc[10, "sweep_low"] = True
    f.loc[10, ["open", "high", "low", "close"]] = [100.0, 100.2, 99.0, 99.8]
    f.loc[10, "prior_swing_high_6"] = 100.5
    f.loc[12, ["open", "close", "high", "low", "body_atr", "close_loc", "rel_volume", "rel_trades", "taker_buy_ratio", "flow_delta"]] = [100.0, 101.0, 101.2, 99.9, 1.0, 0.85, 1.4, 1.3, 0.62, 0.24]
    out = generate_candidates(f, _params())
    assert len(out) == 1
    c = out[0]
    assert c.signal_index == 12
    assert c.entry < 101.2
    assert c.entry > 99.0
    assert c.stop < 99.0
    assert c.quality > 0


def test_weak_displacement_is_rejected():
    f = _features()
    f.loc[10, "sweep_low"] = True
    f.loc[10, "low"] = 99.0
    f.loc[10, "prior_swing_high_6"] = 100.5
    f.loc[12, ["open", "close", "high", "low", "body_atr", "close_loc", "rel_volume", "rel_trades", "taker_buy_ratio", "flow_delta"]] = [100.0, 100.7, 100.8, 99.9, 0.4, 0.80, 1.4, 1.3, 0.62, 0.24]
    assert generate_candidates(f, _params()) == []
