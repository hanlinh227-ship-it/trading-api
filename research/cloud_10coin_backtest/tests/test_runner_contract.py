import pytest

from run import build_final_summary, parse_symbols


def test_parse_symbols_accepts_subset_of_locked_universe():
    assert parse_symbols("BTCUSDT,SOLUSDT") == ["BTCUSDT", "SOLUSDT"]


def test_parse_symbols_rejects_unknown_symbol():
    with pytest.raises(ValueError):
        parse_symbols("BTCUSDT,FAKEUSDT")


def test_final_summary_counts_passes_without_inventing_target():
    rows = [
        {"symbol": "BTCUSDT", "status": "PASS"},
        {"symbol": "SOLUSDT", "status": "FAIL"},
    ]
    out = build_final_summary(rows)
    assert out["pass_count"] == 1
    assert out["total"] == 2
    assert out["all_pass"] is False
