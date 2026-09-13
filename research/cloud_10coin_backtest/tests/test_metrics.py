from engine.metrics import wilson_interval, summarize_outcomes


def test_wilson_interval_is_bounded():
    lo, hi = wilson_interval(80, 100)
    assert 0.70 < lo < 0.80
    assert 0.80 < hi < 0.90


def test_summarize_outcomes_counts_rr2_exactly():
    rows = [
        {"rr1_hit": True, "rr2_hit": True, "net_r": 2.0},
        {"rr1_hit": True, "rr2_hit": False, "net_r": -1.0},
        {"rr1_hit": False, "rr2_hit": False, "net_r": -1.0},
    ]
    m = summarize_outcomes(rows)
    assert m.completed_trades == 3
    assert m.rr2_wins == 1
    assert m.rr2_wr == 1 / 3
