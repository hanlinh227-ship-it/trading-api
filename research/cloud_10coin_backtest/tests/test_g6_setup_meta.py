import numpy as np
import pandas as pd

from optimize.search_g6 import build_setup_candidates, candidate_feature_matrix


def _frame(n=90):
    close = np.linspace(100.0, 104.0, n)
    f = pd.DataFrame({
        "open": close - 0.05,
        "high": close + 0.20,
        "low": close - 0.20,
        "close": close,
        "atr14": np.ones(n),
        "body_atr": np.full(n, 0.2),
        "close_loc": np.full(n, 0.5),
        "rel_volume": np.ones(n),
        "rel_trades": np.ones(n),
        "taker_buy_ratio": np.full(n, 0.5),
        "flow_delta": np.zeros(n),
        "flow_ema12": np.zeros(n),
        "vol_regime": np.ones(n),
        "z_ema20": np.zeros(n),
        "h1_trend": np.zeros(n),
        "h4_trend": np.zeros(n),
        "trend_strength": np.zeros(n),
        "prior_high_12": close + 2.0,
        "prior_low_12": close - 2.0,
        "prior_high_24": close + 3.0,
        "prior_low_24": close - 3.0,
        "recent_sweep_low_3": np.zeros(n),
        "recent_sweep_high_3": np.zeros(n),
        "h1_ma20": close,
        "h4_ma20": close,
    })
    return f


def test_flat_frame_produces_no_structural_setup_candidates():
    f = _frame()
    assert build_setup_candidates(f, roundtrip_cost_bps=12.0) == []


def test_breakout_event_produces_causal_next_bar_candidate():
    f = _frame()
    i = 40
    f.loc[i, "prior_high_12"] = f.loc[i, "close"] - 0.1
    f.loc[i, "body_atr"] = 0.8
    f.loc[i, "close_loc"] = 0.9
    f.loc[i, "rel_volume"] = 1.4
    f.loc[i, "flow_delta"] = 0.2
    candidates = build_setup_candidates(f, roundtrip_cost_bps=12.0)
    hits = [c for c in candidates if c.signal_index == i and c.side == "LONG" and c.family == "setup_breakout"]
    assert hits
    assert all(c.max_fill_bars == 1 for c in hits)
    assert all(c.signal_index == i for c in hits)
    assert all(c.entry == f.loc[i, "close"] for c in hits)


def test_candidate_features_include_setup_identity_and_geometry_without_future_rows():
    f = _frame()
    i = 35
    f.loc[i, "prior_low_12"] = f.loc[i, "close"] + 0.1
    f.loc[i, "low"] = f.loc[i, "close"] - 0.4
    f.loc[i, "close_loc"] = 0.85
    f.loc[i, "flow_delta"] = 0.15
    candidates = build_setup_candidates(f, roundtrip_cost_bps=12.0)
    hits = [c for c in candidates if c.signal_index == i and c.side == "LONG" and c.family == "setup_sweep"]
    assert hits
    x = candidate_feature_matrix(f, hits)
    assert x.shape[0] == len(hits)
    assert x.shape[1] > 20
    assert np.isfinite(x).all()
    # Geometry variants must remain distinguishable to the model.
    assert len(np.unique(x[:, -2])) >= 2
