import pandas as pd

from engine.execution import OrderCandidate, simulate_trade


def test_same_bar_tp_and_sl_is_stop_first():
    bars = pd.DataFrame([
        {"open": 100.0, "high": 100.2, "low": 99.8, "close": 100.0},
        {"open": 100.0, "high": 103.0, "low": 98.0, "close": 101.0},
    ])
    candidate = OrderCandidate(signal_index=0, side="LONG", entry=100.0, stop=99.0, max_fill_bars=1, max_hold_bars=10)
    result = simulate_trade(candidate, bars, rr=(1.0, 2.0))
    assert result is not None
    assert result.exit_reason in {"STOP_AMBIGUOUS", "FILL_STOP_AMBIGUOUS"}
    assert result.rr2_hit is False
