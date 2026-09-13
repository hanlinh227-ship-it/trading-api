from analysis.g7_decision import classify_signal_decision


def _route(**overrides):
    route = {
        "qualified": True,
        "threshold": 0.80,
        "regime_allowed": True,
    }
    route.update(overrides)
    return route


def test_unqualified_route_cannot_emit_qualified_signal_even_at_high_probability():
    assert classify_signal_decision(None, _route(qualified=False), 0.99, data_ok=True) == "NO_TRADE_UNQUALIFIED"


def test_qualified_route_below_frozen_threshold_abstains():
    assert classify_signal_decision(None, _route(threshold=0.85), 0.84, data_ok=True) == "NO_TRADE_CONFIDENCE"


def test_regime_mismatch_abstains_before_confidence():
    assert classify_signal_decision(None, _route(regime_allowed=False), 0.99, data_ok=True) == "NO_TRADE_REGIME"


def test_data_fail_overrides_everything():
    assert classify_signal_decision(None, _route(), 0.99, data_ok=False) == "DATA_FAIL"


def test_qualified_route_above_threshold_can_emit_signal_without_future_wr_claim():
    decision = classify_signal_decision(None, _route(), 0.91, data_ok=True)
    assert decision == "QUALIFIED_SIGNAL"
    assert "80" not in decision
    assert "%" not in decision
