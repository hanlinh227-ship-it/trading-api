import pandas as pd

from strategies.common import make_candidates, quality_score


def _frame():
    return pd.DataFrame({
        "atr14": [1.0, 1.0],
        "body_atr": [0.6, 1.2],
        "trend_strength": [0.5, 1.5],
        "rel_volume": [0.9, 1.6],
        "flow_delta": [0.05, 0.30],
    })


def test_quality_score_ranks_stronger_signal_higher():
    f = _frame()
    q = quality_score(f, "LONG")
    assert q.iloc[1] > q.iloc[0]


def test_make_candidates_rejects_tiny_risk_and_excessive_cost_r():
    f = _frame()
    mask = pd.Series([True, True])
    entry = pd.Series([100.0, 100.0])
    stop = pd.Series([99.95, 99.0])
    q = pd.Series([0.2, 0.8])
    out = make_candidates(
        f, mask, "LONG", entry, stop,
        quality=q,
        min_risk_atr=0.20,
        max_cost_r=0.20,
        roundtrip_cost_bps=12.0,
        family="g2-test",
    )
    assert len(out) == 1
    assert out[0].quality == 0.8
    assert out[0].family == "g2-test"
