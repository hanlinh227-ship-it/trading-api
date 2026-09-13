from __future__ import annotations

import numpy as np
import pandas as pd


def _closed_htf_features(work: pd.DataFrame, freq: str, prefix: str) -> pd.DataFrame:
    indexed = work.set_index("dt")
    bars = indexed.resample(freq, label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    bars[f"{prefix}_ma20"] = bars["close"].rolling(20, min_periods=5).mean()
    bars[f"{prefix}_ma50"] = bars["close"].rolling(50, min_periods=10).mean()
    bars[f"{prefix}_close"] = bars["close"]
    cols = [f"{prefix}_ma20", f"{prefix}_ma50", f"{prefix}_close"]
    closed = bars[cols].shift(1)
    keys = work["dt"].dt.floor(freq)
    mapped = closed.reindex(keys.to_numpy()).reset_index(drop=True)
    mapped.columns = cols
    return mapped


def build_features(df5: pd.DataFrame) -> pd.DataFrame:
    if df5.empty:
        return df5.copy()
    f = df5.sort_values("open_time").reset_index(drop=True).copy()
    f["dt"] = pd.to_datetime(f["open_time"], unit="ms", utc=True)
    prev_close = f["close"].shift(1)
    tr = pd.concat([
        f["high"] - f["low"],
        (f["high"] - prev_close).abs(),
        (f["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    f["atr14"] = tr.rolling(14, min_periods=5).mean()
    f["atr48"] = tr.rolling(48, min_periods=14).mean()
    f["prior_high_3"] = f["high"].shift(1).rolling(3, min_periods=1).max()
    f["prior_low_3"] = f["low"].shift(1).rolling(3, min_periods=1).min()
    f["prior_high_12"] = f["high"].shift(1).rolling(12, min_periods=1).max()
    f["prior_low_12"] = f["low"].shift(1).rolling(12, min_periods=1).min()
    f["prior_high_24"] = f["high"].shift(1).rolling(24, min_periods=3).max()
    f["prior_low_24"] = f["low"].shift(1).rolling(24, min_periods=3).min()
    f["swing_high_6"] = f["high"].rolling(6, min_periods=1).max()
    f["swing_low_6"] = f["low"].rolling(6, min_periods=1).min()
    f["prior_swing_high_6"] = f["high"].shift(1).rolling(6, min_periods=1).max()
    f["prior_swing_low_6"] = f["low"].shift(1).rolling(6, min_periods=1).min()
    candle_range = (f["high"] - f["low"]).replace(0, np.nan)
    f["body"] = (f["close"] - f["open"]).abs()
    f["body_atr"] = f["body"] / f["atr14"].replace(0, np.nan)
    f["close_loc"] = (f["close"] - f["low"]) / candle_range
    f["rel_volume"] = f["volume"] / f["volume"].shift(1).rolling(48, min_periods=12).mean().replace(0, np.nan)
    f["rel_trades"] = f["trade_count"] / f["trade_count"].shift(1).rolling(48, min_periods=12).mean().replace(0, np.nan)
    f["taker_buy_ratio"] = np.where(f["volume"] > 0, f["taker_buy_base"] / f["volume"], 0.5)
    f["flow_delta"] = 2.0 * f["taker_buy_ratio"] - 1.0
    f["flow_ema12"] = f["flow_delta"].ewm(span=12, adjust=False, min_periods=1).mean()
    price_impulse = f["close"] - f["close"].shift(3)
    disagree = np.sign(price_impulse.fillna(0.0)) * np.sign(f["flow_ema12"].fillna(0.0)) < 0
    f["flow_divergence"] = np.where(disagree, -np.sign(price_impulse.fillna(0.0)), 0.0)
    f["vol_regime"] = f["atr14"] / f["atr48"].replace(0, np.nan)
    f["regime"] = np.select(
        [f["vol_regime"] <= 0.80, f["vol_regime"] >= 1.20],
        ["compression", "expansion"],
        default="normal",
    )
    f["ema20"] = f["close"].ewm(span=20, adjust=False).mean().shift(1)
    f["z_ema20"] = (f["close"] - f["ema20"]) / f["atr14"].replace(0, np.nan)
    f["sweep_low"] = (f["low"] < f["prior_low_12"]) & (f["close"] > f["prior_low_12"])
    f["sweep_high"] = (f["high"] > f["prior_high_12"]) & (f["close"] < f["prior_high_12"])
    f["recent_sweep_low_3"] = f["sweep_low"].shift(1).rolling(3, min_periods=1).max().fillna(0)
    f["recent_sweep_high_3"] = f["sweep_high"].shift(1).rolling(3, min_periods=1).max().fillna(0)
    h1 = _closed_htf_features(f, "1h", "h1")
    h4 = _closed_htf_features(f, "4h", "h4")
    for col in h1.columns:
        f[col] = h1[col].to_numpy()
    for col in h4.columns:
        f[col] = h4[col].to_numpy()
    f["h1_trend"] = np.select([f["h1_ma20"] > f["h1_ma50"], f["h1_ma20"] < f["h1_ma50"]], [1, -1], default=0)
    f["h4_trend"] = np.select([f["h4_ma20"] > f["h4_ma50"], f["h4_ma20"] < f["h4_ma50"]], [1, -1], default=0)
    f["trend_strength"] = (f["h1_ma20"] - f["h1_ma50"]).abs() / f["atr14"].replace(0, np.nan)
    return f
