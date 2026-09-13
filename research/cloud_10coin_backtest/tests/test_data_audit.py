import pandas as pd

from data.audit import audit_bars


def _frame(times):
    return pd.DataFrame({
        "open_time": times,
        "open": [10.0] * len(times),
        "high": [11.0] * len(times),
        "low": [9.0] * len(times),
        "close": [10.5] * len(times),
        "volume": [1.0] * len(times),
        "quote_volume": [10.0] * len(times),
        "trade_count": [1] * len(times),
        "taker_buy_base": [0.5] * len(times),
        "taker_buy_quote": [5.0] * len(times),
    })


def test_audit_detects_missing_interval():
    audit = audit_bars(_frame([0, 300_000, 900_000]), interval_ms=300_000)
    assert audit.gaps == 1
    assert audit.ok is False


def test_audit_accepts_clean_grid():
    audit = audit_bars(_frame([0, 300_000, 600_000]), interval_ms=300_000)
    assert audit.gaps == 0
    assert audit.duplicates == 0
    assert audit.ok is True
