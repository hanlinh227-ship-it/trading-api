from config import DEFAULT_CONFIG, SYMBOLS


def test_universe_is_exactly_ten_symbols():
    assert SYMBOLS == (
        "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT",
        "TRXUSDT", "DOGEUSDT", "LINKUSDT", "ADAUSDT", "XLMUSDT",
    )


def test_hard_gates_are_locked():
    assert DEFAULT_CONFIG.rr_primary == 2.0
    assert DEFAULT_CONFIG.rr_secondary == 1.0
    assert DEFAULT_CONFIG.min_completed_trades == 100
    assert DEFAULT_CONFIG.target_wr == 0.80
