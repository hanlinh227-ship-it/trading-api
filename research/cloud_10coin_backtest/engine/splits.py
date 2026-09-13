from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SplitRanges:
    development: list
    validation: list
    holdout: list


def chronological_splits(index, dev: float = 0.60, val: float = 0.20) -> SplitRanges:
    xs = list(index)
    if not 0 < dev < 1 or not 0 < val < 1 or dev + val >= 1:
        raise ValueError("invalid split fractions")
    n = len(xs)
    a = int(n * dev)
    b = int(n * (dev + val))
    return SplitRanges(xs[:a], xs[a:b], xs[b:])
