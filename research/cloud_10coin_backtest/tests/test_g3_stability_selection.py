from engine.metrics import Metrics
from optimize.stability import chronological_folds, rank_stable_candidates, stability_score


def m(n, wr, exp=0.4, lo=None):
    lo = wr - 0.08 if lo is None else lo
    return Metrics(
        completed_trades=n,
        rr1_wins=int(round(n * min(1.0, wr + 0.08))),
        rr2_wins=int(round(n * wr)),
        rr1_wr=min(1.0, wr + 0.08),
        rr2_wr=wr,
        expectancy_r=exp,
        max_drawdown_r=3.0,
        max_losing_streak=3,
        wilson_low=max(0.0, lo),
        wilson_high=min(1.0, wr + 0.08),
    )


def test_chronological_folds_cover_selection_region_without_overlap():
    folds = chronological_folds(103, 5)
    assert len(folds) == 5
    assert folds[0][0] == 0
    assert folds[-1][1] == 103
    for (a, b), (c, d) in zip(folds, folds[1:]):
        assert a < b
        assert b == c
        assert c < d


def test_stability_score_prefers_consistency_over_higher_but_spiky_mean_wr():
    stable = [m(30, 0.68, 0.35, 0.56) for _ in range(5)]
    spiky = [
        m(30, 0.90, 0.75, 0.78),
        m(30, 0.90, 0.75, 0.78),
        m(30, 0.90, 0.75, 0.78),
        m(30, 0.50, -0.10, 0.35),
        m(30, 0.50, -0.10, 0.35),
    ]
    assert sum(x.rr2_wr for x in spiky) / 5 > 0.68
    assert stability_score(stable) > stability_score(spiky)


def test_rank_stable_candidates_does_not_use_validation_or_holdout_fields():
    stable_folds = [m(25, 0.70, 0.45, 0.55) for _ in range(5)]
    weak_folds = [m(25, 0.55, 0.05, 0.40) for _ in range(5)]
    rows = [
        {
            "family": "stable",
            "params": {"x": 1},
            "fold_metrics": stable_folds,
            "validation": {"rr2_wr": 0.01},
            "holdout": {"rr2_wr": 0.01},
        },
        {
            "family": "weak",
            "params": {"x": 2},
            "fold_metrics": weak_folds,
            "validation": {"rr2_wr": 1.0},
            "holdout": {"rr2_wr": 1.0},
        },
    ]
    ranked = rank_stable_candidates(rows)
    assert ranked[0]["family"] == "stable"

    rows[0]["validation"]["rr2_wr"] = 0.0
    rows[0]["holdout"]["rr2_wr"] = 0.0
    rows[1]["validation"]["rr2_wr"] = 1.0
    rows[1]["holdout"]["rr2_wr"] = 1.0
    reranked = rank_stable_candidates(rows)
    assert [r["family"] for r in reranked] == [r["family"] for r in ranked]
