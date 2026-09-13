from __future__ import annotations

import numpy as np
import pandas as pd


G7_REGIMES = (
    "TREND_UP",
    "TREND_DOWN",
    "RANGE",
    "COMPRESSION",
    "EXPANSION",
    "SHOCK",
)


def _num(frame: pd.DataFrame, name: str, default: float) -> pd.Series:
    if name in frame.columns:
        return pd.to_numeric(frame[name], errors="coerce").fillna(default)
    return pd.Series(default, index=frame.index, dtype=float)


def classify_regimes(features: pd.DataFrame) -> pd.Series:
    """Classify each row using only causal same-row features.

    Precedence is SHOCK -> COMPRESSION -> EXPANSION -> directional trend -> RANGE.
    Missing values fall back conservatively and cannot create a directional trend.
    """
    f = features.reset_index(drop=True)
    h1 = _num(f, "h1_trend", 0.0)
    h4 = _num(f, "h4_trend", 0.0)
    strength = _num(f, "trend_strength", 0.0)
    vol = _num(f, "vol_regime", 1.0)
    body = _num(f, "body_atr", 0.0)
    rel_volume = _num(f, "rel_volume", 1.0)

    out = np.full(len(f), "RANGE", dtype=object)

    shock = (body >= 2.5) & (rel_volume >= 2.0) & (vol >= 1.6)
    compression = (vol <= 0.75) & (body <= 0.55) & ~shock
    expansion = (vol >= 1.35) & (body >= 0.75) & ~shock & ~compression
    trend_up = (h1 > 0) & (h4 > 0) & (strength >= 0.70) & ~shock & ~compression & ~expansion
    trend_down = (h1 < 0) & (h4 < 0) & (strength >= 0.70) & ~shock & ~compression & ~expansion

    out[trend_up.to_numpy(bool)] = "TREND_UP"
    out[trend_down.to_numpy(bool)] = "TREND_DOWN"
    out[expansion.to_numpy(bool)] = "EXPANSION"
    out[compression.to_numpy(bool)] = "COMPRESSION"
    out[shock.to_numpy(bool)] = "SHOCK"
    return pd.Series(out, index=f.index, name="g7_regime")
