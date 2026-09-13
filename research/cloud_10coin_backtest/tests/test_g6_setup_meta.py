import numpy as np
import pandas as pd

from engine.execution import OrderCandidate
from optimize.search_g6 import build_setup_candidates, candidate_feature_matrix, label_setup_candidates


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
    assert len(np.unique(x[:, -2])) >= 2


def test_independent_labeling_keeps_only_filled_candidates_and_aligns_features():
    f = _frame(120)
    i = 20
    entry = float(f.loc[i, "close"])
    good = OrderCandidate(i, "LONG", entry, entry - 0.8, 1, 72, 0.0, "setup_breakout")
    never_fills = OrderCandidate(i, "LONG", 999.0, 998.2, 1, 72, 0.0, "setup_breakout")
    x, labels, kept = label_setup_candidates(f, [good, never_fills], roundtrip_cost_bps=12.0)
    assert len(kept) == 1
    assert kept[0] == good
    assert x.shape[0] == len(labels) == 1
    assert set(labels.columns) >= {"rr2_hit", "net_r", "signal_index"}
    assert int(labels.iloc[0]["signal_index"]) == i
    assert bool(labels.iloc[0]["rr2_hit"]) is True
