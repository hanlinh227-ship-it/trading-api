from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from engine.execution import OrderCandidate
from engine.metrics import summarize_outcomes
from optimize.nonlinear_model import fit_nonlinear, predict_nonlinear_proba
from optimize.router_g7 import build_routed_candidates, geometry_key
from optimize.search import (
    CoinResearchResult,
    _cost_bps,
    _simulate_fast,
    diagnose_bottleneck,
    passes_g2_gate,
)
from optimize.search_g4 import _threshold_grid
from optimize.search_g6 import candidate_feature_matrix, label_setup_candidates
from optimize.stability import chronological_folds
from optimize.stability_g7 import select_stable_threshold


MODEL_GRID = (
    {"n_estimators": 120, "max_depth": 4, "min_samples_leaf": 18, "max_features": 0.7, "random_state": 71},
    {"n_estimators": 120, "max_depth": 6, "min_samples_leaf": 32, "max_features": 0.7, "random_state": 71},
)
MIN_ROUTE_TRAIN_LABELS = 80
MIN_GEOMETRY_LABELS = 20
MIN_THRESHOLD_TRADES = 40
MIN_THRESHOLD_FOLD_TRADES = 10


@dataclass(frozen=True)
class G7LockedProfile:
    params: dict
    profile_hash: str


@dataclass
class _RuntimeRoute:
    route: tuple[str, str, str]
    spec: dict
    model: object


def _route_sort_key(route):
    return tuple(str(x) for x in route)


def lock_g7_profile(route_specs) -> G7LockedProfile:
    routes = [dict(spec) for spec in route_specs]
    routes.sort(key=lambda s: (str(s.get("regime", "")), str(s.get("family", "")), str(s.get("side", ""))))
    params = {
        "family": "regime_router_g7_forest",
        "research_only": True,
        "routes": routes,
    }
    raw = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return G7LockedProfile(params=params, profile_hash=hashlib.sha256(raw.encode()).hexdigest())


def filter_locked_geometry(candidates, features: pd.DataFrame, *, risk_atr: float, hold_bars: int):
    kept = []
    target_risk = round(float(risk_atr), 6)
    target_hold = int(hold_bars)
    for candidate in candidates:
        geom = geometry_key(candidate, features)
        if np.isfinite(geom[0]) and geom == (target_risk, target_hold):
            kept.append(candidate)
    return kept


def dedupe_scored_candidates(candidates):
    by_signal = {}
    for candidate in candidates:
        i = int(candidate.signal_index)
        previous = by_signal.get(i)
        rank = (
            float(candidate.quality),
            str(candidate.family),
            str(candidate.side),
            -abs(float(candidate.entry) - float(candidate.stop)),
            -int(candidate.max_hold_bars),
        )
        if previous is None:
            by_signal[i] = candidate
            continue
        previous_rank = (
            float(previous.quality),
            str(previous.family),
            str(previous.side),
            -abs(float(previous.entry) - float(previous.stop)),
            -int(previous.max_hold_bars),
        )
        if rank > previous_rank:
            by_signal[i] = candidate
    return [by_signal[i] for i in sorted(by_signal)]


def _empty_metrics():
    return summarize_outcomes([])


def _fold_route_dataset(segment: pd.DataFrame, config):
    local = segment.reset_index(drop=True)
    routed = build_routed_candidates(local, roundtrip_cost_bps=_cost_bps(config))
    result = {}
    for route, candidates in routed.items():
        geometry_groups = {}
        for candidate in candidates:
            geom = geometry_key(candidate, local)
            if not np.isfinite(geom[0]):
                continue
            geometry_groups.setdefault(geom, []).append(candidate)

        route_sets = {}
        for geom, group in geometry_groups.items():
            x, rows, kept = label_setup_candidates(
                local,
                group,
                roundtrip_cost_bps=_cost_bps(config),
            )
            if len(x) == 0 or len(rows) == 0:
                continue
            route_sets[geom] = {"x": x, "rows": rows.reset_index(drop=True), "candidates": kept}
        if route_sets:
            result[route] = route_sets
    return result


def _build_dev_fold_sets(dev: pd.DataFrame, config):
    folds = []
    for start, end in chronological_folds(len(dev), 5):
        folds.append(_fold_route_dataset(dev.iloc[start:end].copy(), config))
    return folds


def _geometry_evidence(fold_sets, route, geom, *, upto=None):
    end = len(fold_sets) if upto is None else int(upto)
    parts = []
    for fold_id in range(end):
        data = fold_sets[fold_id].get(route, {}).get(geom)
        if data is None or len(data["rows"]) == 0:
            continue
        part = data["rows"].copy()
        part["fold"] = fold_id
        part["prob"] = 1.0
        parts.append(part)
    if not parts:
        return None
    rows = pd.concat(parts, ignore_index=True)
    return select_stable_threshold(
        rows,
        thresholds=(0.0,),
        min_trades=MIN_GEOMETRY_LABELS,
        min_fold_trades=5,
        target_wr=0.80,
    )


def _select_geometry(fold_sets, route, *, upto=None):
    geometries = set()
    end = len(fold_sets) if upto is None else int(upto)
    for fold_id in range(end):
        geometries.update(fold_sets[fold_id].get(route, {}).keys())

    best = None
    for geom in sorted(geometries):
        choice = _geometry_evidence(fold_sets, route, geom, upto=upto)
        if choice is None or choice.get("threshold") is None:
            continue
        key = (
            float(choice.get("min_fold_wr", 0.0)),
            float(choice.get("wilson_lower", 0.0)),
            float(choice.get("expectancy_r", 0.0)),
            int(choice.get("completed_trades", 0)),
            -float(geom[0]),
            -int(geom[1]),
        )
        if best is None or key > best[0]:
            best = (key, geom, choice)
    return (None, None) if best is None else (best[1], best[2])


def _stack_training(fold_sets, route, geom, *, upto):
    xs = []
    rows = []
    for fold_id in range(int(upto)):
        data = fold_sets[fold_id].get(route, {}).get(geom)
        if data is None or len(data["x"]) == 0:
            continue
        xs.append(data["x"])
        rows.append(data["rows"])
    if not xs:
        return np.empty((0, 28), dtype=float), pd.DataFrame()
    return np.vstack(xs), pd.concat(rows, ignore_index=True)


def _fit_route_profile(dev: pd.DataFrame, route, config, *, fold_sets=None):
    route = tuple(route)
    fold_sets = _build_dev_fold_sets(dev, config) if fold_sets is None else fold_sets
    best = None
    diagnostics = []

    for model_cfg in MODEL_GRID:
        oof_parts = []
        geometry_history = []
        for fold_id in range(1, len(fold_sets)):
            geom, geometry_choice = _select_geometry(fold_sets, route, upto=fold_id)
            if geom is None:
                continue
            train_x, train_rows = _stack_training(fold_sets, route, geom, upto=fold_id)
            test_data = fold_sets[fold_id].get(route, {}).get(geom)
            if test_data is None or len(test_data["x"]) == 0:
                continue
            if len(train_rows) < MIN_ROUTE_TRAIN_LABELS:
                continue
            y_train = train_rows["rr2_hit"].astype(int).to_numpy()
            if len(np.unique(y_train)) < 2:
                continue

            model = fit_nonlinear(train_x, y_train, **model_cfg)
            probs = predict_nonlinear_proba(model, test_data["x"])
            part = test_data["rows"].copy()
            part["fold"] = int(fold_id)
            part["prob"] = probs
            oof_parts.append(part)
            geometry_history.append(
                {
                    "fold": int(fold_id),
                    "risk_atr": float(geom[0]),
                    "hold_bars": int(geom[1]),
                    "prior_geometry_wr": float((geometry_choice or {}).get("rr2_wr", 0.0)),
                }
            )

        if not oof_parts:
            continue
        oof = pd.concat(oof_parts, ignore_index=True)
        thresholds = _threshold_grid(oof["prob"].to_numpy(float))
        choice = select_stable_threshold(
            oof,
            thresholds=thresholds,
            min_trades=MIN_THRESHOLD_TRADES,
            min_fold_trades=MIN_THRESHOLD_FOLD_TRADES,
            target_wr=config.target_wr,
        )
        row = {
            "route": route,
            "model_config": dict(model_cfg),
            "oof": choice,
            "oof_total": int(len(oof)),
            "geometry_history": geometry_history,
        }
        diagnostics.append(row)
        if choice.get("threshold") is None:
            continue
        key = (
            bool(choice.get("qualified", False)),
            float(choice.get("min_fold_wr", 0.0)),
            float(choice.get("wilson_lower", 0.0)),
            float(choice.get("expectancy_r", 0.0)),
            int(choice.get("completed_trades", 0)),
            float(choice.get("rr2_wr", 0.0)),
        )
        if best is None or key > best[0]:
            best = (key, row)

    if best is None:
        return None, diagnostics

    final_geom, final_geometry_choice = _select_geometry(fold_sets, route)
    if final_geom is None:
        return None, diagnostics
    all_x, all_rows = _stack_training(fold_sets, route, final_geom, upto=len(fold_sets))
    if len(all_rows) < MIN_ROUTE_TRAIN_LABELS:
        return None, diagnostics
    y_all = all_rows["rr2_hit"].astype(int).to_numpy()
    if len(np.unique(y_all)) < 2:
        return None, diagnostics

    selected = best[1]
    final_cfg = dict(selected["model_config"])
    final_cfg["n_estimators"] = max(240, int(final_cfg["n_estimators"]))
    final_model = fit_nonlinear(all_x, y_all, **final_cfg)
    choice = selected["oof"]
    spec = {
        "regime": str(route[0]),
        "family": str(route[1]),
        "side": str(route[2]),
        "risk_atr": float(final_geom[0]),
        "hold_bars": int(final_geom[1]),
        "threshold": float(choice["threshold"]),
        "qualified": bool(choice.get("qualified", False)),
        "oof_completed_trades": int(choice.get("completed_trades", 0)),
        "oof_rr2_wr": float(choice.get("rr2_wr", 0.0)),
        "oof_expectancy_r": float(choice.get("expectancy_r", 0.0)),
        "oof_min_fold_wr": float(choice.get("min_fold_wr", 0.0)),
        "oof_wilson_lower": float(choice.get("wilson_lower", 0.0)),
        "geometry_dev_rr2_wr": float((final_geometry_choice or {}).get("rr2_wr", 0.0)),
        "geometry_dev_expectancy_r": float((final_geometry_choice or {}).get("expectancy_r", 0.0)),
        "model_config": final_cfg,
        "feature_importances": [
            float(x) for x in getattr(final_model, "feature_importances_", np.zeros(all_x.shape[1]))
        ],
    }
    return _RuntimeRoute(route=route, spec=spec, model=final_model), diagnostics


def _score_segment(segment: pd.DataFrame, runtimes, config, *, qualified_only=True):
    local = segment.reset_index(drop=True)
    routed = build_routed_candidates(local, roundtrip_cost_bps=_cost_bps(config))
    scored = []
    for runtime in runtimes:
        if qualified_only and not bool(runtime.spec.get("qualified", False)):
            continue
        candidates = routed.get(runtime.route, [])
        candidates = filter_locked_geometry(
            candidates,
            local,
            risk_atr=runtime.spec["risk_atr"],
            hold_bars=runtime.spec["hold_bars"],
        )
        if not candidates:
            continue
        x = candidate_feature_matrix(local, candidates)
        probs = predict_nonlinear_proba(runtime.model, x)
        threshold = float(runtime.spec["threshold"])
        for candidate, probability in zip(candidates, probs):
            if float(probability) < threshold:
                continue
            scored.append(
                OrderCandidate(
                    int(candidate.signal_index),
                    str(candidate.side),
                    float(candidate.entry),
                    float(candidate.stop),
                    int(candidate.max_fill_bars),
                    int(candidate.max_hold_bars),
                    float(probability),
                    str(candidate.family),
                )
            )
    return dedupe_scored_candidates(scored)


def _evaluate_segment(segment: pd.DataFrame, runtimes, config):
    candidates = _score_segment(segment, runtimes, config, qualified_only=True)
    trades = _simulate_fast(candidates, segment.reset_index(drop=True), config)
    return summarize_outcomes(trades), trades


def _diagnostic_rows(route_diagnostics):
    rows = []
    for route, diagnostics in route_diagnostics.items():
        for item in diagnostics:
            choice = item.get("oof", {})
            rows.append(
                {
                    "family": "regime_router_g7_forest",
                    "params": {
                        "regime": route[0],
                        "setup_family": route[1],
                        "side": route[2],
                        **dict(item.get("model_config", {})),
                    },
                    "metrics": {
                        "completed_trades": int(choice.get("completed_trades", 0)),
                        "rr2_wr": float(choice.get("rr2_wr", 0.0)),
                        "expectancy_r": float(choice.get("expectancy_r", 0.0)),
                        "min_fold_wr": float(choice.get("min_fold_wr", 0.0)),
                        "wilson_lower": float(choice.get("wilson_lower", 0.0)),
                        "qualified": bool(choice.get("qualified", False)),
                    },
                    "score": float(choice.get("min_fold_wr", 0.0)),
                }
            )
    rows.sort(
        key=lambda r: (
            bool(r["metrics"].get("qualified", False)),
            r["metrics"].get("min_fold_wr", 0.0),
            r["metrics"].get("wilson_lower", 0.0),
            r["metrics"].get("expectancy_r", 0.0),
        ),
        reverse=True,
    )
    return rows


def search_coin_g7(symbol: str, features: pd.DataFrame, config) -> CoinResearchResult:
    n = len(features)
    a = int(n * config.development_fraction)
    b = int(n * (config.development_fraction + config.validation_fraction))
    dev = features.iloc[:a].copy()
    val = features.iloc[a:b].copy()
    hold = features.iloc[b:].copy()

    fold_sets = _build_dev_fold_sets(dev, config)
    routes = sorted(
        {route for fold in fold_sets for route in fold.keys()},
        key=_route_sort_key,
    )

    runtimes = []
    route_diagnostics = {}
    for route in routes:
        runtime, diagnostics = _fit_route_profile(dev, route, config, fold_sets=fold_sets)
        route_diagnostics[route] = diagnostics
        if runtime is not None:
            runtimes.append(runtime)

    rejected = _diagnostic_rows(route_diagnostics)
    locked = lock_g7_profile([runtime.spec for runtime in runtimes]) if runtimes else None
    qualified = [runtime for runtime in runtimes if bool(runtime.spec.get("qualified", False))]

    if not qualified:
        zero = _empty_metrics()
        return CoinResearchResult(
            symbol,
            "FAIL",
            locked,
            zero,
            zero,
            zero,
            zero,
            ["g7-no-target-qualified-route"],
            rejected[:20],
            [],
        )

    dev_metrics, _ = _evaluate_segment(dev, qualified, config)
    val_metrics, val_trades = _evaluate_segment(val, qualified, config)
    hold_metrics, hold_trades = _evaluate_segment(hold, qualified, config)
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
    if eval_metrics.completed_trades < config.min_completed_trades:
        bottlenecks.append("g7-qualified-route-frequency")
    if eval_metrics.rr2_wr < config.target_wr:
        bottlenecks.append("g7-qualified-route-oos-precision")

    return CoinResearchResult(
        symbol,
        "PASS" if passed else "FAIL",
        locked,
        dev_metrics,
        val_metrics,
        hold_metrics,
        eval_metrics,
        list(dict.fromkeys(bottlenecks)),
        rejected[:20],
        evaluation_trades,
    )
