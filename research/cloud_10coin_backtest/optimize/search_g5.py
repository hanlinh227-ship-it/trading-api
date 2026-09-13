from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from engine.execution import OrderCandidate
from engine.metrics import summarize_outcomes
from optimize.meta_model import select_oof_threshold
from optimize.nonlinear_model import fit_nonlinear, predict_nonlinear_proba
from optimize.search import CoinResearchResult, _simulate_fast, diagnose_bottleneck, passes_g2_gate
from optimize.search_g4 import FEATURE_NAMES, _dataset, _threshold_grid, build_base_candidates, directional_feature_matrix
from optimize.stability import chronological_folds


MODEL_GRID = (
    {"n_estimators": 80, "max_depth": 3, "min_samples_leaf": 24, "max_features": 0.7, "random_state": 31},
    {"n_estimators": 80, "max_depth": 5, "min_samples_leaf": 40, "max_features": 0.7, "random_state": 31},
)
GEOMETRY_GRID = tuple((risk_atr, hold_bars) for risk_atr in (0.9, 1.2, 1.5) for hold_bars in (72, 144))


@dataclass(frozen=True)
class G5LockedProfile:
    params: dict
    profile_hash: str


@dataclass
class _RuntimeProfile:
    spec: dict
    model: object


def _model_config_for_final(cfg: dict) -> dict:
    out = dict(cfg)
    out["n_estimators"] = max(160, int(out["n_estimators"]))
    return out


def _fit_side_profile(dev: pd.DataFrame, side: str, config):
    folds = [dev.iloc[a:b].copy() for a, b in chronological_folds(len(dev), 5)]
    dataset_cache = {}
    for risk_atr, hold_bars in GEOMETRY_GRID:
        dataset_cache[(risk_atr, hold_bars)] = [_dataset(f, side, risk_atr, hold_bars, config) for f in folds]

    best = None
    rejected = []
    for risk_atr, hold_bars in GEOMETRY_GRID:
        fold_sets = dataset_cache[(risk_atr, hold_bars)]
        for model_cfg in MODEL_GRID:
            oof_parts = []
            for j in range(1, len(fold_sets)):
                train_x = [fold_sets[i][0] for i in range(j) if len(fold_sets[i][0])]
                train_rows = [fold_sets[i][1] for i in range(j) if len(fold_sets[i][1])]
                test_x, test_rows = fold_sets[j]
                if not train_x or len(test_x) == 0:
                    continue
                x_train = np.vstack(train_x)
                rows_train = pd.concat(train_rows, ignore_index=True)
                y_train = rows_train["rr2_hit"].astype(int).to_numpy()
                if len(y_train) < 120 or len(np.unique(y_train)) < 2:
                    continue
                model = fit_nonlinear(x_train, y_train, **model_cfg)
                p = predict_nonlinear_proba(model, test_x)
                part = test_rows.copy()
                part["prob"] = p
                oof_parts.append(part)
            if not oof_parts:
                continue
            oof = pd.concat(oof_parts, ignore_index=True)
            # Demand meaningful breadth in DEV OOF so a high-WR tiny tail cannot win.
            min_trades = min(240, max(80, int(len(oof) * 0.12)))
            choice = select_oof_threshold(
                oof,
                thresholds=_threshold_grid(oof["prob"].to_numpy(float)),
                min_trades=min_trades,
            )
            if choice["threshold"] is None:
                continue
            row = {
                "side": side,
                "risk_atr": float(risk_atr),
                "hold_bars": int(hold_bars),
                "model_config": dict(model_cfg),
                "oof": choice,
                "oof_total": int(len(oof)),
            }
            rejected.append(row)
            # Precision is primary, but zero/negative expectancy and tiny tails are penalized by selector score.
            key = (choice["score"], choice["rr2_wr"], choice["completed_trades"])
            if best is None or key > best[0]:
                best = (key, row, fold_sets)

    if best is None:
        return None, rejected

    _, selected, fold_sets = best
    train_x = [x for x, _ in fold_sets if len(x)]
    train_rows = [r for _, r in fold_sets if len(r)]
    x_all = np.vstack(train_x)
    rows_all = pd.concat(train_rows, ignore_index=True)
    y_all = rows_all["rr2_hit"].astype(int).to_numpy()
    final_cfg = _model_config_for_final(selected["model_config"])
    final_model = fit_nonlinear(x_all, y_all, **final_cfg)
    spec = {
        "side": side,
        "risk_atr": selected["risk_atr"],
        "hold_bars": selected["hold_bars"],
        "threshold": float(selected["oof"]["threshold"]),
        "oof_completed_trades": int(selected["oof"]["completed_trades"]),
        "oof_rr2_wr": float(selected["oof"]["rr2_wr"]),
        "oof_expectancy_r": float(selected["oof"]["expectancy_r"]),
        "model_config": final_cfg,
        "feature_importances": [float(x) for x in getattr(final_model, "feature_importances_", np.zeros(len(FEATURE_NAMES)))],
    }
    return _RuntimeProfile(spec=spec, model=final_model), sorted(rejected, key=lambda r: r["oof"]["score"], reverse=True)[:8]


def _selected_candidates(segment: pd.DataFrame, runtime: _RuntimeProfile, config):
    local = segment.reset_index(drop=True)
    spec = runtime.spec
    base = build_base_candidates(
        local,
        spec["side"],
        risk_atr=spec["risk_atr"],
        hold_bars=spec["hold_bars"],
        stride=6,
        roundtrip_cost_bps=float(config.maker_fee_bps + config.taker_fee_bps + config.slippage_bps),
    )
    if not base:
        return []
    matrix = directional_feature_matrix(local, spec["side"])
    idx = np.array([c.signal_index for c in base], dtype=int)
    probs = predict_nonlinear_proba(runtime.model, matrix[idx])
    return [
        OrderCandidate(c.signal_index, c.side, c.entry, c.stop, c.max_fill_bars, c.max_hold_bars, float(p), "meta_g5_forest")
        for c, p in zip(base, probs)
        if float(p) >= float(spec["threshold"])
    ]


def _evaluate(segment: pd.DataFrame, runtimes, config):
    pool = []
    for runtime in runtimes:
        pool.extend(_selected_candidates(segment, runtime, config))
    by_index = {}
    for c in pool:
        prev = by_index.get(c.signal_index)
        if prev is None or c.quality > prev.quality:
            by_index[c.signal_index] = c
    candidates = sorted(by_index.values(), key=lambda c: c.signal_index)
    trades = _simulate_fast(candidates, segment.reset_index(drop=True), config)
    return summarize_outcomes(trades), trades


def _lock(runtimes):
    params = {
        "family": "meta_g5_forest",
        "feature_names": list(FEATURE_NAMES),
        "sides": [r.spec for r in runtimes],
    }
    raw = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return G5LockedProfile(params=params, profile_hash=hashlib.sha256(raw.encode()).hexdigest())


def search_coin_g5(symbol: str, features: pd.DataFrame, config) -> CoinResearchResult:
    n = len(features)
    a = int(n * config.development_fraction)
    b = int(n * (config.development_fraction + config.validation_fraction))
    dev, val, hold = features.iloc[:a].copy(), features.iloc[a:b].copy(), features.iloc[b:].copy()

    runtimes = []
    rejected = []
    for side in ("LONG", "SHORT"):
        runtime, rows = _fit_side_profile(dev, side, config)
        if runtime is not None:
            runtimes.append(runtime)
        for row in rows:
            rejected.append({
                "family": "meta_g5_forest",
                "params": {
                    "side": row["side"], "risk_atr": row["risk_atr"], "hold_bars": row["hold_bars"],
                    **row["model_config"],
                },
                "metrics": {
                    "completed_trades": row["oof"]["completed_trades"],
                    "rr2_wr": row["oof"]["rr2_wr"],
                    "expectancy_r": row["oof"]["expectancy_r"],
                },
                "score": row["oof"]["score"],
            })

    if not runtimes:
        zero = summarize_outcomes([])
        return CoinResearchResult(symbol, "FAIL", None, zero, zero, zero, zero, ["nonlinear-no-stable-profile"], rejected[:8], [])

    dev_metrics, _ = _evaluate(dev, runtimes, config)
    val_metrics, val_trades = _evaluate(val, runtimes, config)
    hold_metrics, hold_trades = _evaluate(hold, runtimes, config)
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
    best_oof = max((r.spec["oof_rr2_wr"] for r in runtimes), default=0.0)
    if best_oof >= 0.70 and eval_metrics.rr2_wr + 0.15 < best_oof:
        bottlenecks.append("nonlinear-generalization-gap")

    return CoinResearchResult(
        symbol,
        "PASS" if passed else "FAIL",
        _lock(runtimes),
        dev_metrics,
        val_metrics,
        hold_metrics,
        eval_metrics,
        list(dict.fromkeys(bottlenecks)),
        sorted(rejected, key=lambda r: r["score"], reverse=True)[:8],
        evaluation_trades,
    )
