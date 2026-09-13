from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class LogisticModel:
    mean: np.ndarray
    scale: np.ndarray
    weights: np.ndarray
    bias: float


def split_walk_forward(n: int, k: int = 5):
    if n < 2 or k < 2:
        return []
    edges = np.linspace(0, n, k + 1, dtype=int)
    out = []
    for i in range(1, k):
        train_end = int(edges[i])
        test_start = train_end
        test_end = int(edges[i + 1])
        if train_end <= 0 or test_end <= test_start:
            continue
        out.append((np.arange(0, train_end, dtype=int), np.arange(test_start, test_end, dtype=int)))
    return out


def _sigmoid(z):
    z = np.clip(np.asarray(z, dtype=float), -35.0, 35.0)
    return 1.0 / (1.0 + np.exp(-z))


def fit_logistic(
    x,
    y,
    *,
    l2: float = 1.0,
    iterations: int = 300,
    learning_rate: float = 0.05,
) -> LogisticModel:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float).reshape(-1)
    if x.ndim != 2 or len(x) != len(y) or len(y) == 0:
        raise ValueError("x/y shape mismatch or empty training data")
    mean = np.nanmean(x, axis=0)
    scale = np.nanstd(x, axis=0)
    scale = np.where(np.isfinite(scale) & (scale > 1e-9), scale, 1.0)
    xs = np.nan_to_num((x - mean) / scale, nan=0.0, posinf=0.0, neginf=0.0)
    w = np.zeros(xs.shape[1], dtype=float)
    pos = float(np.clip(y.mean(), 1e-5, 1 - 1e-5))
    b = float(np.log(pos / (1.0 - pos)))
    n = float(len(y))
    for _ in range(int(iterations)):
        p = _sigmoid(xs @ w + b)
        err = p - y
        grad_w = (xs.T @ err) / n + float(l2) * w / n
        grad_b = float(err.mean())
        w -= float(learning_rate) * grad_w
        b -= float(learning_rate) * grad_b
    return LogisticModel(mean=mean, scale=scale, weights=w, bias=b)


def predict_proba(model: LogisticModel, x):
    x = np.asarray(x, dtype=float)
    xs = np.nan_to_num((x - model.mean) / model.scale, nan=0.0, posinf=0.0, neginf=0.0)
    return _sigmoid(xs @ model.weights + model.bias)


def select_oof_threshold(
    rows: pd.DataFrame,
    *,
    thresholds=(0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90),
    min_trades: int = 20,
):
    required = {"prob", "rr2_hit", "net_r"}
    if not required.issubset(rows.columns):
        raise ValueError("OOF rows missing required columns")
    best = None
    for threshold in thresholds:
        sub = rows.loc[pd.to_numeric(rows["prob"], errors="coerce") >= float(threshold)]
        n = len(sub)
        if n < int(min_trades):
            continue
        wins = int(pd.Series(sub["rr2_hit"]).astype(bool).sum())
        wr = wins / n if n else 0.0
        expectancy = float(pd.to_numeric(sub["net_r"], errors="coerce").fillna(0.0).mean())
        breadth = min(1.0, n / max(float(min_trades), 1.0))
        score = 0.78 * wr + 0.17 * max(-1.0, min(1.0, expectancy / 2.0)) + 0.05 * breadth
        candidate = {
            "threshold": float(threshold),
            "completed_trades": int(n),
            "rr2_wins": wins,
            "rr2_wr": float(wr),
            "expectancy_r": expectancy,
            "score": float(score),
        }
        if best is None or (candidate["score"], candidate["rr2_wr"], candidate["threshold"]) > (
            best["score"], best["rr2_wr"], best["threshold"]
        ):
            best = candidate
    if best is None:
        return {
            "threshold": None,
            "completed_trades": 0,
            "rr2_wins": 0,
            "rr2_wr": 0.0,
            "expectancy_r": 0.0,
            "score": float("-inf"),
        }
    return best
