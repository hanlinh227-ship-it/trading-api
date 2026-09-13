from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from engine.execution import OrderCandidate, simulate_trade
from engine.metrics import summarize_outcomes
from optimize.meta_model import select_oof_threshold
from optimize.nonlinear_model import fit_nonlinear, predict_nonlinear_proba
from optimize.search import (
    CoinResearchResult,
    _cost_bps,
    _simulate_fast,
    diagnose_bottleneck,
    passes_g2_gate,
)
from optimize.search_g4 import _threshold_grid, directional_feature_matrix
from optimize.stability import chronological_folds


SETUP_FAMILIES = (
    "setup_trend",
    "setup_breakout",
    "setup_sweep",
    "setup_compression",
    "setup_exhaustion",
)
RISK_ATR_GRID = (0.8, 1.2, 1.6)
HOLD_GRID = (72, 144)
MAX_COST_R = 0.20
MODEL_GRID = (
    {"n_estimators": 120, "max_depth": 4, "min_samples_leaf": 18, "max_features": 0.7, "random_state": 41},
    {"n_estimators": 120, "max_depth": 6, "min_samples_leaf": 32, "max_features": 0.7, "random_state": 41},
)


@dataclass(frozen=True)
class G6LockedProfile:
    params: dict
    profile_hash: str


@dataclass
class _RuntimeProfile:
    spec: dict
    model: object


def _num(frame: pd.DataFrame, name: str, default=0.0) -> pd.Series:
    if name in frame.columns:
        return pd.to_numeric(frame[name], errors="coerce")
    return pd.Series(default, index=frame.index, dtype=float)


def _event_masks(f: pd.DataFrame):
    close = _num(f, "close")
    high = _num(f, "high")
    low = _num(f, "low")
    prior_high = _num(f, "prior_high_12")
    prior_low = _num(f, "prior_low_12")
    body = _num(f, "body_atr")
    close_loc = _num(f, "close_loc", 0.5)
    rel_volume = _num(f, "rel_volume", 1.0)
    flow = _num(f, "flow_delta")
    vol_regime = _num(f, "vol_regime", 1.0)
    z = _num(f, "z_ema20")
    h1 = _num(f, "h1_trend")
    h4 = _num(f, "h4_trend")

    long_break = (close > prior_high) & (body >= 0.50) & (close_loc >= 0.70) & (rel_volume >= 1.0) & (flow >= 0.0)
    short_break = (close < prior_low) & (body >= 0.50) & (close_loc <= 0.30) & (rel_volume >= 1.0) & (flow <= 0.0)

    return {
        ("setup_trend", "LONG"): (h1 > 0) & (h4 > 0) & (body >= 0.45) & (close_loc >= 0.68) & (rel_volume >= 0.9) & (flow >= 0.0),
        ("setup_trend", "SHORT"): (h1 < 0) & (h4 < 0) & (body >= 0.45) & (close_loc <= 0.32) & (rel_volume >= 0.9) & (flow <= 0.0),
        ("setup_breakout", "LONG"): long_break,
        ("setup_breakout", "SHORT"): short_break,
        ("setup_sweep", "LONG"): (low < prior_low) & (close_loc >= 0.75) & (flow >= 0.0),
        ("setup_sweep", "SHORT"): (high > prior_high) & (close_loc <= 0.25) & (flow <= 0.0),
        ("setup_compression", "LONG"): long_break & (vol_regime <= 0.85),
        ("setup_compression", "SHORT"): short_break & (vol_regime <= 0.85),
        ("setup_exhaustion", "LONG"): (z <= -2.0) & (close_loc >= 0.75) & (flow >= 0.0),
        ("setup_exhaustion", "SHORT"): (z >= 2.0) & (close_loc <= 0.25) & (flow <= 0.0),
    }


def build_setup_candidates(features: pd.DataFrame, *, roundtrip_cost_bps: float = 12.0):
    f = features.reset_index(drop=True)
    atr = _num(f, "atr14").to_numpy(float)
    close = _num(f, "close").to_numpy(float)
    out = []
    masks = _event_masks(f)
    for (family, side), mask in masks.items():
        indices = np.flatnonzero(mask.fillna(False).to_numpy(bool))
        for i in indices:
            entry = float(close[i])
            atr_i = float(atr[i])
            if not np.isfinite(entry) or entry <= 0 or not np.isfinite(atr_i) or atr_i <= 0:
                continue
            for risk_atr in RISK_ATR_GRID:
                risk = float(risk_atr) * atr_i
                cost_r = (entry * float(roundtrip_cost_bps) / 10_000.0) / risk
                if not np.isfinite(cost_r) or cost_r > MAX_COST_R:
                    continue
                stop = entry - risk if side == "LONG" else entry + risk
                for hold_bars in HOLD_GRID:
                    out.append(
                        OrderCandidate(
                            signal_index=int(i),
                            side=side,
                            entry=entry,
                            stop=stop,
                            max_fill_bars=1,
                            max_hold_bars=int(hold_bars),
                            quality=0.0,
                            family=family,
                        )
                    )
    out.sort(key=lambda c: (c.signal_index, c.family, c.side, c.stop, c.max_hold_bars))
    return out


def candidate_feature_matrix(features: pd.DataFrame, candidates) -> np.ndarray:
    candidates = list(candidates)
    if not candidates:
        return np.empty((0, 20 + len(SETUP_FAMILIES) + 3), dtype=float)
    f = features.reset_index(drop=True)
    long_x = directional_feature_matrix(f, "LONG")
    short_x = directional_feature_matrix(f, "SHORT")
    atr = _num(f, "atr14").to_numpy(float)
    family_index = {name: i for i, name in enumerate(SETUP_FAMILIES)}
    rows = []
    for c in candidates:
        i = int(c.signal_index)
        base = long_x[i] if c.side == "LONG" else short_x[i]
        onehot = np.zeros(len(SETUP_FAMILIES), dtype=float)
        if c.family in family_index:
            onehot[family_index[c.family]] = 1.0
        side_flag = 1.0 if c.side == "LONG" else -1.0
        atr_i = float(atr[i]) if 0 <= i < len(atr) else np.nan
        risk_atr = abs(float(c.entry) - float(c.stop)) / atr_i if np.isfinite(atr_i) and atr_i > 0 else 0.0
        hold_norm = float(c.max_hold_bars) / 144.0
        rows.append(np.concatenate([base, onehot, [side_flag, risk_atr, hold_norm]]))
    return np.clip(np.nan_to_num(np.vstack(rows), nan=0.0, posinf=5.0, neginf=-5.0), -5.0, 5.0)


def label_setup_candidates(
    features: pd.DataFrame,
    candidates,
    *,
    roundtrip_cost_bps: float = 12.0,
):
    """Label each setup independently inside the supplied causal segment."""
    f = features.reset_index(drop=True)
    candidates = list(candidates)
    kept = []
    rows = []
    for candidate in candidates:
        result = simulate_trade(
            candidate,
            f,
            rr=(1.0, 2.0),
            roundtrip_cost_bps=float(roundtrip_cost_bps),
        )
        if result is None:
            continue
        kept.append(candidate)
        rows.append(
            {
                "signal_index": int(result.signal_index),
                "fill_index": int(result.fill_index),
                "exit_index": int(result.exit_index),
                "rr1_hit": bool(result.rr1_hit),
                "rr2_hit": bool(result.rr2_hit),
                "gross_r": float(result.gross_r),
                "net_r": float(result.net_r),
                "exit_reason": result.exit_reason,
            }
        )
    x = candidate_feature_matrix(f, kept)
    labels = pd.DataFrame(rows)
    return x, labels, kept


def _fold_dataset(segment: pd.DataFrame, config):
    local = segment.reset_index(drop=True)
    candidates = build_setup_candidates(local, roundtrip_cost_bps=_cost_bps(config))
    return label_setup_candidates(local, candidates, roundtrip_cost_bps=_cost_bps(config))


def _fit_setup_profile(dev: pd.DataFrame, config):
    folds = [dev.iloc[a:b].copy() for a, b in chronological_folds(len(dev), 5)]
    fold_sets = [_fold_dataset(fold, config) for fold in folds]
    best = None
    rejected = []

    for model_cfg in MODEL_GRID:
        oof_parts = []
        for j in range(1, len(fold_sets)):
            train_x = [fold_sets[i][0] for i in range(j) if len(fold_sets[i][0])]
            train_rows = [fold_sets[i][1] for i in range(j) if len(fold_sets[i][1])]
            test_x, test_rows, _ = fold_sets[j]
            if not train_x or len(test_x) == 0:
                continue
            x_train = np.vstack(train_x)
            rows_train = pd.concat(train_rows, ignore_index=True)
            y_train = rows_train["rr2_hit"].astype(int).to_numpy()
            if len(y_train) < 120 or len(np.unique(y_train)) < 2:
                continue
            model = fit_nonlinear(x_train, y_train, **model_cfg)
            probs = predict_nonlinear_proba(model, test_x)
            part = test_rows.copy()
            part["prob"] = probs
            oof_parts.append(part)

        if not oof_parts:
            continue
        oof = pd.concat(oof_parts, ignore_index=True)
        min_trades = min(240, max(80, int(len(oof) * 0.10)))
        choice = select_oof_threshold(
            oof,
            thresholds=_threshold_grid(oof["prob"].to_numpy(float)),
            min_trades=min_trades,
        )
        row = {"model_config": dict(model_cfg), "oof": choice, "oof_total": int(len(oof))}
        rejected.append(row)
        if choice["threshold"] is None:
            continue
        key = (choice["score"], choice["rr2_wr"], choice["completed_trades"])
        if best is None or key > best[0]:
            best = (key, row)

    if best is None:
        return None, rejected

    all_x, all_rows, _ = _fold_dataset(dev, config)
    if len(all_x) < 120 or len(all_rows) != len(all_x):
        return None, rejected
    y_all = all_rows["rr2_hit"].astype(int).to_numpy()
    if len(np.unique(y_all)) < 2:
        return None, rejected

    selected = best[1]
    final_cfg = dict(selected["model_config"])
    final_cfg["n_estimators"] = max(240, int(final_cfg["n_estimators"]))
    model = fit_nonlinear(all_x, y_all, **final_cfg)
    spec = {
        "family": "setup_meta_g6_forest",
        "setup_families": list(SETUP_FAMILIES),
        "threshold": float(selected["oof"]["threshold"]),
        "oof_completed_trades": int(selected["oof"]["completed_trades"]),
        "oof_rr2_wr": float(selected["oof"]["rr2_wr"]),
        "oof_expectancy_r": float(selected["oof"]["expectancy_r"]),
        "model_config": final_cfg,
        "feature_importances": [float(x) for x in getattr(model, "feature_importances_", np.zeros(all_x.shape[1]))],
    }
    return _RuntimeProfile(spec=spec, model=model), rejected


def _selected_candidates(segment: pd.DataFrame, runtime: _RuntimeProfile, config):
    local = segment.reset_index(drop=True)
    candidates = build_setup_candidates(local, roundtrip_cost_bps=_cost_bps(config))
    if not candidates:
        return []
    x = candidate_feature_matrix(local, candidates)
    probs = predict_nonlinear_proba(runtime.model, x)
    threshold = float(runtime.spec["threshold"])
    selected = [
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
        for c, p in zip(candidates, probs)
        if float(p) >= threshold
    ]

    by_signal = {}
    for c in selected:
        key = int(c.signal_index)
        prev = by_signal.get(key)
        rank = (float(c.quality), c.family, c.side, -abs(c.entry - c.stop), -c.max_hold_bars)
        prev_rank = None if prev is None else (
            float(prev.quality), prev.family, prev.side, -abs(prev.entry - prev.stop), -prev.max_hold_bars
        )
        if prev is None or rank > prev_rank:
            by_signal[key] = c
    return sorted(by_signal.values(), key=lambda c: c.signal_index)


def _evaluate(segment: pd.DataFrame, runtime: _RuntimeProfile, config):
    candidates = _selected_candidates(segment, runtime, config)
    trades = _simulate_fast(candidates, segment.reset_index(drop=True), config)
    return summarize_outcomes(trades), trades


def _lock(runtime: _RuntimeProfile):
    params = dict(runtime.spec)
    raw = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return G6LockedProfile(params=params, profile_hash=hashlib.sha256(raw.encode()).hexdigest())


def search_coin_g6(symbol: str, features: pd.DataFrame, config) -> CoinResearchResult:
    n = len(features)
    a = int(n * config.development_fraction)
    b = int(n * (config.development_fraction + config.validation_fraction))
    dev = features.iloc[:a].copy()
    val = features.iloc[a:b].copy()
    hold = features.iloc[b:].copy()

    runtime, search_rows = _fit_setup_profile(dev, config)
    rejected = []
    for row in search_rows:
        choice = row["oof"]
        rejected.append(
            {
                "family": "setup_meta_g6_forest",
                "params": dict(row["model_config"]),
                "metrics": {
                    "completed_trades": int(choice["completed_trades"]),
                    "rr2_wr": float(choice["rr2_wr"]),
                    "expectancy_r": float(choice["expectancy_r"]),
                },
                "score": float(choice["score"]),
            }
        )

    if runtime is None:
        zero = summarize_outcomes([])
        return CoinResearchResult(
            symbol,
            "FAIL",
            None,
            zero,
            zero,
            zero,
            zero,
            ["g6-no-stable-setup-profile"],
            sorted(rejected, key=lambda r: r["score"], reverse=True)[:8],
            [],
        )

    dev_metrics, _ = _evaluate(dev, runtime, config)
    val_metrics, val_trades = _evaluate(val, runtime, config)
    hold_metrics, hold_trades = _evaluate(hold, runtime, config)
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
    if runtime.spec["oof_rr2_wr"] >= 0.70 and eval_metrics.rr2_wr + 0.15 < runtime.spec["oof_rr2_wr"]:
        bottlenecks.append("g6-setup-generalization-gap")

    return CoinResearchResult(
        symbol,
        "PASS" if passed else "FAIL",
        _lock(runtime),
        dev_metrics,
        val_metrics,
        hold_metrics,
        eval_metrics,
        list(dict.fromkeys(bottlenecks)),
        sorted(rejected, key=lambda r: r["score"], reverse=True)[:8],
        evaluation_trades,
    )
