from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from engine.metrics import summarize_outcomes
from g8.candidate import CandidateSpec
from g8.fitness import TrialMetrics
from g8.validation import TimeFold, purged_walk_forward
from optimize.meta_model import fit_logistic, predict_proba
from optimize.nonlinear_model import fit_nonlinear, predict_nonlinear_proba
from optimize.router_g7 import build_routed_candidates
from optimize.search import _cost_bps, _simulate_fast
from optimize.search_g6 import candidate_feature_matrix, label_setup_candidates
from optimize.search_g7 import filter_locked_geometry


MIN_TRAIN_LABELS = 40
COST_STRESS_MULTIPLIER = 1.5


@dataclass
class _ModelBundle:
    base_model: object
    model_family: str
    calibration: str
    calibration_model: object | None = None


def _route(candidate: CandidateSpec) -> tuple[str, str, str]:
    return (str(candidate.regime), str(candidate.family), str(candidate.side).upper())


def _candidate_set(frame: pd.DataFrame, candidate: CandidateSpec, config):
    local = frame.reset_index(drop=True)
    routed = build_routed_candidates(local, roundtrip_cost_bps=_cost_bps(config))
    candidates = routed.get(_route(candidate), [])
    return filter_locked_geometry(
        candidates,
        local,
        risk_atr=float(candidate.risk_atr),
        hold_bars=int(candidate.hold_bars),
    )


def _fit_base(candidate: CandidateSpec, x, y):
    if candidate.model_family == "logistic":
        return fit_logistic(x, y)
    if candidate.model_family == "random_forest":
        params = {str(k): v for k, v in candidate.model_params}
        allowed = {"n_estimators", "max_depth", "min_samples_leaf", "max_features", "random_state"}
        params = {k: v for k, v in params.items() if k in allowed}
        return fit_nonlinear(x, y, **params)
    raise ValueError(f"unsupported G8 model family: {candidate.model_family}")


def _base_predict(bundle: _ModelBundle, x):
    if bundle.model_family == "logistic":
        return np.asarray(predict_proba(bundle.base_model, x), dtype=float)
    return np.asarray(predict_nonlinear_proba(bundle.base_model, x), dtype=float)


def _fit_bundle(candidate: CandidateSpec, x, y) -> _ModelBundle | None:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=int).reshape(-1)
    if x.ndim != 2 or len(x) != len(y) or len(y) < MIN_TRAIN_LABELS or len(np.unique(y)) < 2:
        return None

    calibration = str(candidate.calibration)
    if calibration == "none":
        base = _fit_base(candidate, x, y)
        return _ModelBundle(base, candidate.model_family, calibration)

    split = max(MIN_TRAIN_LABELS, int(len(y) * 0.80))
    if split >= len(y) - 10:
        return None
    fit_x, cal_x = x[:split], x[split:]
    fit_y, cal_y = y[:split], y[split:]
    if len(np.unique(fit_y)) < 2 or len(np.unique(cal_y)) < 2:
        return None
    base = _fit_base(candidate, fit_x, fit_y)
    temp = _ModelBundle(base, candidate.model_family, "none")
    raw = _base_predict(temp, cal_x)
    if calibration == "platt":
        cal_model = fit_logistic(raw.reshape(-1, 1), cal_y, l2=0.1, iterations=250, learning_rate=0.05)
    elif calibration == "isotonic":
        cal_model = IsotonicRegression(out_of_bounds="clip").fit(raw, cal_y)
    else:
        raise ValueError(f"unsupported G8 calibration: {calibration}")
    return _ModelBundle(base, candidate.model_family, calibration, cal_model)


def _predict(bundle: _ModelBundle, x) -> np.ndarray:
    raw = _base_predict(bundle, x)
    if bundle.calibration == "none":
        return raw
    if bundle.calibration == "platt":
        return np.asarray(predict_proba(bundle.calibration_model, raw.reshape(-1, 1)), dtype=float)
    if bundle.calibration == "isotonic":
        return np.asarray(bundle.calibration_model.predict(raw), dtype=float)
    raise ValueError(f"unsupported G8 calibration: {bundle.calibration}")


def run_falsification_suite(labels, scores, *, seed: int = 17) -> dict:
    labels = np.asarray(labels, dtype=int).reshape(-1)
    scores = np.asarray(scores, dtype=float).reshape(-1)
    if len(labels) != len(scores):
        raise ValueError("falsification labels/scores length mismatch")
    if len(labels) == 0:
        return {
            "selected": 0,
            "shuffled_selected_wr": 0.0,
            "time_shift_selected_wr": 0.0,
            "ok": True,
        }
    selected = np.isfinite(scores) & (scores >= 0.5)
    selected_n = int(selected.sum())
    if selected_n == 0:
        return {
            "selected": 0,
            "shuffled_selected_wr": 0.0,
            "time_shift_selected_wr": 0.0,
            "ok": True,
        }
    rng = np.random.default_rng(int(seed))
    shuffled = rng.permutation(labels)
    shift = max(1, len(labels) // 7)
    shifted = np.roll(labels, shift)
    shuffled_wr = float(shuffled[selected].mean())
    shifted_wr = float(shifted[selected].mean())
    suspicious = selected_n >= 20 and max(shuffled_wr, shifted_wr) >= 0.75
    return {
        "selected": selected_n,
        "shuffled_selected_wr": shuffled_wr,
        "time_shift_selected_wr": shifted_wr,
        "ok": not suspicious,
    }


def _stress_config(config):
    costs = replace(
        config.costs,
        fee_bps_per_side=float(config.costs.fee_bps_per_side) * COST_STRESS_MULTIPLIER,
        slippage_bps_per_side=float(config.costs.slippage_bps_per_side) * COST_STRESS_MULTIPLIER,
    )
    return replace(config, costs=costs)


def _empty_fold(fold_id: int, reason: str) -> dict:
    return {
        "fold": int(fold_id),
        "completed_trades": 0,
        "rr2_wr": 0.0,
        "expectancy_r": 0.0,
        "wilson_low": 0.0,
        "reason": str(reason),
    }


def evaluate_candidate(
    symbol: str,
    features: pd.DataFrame,
    config,
    candidate: CandidateSpec,
    validation_plan: list[TimeFold] | tuple[TimeFold, ...] | None = None,
) -> TrialMetrics:
    symbol = str(symbol).upper()
    if symbol != str(candidate.symbol).upper():
        raise ValueError("candidate symbol does not match evaluator symbol")
    local = features.reset_index(drop=True)
    if validation_plan is None:
        validation_plan = purged_walk_forward(
            len(local),
            n_splits=4,
            purge_bars=int(candidate.hold_bars) + 1,
            embargo_bars=12,
        )

    all_trades: list[dict] = []
    stress_trades: list[dict] = []
    fold_rows: list[dict] = []
    null_labels: list[int] = []
    null_scores: list[float] = []
    leakage_ok = True
    stress_cfg = _stress_config(config)

    for fold_id, fold in enumerate(validation_plan):
        train_idx = tuple(int(i) for i in fold.train_idx)
        test_idx = tuple(int(i) for i in fold.test_idx)
        if not train_idx or not test_idx or set(train_idx).intersection(test_idx):
            leakage_ok = False
            fold_rows.append(_empty_fold(fold_id, "invalid-split"))
            continue
        if max(train_idx) >= min(test_idx):
            leakage_ok = False
            fold_rows.append(_empty_fold(fold_id, "noncausal-split"))
            continue

        train = local.iloc[list(train_idx)].reset_index(drop=True)
        test = local.iloc[list(test_idx)].reset_index(drop=True)
        train_candidates = _candidate_set(train, candidate, config)
        train_x, train_rows, _ = label_setup_candidates(
            train,
            train_candidates,
            roundtrip_cost_bps=_cost_bps(config),
        )
        if len(train_rows) < MIN_TRAIN_LABELS or len(train_x) != len(train_rows):
            fold_rows.append(_empty_fold(fold_id, "insufficient-train-labels"))
            continue
        y_train = train_rows["rr2_hit"].astype(int).to_numpy()
        bundle = _fit_bundle(candidate, train_x, y_train)
        if bundle is None:
            fold_rows.append(_empty_fold(fold_id, "unfit-model"))
            continue

        test_candidates = _candidate_set(test, candidate, config)
        if not test_candidates:
            fold_rows.append(_empty_fold(fold_id, "no-test-candidates"))
            continue
        test_x = candidate_feature_matrix(test, test_candidates)
        probs = _predict(bundle, test_x)
        scored = []
        for setup, probability in zip(test_candidates, probs):
            if float(probability) < float(candidate.threshold):
                continue
            scored.append(replace(setup, quality=float(probability)))
        trades = _simulate_fast(scored, test, config)
        stress = _simulate_fast(scored, test, stress_cfg)
        all_trades.extend(trades)
        stress_trades.extend(stress)
        metrics = summarize_outcomes(trades)
        fold_rows.append(
            {
                "fold": int(fold_id),
                "completed_trades": int(metrics.completed_trades),
                "rr2_wr": float(metrics.rr2_wr),
                "expectancy_r": float(metrics.expectancy_r),
                "wilson_low": float(metrics.wilson_low),
                "reason": "ok",
            }
        )

        _, independent_rows, kept = label_setup_candidates(
            test,
            test_candidates,
            roundtrip_cost_bps=_cost_bps(config),
        )
        if len(kept):
            kept_x = candidate_feature_matrix(test, kept)
            kept_probs = _predict(bundle, kept_x)
            null_labels.extend(independent_rows["rr2_hit"].astype(int).tolist())
            null_scores.extend(float(x) for x in kept_probs)

    overall = summarize_outcomes(all_trades)
    stressed = summarize_outcomes(stress_trades)
    active_folds = [row for row in fold_rows if int(row["completed_trades"]) > 0]
    worst_fold = min((float(row["rr2_wr"]) for row in active_folds), default=0.0)
    pbo_proxy = (
        sum(float(row["expectancy_r"]) <= 0.0 for row in active_folds) / len(active_folds)
        if active_folds
        else 1.0
    )
    falsification = run_falsification_suite(null_labels, null_scores, seed=17)

    return TrialMetrics(
        trades=int(overall.completed_trades),
        rr2_wr=float(overall.rr2_wr),
        worst_fold_wr=float(worst_fold),
        wilson_lower=float(overall.wilson_low),
        expectancy_r=float(overall.expectancy_r),
        max_drawdown_r=float(overall.max_drawdown_r),
        cost_stress_expectancy_r=float(stressed.expectancy_r),
        pbo=float(pbo_proxy),
        leakage_ok=bool(leakage_ok),
        falsification_ok=bool(falsification["ok"]),
        min_required_trades=int(config.min_completed_trades),
        provenance_complete=True,
        fold_metrics=tuple(fold_rows),
        in_sample_score=None,
    )
