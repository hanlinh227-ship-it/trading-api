import pandas as pd

from engine.execution import OrderCandidate, simulate_trade


def _bars(rows):
    return pd.DataFrame(rows)


def test_order_cannot_fill_on_signal_bar():
    bars = _bars([
        {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5},
        {"open": 101.0, "high": 102.0, "low": 100.8, "close": 101.5},
    ])
    candidate = OrderCandidate(signal_index=0, side="LONG", entry=99.5, stop=98.5, max_fill_bars=1, max_hold_bars=10)
    result = simulate_trade(candidate, bars, rr=(1.0, 2.0))
    assert result is None


def test_limit_fill_must_trade_through_on_subsequent_bar():
    bars = _bars([
        {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5},
        {"open": 100.4, "high": 101.2, "low": 99.4, "close": 100.0},
        {"open": 100.0, "high": 103.0, "low": 99.8, "close": 102.0},
    ])
    candidate = OrderCandidate(signal_index=0, side="LONG", entry=99.5, stop=98.5, max_fill_bars=2, max_hold_bars=10)
    result = simulate_trade(candidate, bars, rr=(1.0, 2.0))
    assert result is not None
    assert result.fill_index == 1
