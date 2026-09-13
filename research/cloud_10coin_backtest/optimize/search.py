from __future__ import annotations

import importlib
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from config import BacktestConfig
from engine.metrics import Metrics, summarize_outcomes
from optimize.selection import LockedProfile, lock_profile

FAMILIES = (
    "strategies.trend_ote",
    "strategies.sweep_mss",
    "strategies.break_retest",
    "strategies.compression",
    "strategies.mean_reversion",
)


@dataclass
class CoinResearchResult:
    symbol: str
    status: str
    locked_profile: LockedProfile | None
    development: Metrics
    validation: Metrics
    holdout: Metrics
    evaluation: Metrics
    bottlenecks: list[str]
    rejected_candidates: list[dict]
    evaluation_trades: list[dict]

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "status": self.status,
            "locked_profile": None if self.locked_profile is None else {"params": self.locked_profile.params, "profile_hash": self.locked_profile.profile_hash},
            "development": self.development.to_dict(),
            "validation": self.validation.to_dict(),
            "holdout": self.holdout.to_dict(),
            "evaluation": self.evaluation.to_dict(),
            "bottlenecks": self.bottlenecks,
            "rejected_candidates": self.rejected_candidates,
        }


def passes_hard_gate(completed_trades: int, rr2_wr: float, target_wr: float, min_trades: int) -> bool:
    return completed_trades >= min_trades and rr2_wr >= target_wr


def _cost_bps(config: BacktestConfig) -> float:
    return 2.0 * (config.costs.fee_bps_per_side + config.costs.slippage_bps_per_side)


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
        gross = (closes[exit_index] - c.entry) / risk if side == "LONG" else (c.entry - closes[exit_index]) / risk
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
        results.append({
            "signal_index": c.signal_index, "fill_index": fill, "exit_index": exit_index,
            "side": side, "entry": c.entry, "stop": c.stop, "rr1_hit": rr1,
            "rr2_hit": rr2, "exit_reason": reason, "gross_r": gross, "net_r": gross - cost_r,
        })
        last_exit = exit_index
    return results


def _evaluate(module, params: dict, segment: pd.DataFrame, config: BacktestConfig) -> tuple[Metrics, list[dict]]:
    local = segment.reset_index(drop=True)
    candidates = module.generate_candidates(local, params)
    trades = _simulate_fast(candidates, local, config)
    return summarize_outcomes(trades), trades


def _rank(metrics: Metrics) -> float:
    breadth = min(1.0, metrics.completed_trades / 100.0)
    expectancy_term = max(-1.0, min(1.0, metrics.expectancy_r / 2.0))
    return 0.55 * metrics.rr2_wr + 0.30 * metrics.wilson_low + 0.10 * breadth + 0.05 * expectancy_term


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
    dev, val, hold = features.iloc[:a].copy(), features.iloc[a:b].copy(), features.iloc[b:].copy()
    ranked = []
    rejected = []
    for module_name in FAMILIES:
        module = importlib.import_module(module_name)
        for params in module.parameter_grid():
            metrics, _ = _evaluate(module, params, dev, config)
            if metrics.completed_trades < 30:
                continue
            row = {"family": module.family_name, "params": params, "metrics": metrics.to_dict(), "score": _rank(metrics)}
            ranked.append(row)
    if not ranked:
        zero = summarize_outcomes([])
        return CoinResearchResult(symbol, "FAIL", None, zero, zero, zero, zero, ["insufficient-frequency"], [], [])
    ranked.sort(key=lambda x: (x["score"], x["metrics"]["rr2_wr"], x["metrics"]["completed_trades"]), reverse=True)
    best = ranked[0]
    rejected.extend(ranked[1: min(8, len(ranked))])
    locked_params = {"family": best["family"], **best["params"]}
    locked = lock_profile(locked_params)
    module = importlib.import_module(f"strategies.{best['family']}")
    dev_metrics, _ = _evaluate(module, best["params"], dev, config)
    val_metrics, val_trades = _evaluate(module, best["params"], val, config)
    hold_metrics, hold_trades = _evaluate(module, best["params"], hold, config)
    evaluation_trades = val_trades + hold_trades
    eval_metrics = summarize_outcomes(evaluation_trades)
    segment_floor_ok = (val_metrics.completed_trades < 20 or val_metrics.rr2_wr >= 0.60) and (hold_metrics.completed_trades < 20 or hold_metrics.rr2_wr >= 0.60)
    passed = passes_hard_gate(eval_metrics.completed_trades, eval_metrics.rr2_wr, config.target_wr, config.min_completed_trades) and eval_metrics.expectancy_r > 0 and segment_floor_ok
    status = "PASS" if passed else "FAIL"
    return CoinResearchResult(symbol, status, locked, dev_metrics, val_metrics, hold_metrics, eval_metrics, diagnose_bottleneck(dev_metrics, eval_metrics), rejected, evaluation_trades)
