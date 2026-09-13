import numpy as np
import pandas as pd

from optimize.meta_model import (
    fit_logistic,
    predict_proba,
    select_oof_threshold,
    split_walk_forward,
)
from optimize.search_g4 import build_base_candidates, directional_feature_matrix


def test_walk_forward_train_is_strictly_before_test():
    folds = split_walk_forward(100, 5)
    assert len(folds) >= 3
    for train_idx, test_idx in folds:
        assert len(train_idx) > 0
        assert len(test_idx) > 0
        assert train_idx.max() < test_idx.min()


def test_logistic_fit_learns_separable_signal_without_future_input():
    x = np.array([
        [-2.0, 0.1], [-1.5, -0.2], [-1.0, 0.0],
        [1.0, 0.0], [1.5, 0.2], [2.0, -0.1],
    ])
    y = np.array([0, 0, 0, 1, 1, 1], dtype=float)
    model = fit_logistic(x, y, l2=0.1, iterations=400, learning_rate=0.1)
    p = predict_proba(model, x)
    assert p[:3].max() < 0.5
    assert p[3:].min() > 0.5


def test_threshold_selection_uses_oof_rows_and_requires_breadth():
    rows = pd.DataFrame({
        "prob": [0.95, 0.92, 0.88, 0.86, 0.70, 0.65, 0.60, 0.55],
        "rr2_hit": [1, 1, 1, 0, 1, 0, 0, 0],
        "net_r": [1.8, 1.8, 1.8, -1.2, 1.8, -1.2, -1.2, -1.2],
    })
    choice = select_oof_threshold(rows, thresholds=(0.55, 0.65, 0.85), min_trades=4)
    assert choice["threshold"] == 0.85
    assert choice["completed_trades"] == 4
    assert choice["rr2_wr"] == 0.75


def _feature_frame():
    n = 80
    x = np.linspace(100.0, 108.0, n)
    return pd.DataFrame({
        "open": x - 0.1,
        "high": x + 0.3,
        "low": x - 0.3,
        "close": x,
        "atr14": np.full(n, 1.0),
        "body_atr": np.full(n, 0.2),
        "close_loc": np.full(n, 0.7),
        "rel_volume": np.full(n, 1.2),
        "rel_trades": np.full(n, 1.1),
        "taker_buy_ratio": np.full(n, 0.6),
        "flow_delta": np.full(n, 0.2),
        "flow_ema12": np.full(n, 0.15),
        "vol_regime": np.full(n, 1.0),
        "z_ema20": np.full(n, 0.5),
        "h1_trend": np.ones(n),
        "h4_trend": np.ones(n),
        "trend_strength": np.full(n, 0.8),
        "prior_high_12": x - 0.2,
        "prior_low_12": x - 1.0,
        "prior_high_24": x + 0.5,
        "prior_low_24": x - 1.5,
        "recent_sweep_low_3": np.zeros(n),
        "recent_sweep_high_3": np.zeros(n),
        "h1_ma20": x - 0.4,
        "h4_ma20": x - 0.8,
    })


def test_directional_features_flip_trend_and_flow_for_short():
    f = _feature_frame()
    long_x = directional_feature_matrix(f, "LONG")
    short_x = directional_feature_matrix(f, "SHORT")
    assert long_x.shape == short_x.shape
    # First two directional features are H1/H4 trend alignment.
    assert np.allclose(long_x[:, 0], -short_x[:, 0])
    assert np.allclose(long_x[:, 1], -short_x[:, 1])
    # Flow delta is also directional and must flip sign.
    assert np.allclose(long_x[:, 3], -short_x[:, 3])


def test_base_candidates_use_fixed_atr_risk_and_next_bar_fill_only():
    f = _feature_frame()
    candidates = build_base_candidates(f, "LONG", risk_atr=0.8, hold_bars=72, stride=6, roundtrip_cost_bps=12.0)
    assert candidates
    c = candidates[0]
    assert c.max_fill_bars == 1
    assert c.max_hold_bars == 72
    assert abs((c.entry - c.stop) - 0.8) < 1e-9
    assert c.family == "meta_g4"
