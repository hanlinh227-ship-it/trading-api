from __future__ import annotations

import math

import numpy as np
import pandas as pd


ROUTE_MIN_OOF_TRADES = 40
ROUTE_MIN_FOLD_WR = 0.65
ROUTE_MIN_WILSON = 0.60


def wilson_lower(wins: int, n: int, z: float = 1.96) -> float:
    wins = int(wins)
    n = int(n)
    if n <= 0:
        return 0.0
    p = max(0.0, min(1.0, wins / n))
    z2 = float(z) ** 2
    denom = 1.0 + z2 / n
    centre = p + z2 / (2.0 * n)
    margin = float(z) * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n)
    return float(max(0.0, min(1.0, (centre - margin) / denom)))


def route_is_target_qualified(choice: dict, target_wr: float = 0.80) -> bool:
    return (
        int(choice.get("completed_trades", 0)) >= ROUTE_MIN_OOF_TRADES
        and float(choice.get("rr2_wr", 0.0)) >= float(target_wr)
        and float(choice.get("expectancy_r", 0.0)) > 0.0
        and float(choice.get("min_fold_wr", 0.0)) >= ROUTE_MIN_FOLD_WR
        and float(choice.get("wilson_lower", 0.0)) >= ROUTE_MIN_WILSON
    )


def _empty_choice() -> dict:
    return {
        "threshold": None,
        "completed_trades": 0,
        "rr2_wins": 0,
        "rr2_wr": 0.0,
        "expectancy_r": 0.0,
        "min_fold_wr": 0.0,
        "wilson_lower": 0.0,
        "qualified": False,
        "folds": [],
    }


def select_stable_threshold(
    rows: pd.DataFrame,
    *,
    thresholds,
    min_trades: int = 40,
    min_fold_trades: int = 10,
    target_wr: float = 0.80,
) -> dict:
    required = {"fold", "prob", "rr2_hit", "net_r"}
    if not required.issubset(rows.columns):
        raise ValueError("G7 OOF rows missing required columns")

    frame = rows.copy()
    frame["prob"] = pd.to_numeric(frame["prob"], errors="coerce")
    frame["net_r"] = pd.to_numeric(frame["net_r"], errors="coerce").fillna(0.0)
    frame["rr2_hit"] = frame["rr2_hit"].astype(bool)

    best = None
    for threshold in thresholds:
        sub = frame.loc[frame["prob"] >= float(threshold)].copy()
        n = int(len(sub))
        if n < int(min_trades):
            continue

        fold_stats = []
        for fold, fold_rows in sub.groupby("fold", sort=True):
            fn = int(len(fold_rows))
            if fn < int(min_fold_trades):
                continue
            fwins = int(fold_rows["rr2_hit"].sum())
            fold_stats.append(
                {
                    "fold": int(fold) if isinstance(fold, (int, np.integer)) else fold,
                    "completed_trades": fn,
                    "rr2_wr": float(fwins / fn if fn else 0.0),
                }
            )
        if not fold_stats:
            continue

        wins = int(sub["rr2_hit"].sum())
        wr = float(wins / n if n else 0.0)
        expectancy = float(sub["net_r"].mean())
        min_fold_wr = float(min(x["rr2_wr"] for x in fold_stats))
        lower = wilson_lower(wins, n)
        candidate = {
            "threshold": float(threshold),
            "completed_trades": n,
            "rr2_wins": wins,
            "rr2_wr": wr,
            "expectancy_r": expectancy,
            "min_fold_wr": min_fold_wr,
            "wilson_lower": lower,
            "folds": fold_stats,
        }
        candidate["qualified"] = route_is_target_qualified(candidate, target_wr=target_wr)
        key = (min_fold_wr, lower, expectancy, n, float(threshold))
        if best is None or key > best[0]:
            best = (key, candidate)

    return _empty_choice() if best is None else best[1]
