from __future__ import annotations

import importlib
from itertools import combinations

from engine.metrics import summarize_outcomes
from optimize.ensemble import lock_ensemble, merge_candidates
from optimize.search import (
    CoinResearchResult,
    G2_FAMILIES,
    _evaluate_g2,
    _evaluate_member_rows_g2,
    _g2_candidates,
    _simulate_fast,
    diagnose_bottleneck,
    passes_g2_gate,
)
from optimize.stability import chronological_folds, rank_stable_candidates, stability_score


def _fold_segments(dev, k: int = 5):
    return [dev.iloc[a:b].copy() for a, b in chronological_folds(len(dev), k)]


def _ensemble_stability(rows, folds, config):
    fold_metrics = []
    for fold in folds:
        local = fold.reset_index(drop=True)
        sets = []
        for row in rows:
            module = importlib.import_module(f"strategies.{row['family']}")
            sets.append(_g2_candidates(module, row["params"], local, config))
        merged = merge_candidates(sets)
        trades = _simulate_fast(merged, local, config)
        fold_metrics.append(summarize_outcomes(trades))
    return fold_metrics, stability_score(fold_metrics)


def search_coin_g3(symbol, features, config) -> CoinResearchResult:
    """G3: select profiles only from chronological DEV-fold stability, then freeze."""
    n = len(features)
    a = int(n * config.development_fraction)
    b = int(n * (config.development_fraction + config.validation_fraction))
    dev = features.iloc[:a].copy()
    val = features.iloc[a:b].copy()
    hold = features.iloc[b:].copy()
    folds = _fold_segments(dev, 5)

    frontier = []
    for module_name in G2_FAMILIES:
        module = importlib.import_module(module_name)
        family_rows = []
        for params in module.parameter_grid():
            fold_metrics = []
            for fold in folds:
                metrics, _ = _evaluate_g2(module, params, fold, config)
                fold_metrics.append(metrics)
            total_trades = sum(m.completed_trades for m in fold_metrics)
            if total_trades < 20:
                continue
            dev_metrics, _ = _evaluate_g2(module, params, dev, config)
            family_rows.append(
                {
                    "family": module.family_name,
                    "params": params,
                    "fold_metrics": fold_metrics,
                    "development": dev_metrics,
                }
            )
        family_rows = rank_stable_candidates(family_rows)
        frontier.extend(family_rows[:3])

    if not frontier:
        zero = summarize_outcomes([])
        return CoinResearchResult(
            symbol,
            "FAIL",
            None,
            zero,
            zero,
            zero,
            zero,
            ["insufficient-frequency"],
            [],
            [],
        )

    # Cross-family competition remains DEV-only. Limit the frontier to keep the
    # ensemble search tractable and deterministic without touching OOS data.
    frontier = rank_stable_candidates(frontier)[:8]
    best_rows = None
    best_score = float("-inf")
    for k in range(1, min(3, len(frontier)) + 1):
        for combo in combinations(frontier, k):
            fold_metrics, score = _ensemble_stability(combo, folds, config)
            score -= 0.01 * (k - 1)
            if score > best_score:
                best_score = score
                best_rows = list(combo)

    if not best_rows:
        zero = summarize_outcomes([])
        return CoinResearchResult(
            symbol,
            "FAIL",
            None,
            zero,
            zero,
            zero,
            zero,
            ["insufficient-frequency"],
            [],
            [],
        )

    locked = lock_ensemble(
        [{"family": row["family"], "params": row["params"]} for row in best_rows]
    )

    # Freeze first. Only after the lock do validation/holdout get evaluated.
    dev_metrics, _ = _evaluate_member_rows_g2(locked.members, dev, config)
    val_metrics, val_trades = _evaluate_member_rows_g2(locked.members, val, config)
    hold_metrics, hold_trades = _evaluate_member_rows_g2(locked.members, hold, config)
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

    selected = {(row["family"], repr(sorted(row["params"].items()))) for row in best_rows}
    rejected = []
    for row in frontier:
        key = (row["family"], repr(sorted(row["params"].items())))
        if key in selected:
            continue
        rejected.append(
            {
                "family": row["family"],
                "params": row["params"],
                "stability_score": row["stability_score"],
                "development": row["development"].to_dict(),
                "fold_metrics": [m.to_dict() for m in row["fold_metrics"]],
            }
        )

    bottlenecks = diagnose_bottleneck(dev_metrics, eval_metrics)
    if dev_metrics.completed_trades >= 100 and eval_metrics.completed_trades < 100:
        if "regime-instability" not in bottlenecks:
            bottlenecks.append("regime-instability")

    return CoinResearchResult(
        symbol,
        "PASS" if passed else "FAIL",
        locked,
        dev_metrics,
        val_metrics,
        hold_metrics,
        eval_metrics,
        bottlenecks,
        rejected[:8],
        evaluation_trades,
    )
