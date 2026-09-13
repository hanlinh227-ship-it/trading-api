from __future__ import annotations

import math
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Metrics:
    completed_trades: int
    rr1_wins: int
    rr2_wins: int
    rr1_wr: float
    rr2_wr: float
    expectancy_r: float
    max_drawdown_r: float
    max_losing_streak: int
    wilson_low: float
    wilson_high: float

    def to_dict(self) -> dict:
        return asdict(self)


def wilson_interval(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 0.0
    p = wins / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return max(0.0, center - margin), min(1.0, center + margin)


def _value(row, name):
    if isinstance(row, dict):
        return row[name]
    return getattr(row, name)


def summarize_outcomes(rows) -> Metrics:
    rows = list(rows)
    n = len(rows)
    if not n:
        return Metrics(0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0, 0.0, 0.0)
    rr1 = sum(bool(_value(r, "rr1_hit")) for r in rows)
    rr2 = sum(bool(_value(r, "rr2_hit")) for r in rows)
    rs = [float(_value(r, "net_r")) for r in rows]
    equity = peak = drawdown = 0.0
    losing = max_losing = 0
    for r in rs:
        equity += r
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
        if r < 0:
            losing += 1
            max_losing = max(max_losing, losing)
        else:
            losing = 0
    lo, hi = wilson_interval(rr2, n)
    return Metrics(n, rr1, rr2, rr1 / n, rr2 / n, sum(rs) / n, drawdown, max_losing, lo, hi)
