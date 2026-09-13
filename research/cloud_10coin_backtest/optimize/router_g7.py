from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from engine.execution import OrderCandidate
from optimize.regime_g7 import classify_regimes
from optimize.search_g6 import build_setup_candidates


ALLOWED = {
    "TREND_UP": {
        ("setup_trend", "LONG"),
        ("setup_breakout", "LONG"),
        ("setup_compression", "LONG"),
    },
    "TREND_DOWN": {
        ("setup_trend", "SHORT"),
        ("setup_breakout", "SHORT"),
        ("setup_compression", "SHORT"),
    },
    "RANGE": {
        ("setup_sweep", "LONG"),
        ("setup_sweep", "SHORT"),
        ("setup_exhaustion", "LONG"),
        ("setup_exhaustion", "SHORT"),
    },
    "COMPRESSION": {
        ("setup_breakout", "LONG"),
        ("setup_breakout", "SHORT"),
        ("setup_compression", "LONG"),
        ("setup_compression", "SHORT"),
    },
    "EXPANSION": {
        ("setup_trend", "LONG"),
        ("setup_trend", "SHORT"),
        ("setup_breakout", "LONG"),
        ("setup_breakout", "SHORT"),
    },
    "SHOCK": set(),
}


def _value(frame: pd.DataFrame, name: str, index: int, default: float = 0.0) -> float:
    if name not in frame.columns or index < 0 or index >= len(frame):
        return float(default)
    value = pd.to_numeric(pd.Series([frame.iloc[index][name]]), errors="coerce").iloc[0]
    return float(value) if np.isfinite(value) else float(default)


def route_key(regime: str, candidate: OrderCandidate, features: pd.DataFrame):
    regime = str(regime)
    family_side = (str(candidate.family), str(candidate.side).upper())
    if family_side not in ALLOWED.get(regime, set()):
        return None

    if regime == "EXPANSION":
        i = int(candidate.signal_index)
        h1 = _value(features, "h1_trend", i, 0.0)
        h4 = _value(features, "h4_trend", i, 0.0)
        if candidate.side == "LONG" and not (h1 > 0 and h4 > 0):
            return None
        if candidate.side == "SHORT" and not (h1 < 0 and h4 < 0):
            return None

    return (regime, str(candidate.family), str(candidate.side).upper())


def geometry_key(candidate: OrderCandidate, features: pd.DataFrame) -> tuple[float, int]:
    i = int(candidate.signal_index)
    atr = _value(features, "atr14", i, np.nan)
    if not np.isfinite(atr) or atr <= 0:
        return (float("nan"), int(candidate.max_hold_bars))
    risk_atr = abs(float(candidate.entry) - float(candidate.stop)) / atr
    return (round(float(risk_atr), 6), int(candidate.max_hold_bars))


def build_routed_candidates(features: pd.DataFrame, *, roundtrip_cost_bps: float = 12.0):
    local = features.reset_index(drop=True)
    regimes = classify_regimes(local)
    routed = defaultdict(list)
    for candidate in build_setup_candidates(local, roundtrip_cost_bps=roundtrip_cost_bps):
        i = int(candidate.signal_index)
        if i < 0 or i >= len(regimes):
            continue
        key = route_key(str(regimes.iloc[i]), candidate, local)
        if key is not None:
            routed[key].append(candidate)
    return dict(routed)
