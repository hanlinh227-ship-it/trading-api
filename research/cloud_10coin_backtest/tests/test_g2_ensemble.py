from engine.execution import OrderCandidate
from optimize.ensemble import merge_candidates, lock_ensemble


def test_overlap_keeps_highest_signal_time_quality():
    weak = OrderCandidate(10, "LONG", 100.0, 99.0, quality=0.3, family="weak")
    strong = OrderCandidate(10, "LONG", 100.0, 99.0, quality=0.9, family="strong")
    merged = merge_candidates([[weak], [strong]])
    assert len(merged) == 1
    assert merged[0].family == "strong"


def test_overlap_tie_break_is_deterministic():
    b = OrderCandidate(10, "LONG", 100.0, 99.0, quality=0.8, family="b_family")
    a = OrderCandidate(10, "LONG", 100.0, 99.0, quality=0.8, family="a_family")
    merged = merge_candidates([[b], [a]])
    assert merged[0].family == "a_family"


def test_locked_ensemble_is_independent_from_input_mutation():
    members = [
        {"family": "sweep_mss_ote_g2", "params": {"side": "LONG", "r": 0.79}},
        {"family": "trend_ote", "params": {"side": "SHORT", "r": 0.90}},
    ]
    locked = lock_ensemble(members)
    before = locked.ensemble_hash
    members[0]["params"]["r"] = 0.1
    assert locked.members[0].params["r"] == 0.79
    assert locked.ensemble_hash == before
