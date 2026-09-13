from __future__ import annotations

import math


QUALIFIED_SIGNAL = "QUALIFIED_SIGNAL"
NO_TRADE_UNQUALIFIED = "NO_TRADE_UNQUALIFIED"
NO_TRADE_REGIME = "NO_TRADE_REGIME"
NO_TRADE_CONFIDENCE = "NO_TRADE_CONFIDENCE"
DATA_FAIL = "DATA_FAIL"


def classify_signal_decision(profile, route_spec, probability, *, data_ok: bool = True) -> str:
    """Return a research-only, fail-closed G7 signal decision.

    This helper never places an order and never converts model probability into a
    claimed future win rate. Historical route qualification is a separate frozen
    gate from the current model score.
    """
    if not bool(data_ok):
        return DATA_FAIL
    if not isinstance(route_spec, dict):
        return NO_TRADE_UNQUALIFIED
    if not bool(route_spec.get("regime_allowed", True)):
        return NO_TRADE_REGIME
    if not bool(route_spec.get("qualified", False)):
        return NO_TRADE_UNQUALIFIED

    try:
        p = float(probability)
        threshold = float(route_spec.get("threshold"))
    except (TypeError, ValueError):
        return NO_TRADE_CONFIDENCE
    if not math.isfinite(p) or not math.isfinite(threshold):
        return NO_TRADE_CONFIDENCE
    if p < threshold:
        return NO_TRADE_CONFIDENCE
    return QUALIFIED_SIGNAL
