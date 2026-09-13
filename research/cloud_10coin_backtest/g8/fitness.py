from __future__ import annotations

from dataclasses import dataclass, replace

from g8.state import LoopState, can_promote


WORST_FOLD_REGRESSION_TOLERANCE = 0.02
PBO_REGRESSION_TOLERANCE = 0.15


@dataclass(frozen=True)
class TrialMetrics:
    trades: int
    rr2_wr: float
    worst_fold_wr: float
    wilson_lower: float
    expectancy_r: float
    max_drawdown_r: float
    cost_stress_expectancy_r: float
    pbo: float
    leakage_ok: bool
    falsification_ok: bool
    min_required_trades: int = 100
    provenance_complete: bool = True
    dsr: float | None = None
    calibration_error: float | None = None
    fold_metrics: tuple[dict, ...] = ()
    in_sample_score: float | None = None

    @classmethod
    def good_example(cls, **changes) -> "TrialMetrics":
        base = cls(
            trades=180,
            rr2_wr=0.72,
            worst_fold_wr=0.67,
            wilson_lower=0.64,
            expectancy_r=0.88,
            max_drawdown_r=6.0,
            cost_stress_expectancy_r=0.65,
            pbo=0.20,
            leakage_ok=True,
            falsification_ok=True,
        )
        return replace(base, **changes)

    def to_dict(self) -> dict:
        return {
            "trades": int(self.trades),
            "rr2_wr": float(self.rr2_wr),
            "worst_fold_wr": float(self.worst_fold_wr),
            "wilson_lower": float(self.wilson_lower),
            "expectancy_r": float(self.expectancy_r),
            "max_drawdown_r": float(self.max_drawdown_r),
            "cost_stress_expectancy_r": float(self.cost_stress_expectancy_r),
            "pbo": float(self.pbo),
            "leakage_ok": bool(self.leakage_ok),
            "falsification_ok": bool(self.falsification_ok),
            "min_required_trades": int(self.min_required_trades),
            "provenance_complete": bool(self.provenance_complete),
            "dsr": None if self.dsr is None else float(self.dsr),
            "calibration_error": None if self.calibration_error is None else float(self.calibration_error),
            "fold_metrics": [dict(row) for row in self.fold_metrics],
            "in_sample_score": self.in_sample_score,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "TrialMetrics":
        return cls(
            trades=int(payload.get("trades", 0)),
            rr2_wr=float(payload.get("rr2_wr", 0.0)),
            worst_fold_wr=float(payload.get("worst_fold_wr", 0.0)),
            wilson_lower=float(payload.get("wilson_lower", 0.0)),
            expectancy_r=float(payload.get("expectancy_r", 0.0)),
            max_drawdown_r=float(payload.get("max_drawdown_r", 0.0)),
            cost_stress_expectancy_r=float(payload.get("cost_stress_expectancy_r", 0.0)),
            pbo=float(payload.get("pbo", 1.0)),
            leakage_ok=bool(payload.get("leakage_ok", False)),
            falsification_ok=bool(payload.get("falsification_ok", False)),
            min_required_trades=int(payload.get("min_required_trades", 100)),
            provenance_complete=bool(payload.get("provenance_complete", False)),
            dsr=None if payload.get("dsr") is None else float(payload["dsr"]),
            calibration_error=None if payload.get("calibration_error") is None else float(payload["calibration_error"]),
            fold_metrics=tuple(dict(row) for row in payload.get("fold_metrics", ())),
            in_sample_score=payload.get("in_sample_score"),
        )


@dataclass(frozen=True)
class PromotionDecision:
    promote: bool
    reasons: tuple[str, ...]
    incumbent_key: tuple | None
    challenger_key: tuple


def fitness_key(metrics: TrialMetrics) -> tuple:
    integrity = metrics.leakage_ok and metrics.falsification_ok and metrics.provenance_complete
    return (
        int(integrity),
        int(metrics.trades >= metrics.min_required_trades),
        float(metrics.worst_fold_wr),
        float(metrics.wilson_lower),
        float(metrics.rr2_wr),
        float(metrics.cost_stress_expectancy_r),
        float(metrics.expectancy_r),
        -float(metrics.pbo),
        -float(metrics.max_drawdown_r),
        int(metrics.trades),
    )


def compare_for_promotion(
    incumbent: TrialMetrics | None,
    challenger: TrialMetrics,
    state: LoopState,
    symbol: str,
) -> PromotionDecision:
    reasons: list[str] = []
    challenger_key = fitness_key(challenger)
    incumbent_key = None if incumbent is None else fitness_key(incumbent)

    if not can_promote(state, symbol):
        reasons.append("evidence-budget-exhausted")
    if not challenger.provenance_complete:
        reasons.append("incomplete-provenance")
    if not challenger.leakage_ok:
        reasons.append("leakage-audit-failed")
    if not challenger.falsification_ok:
        reasons.append("falsification-failed")
    if challenger.expectancy_r <= 0.0:
        reasons.append("nonpositive-expectancy")
    if challenger.cost_stress_expectancy_r <= 0.0:
        reasons.append("nonpositive-cost-stress-expectancy")
    if challenger.trades <= 0:
        reasons.append("no-oof-trades")

    if incumbent is not None:
        if challenger.worst_fold_wr < incumbent.worst_fold_wr - WORST_FOLD_REGRESSION_TOLERANCE:
            reasons.append("worst-fold-regression")
        if challenger.pbo > incumbent.pbo + PBO_REGRESSION_TOLERANCE:
            reasons.append("pbo-regression")
        if challenger_key <= incumbent_key:
            reasons.append("fitness-not-improved")

    return PromotionDecision(
        promote=not reasons,
        reasons=tuple(reasons),
        incumbent_key=incumbent_key,
        challenger_key=challenger_key,
    )
