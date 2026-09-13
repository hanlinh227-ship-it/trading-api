from __future__ import annotations

import importlib
from dataclasses import dataclass, replace
from itertools import combinations

import numpy as np
import pandas as pd

from config import BacktestConfig
from engine.metrics import Metrics, summarize_outcomes
from optimize.ensemble import LockedEnsemble, lock_ensemble, merge_candidates
from optimize.selection import lock_profile
from strategies.common import quality_score

FAMILIES = (
    "strategies.trend_ote",
    "strategies.sweep_mss",
    "strategies.break_retest",
    "strategies.compression",
    "strategies.mean_reversion",
)

G2_FAMILIES = (
    "strategies.sweep_mss_ote_g2",
    "strategies.trend_ote",
    "strategies.compression",
    "strategies.break_retest",
    "strategies.mean_reversion",
)

G2_MIN_RISK_ATR = 0.20
G2_MAX_COST_R = 0.20


@dataclass
class CoinResearchResult:
    symbol: str
    status: str
    locked_profile: object | None
    development: Metrics
    validation: Metrics
    holdout: Metrics
    evaluation: Metrics
    bottlenecks: list[str]
    rejected_candidates: list[dict]
    evaluation_trades: list[dict]

    def to_dict(self) -> dict:
        if self.locked_profile is None:
            locked = None
        elif isinstance(self.locked_profile, LockedEnsemble):
            locked = {
                "ensemble_hash": self.locked_profile.ensemble_hash,
                "members": [
                    {"family": m.family, "params": m.params, "profile_hash": m.profile_hash}
                    for m in self.locked_profile.members
                ],
            }
        else:
            locked = {
                "params": self.locked_profile.params,
                "profile_hash": self.locked_profile.profile_hash,
            }
        return {
            "symbol": self.symbol,
            "status": self.status,
            "locked_profile": locked,
            "development": self.development.to_dict(),
            "validation": self.validation.to_dict(),
            "holdout": self.holdout.to_dict(),
            "evaluation": self.evaluation.to_dict(),
            "bottlenecks": self.bottlenecks,
            "rejected_candidates": self.rejected_candidates,
        }


def passes_hard_gate(completed_trades: int, rr2_wr: float, target_wr: float, min_trades: int) -> bool:
    return completed_trades >= min_trades and rr2_wr >= target_wr


def passes_g2_gate(
    *,
    completed_trades: int,
    rr2_wr: float,
    expectancy_r: float,
    validation_trades: int,
    validation_wr: float,
    holdout_trades: int,
    holdout_wr: float,
    target_wr: float = 0.80,
    min_trades: int = 100,
    segment_floor: float = 0.60,
) -> bool:
    validation_ok = validation_trades < 20 or validation_wr >= segment_floor
    holdout_ok = holdout_trades < 20 or holdout_wr >= segment_floor
    return (
        completed_trades >= min_trades
        and rr2_wr >= target_wr
        and expectancy_r > 0
        and validation_ok
        and holdout_ok
    )


def _cost_bps(config: BacktestConfig) -> float:
    return 2.0 * (config.costs.fee_bps_per_side + config.costs.slippage_bps_per_side)


def apply_g2_candidate_guard(
    candidates,
    features: pd.DataFrame,
    *,
    min_risk_atr: float = G2_MIN_RISK_ATR,
    max_cost_r: float = G2_MAX_COST_R,
    roundtrip_cost_bps: float = 12.0,
):
    """Causal global guard for every G2 family, including legacy families."""
    if not candidates:
        return []
    if "atr14" not in features.columns:
        return []

    atr = pd.to_numeric(features["atr14"], errors="coerce").to_numpy(float)
    kept = []
    for candidate in candidates:
        i = int(candidate.signal_index)
        if i < 0 or i >= len(atr):
            continue
        atr_i = atr[i]
        risk = (
            candidate.entry - candidate.stop
            if candidate.side == "LONG"
            else candidate.stop - candidate.entry
        )
        if (
            not np.isfinite(risk)
            or risk <= 0
            or not np.isfinite(atr_i)
            or atr_i <= 0
        ):
            continue
        if risk / atr_i < min_risk_atr:
            continue
        cost_r = (abs(candidate.entry) * roundtrip_cost_bps / 10_000.0) / risk
        if not np.isfinite(cost_r) or cost_r > max_cost_r:
            continue
        kept.append(candidate)
    return kept


def _simulate_fast(candidates, bars: pd.DataFrame, config: BacktestConfig) -> list[dict]:
    if bars.empty:
        return []
    highs = bars.high.to_numpy(float)
    lows = bars.low.to_numpy(float)
    closes = bars.close.to_numpy(float)
    n = len(bars)
    cost_bps = _cost_bps(config)
    results: list[dict] = []
    last_exit = -1
    for c in candidates:
        if c.signal_index <= last_exit:
            continue
        side = c.side
        risk = c.entry - c.stop if side == "LONG" else c.stop - c.entry
        if risk <= 0 or not np.isfinite(risk):
            continue
        tp1 = c.entry + risk if side == "LONG" else c.entry - risk
        tp2 = c.entry + 2.0 * risk if side == "LONG" else c.entry - 2.0 * risk
        fill = None
        for j in range(c.signal_index + 1, min(n, c.signal_index + c.max_fill_bars + 1)):
            if lows[j] <= c.entry <= highs[j]:
                fill = j
                break
        if fill is None:
            continue
        rr1 = False
        exit_index = min(n - 1, fill + c.max_hold_bars)
        reason = "TIMEOUT"
        gross = (
            (closes[exit_index] - c.entry) / risk
            if side == "LONG"
            else (c.entry - closes[exit_index]) / risk
        )
        rr2 = False
        for j in range(fill, exit_index + 1):
            stop_hit = lows[j] <= c.stop if side == "LONG" else highs[j] >= c.stop
            one_hit = highs[j] >= tp1 if side == "LONG" else lows[j] <= tp1
            two_hit = highs[j] >= tp2 if side == "LONG" else lows[j] <= tp2
            if (j == fill and stop_hit) or (stop_hit and (one_hit or two_hit)):
                reason = "STOP_AMBIGUOUS"
                gross = -1.0
                rr2 = False
                exit_index = j
                break
            if stop_hit:
                reason = "STOP"
                gross = -1.0
                rr2 = False
                exit_index = j
                break
            if one_hit:
                rr1 = True
            if two_hit:
                reason = "TP2"
                gross = 2.0
                rr1 = True
                rr2 = True
                exit_index = j
                break
        cost_r = (c.entry * cost_bps / 10_000.0) / risk
        results.append(
            {
                "signal_index": c.signal_index,
                "fill_index": fill,
                "exit_index": exit_index,
                "side": side,
                "entry": c.entry,
                "stop": c.stop,
                "rr1_hit": rr1,
                "rr2_hit": rr2,
                "exit_reason": reason,
                "gross_r": gross,
                "cost_r": cost_r,
                "net_r": gross - cost_r,
            }
        )
        last_exit = exit_index
    return results


def _with_family_quality(module, params: dict, segment: pd.DataFrame):
    local = segment.reset_index(drop=True)
    candidates = module.generate_candidates(local, params)
    if not candidates:
        return []
    side = params.get("side", candidates[0].side)
    q = quality_score(local, side)
    out = []
    for c in candidates:
        qi = c.quality if c.quality > 0 else float(q.iloc[c.signal_index])
        family = c.family or module.family_name
        out.append(replace(c, quality=qi, family=family))
    return out


def _g2_candidates(module, params: dict, segment: pd.DataFrame, config: BacktestConfig):
    local = segment.reset_index(drop=True)
    candidates = _with_family_quality(module, params, local)
    return apply_g2_candidate_guard(
        candidates,
        local,
        min_risk_atr=G2_MIN_RISK_ATR,
        max_cost_r=G2_MAX_COST_R,
        roundtrip_cost_bps=_cost_bps(config),
    )


def _evaluate(module, params: dict, segment: pd.DataFrame, config: BacktestConfig) -> tuple[Metrics, list[dict]]:
    local = segment.reset_index(drop=True)
    candidates = _with_family_quality(module, params, local)
    trades = _simulate_fast(candidates, local, config)
    return summarize_outcomes(trades), trades


def _evaluate_g2(module, params: dict, segment: pd.DataFrame, config: BacktestConfig) -> tuple[Metrics, list[dict]]:
    local = segment.reset_index(drop=True)
    candidates = _g2_candidates(module, params, local, config)
    trades = _simulate_fast(candidates, local, config)
    return summarize_outcomes(trades), trades


def _evaluate_member_rows(rows, segment: pd.DataFrame, config: BacktestConfig) -> tuple[Metrics, list[dict]]:
    local = segment.reset_index(drop=True)
    sets = []
    for row in rows:
        family = row.family if hasattr(row, "family") else row["family"]
        params = row.params if hasattr(row, "params") else row["params"]
        module = importlib.import_module(f"strategies.{family}")
        sets.append(_with_family_quality(module, params, local))
    merged = merge_candidates(sets)
    trades = _simulate_fast(merged, local, config)
    return summarize_outcomes(trades), trades


def _evaluate_member_rows_g2(rows, segment: pd.DataFrame, config: BacktestConfig) -> tuple[Metrics, list[dict]]:
    local = segment.reset_index(drop=True)
    sets = []
    for row in rows:
        family = row.family if hasattr(row, "family") else row["family"]
        params = row.params if hasattr(row, "params") else row["params"]
        module = importlib.import_module(f"strategies.{family}")
        sets.append(_g2_candidates(module, params, local, config))
    merged = merge_candidates(sets)
    trades = _simulate_fast(merged, local, config)
    return summarize_outcomes(trades), trades


def _rank(metrics: Metrics) -> float:
    breadth = min(1.0, metrics.completed_trades / 100.0)
    expectancy_term = max(-1.0, min(1.0, metrics.expectancy_r / 2.0))
    return 0.55 * metrics.rr2_wr + 0.30 * metrics.wilson_low + 0.10 * breadth + 0.05 * expectancy_term


def _rank_g2(metrics: Metrics, complexity: int = 1) -> float:
    breadth = min(1.0, metrics.completed_trades / 100.0)
    expectancy_term = max(-1.0, min(1.0, metrics.expectancy_r / 2.0))
    complexity_penalty = 0.002 * max(0, complexity - 5)
    return (
        0.62 * metrics.rr2_wr
        + 0.23 * metrics.wilson_low
        + 0.10 * breadth
        + 0.05 * expectancy_term
        - complexity_penalty
    )


def _validation_row_score(row: dict) -> float:
    m = row["validation"]
    expectancy = max(-1.0, min(1.0, float(m.get("expectancy_r", 0.0)) / 2.0))
    breadth = min(1.0, float(m.get("completed_trades", 0)) / 100.0)
    return (
        0.70 * float(m.get("rr2_wr", 0.0))
        + 0.20 * float(m.get("wilson_low", 0.0))
        + 0.05 * breadth
        + 0.05 * expectancy
    )


def choose_validation_members(rows: list[dict], max_members: int = 3) -> list[dict]:
    ranked = sorted(
        rows,
        key=lambda r: (_validation_row_score(r), r.get("family", "")),
        reverse=True,
    )
    return ranked[:max_members]


def diagnose_bottleneck(dev: Metrics, evaluation: Metrics) -> list[str]:
    out = []
    if evaluation.completed_trades < 100:
        out.append("insufficient-frequency")
    if evaluation.rr2_wr < 0.80:
        out.append("state-selection")
    if dev.rr2_wr - evaluation.rr2_wr > 0.15:
        out.append("regime-instability")
    if evaluation.expectancy_r <= 0:
        out.append("cost-or-entry-geometry")
    return out or ["none"]


def search_coin(symbol: str, features: pd.DataFrame, config: BacktestConfig) -> CoinResearchResult:
    n = len(features)
    a = int(n * config.development_fraction)
    b = int(n * (config.development_fraction + config.validation_fraction))
    dev, val, hold = (
        features.iloc[:a].copy(),
        features.iloc[a:b].copy(),
        features.iloc[b:].copy(),
    )
    ranked = []
    rejected = []
    for module_name in FAMILIES:
        module = importlib.import_module(module_name)
        for params in module.parameter_grid():
            metrics, _ = _evaluate(module, params, dev, config)
            if metrics.completed_trades < 30:
                continue
            ranked.append(
                {
                    "family": module.family_name,
                    "params": params,
                    "metrics": metrics.to_dict(),
                    "score": _rank(metrics),
                }
            )
    if not ranked:
        zero = summarize_outcomes([])
        return CoinResearchResult(
            symbol, "FAIL", None, zero, zero, zero, zero,
            ["insufficient-frequency"], [], []
        )
    ranked.sort(
        key=lambda x: (
            x["score"],
            x["metrics"]["rr2_wr"],
            x["metrics"]["completed_trades"],
        ),
        reverse=True,
    )
    best = ranked[0]
    rejected.extend(ranked[1:min(8, len(ranked))])
    locked_params = {"family": best["family"], **best["params"]}
    locked = lock_profile(locked_params)
    module = importlib.import_module(f"strategies.{best['family']}")
    dev_metrics, _ = _evaluate(module, best["params"], dev, config)
    val_metrics, val_trades = _evaluate(module, best["params"], val, config)
    hold_metrics, hold_trades = _evaluate(module, best["params"], hold, config)
    evaluation_trades = val_trades + hold_trades
    eval_metrics = summarize_outcomes(evaluation_trades)
    segment_floor_ok = (
        (val_metrics.completed_trades < 20 or val_metrics.rr2_wr >= 0.60)
        and (hold_metrics.completed_trades < 20 or hold_metrics.rr2_wr >= 0.60)
    )
    passed = (
        passes_hard_gate(
            eval_metrics.completed_trades,
            eval_metrics.rr2_wr,
            config.target_wr,
            config.min_completed_trades,
        )
        and eval_metrics.expectancy_r > 0
        and segment_floor_ok
    )
    return CoinResearchResult(
        symbol,
        "PASS" if passed else "FAIL",
        locked,
        dev_metrics,
        val_metrics,
        hold_metrics,
        eval_metrics,
        diagnose_bottleneck(dev_metrics, eval_metrics),
        rejected,
        evaluation_trades,
    )


def search_coin_g2(symbol: str, features: pd.DataFrame, config: BacktestConfig) -> CoinResearchResult:
    n = len(features)
    a = int(n * config.development_fraction)
    b = int(n * (config.development_fraction + config.validation_fraction))
    dev, val, hold = (
        features.iloc[:a].copy(),
        features.iloc[a:b].copy(),
        features.iloc[b:].copy(),
    )
    frontier: list[dict] = []

    for module_name in G2_FAMILIES:
        module = importlib.import_module(module_name)
        family_rows = []
        for params in module.parameter_grid():
            metrics, _ = _evaluate_g2(module, params, dev, config)
            if metrics.completed_trades < 20:
                continue
            family_rows.append(
                {
                    "family": module.family_name,
                    "params": params,
                    "metrics": metrics.to_dict(),
                    "score": _rank_g2(metrics, len(params)),
                }
            )
        family_rows.sort(
            key=lambda x: (
                x["score"],
                x["metrics"]["rr2_wr"],
                x["metrics"]["completed_trades"],
            ),
            reverse=True,
        )
        frontier.extend(family_rows[:6])

    if not frontier:
        zero = summarize_outcomes([])
        return CoinResearchResult(
            symbol, "FAIL", None, zero, zero, zero, zero,
            ["insufficient-frequency"], [], []
        )

    validation_rows = []
    val_candidate_cache = []
    local_val = val.reset_index(drop=True)
    for row in frontier:
        module = importlib.import_module(f"strategies.{row['family']}")
        candidates = _g2_candidates(module, row["params"], local_val, config)
        trades = _simulate_fast(candidates, local_val, config)
        vm = summarize_outcomes(trades)
        validation_rows.append({**row, "validation": vm.to_dict()})
        val_candidate_cache.append(candidates)

    order = sorted(
        range(len(validation_rows)),
        key=lambda i: _validation_row_score(validation_rows[i]),
        reverse=True,
    )[:6]
    best_combo = None
    best_score = -float("inf")
    best_val_metrics = summarize_outcomes([])
    best_val_trades: list[dict] = []
    for k in range(1, min(3, len(order)) + 1):
        for combo in combinations(order, k):
            merged = merge_candidates([val_candidate_cache[i] for i in combo])
            trades = _simulate_fast(merged, local_val, config)
            metrics = summarize_outcomes(trades)
            row_score = (
                0.70 * metrics.rr2_wr
                + 0.20 * metrics.wilson_low
                + 0.05 * min(1.0, metrics.completed_trades / 100.0)
                + 0.05 * max(-1.0, min(1.0, metrics.expectancy_r / 2.0))
                - 0.01 * (k - 1)
            )
            if row_score > best_score:
                best_score = row_score
                best_combo = combo
                best_val_metrics = metrics
                best_val_trades = trades

    if best_combo is None:
        zero = summarize_outcomes([])
        return CoinResearchResult(
            symbol, "FAIL", None, zero, zero, zero, zero,
            ["insufficient-frequency"], [], []
        )

    selected_rows = [validation_rows[i] for i in best_combo]
    locked = lock_ensemble(
        [{"family": r["family"], "params": r["params"]} for r in selected_rows]
    )
    dev_metrics, _ = _evaluate_member_rows_g2(locked.members, dev, config)
    hold_metrics, hold_trades = _evaluate_member_rows_g2(locked.members, hold, config)
    evaluation_trades = best_val_trades + hold_trades
    eval_metrics = summarize_outcomes(evaluation_trades)
    passed = passes_g2_gate(
        completed_trades=eval_metrics.completed_trades,
        rr2_wr=eval_metrics.rr2_wr,
        expectancy_r=eval_metrics.expectancy_r,
        validation_trades=best_val_metrics.completed_trades,
        validation_wr=best_val_metrics.rr2_wr,
        holdout_trades=hold_metrics.completed_trades,
        holdout_wr=hold_metrics.rr2_wr,
        target_wr=config.target_wr,
        min_trades=config.min_completed_trades,
    )

    selected_hashes = {m.profile_hash for m in locked.members}
    rejected = []
    for row in sorted(validation_rows, key=_validation_row_score, reverse=True):
        candidate_hash = lock_profile(
            {"family": row["family"], **row["params"]}
        ).profile_hash
        if candidate_hash not in selected_hashes:
            rejected.append(
                {
                    "family": row["family"],
                    "params": row["params"],
                    "metrics": row["metrics"],
                    "validation": row["validation"],
                    "score": row["score"],
                }
            )
        if len(rejected) >= 8:
            break

    return CoinResearchResult(
        symbol,
        "PASS" if passed else "FAIL",
        locked,
        dev_metrics,
        best_val_metrics,
        hold_metrics,
        eval_metrics,
        diagnose_bottleneck(dev_metrics, eval_metrics),
        rejected,
        evaluation_trades,
    )
