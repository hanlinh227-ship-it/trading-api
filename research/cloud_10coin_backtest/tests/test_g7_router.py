import numpy as np
import pandas as pd

from engine.execution import OrderCandidate
from optimize.router_g7 import geometry_key, route_key


def _features(n=12):
    return pd.DataFrame({
        "atr14": np.ones(n),
        "h1_trend": np.zeros(n),
        "h4_trend": np.zeros(n),
    })


def _candidate(side="LONG", family="setup_trend", signal_index=3, risk=1.2, hold=72):
    entry = 100.0
    stop = entry - risk if side == "LONG" else entry + risk
    return OrderCandidate(signal_index, side, entry, stop, 1, hold, 0.0, family)


def test_trend_up_rejects_short_trend_candidate():
    c = _candidate(side="SHORT", family="setup_trend")
    assert route_key("TREND_UP", c, _features()) is None


def test_trend_up_accepts_long_breakout():
    c = _candidate(side="LONG", family="setup_breakout")
    assert route_key("TREND_UP", c, _features()) == ("TREND_UP", "setup_breakout", "LONG")


def test_range_accepts_sweep_on_both_sides():
    f = _features()
    long_c = _candidate(side="LONG", family="setup_sweep")
    short_c = _candidate(side="SHORT", family="setup_sweep")
    assert route_key("RANGE", long_c, f) == ("RANGE", "setup_sweep", "LONG")
    assert route_key("RANGE", short_c, f) == ("RANGE", "setup_sweep", "SHORT")


def test_shock_rejects_everything():
    c = _candidate(side="LONG", family="setup_breakout")
    assert route_key("SHOCK", c, _features()) is None


def test_expansion_requires_h1_h4_side_alignment():
    f = _features()
    f.loc[3, ["h1_trend", "h4_trend"]] = [1, 1]
    long_c = _candidate(side="LONG", family="setup_breakout")
    short_c = _candidate(side="SHORT", family="setup_breakout")
    assert route_key("EXPANSION", long_c, f) == ("EXPANSION", "setup_breakout", "LONG")
    assert route_key("EXPANSION", short_c, f) is None


def test_geometry_key_uses_risk_atr_and_hold():
    f = _features()
    c = _candidate(side="LONG", family="setup_breakout", risk=1.2, hold=144)
    assert geometry_key(c, f) == (1.2, 144)
