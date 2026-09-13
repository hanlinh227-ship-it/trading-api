import numpy as np
import pandas as pd

from optimize.regime_g7 import classify_regimes


def _frame(n=80):
    return pd.DataFrame({
        "h1_trend": np.zeros(n),
        "h4_trend": np.zeros(n),
        "trend_strength": np.full(n, 0.2),
        "vol_regime": np.ones(n),
        "body_atr": np.full(n, 0.2),
        "rel_volume": np.ones(n),
        "z_ema20": np.zeros(n),
        "close": np.linspace(100, 101, n),
        "atr14": np.ones(n),
    })


def test_aligned_trend_classifies_trend_up():
    f = _frame()
    f.loc[30, ["h1_trend", "h4_trend", "trend_strength"]] = [1, 1, 1.2]
    assert classify_regimes(f).iloc[30] == "TREND_UP"


def test_aligned_trend_classifies_trend_down():
    f = _frame()
    f.loc[30, ["h1_trend", "h4_trend", "trend_strength"]] = [-1, -1, 1.2]
    assert classify_regimes(f).iloc[30] == "TREND_DOWN"


def test_shock_overrides_trend():
    f = _frame()
    f.loc[30, ["h1_trend", "h4_trend", "trend_strength", "body_atr", "rel_volume", "vol_regime"]] = [1, 1, 1.5, 3.2, 3.5, 2.2]
    assert classify_regimes(f).iloc[30] == "SHOCK"


def test_compression_precedes_range():
    f = _frame()
    f.loc[30, ["vol_regime", "body_atr"]] = [0.6, 0.3]
    assert classify_regimes(f).iloc[30] == "COMPRESSION"


def test_expansion_precedes_trend():
    f = _frame()
    f.loc[30, ["h1_trend", "h4_trend", "trend_strength", "vol_regime", "body_atr"]] = [1, 1, 1.2, 1.5, 0.9]
    assert classify_regimes(f).iloc[30] == "EXPANSION"


def test_future_row_change_does_not_change_prior_regime():
    f = _frame()
    before = classify_regimes(f).iloc[25]
    f.loc[70, ["body_atr", "rel_volume", "vol_regime"]] = [9, 9, 9]
    assert classify_regimes(f).iloc[25] == before
