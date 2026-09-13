from __future__ import annotations

from itertools import product

import numpy as np

from engine.execution import OrderCandidate
from strategies.common import quality_score

family_name = "sweep_mss_ote_g2"


def parameter_grid():
    for side, r, confirm_window, displacement_min, flow_min, regime in product(
        ("LONG", "SHORT"),
        (0.618, 0.79, 0.90),
        (3, 6),
        (0.60, 0.90),
        (0.52, 0.58),
        ("any", "normal"),
    ):
        yield {
            "side": side,
            "r": r,
            "confirm_window": confirm_window,
            "displacement_min": displacement_min,
            "flow_min": flow_min,
            "rel_volume_min": 1.0,
            "min_risk_atr": 0.20,
            "stop_buffer_atr": 0.03,
            "max_cost_r": 0.20,
            "roundtrip_cost_bps": 12.0,
            "regime": regime,
        }


def _regime_ok(value: str, wanted: str) -> bool:
    return wanted == "any" or value == wanted


def _cost_r(entry: float, stop: float, bps: float) -> float:
    risk = abs(entry - stop)
    if risk <= 0:
        return float("inf")
    return (entry * bps / 10_000.0) / risk


def generate_candidates(f, params):
    if f.empty:
        return []
    side = params["side"].upper()
    confirm_window = int(params["confirm_window"])
    displacement_min = float(params["displacement_min"])
    flow_min = float(params["flow_min"])
    rel_volume_min = float(params.get("rel_volume_min", 1.0))
    r = float(params["r"])
    stop_buffer = float(params.get("stop_buffer_atr", 0.03))
    min_risk_atr = float(params.get("min_risk_atr", 0.20))
    max_cost_r = float(params.get("max_cost_r", 0.20))
    roundtrip_cost_bps = float(params.get("roundtrip_cost_bps", 12.0))
    wanted_regime = params.get("regime", "any")
    base_quality = quality_score(f, side)
    out = []
    n = len(f)

    if side == "LONG":
        sweeps = np.flatnonzero(f["sweep_low"].fillna(False).to_numpy(bool))
    else:
        sweeps = np.flatnonzero(f["sweep_high"].fillna(False).to_numpy(bool))

    for s in sweeps:
        trend_ok = (f["h1_trend"].iloc[s] == (1 if side == "LONG" else -1)) and (f["h4_trend"].iloc[s] == (1 if side == "LONG" else -1))
        if not trend_ok or not _regime_ok(str(f["regime"].iloc[s]), wanted_regime):
            continue
        structure = float(f["prior_swing_high_6"].iloc[s] if side == "LONG" else f["prior_swing_low_6"].iloc[s])
        sweep_extreme = float(f["low"].iloc[s] if side == "LONG" else f["high"].iloc[s])
        if not np.isfinite(structure) or not np.isfinite(sweep_extreme):
            continue
        for j in range(s + 1, min(n, s + confirm_window + 1)):
            if f["h1_trend"].iloc[j] != (1 if side == "LONG" else -1) or f["h4_trend"].iloc[j] != (1 if side == "LONG" else -1):
                continue
            if not _regime_ok(str(f["regime"].iloc[j]), wanted_regime):
                continue
            if float(f["body_atr"].iloc[j]) < displacement_min or float(f["rel_volume"].iloc[j]) < rel_volume_min:
                continue
            if float(f["rel_trades"].iloc[j]) < 0.80:
                continue
            if side == "LONG":
                if not (float(f["close"].iloc[j]) > structure and float(f["close_loc"].iloc[j]) >= 0.70 and float(f["taker_buy_ratio"].iloc[j]) >= flow_min):
                    continue
                impulse_high = float(f["high"].iloc[j])
                impulse_low = float(f["low"].iloc[j])
                entry = impulse_high - r * (impulse_high - impulse_low)
                stop = sweep_extreme - stop_buffer * float(f["atr14"].iloc[j])
                risk = entry - stop
            else:
                if not (float(f["close"].iloc[j]) < structure and float(f["close_loc"].iloc[j]) <= 0.30 and float(f["taker_buy_ratio"].iloc[j]) <= 1.0 - flow_min):
                    continue
                impulse_high = float(f["high"].iloc[j])
                impulse_low = float(f["low"].iloc[j])
                entry = impulse_low + r * (impulse_high - impulse_low)
                stop = sweep_extreme + stop_buffer * float(f["atr14"].iloc[j])
                risk = stop - entry
            atr = float(f["atr14"].iloc[j])
            if risk <= 0 or not np.isfinite(atr) or atr <= 0 or risk / atr < min_risk_atr:
                continue
            if _cost_r(entry, stop, roundtrip_cost_bps) > max_cost_r:
                continue
            sequence_bonus = min(0.15, 0.03 * max(0, confirm_window - (j - s)))
            q = float(min(1.0, base_quality.iloc[j] + sequence_bonus))
            out.append(OrderCandidate(j, side, entry, stop, max_fill_bars=8, max_hold_bars=144, quality=q, family=family_name))
            break
    return out
