import numpy as np
import pandas as pd

from features.state import build_features


def _bars(n=720):
    t = np.arange(n)
    close = 100.0 + 0.02 * t + np.sin(t / 17.0)
    open_ = close - 0.05
    high = close + 0.30
    low = close - 0.30
    volume = 1000.0 + (t % 11) * 15.0
    taker = volume * (0.50 + 0.08 * np.sin(t / 13.0))
    return pd.DataFrame({
        "open_time": 1_700_000_000_000 + t * 300_000,
        "open": open_, "high": high, "low": low, "close": close,
        "volume": volume, "trade_count": 100 + (t % 9),
        "taker_buy_base": taker,
    })


def test_g2_prior_swing_excludes_current_bar():
    bars = _bars()
    bars.loc[300, "high"] = 999.0
    f = build_features(bars)
    assert f.loc[300, "prior_swing_high_6"] < 999.0
    assert f.loc[301, "prior_swing_high_6"] == 999.0


def test_g2_features_are_causal_when_future_bars_are_appended():
    base = _bars(600)
    extended = _bars(650)
    a = build_features(base)
    b = build_features(extended).iloc[: len(base)]
    cols = [
        "h1_trend", "h4_trend", "regime", "flow_ema12", "flow_divergence",
        "prior_swing_high_6", "prior_swing_low_6",
    ]
    pd.testing.assert_frame_equal(a[cols].reset_index(drop=True), b[cols].reset_index(drop=True))
