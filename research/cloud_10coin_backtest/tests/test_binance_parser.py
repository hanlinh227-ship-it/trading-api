from data.binance_usdm import parse_kline


def test_parse_kline_exposes_taker_flow():
    row = [1000, "10", "12", "9", "11", "20", 1299, "210", 15, "13", "140", "0"]
    out = parse_kline(row)
    assert out["open_time"] == 1000
    assert out["open"] == 10.0
    assert out["high"] == 12.0
    assert out["low"] == 9.0
    assert out["close"] == 11.0
    assert out["volume"] == 20.0
    assert out["quote_volume"] == 210.0
    assert out["trade_count"] == 15
    assert out["taker_buy_base"] == 13.0
    assert out["taker_buy_quote"] == 140.0
