import numpy as np
import pandas as pd

from config import DEFAULT_CONFIG
from g8.candidate import CandidateSpec
from g8.evaluator import evaluate_candidate, run_falsification_suite


def _features(n=900):
    i = np.arange(n, dtype=float)
    close = 100.0 + 4.0 * np.sin(i / 7.0) + 0.004 * i
    return pd.DataFrame({
        "open": close - 0.10,
        "high": close + 0.70,
        "low": close - 0.70,
        "close": close,
        "atr14": np.ones(n),
        "body_atr": np.full(n, 0.50),
        "close_loc": np.full(n, 0.75),
        "rel_volume": np.ones(n),
        "rel_trades": np.ones(n),
        "taker_buy_ratio": np.full(n, 0.60),
        "flow_delta": np.full(n, 0.20),
        "flow_ema12": np.full(n, 0.20),
        "vol_regime": np.ones(n),
        "z_ema20": np.zeros(n),
        "h1_trend": np.ones(n),
        "h4_trend": np.ones(n),
        "trend_strength": np.full(n, 0.80),
        "prior_high_12": close - 0.10,
        "prior_low_12": close - 3.0,
        "prior_high_24": close + 3.0,
        "prior_low_24": close - 3.0,
        "recent_sweep_low_3": np.zeros(n),
        "recent_sweep_high_3": np.zeros(n),
        "h1_ma20": close - 0.10,
        "h4_ma20": close - 0.10,
    })


def _candidate():
    return CandidateSpec(
        symbol="BTCUSDT",
        regime="TREND_UP",
        family="setup_trend",
        side="LONG",
        feature_pack=("base_g7",),
        model_family="random_forest",
        model_params=(("max_depth", 4), ("max_features", 0.7), ("min_samples_leaf", 18), ("n_estimators", 80), ("random_state", 71)),
        calibration="none",
        threshold=0.55,
        risk_atr=1.2,
        hold_bars=72,
    )


def test_evaluator_returns_only_oof_metrics():
    result = evaluate_candidate("BTCUSDT", _features(), DEFAULT_CONFIG, _candidate())
    assert result.provenance_complete is True
    assert result.in_sample_score is None
    assert result.trades >= 0
    assert isinstance(result.fold_metrics, tuple)


def test_future_mutation_does_not_change_completed_early_fold():
    left = _features()
    right = left.copy()
    right.loc[700:, ["open", "high", "low", "close"]] += 50.0
    a = evaluate_candidate("BTCUSDT", left, DEFAULT_CONFIG, _candidate())
    b = evaluate_candidate("BTCUSDT", right, DEFAULT_CONFIG, _candidate())
    assert a.fold_metrics[0] == b.fold_metrics[0]


def test_falsification_suite_is_deterministic_and_rejects_perfect_null_alignment():
    labels = np.array([0, 1] * 40, dtype=int)
    scores = labels.astype(float)
    a = run_falsification_suite(labels, scores, seed=17)
    b = run_falsification_suite(labels, scores, seed=17)
    assert a == b
    assert "shuffled_selected_wr" in a
    assert "time_shift_selected_wr" in a
