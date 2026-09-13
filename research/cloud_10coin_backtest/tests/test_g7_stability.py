import pandas as pd

from optimize.stability_g7 import route_is_target_qualified, select_stable_threshold, wilson_lower


def _rows_for_threshold_comparison():
    rows = []
    # High-probability subset: spectacular in 3 folds, collapses in fold 2.
    high_rates = {0: 0.90, 1: 0.90, 2: 0.35, 3: 0.90}
    # Lower-probability additions make the broader threshold stable near 75%.
    target_rates = {0: 0.74, 1: 0.75, 2: 0.76, 3: 0.75}
    for fold in range(4):
        high_n = 20
        high_wins = round(high_rates[fold] * high_n)
        for i in range(high_n):
            win = i < high_wins
            rows.append({"fold": fold, "prob": 0.90, "rr2_hit": win, "net_r": 1.8 if win else -1.0})

        add_n = 80
        total_target_wins = round(target_rates[fold] * (high_n + add_n))
        add_wins = max(0, min(add_n, total_target_wins - high_wins))
        for i in range(add_n):
            win = i < add_wins
            rows.append({"fold": fold, "prob": 0.60, "rr2_hit": win, "net_r": 1.8 if win else -1.0})
    return pd.DataFrame(rows)


def test_wilson_lower_is_bounded_and_increases_with_wins():
    assert 0.0 <= wilson_lower(8, 10) <= 1.0
    assert wilson_lower(9, 10) > wilson_lower(8, 10)


def test_stability_ranking_prefers_consistent_threshold_over_spiky_threshold():
    rows = _rows_for_threshold_comparison()
    choice = select_stable_threshold(rows, thresholds=(0.50, 0.80), min_trades=40, min_fold_trades=10)
    assert choice["threshold"] == 0.50
    assert choice["min_fold_wr"] >= 0.70
    assert choice["completed_trades"] == 400


def test_target_qualification_requires_all_quality_gates():
    good = {
        "completed_trades": 100,
        "rr2_wr": 0.84,
        "expectancy_r": 1.1,
        "min_fold_wr": 0.72,
        "wilson_lower": 0.70,
    }
    assert route_is_target_qualified(good, target_wr=0.80) is True

    for key, value in {
        "completed_trades": 20,
        "rr2_wr": 0.79,
        "expectancy_r": -0.01,
        "min_fold_wr": 0.50,
        "wilson_lower": 0.50,
    }.items():
        bad = dict(good)
        bad[key] = value
        assert route_is_target_qualified(bad, target_wr=0.80) is False


def test_threshold_output_contains_stability_fields_and_qualified_flag():
    rows = _rows_for_threshold_comparison()
    choice = select_stable_threshold(rows, thresholds=(0.50,), min_trades=40, min_fold_trades=10)
    assert set(choice) >= {
        "threshold", "completed_trades", "rr2_wr", "expectancy_r",
        "min_fold_wr", "wilson_lower", "qualified",
    }
