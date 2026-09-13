import pandas as pd

from features.state import build_features


def _bars(n=360):
    rows = []
    for i in range(n):
        px = 100.0 + i * 0.01
        rows.append({
            "open_time": i * 300_000,
            "open": px,
            "high": px + 0.20,
            "low": px - 0.20,
            "close": px + 0.05,
            "volume": 100.0 + (i % 7),
            "quote_volume": 10_000.0,
            "trade_count": 20 + (i % 5),
            "taker_buy_base": 45.0 + (i % 9),
            "taker_buy_quote": 4_500.0,
        })
    return pd.DataFrame(rows)


def test_future_price_change_does_not_change_past_features():
    source = _bars()
    a = build_features(source)
    changed = source.copy()
    changed.loc[changed.index[-1], "close"] *= 10
    b = build_features(changed)
    pd.testing.assert_series_equal(a.iloc[:-1]["atr14"], b.iloc[:-1]["atr14"], check_names=False)
    pd.testing.assert_series_equal(a.iloc[:-1]["prior_high_12"], b.iloc[:-1]["prior_high_12"], check_names=False)


def test_prior_extrema_exclude_current_bar():
    source = _bars(40)
    source.loc[20, "high"] = 999.0
    features = build_features(source)
    assert features.loc[20, "prior_high_12"] < 999.0
    assert features.loc[21, "prior_high_12"] == 999.0
