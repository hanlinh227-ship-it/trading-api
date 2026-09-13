import numpy as np
import pandas as pd

from optimize.meta_model import (
    fit_logistic,
    predict_proba,
    select_oof_threshold,
    split_walk_forward,
)


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
