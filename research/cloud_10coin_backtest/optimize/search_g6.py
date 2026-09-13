from __future__ import annotations

import numpy as np
import pandas as pd

from engine.execution import OrderCandidate
from optimize.search_g4 import directional_feature_matrix


SETUP_FAMILIES = (
    "setup_trend",
    "setup_breakout",
    "setup_sweep",
    "setup_compression",
    "setup_exhaustion",
)
RISK_ATR_GRID = (0.8, 1.2, 1.6)
HOLD_GRID = (72, 144)
MAX_COST_R = 0.20


def _num(frame: pd.DataFrame, name: str, default=0.0) -> pd.Series:
    if name in frame.columns:
        return pd.to_numeric(frame[name], errors="coerce")
    return pd.Series(default, index=frame.index, dtype=float)


def _event_masks(f: pd.DataFrame):
    close = _num(f, "close")
    high = _num(f, "high")
    low = _num(f, "low")
    prior_high = _num(f, "prior_high_12")
    prior_low = _num(f, "prior_low_12")
    body = _num(f, "body_atr")
    close_loc = _num(f, "close_loc", 0.5)
    rel_volume = _num(f, "rel_volume", 1.0)
    flow = _num(f, "flow_delta")
    vol_regime = _num(f, "vol_regime", 1.0)
    z = _num(f, "z_ema20")
    h1 = _num(f, "h1_trend")
    h4 = _num(f, "h4_trend")

    long_break = (close > prior_high) & (body >= 0.50) & (close_loc >= 0.70) & (rel_volume >= 1.0) & (flow >= 0.0)
    short_break = (close < prior_low) & (body >= 0.50) & (close_loc <= 0.30) & (rel_volume >= 1.0) & (flow <= 0.0)

    return {
        ("setup_trend", "LONG"): (h1 > 0) & (h4 > 0) & (body >= 0.45) & (close_loc >= 0.68) & (rel_volume >= 0.9) & (flow >= 0.0),
        ("setup_trend", "SHORT"): (h1 < 0) & (h4 < 0) & (body >= 0.45) & (close_loc <= 0.32) & (rel_volume >= 0.9) & (flow <= 0.0),
        ("setup_breakout", "LONG"): long_break,
        ("setup_breakout", "SHORT"): short_break,
        ("setup_sweep", "LONG"): (low < prior_low) & (close_loc >= 0.75) & (flow >= 0.0),
        ("setup_sweep", "SHORT"): (high > prior_high) & (close_loc <= 0.25) & (flow <= 0.0),
        ("setup_compression", "LONG"): long_break & (vol_regime <= 0.85),
        ("setup_compression", "SHORT"): short_break & (vol_regime <= 0.85),
        ("setup_exhaustion", "LONG"): (z <= -2.0) & (close_loc >= 0.75) & (flow >= 0.0),
        ("setup_exhaustion", "SHORT"): (z >= 2.0) & (close_loc <= 0.25) & (flow <= 0.0),
    }


def build_setup_candidates(features: pd.DataFrame, *, roundtrip_cost_bps: float = 12.0):
    f = features.reset_index(drop=True)
    atr = _num(f, "atr14").to_numpy(float)
    close = _num(f, "close").to_numpy(float)
    out = []
    masks = _event_masks(f)
    for (family, side), mask in masks.items():
        indices = np.flatnonzero(mask.fillna(False).to_numpy(bool))
        for i in indices:
            entry = float(close[i])
            atr_i = float(atr[i])
            if not np.isfinite(entry) or entry <= 0 or not np.isfinite(atr_i) or atr_i <= 0:
                continue
            for risk_atr in RISK_ATR_GRID:
                risk = float(risk_atr) * atr_i
                cost_r = (entry * float(roundtrip_cost_bps) / 10_000.0) / risk
                if not np.isfinite(cost_r) or cost_r > MAX_COST_R:
                    continue
                stop = entry - risk if side == "LONG" else entry + risk
                for hold_bars in HOLD_GRID:
                    out.append(
                        OrderCandidate(
                            signal_index=int(i),
                            side=side,
                            entry=entry,
                            stop=stop,
                            max_fill_bars=1,
                            max_hold_bars=int(hold_bars),
                            quality=0.0,
                            family=family,
                        )
                    )
    out.sort(key=lambda c: (c.signal_index, c.family, c.side, c.stop, c.max_hold_bars))
    return out


def candidate_feature_matrix(features: pd.DataFrame, candidates) -> np.ndarray:
    candidates = list(candidates)
    if not candidates:
        return np.empty((0, 20 + len(SETUP_FAMILIES) + 3), dtype=float)
    f = features.reset_index(drop=True)
    long_x = directional_feature_matrix(f, "LONG")
    short_x = directional_feature_matrix(f, "SHORT")
    atr = _num(f, "atr14").to_numpy(float)
    family_index = {name: i for i, name in enumerate(SETUP_FAMILIES)}
    rows = []
    for c in candidates:
        i = int(c.signal_index)
        base = long_x[i] if c.side == "LONG" else short_x[i]
        onehot = np.zeros(len(SETUP_FAMILIES), dtype=float)
        if c.family in family_index:
            onehot[family_index[c.family]] = 1.0
        side_flag = 1.0 if c.side == "LONG" else -1.0
        atr_i = float(atr[i]) if 0 <= i < len(atr) else np.nan
        risk_atr = abs(float(c.entry) - float(c.stop)) / atr_i if np.isfinite(atr_i) and atr_i > 0 else 0.0
        hold_norm = float(c.max_hold_bars) / 144.0
        rows.append(np.concatenate([base, onehot, [side_flag, risk_atr, hold_norm]]))
    return np.clip(np.nan_to_num(np.vstack(rows), nan=0.0, posinf=5.0, neginf=-5.0), -5.0, 5.0)
