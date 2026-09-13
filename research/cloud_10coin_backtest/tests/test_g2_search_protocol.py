from optimize.search import choose_validation_members, passes_g2_gate


def test_validation_selection_ignores_holdout_fields():
    rows = [
        {
            "family": "a", "params": {"x": 1},
            "validation": {"rr2_wr": 0.82, "wilson_low": 0.70, "completed_trades": 60, "expectancy_r": 0.5},
            "holdout": {"rr2_wr": 0.10},
        },
        {
            "family": "b", "params": {"x": 2},
            "validation": {"rr2_wr": 0.78, "wilson_low": 0.68, "completed_trades": 80, "expectancy_r": 0.7},
            "holdout": {"rr2_wr": 1.00},
        },
    ]
    selected = choose_validation_members(rows, max_members=1)
    assert selected[0]["family"] == "a"


def test_g2_gate_requires_100_trades_even_at_perfect_win_rate():
    assert not passes_g2_gate(
        completed_trades=99,
        rr2_wr=1.0,
        expectancy_r=1.5,
        validation_trades=50,
        validation_wr=0.9,
        holdout_trades=49,
        holdout_wr=0.9,
    )


def test_g2_gate_requires_segment_stability():
    assert not passes_g2_gate(
        completed_trades=120,
        rr2_wr=0.85,
        expectancy_r=0.5,
        validation_trades=60,
        validation_wr=0.90,
        holdout_trades=60,
        holdout_wr=0.55,
    )
