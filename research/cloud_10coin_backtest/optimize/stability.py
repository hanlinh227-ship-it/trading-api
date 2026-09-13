from __future__ import annotations

import math
from statistics import fmean, pstdev

from engine.metrics import Metrics


def chronological_folds(n: int, k: int = 5) -> list[tuple[int, int]]:
    """Partition [0, n) into contiguous chronological folds with no overlap."""
    if n < 0:
        raise ValueError("n must be non-negative")
    if k <= 0:
        raise ValueError("k must be positive")
    if n == 0:
        return []
    k = min(k, n)
    base, remainder = divmod(n, k)
    folds: list[tuple[int, int]] = []
    start = 0
    for i in range(k):
        size = base + (1 if i < remainder else 0)
        end = start + size
        folds.append((start, end))
        start = end
    return folds


def stability_score(fold_metrics: list[Metrics]) -> float:
    """Score a candidate using development folds only, rewarding worst-fold robustness."""
    if not fold_metrics:
        return -math.inf

    wrs = [m.rr2_wr for m in fold_metrics]
    lows = [m.wilson_low for m in fold_metrics]
    expectancies = [max(-1.0, min(1.0, m.expectancy_r)) for m in fold_metrics]
    total_trades = sum(m.completed_trades for m in fold_metrics)

    min_wr = min(wrs)
    mean_wr = fmean(wrs)
    min_wilson = min(lows)
    mean_expectancy = fmean(expectancies)
    breadth = min(1.0, total_trades / 100.0)
    dispersion = pstdev(wrs) if len(wrs) > 1 else 0.0

    return (
        0.35 * min_wr
        + 0.25 * mean_wr
        + 0.15 * min_wilson
        + 0.10 * breadth
        + 0.10 * mean_expectancy
        - 0.15 * dispersion
    )


def rank_stable_candidates(rows: list[dict]) -> list[dict]:
    """Rank candidates only from fold_metrics; validation/holdout are deliberately ignored."""
    ranked = []
    for row in rows:
        item = dict(row)
        item["stability_score"] = stability_score(list(row.get("fold_metrics", [])))
        ranked.append(item)
    ranked.sort(
        key=lambda r: (
            r["stability_score"],
            r.get("family", ""),
            repr(sorted(r.get("params", {}).items())),
        ),
        reverse=True,
    )
    return ranked
