from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from engine.execution import OrderCandidate
from engine.metrics import summarize_outcomes
from optimize.meta_model import fit_logistic, predict_proba, select_oof_threshold
from optimize.search import (
    CoinResearchResult,
    G2_MAX_COST_R,
    _cost_bps,
    _simulate_fast,
    diagnose_bottleneck,
    passes_g2_gate,
)
from optimize.stability import chronological_folds


FEATURE_NAMES = (
    "h1_trend_dir",
    "h4_trend_dir",
    "trend_strength",
    "flow_delta_dir",
    "flow_ema12_dir",
    "z_ema20_dir",
    "close_loc_dir",
    "body_atr",
    "log_rel_volume",
    "log_rel_trades",
    "vol_regime",
    "breakout_dir_atr",
    "opposite_distance_atr",
    "range_position_dir",
    "h1_ma20_distance_dir",
    "h4_ma20_distance_dir",
    "impulse3_atr_dir",
    "impulse12_atr_dir",
    "favorable_sweep",
    "adverse_sweep",
)


@dataclass(frozen=True)
class MetaLockedProfile:
    params: dict
    profile_hash: str


def _safe_series(frame: pd.DataFrame, name: str, default=0.0) -> pd.Series:
    if name in frame.columns:
        return pd.to_numeric(frame[name], errors="coerce")
    return pd.Series(default, index=frame.index, dtype=float)


def directional_feature_matrix(features: pd.DataFrame, side: str) -> np.ndarray:
    side = side.upper()
    direction = 1.0 if side == "LONG" else -1.0
    atr = _safe_series(features, "atr14").replace(0, np.nan)
    close = _safe_series(features, "close")
    h1_trend = _safe_series(features, "h1_trend") * direction
    h4_trend = _safe_series(features, "h4_trend") * direction
    trend_strength = _safe_series(features, "trend_strength")
    flow_delta = _safe_series(features, "flow_delta") * direction
    flow_ema = _safe_series(features, "flow_ema12") * direction
    z = _safe_series(features, "z_ema20") * direction
    close_loc = _safe_series(features, "close_loc", 0.5)
    close_loc_dir = close_loc if side == "LONG" else 1.0 - close_loc
    body_atr = _safe_series(features, "body_atr")
    rel_volume = np.log1p(_safe_series(features, "rel_volume").clip(lower=0.0))
    rel_trades = np.log1p(_safe_series(features, "rel_trades").clip(lower=0.0))
    vol_regime = _safe_series(features, "vol_regime", 1.0)

    ph12 = _safe_series(features, "prior_high_12")
    pl12 = _safe_series(features, "prior_low_12")
    ph24 = _safe_series(features, "prior_high_24")
    pl24 = _safe_series(features, "prior_low_24")
    if side == "LONG":
        breakout = (close - ph12) / atr
        opposite = (close - pl12) / atr
        range_pos = (close - pl24) / (ph24 - pl24).replace(0, np.nan)
        favorable_sweep = _safe_series(features, "recent_sweep_low_3")
        adverse_sweep = _safe_series(features, "recent_sweep_high_3")
    else:
        breakout = (pl12 - close) / atr
        opposite = (ph12 - close) / atr
        raw_pos = (close - pl24) / (ph24 - pl24).replace(0, np.nan)
        range_pos = 1.0 - raw_pos
        favorable_sweep = _safe_series(features, "recent_sweep_high_3")
        adverse_sweep = _safe_series(features, "recent_sweep_low_3")

    h1_dist = ((close - _safe_series(features, "h1_ma20")) / atr) * direction
    h4_dist = ((close - _safe_series(features, "h4_ma20")) / atr) * direction
    impulse3 = ((close - close.shift(3)) / atr) * direction
    impulse12 = ((close - close.shift(12)) / atr) * direction

    cols = [
        h1_trend,
        h4_trend,
        trend_strength,
        flow_delta,
        flow_ema,
        z,
        close_loc_dir,
        body_atr,
        rel_volume,
        rel_trades,
        vol_regime,
        breakout,
        opposite,
        range_pos,
        h1_dist,
        h4_dist,
        impulse3,
        impulse12,
        favorable_sweep,
        adverse_sweep,
    ]
    matrix = np.column_stack([pd.to_numeric(c, errors="coerce").to_numpy(float) for c in cols])
    return np.clip(np.nan_to_num(matrix, nan=0.0, posinf=5.0, neginf=-5.0), -5.0, 5.0)


def build_base_candidates(
    features: pd.DataFrame,
    side: str,
    *,
    risk_atr: float,
    hold_bars: int,
    stride: int = 6,
    roundtrip_cost_bps: float = 12.0,
):
    side = side.upper()
    local = features.reset_index(drop=True)
    end = max(0, len(local) - int(hold_bars) - 2)
    out = []
    for i in range(0, end, max(1, int(stride))):
        entry = float(local.close.iloc[i])
        atr = float(local.atr14.iloc[i])
        if not np.isfinite(entry) or entry <= 0 or not np.isfinite(atr) or atr <= 0:
            continue
        risk = float(risk_atr) * atr
        stop = entry - risk if side == "LONG" else entry + risk
        cost_r = (entry * float(roundtrip_cost_bps) / 10_000.0) / risk
        if not np.isfinite(cost_r) or cost_r > G2_MAX_COST_R:
            continue
        out.append(
            OrderCandidate(
                signal_index=i,
                side=side,
                entry=entry,
                stop=stop,
                max_fill_bars=1,
                max_hold_bars=int(hold_bars),
                quality=0.0,
                family="meta_g4",
            )
        )
    return out


def _dataset(segment: pd.DataFrame, side: str, risk_atr: float, hold_bars: int, config):
    local = segment.reset_index(drop=True)
    base = build_base_candidates(
        local,
        side,
        risk_atr=risk_atr,
        hold_bars=hold_bars,
        stride=6,
        roundtrip_cost_bps=_cost_bps(config),
    )
    trades = _simulate_fast(base, local, config)
    if not trades:
        return np.empty((0, len(FEATURE_NAMES))), pd.DataFrame(columns=["rr2_hit", "net_r"])
    all_x = directional_feature_matrix(local, side)
    idx = np.array([int(t["signal_index"]) for t in trades], dtype=int)
    x = all_x[idx]
    rows = pd.DataFrame(
        {
            "rr2_hit": [bool(t["rr2_hit"]) for t in trades],
            "net_r": [float(t["net_r"]) for t in trades],
        }
    )
    return x, rows


def _threshold_grid(probs: np.ndarray):
    probs = np.asarray(probs, dtype=float)
    probs = probs[np.isfinite(probs)]
    if len(probs) == 0:
        return ()
    qs = np.quantile(probs, [0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.93, 0.95, 0.97])
    return tuple(sorted({float(np.clip(x, 0.01, 0.99)) for x in qs}))


def _fit_side_profile(dev: pd.DataFrame, side: str, config):
    folds = [dev.iloc[a:b].copy() for a, b in chronological_folds(len(dev), 5)]
    best = None
    rejected = []
    for risk_atr in (0.6, 0.9, 1.2):
        for hold_bars in (72, 144):
            fold_sets = [_dataset(f, side, risk_atr, hold_bars, config) for f in folds]
            oof_parts = []
            for j in range(1, len(fold_sets)):
                train_x = [fold_sets[i][0] for i in range(j) if len(fold_sets[i][0])]
                train_rows = [fold_sets[i][1] for i in range(j) if len(fold_sets[i][1])]
                test_x, test_rows = fold_sets[j]
                if not train_x or len(test_x) == 0:
                    continue
                x_train = np.vstack(train_x)
                rows_train = pd.concat(train_rows, ignore_index=True)
                y_train = rows_train["rr2_hit"].astype(float).to_numpy()
                if len(y_train) < 40 or len(np.unique(y_train)) < 2:
                    continue
                model = fit_logistic(x_train, y_train, l2=2.0, iterations=250, learning_rate=0.04)
                p = predict_proba(model, test_x)
                part = test_rows.copy()
                part["prob"] = p
                oof_parts.append(part)
            if not oof_parts:
                continue
            oof = pd.concat(oof_parts, ignore_index=True)
            min_trades = min(150, max(40, int(len(oof) * 0.20)))
            choice = select_oof_threshold(
                oof,
                thresholds=_threshold_grid(oof["prob"].to_numpy(float)),
                min_trades=min_trades,
            )
            if choice["threshold"] is None:
                continue
            geometry = {
                "side": side,
                "risk_atr": float(risk_atr),
                "hold_bars": int(hold_bars),
                "oof": choice,
                "oof_total": int(len(oof)),
            }
            rejected.append(geometry)
            key = (choice["score"], choice["rr2_wr"], choice["completed_trades"])
            if best is None or key > best[0]:
                best = (key, risk_atr, hold_bars, choice, fold_sets)
    if best is None:
        return None, rejected

    _, risk_atr, hold_bars, choice, fold_sets = best
    train_x = [x for x, _ in fold_sets if len(x)]
    train_rows = [r for _, r in fold_sets if len(r)]
    x_all = np.vstack(train_x)
    rows_all = pd.concat(train_rows, ignore_index=True)
    y_all = rows_all["rr2_hit"].astype(float).to_numpy()
    model = fit_logistic(x_all, y_all, l2=2.0, iterations=350, learning_rate=0.04)
    profile = {
        "side": side,
        "risk_atr": float(risk_atr),
        "hold_bars": int(hold_bars),
        "threshold": float(choice["threshold"]),
        "oof_completed_trades": int(choice["completed_trades"]),
        "oof_rr2_wr": float(choice["rr2_wr"]),
        "oof_expectancy_r": float(choice["expectancy_r"]),
        "model": {
            "mean": model.mean.tolist(),
            "scale": model.scale.tolist(),
            "weights": model.weights.tolist(),
            "bias": float(model.bias),
        },
    }
    rejected = sorted(rejected, key=lambda r: r["oof"]["score"], reverse=True)
    return profile, rejected[:6]


def _restore_model(profile):
    from optimize.meta_model import LogisticModel

    m = profile["model"]
    return LogisticModel(
        mean=np.asarray(m["mean"], dtype=float),
        scale=np.asarray(m["scale"], dtype=float),
        weights=np.asarray(m["weights"], dtype=float),
        bias=float(m["bias"]),
    )


def _selected_candidates(segment: pd.DataFrame, profile, config):
    local = segment.reset_index(drop=True)
    side = profile["side"]
    base = build_base_candidates(
        local,
        side,
        risk_atr=profile["risk_atr"],
        hold_bars=profile["hold_bars"],
        stride=6,
        roundtrip_cost_bps=_cost_bps(config),
    )
    if not base:
        return []
    matrix = directional_feature_matrix(local, side)
    idx = np.array([c.signal_index for c in base], dtype=int)
    probs = predict_proba(_restore_model(profile), matrix[idx])
    out = []
    for c, p in zip(base, probs):
        if float(p) >= float(profile["threshold"]):
            out.append(
                OrderCandidate(
                    c.signal_index,
                    c.side,
                    c.entry,
                    c.stop,
                    c.max_fill_bars,
                    c.max_hold_bars,
                    float(p),
                    c.family,
                )
            )
    return out


def _evaluate_profiles(segment: pd.DataFrame, profiles, config):
    pool = []
    for profile in profiles:
        pool.extend(_selected_candidates(segment, profile, config))
    # One directional decision per signal timestamp: keep the higher model probability.
    by_index = {}
    for c in pool:
        prev = by_index.get(c.signal_index)
        if prev is None or c.quality > prev.quality:
            by_index[c.signal_index] = c
    candidates = sorted(by_index.values(), key=lambda c: c.signal_index)
    trades = _simulate_fast(candidates, segment.reset_index(drop=True), config)
    return summarize_outcomes(trades), trades


def _lock_meta(profiles):
    payload = {"family": "meta_g4", "feature_names": list(FEATURE_NAMES), "sides": profiles}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return MetaLockedProfile(params=payload, profile_hash=hashlib.sha256(raw.encode()).hexdigest())


def search_coin_g4(symbol: str, features: pd.DataFrame, config) -> CoinResearchResult:
    n = len(features)
    a = int(n * config.development_fraction)
    b = int(n * (config.development_fraction + config.validation_fraction))
    dev = features.iloc[:a].copy()
    val = features.iloc[a:b].copy()
    hold = features.iloc[b:].copy()

    profiles = []
    rejected = []
    for side in ("LONG", "SHORT"):
        profile, side_rejected = _fit_side_profile(dev, side, config)
        if profile is not None:
            profiles.append(profile)
        for row in side_rejected:
            rejected.append(
                {
                    "family": "meta_g4",
                    "params": {
                        "side": row["side"],
                        "risk_atr": row["risk_atr"],
                        "hold_bars": row["hold_bars"],
                    },
                    "metrics": {
                        "completed_trades": row["oof"]["completed_trades"],
                        "rr2_wr": row["oof"]["rr2_wr"],
                        "expectancy_r": row["oof"]["expectancy_r"],
                    },
                    "score": row["oof"]["score"],
                }
            )

    if not profiles:
        zero = summarize_outcomes([])
        return CoinResearchResult(symbol, "FAIL", None, zero, zero, zero, zero, ["meta-model-no-stable-profile"], rejected[:8], [])

    locked = _lock_meta(profiles)
    dev_metrics, _ = _evaluate_profiles(dev, profiles, config)
    val_metrics, val_trades = _evaluate_profiles(val, profiles, config)
    hold_metrics, hold_trades = _evaluate_profiles(hold, profiles, config)
    evaluation_trades = val_trades + hold_trades
    eval_metrics = summarize_outcomes(evaluation_trades)

    passed = passes_g2_gate(
        completed_trades=eval_metrics.completed_trades,
        rr2_wr=eval_metrics.rr2_wr,
        expectancy_r=eval_metrics.expectancy_r,
        validation_trades=val_metrics.completed_trades,
        validation_wr=val_metrics.rr2_wr,
        holdout_trades=hold_metrics.completed_trades,
        holdout_wr=hold_metrics.rr2_wr,
        target_wr=config.target_wr,
        min_trades=config.min_completed_trades,
    )
    bottlenecks = diagnose_bottleneck(dev_metrics, eval_metrics)
    if any(p["oof_rr2_wr"] >= 0.70 for p in profiles) and eval_metrics.rr2_wr + 0.15 < max(p["oof_rr2_wr"] for p in profiles):
        if "meta-generalization-gap" not in bottlenecks:
            bottlenecks.append("meta-generalization-gap")

    return CoinResearchResult(
        symbol,
        "PASS" if passed else "FAIL",
        locked,
        dev_metrics,
        val_metrics,
        hold_metrics,
        eval_metrics,
        bottlenecks,
        sorted(rejected, key=lambda r: r["score"], reverse=True)[:8],
        evaluation_trades,
    )
