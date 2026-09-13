from g9.supervisor import allocate_research_budget, diagnose_bottlenecks


def test_supervisor_prioritizes_sample_and_stability_before_model_tuning():
    metrics = {
        "completed_trades": 62,
        "worst_fold_win_rate": 0.41,
        "oof_win_rate": 0.72,
        "expectancy_r": 0.38,
        "cost_stress_expectancy_r": 0.12,
        "calibration_ece": 0.03,
        "expert_disagreement": 0.10,
        "regime_confusion_rate": 0.20,
    }
    reasons = diagnose_bottlenecks(metrics)
    assert reasons[0] == "INSUFFICIENT_SAMPLE"
    assert "UNSTABLE_FOLDS" in reasons


def test_supervisor_detects_cost_calibration_and_disagreement_bottlenecks():
    metrics = {
        "completed_trades": 220,
        "worst_fold_win_rate": 0.68,
        "oof_win_rate": 0.73,
        "expectancy_r": 0.44,
        "cost_stress_expectancy_r": -0.02,
        "calibration_ece": 0.12,
        "expert_disagreement": 0.46,
        "regime_confusion_rate": 0.18,
    }
    reasons = diagnose_bottlenecks(metrics)
    assert reasons[:3] == ["COST_FRAGILITY", "POOR_CALIBRATION", "HIGH_DISAGREEMENT"]


def test_budget_allocation_is_bounded_and_routes_to_diagnosed_dimensions():
    metrics = {
        "completed_trades": 250,
        "worst_fold_win_rate": 0.71,
        "oof_win_rate": 0.76,
        "expectancy_r": 0.51,
        "cost_stress_expectancy_r": 0.20,
        "calibration_ece": 0.02,
        "expert_disagreement": 0.08,
        "regime_confusion_rate": 0.44,
    }
    allocation = allocate_research_budget(metrics, total_budget=7)
    assert sum(allocation.values()) == 7
    assert allocation["regime"] >= allocation.get("calibration", 0)
    assert set(allocation).issubset({"sample", "stability", "cost", "calibration", "agreement", "regime", "structure"})
