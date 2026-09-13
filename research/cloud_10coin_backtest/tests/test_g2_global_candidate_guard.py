import pandas as pd

from engine.execution import OrderCandidate
from optimize.search import apply_g2_candidate_guard


def test_g2_guard_rejects_legacy_candidate_with_tiny_risk_or_excessive_cost_r():
    features = pd.DataFrame({"atr14": [1.0, 1.0]})
    tiny = OrderCandidate(0, "LONG", 100.0, 99.95, quality=0.5, family="compression")
    healthy = OrderCandidate(1, "LONG", 100.0, 99.0, quality=0.5, family="compression")

    kept = apply_g2_candidate_guard(
        [tiny, healthy],
        features,
        min_risk_atr=0.20,
        max_cost_r=0.20,
        roundtrip_cost_bps=12.0,
    )

    assert kept == [healthy]


def test_g2_guard_is_side_symmetric():
    features = pd.DataFrame({"atr14": [1.0, 1.0]})
    tiny_short = OrderCandidate(0, "SHORT", 100.0, 100.05, quality=0.5, family="compression")
    healthy_short = OrderCandidate(1, "SHORT", 100.0, 101.0, quality=0.5, family="compression")

    kept = apply_g2_candidate_guard(
        [tiny_short, healthy_short],
        features,
        min_risk_atr=0.20,
        max_cost_r=0.20,
        roundtrip_cost_bps=12.0,
    )

    assert kept == [healthy_short]
