from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier


def fit_nonlinear(
    x,
    y,
    *,
    n_estimators: int = 160,
    max_depth: int = 3,
    min_samples_leaf: int = 12,
    max_features: float | str | None = 0.7,
    random_state: int = 17,
):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=int).reshape(-1)
    if x.ndim != 2 or len(x) != len(y) or len(y) == 0:
        raise ValueError("x/y shape mismatch or empty training data")
    if len(np.unique(y)) < 2:
        raise ValueError("training labels must contain both classes")
    x = np.nan_to_num(x, nan=0.0, posinf=5.0, neginf=-5.0)
    model = RandomForestClassifier(
        n_estimators=int(n_estimators),
        criterion="log_loss",
        max_depth=int(max_depth),
        min_samples_leaf=int(min_samples_leaf),
        max_features=max_features,
        bootstrap=True,
        class_weight="balanced_subsample",
        random_state=int(random_state),
        n_jobs=1,
    )
    model.fit(x, y)
    return model


def predict_nonlinear_proba(model, x):
    x = np.asarray(x, dtype=float)
    if x.ndim != 2:
        raise ValueError("x must be a 2-D feature matrix")
    x = np.nan_to_num(x, nan=0.0, posinf=5.0, neginf=-5.0)
    return np.asarray(model.predict_proba(x)[:, 1], dtype=float)
