from __future__ import annotations

from collections import OrderedDict
from typing import Mapping


_REASON_TO_DIMENSION = OrderedDict(
    [
        ("INSUFFICIENT_SAMPLE", "sample"),
        ("UNSTABLE_FOLDS", "stability"),
        ("COST_FRAGILITY", "cost"),
        ("POOR_CALIBRATION", "calibration"),
        ("HIGH_DISAGREEMENT", "agreement"),
        ("REGIME_CONFUSION", "regime"),
        ("WEAK_STRUCTURE", "structure"),
    ]
)


def diagnose_bottlenecks(metrics: Mapping[str, float | int]) -> list[str]:
    reasons: list[str] = []
    completed = int(metrics.get("completed_trades", 0))
    worst_fold = float(metrics.get("worst_fold_win_rate", 0.0))
    expectancy = float(metrics.get("expectancy_r", 0.0))
    cost_expectancy = float(metrics.get("cost_stress_expectancy_r", expectancy))
    calibration_ece = float(metrics.get("calibration_ece", 0.0))
    disagreement = float(metrics.get("expert_disagreement", 0.0))
    regime_confusion = float(metrics.get("regime_confusion_rate", 0.0))
    structure_precision = float(metrics.get("structure_precision", 1.0))

    if completed < 100:
        reasons.append("INSUFFICIENT_SAMPLE")
    if worst_fold < 0.55:
        reasons.append("UNSTABLE_FOLDS")
    if expectancy > 0.0 and cost_expectancy <= 0.0:
        reasons.append("COST_FRAGILITY")
    if calibration_ece > 0.08:
        reasons.append("POOR_CALIBRATION")
    if disagreement > 0.35:
        reasons.append("HIGH_DISAGREEMENT")
    if regime_confusion > 0.35:
        reasons.append("REGIME_CONFUSION")
    if structure_precision < 0.50:
        reasons.append("WEAK_STRUCTURE")
    return reasons


def allocate_research_budget(
    metrics: Mapping[str, float | int], *, total_budget: int
) -> dict[str, int]:
    if total_budget <= 0:
        raise ValueError("total_budget must be positive")
    reasons = diagnose_bottlenecks(metrics)
    dimensions: list[str] = []
    for reason in reasons:
        dimension = _REASON_TO_DIMENSION[reason]
        if dimension not in dimensions:
            dimensions.append(dimension)
    if not dimensions:
        dimensions = ["structure"]

    allocation = {dimension: 0 for dimension in dimensions}
    for index in range(total_budget):
        allocation[dimensions[index % len(dimensions)]] += 1
    return allocation
