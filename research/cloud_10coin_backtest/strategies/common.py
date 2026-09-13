from __future__ import annotations

import numpy as np
import pandas as pd

from engine.execution import OrderCandidate


def quality_score(features, side: str) -> pd.Series:
    side = side.upper()
    body = features["body_atr"].fillna(0.0).clip(0.0, 2.0) / 2.0
    trend = features["trend_strength"].fillna(0.0).clip(0.0, 2.0) / 2.0
    rel_volume = features["rel_volume"].fillna(0.0).clip(0.0, 2.0) / 2.0
    flow = features["flow_delta"].fillna(0.0)
    directional_flow = flow.clip(lower=0.0) if side == "LONG" else (-flow).clip(lower=0.0)
    directional_flow = directional_flow.clip(0.0, 0.5) / 0.5
    return (0.30 * body + 0.25 * trend + 0.20 * rel_volume + 0.25 * directional_flow).clip(0.0, 1.0)


def make_candidates(
    features,
    mask,
    side: str,
    entry,
    stop,
    max_fill_bars: int = 12,
    max_hold_bars: int = 144,
    *,
    quality=None,
    min_risk_atr: float = 0.0,
    max_cost_r: float = float("inf"),
    roundtrip_cost_bps: float = 0.0,
    family: str = "",
):
    valid = mask.fillna(False).to_numpy(dtype=bool)
    positions = np.flatnonzero(valid)
    out = []
    q = quality if quality is not None else pd.Series(0.0, index=features.index)
    for i in positions:
        e = float(entry.iloc[i])
        s = float(stop.iloc[i])
        if not np.isfinite(e) or not np.isfinite(s):
            continue
        risk = e - s if side == "LONG" else s - e
        if risk <= 0:
            continue
        atr = float(features["atr14"].iloc[i]) if "atr14" in features.columns else float("nan")
        if min_risk_atr > 0 and (not np.isfinite(atr) or atr <= 0 or risk / atr < min_risk_atr):
            continue
        cost_r = (e * roundtrip_cost_bps / 10_000.0) / risk if roundtrip_cost_bps > 0 else 0.0
        if cost_r > max_cost_r:
            continue
        qi = float(q.iloc[i]) if hasattr(q, "iloc") else float(q)
        out.append(OrderCandidate(int(i), side, e, s, max_fill_bars, max_hold_bars, qi, family))
    return out


def trend_mask(f, side: str):
    if side == "LONG":
        return (f.h1_ma20 > f.h1_ma50) & (f.h4_ma20 > f.h4_ma50)
    return (f.h1_ma20 < f.h1_ma50) & (f.h4_ma20 < f.h4_ma50)


def flow_mask(f, side: str, threshold: float):
    if side == "LONG":
        return f.taker_buy_ratio >= threshold
    return f.taker_buy_ratio <= 1.0 - threshold
