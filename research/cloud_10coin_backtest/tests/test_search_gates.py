from optimize.search import passes_hard_gate


def test_candidate_with_99_trades_cannot_pass():
    assert passes_hard_gate(completed_trades=99, rr2_wr=1.0, target_wr=0.80, min_trades=100) is False


def test_candidate_with_100_trades_and_79pct_cannot_pass():
    assert passes_hard_gate(completed_trades=100, rr2_wr=0.79, target_wr=0.80, min_trades=100) is False


def test_candidate_with_100_trades_and_80pct_can_pass_numeric_gate():
    assert passes_hard_gate(completed_trades=100, rr2_wr=0.80, target_wr=0.80, min_trades=100) is True
