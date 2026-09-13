from __future__ import annotations

import numpy as np

from engine.execution import OrderCandidate


def make_candidates(features, mask, side: str, entry, stop, max_fill_bars: int = 12, max_hold_bars: int = 144):
    valid = mask.fillna(False).to_numpy(dtype=bool)
    positions = np.flatnonzero(valid)
    out = []
    for i in positions:
        e = float(entry.iloc[i])
        s = float(stop.iloc[i])
        if not np.isfinite(e) or not np.isfinite(s):
            continue
        risk = e - s if side == "LONG" else s - e
        if risk <= 0:
            continue
        out.append(OrderCandidate(int(i), side, e, s, max_fill_bars, max_hold_bars))
    return out


def trend_mask(f, side: str):
    if side == "LONG":
        return (f.h1_ma20 > f.h1_ma50) & (f.h4_ma20 > f.h4_ma50)
    return (f.h1_ma20 < f.h1_ma50) & (f.h4_ma20 < f.h4_ma50)


def flow_mask(f, side: str, threshold: float):
    if side == "LONG":
        return f.taker_buy_ratio >= threshold
    return f.taker_buy_ratio <= 1.0 - threshold
