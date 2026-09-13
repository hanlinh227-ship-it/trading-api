from __future__ import annotations

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier


def fit_nonlinear(
    x,
    y,
    *,
    max_depth: int = 2,
    learning_rate: float = 0.06,
    max_iter: int = 100,
    l2_regularization: float = 1.0,
    random_state: int = 17,
):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=int).reshape(-1)
    if x.ndim != 2 or len(x) != len(y) or len(y) == 0:
        raise ValueError("x/y shape mismatch or empty training data")
    if len(np.unique(y)) < 2:
        raise ValueError("training labels must contain both classes")
    x = np.nan_to_num(x, nan=0.0, posinf=5.0, neginf=-5.0)
    model = HistGradientBoostingClassifier(
        loss="log_loss",
        learning_rate=float(learning_rate),
        max_iter=int(max_iter),
        max_depth=int(max_depth),
        min_samples_leaf=12,
        l2_regularization=float(l2_regularization),
        early_stopping=False,
        random_state=int(random_state),
    )
    model.fit(x, y)
    return model


def predict_nonlinear_proba(model, x):
    x = np.asarray(x, dtype=float)
    if x.ndim != 2:
        raise ValueError("x must be a 2-D feature matrix")
    x = np.nan_to_num(x, nan=0.0, posinf=5.0, neginf=-5.0)
    return np.asarray(model.predict_proba(x)[:, 1], dtype=float)
