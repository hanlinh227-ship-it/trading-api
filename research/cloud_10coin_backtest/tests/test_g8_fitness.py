from g8.fitness import TrialMetrics, compare_for_promotion, fitness_key
from g8.state import LoopState


def test_stable_candidate_beats_spiky_high_mean_candidate():
    stable = TrialMetrics(
        trades=220,
        rr2_wr=.76,
        worst_fold_wr=.72,
        wilson_lower=.69,
        expectancy_r=.95,
        max_drawdown_r=7.0,
        cost_stress_expectancy_r=.72,
        pbo=.20,
        leakage_ok=True,
        falsification_ok=True,
    )
    spiky = TrialMetrics(
        trades=220,
        rr2_wr=.84,
        worst_fold_wr=.39,
        wilson_lower=.70,
        expectancy_r=1.02,
        max_drawdown_r=8.0,
        cost_stress_expectancy_r=.80,
        pbo=.35,
        leakage_ok=True,
        falsification_ok=True,
    )
    assert fitness_key(stable) > fitness_key(spiky)


def test_exhausted_epoch_blocks_promotion_even_if_challenger_is_better():
    state = LoopState.new(symbols=["BTCUSDT"], source_sha="abc", max_adaptive_trials=0)
    decision = compare_for_promotion(None, TrialMetrics.good_example(), state, "BTCUSDT")
    assert decision.promote is False
    assert "evidence-budget-exhausted" in decision.reasons


def test_negative_cost_stress_expectancy_blocks_promotion():
    state = LoopState.new(symbols=["BTCUSDT"], source_sha="abc", max_adaptive_trials=10)
    challenger = TrialMetrics.good_example(cost_stress_expectancy_r=-0.01)
    decision = compare_for_promotion(None, challenger, state, "BTCUSDT")
    assert decision.promote is False
    assert "nonpositive-cost-stress-expectancy" in decision.reasons


def test_falsification_failure_blocks_promotion():
    state = LoopState.new(symbols=["BTCUSDT"], source_sha="abc", max_adaptive_trials=10)
    challenger = TrialMetrics.good_example(falsification_ok=False)
    decision = compare_for_promotion(None, challenger, state, "BTCUSDT")
    assert decision.promote is False
    assert "falsification-failed" in decision.reasons


def test_material_worst_fold_regression_blocks_higher_raw_wr():
    state = LoopState.new(symbols=["BTCUSDT"], source_sha="abc", max_adaptive_trials=10)
    incumbent = TrialMetrics.good_example(rr2_wr=.70, worst_fold_wr=.68, wilson_lower=.62)
    challenger = TrialMetrics.good_example(rr2_wr=.85, worst_fold_wr=.50, wilson_lower=.70)
    decision = compare_for_promotion(incumbent, challenger, state, "BTCUSDT")
    assert decision.promote is False
    assert "worst-fold-regression" in decision.reasons
