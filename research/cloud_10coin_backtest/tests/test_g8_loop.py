import pandas as pd

from g8.fitness import TrialMetrics
from g8.loop import run_generation


def _feature_provider(symbol, start, end, config):
    return pd.DataFrame({"close": [100.0, 100.1, 100.2]})


def _evaluator(symbol, features, config, candidate):
    return TrialMetrics.good_example(
        trades=140,
        rr2_wr=0.70,
        worst_fold_wr=0.66,
        wilson_lower=0.62,
        expectancy_r=0.75,
        cost_stress_expectancy_r=0.55,
    )


def test_generation_never_exceeds_candidate_budget(tmp_path):
    result = run_generation(
        ["BTCUSDT"],
        "2025-01-01",
        "2025-03-01",
        tmp_path / "state",
        tmp_path / "results",
        candidate_budget=3,
        source_sha="abc",
        feature_provider=_feature_provider,
        evaluator_fn=_evaluator,
    )
    assert result.trials_attempted["BTCUSDT"] <= 3
    assert (tmp_path / "state" / "checkpoint.json").exists()
    assert (tmp_path / "state" / "trials.jsonl").exists()
    assert (tmp_path / "state" / "champions.json").exists()


def test_second_generation_resumes_from_checkpoint(tmp_path):
    first = run_generation(
        ["BTCUSDT"],
        "2025-01-01",
        "2025-03-01",
        tmp_path / "state",
        tmp_path / "results",
        candidate_budget=2,
        source_sha="abc",
        feature_provider=_feature_provider,
        evaluator_fn=_evaluator,
    )
    second = run_generation(
        ["BTCUSDT"],
        "2025-01-01",
        "2025-03-01",
        tmp_path / "state",
        tmp_path / "results",
        candidate_budget=2,
        source_sha="def",
        feature_provider=_feature_provider,
        evaluator_fn=_evaluator,
    )
    assert second.generation == first.generation + 1
    assert second.previous_snapshot_hash == first.snapshot_hash


def test_new_data_cutoff_starts_new_evidence_epoch(tmp_path):
    first = run_generation(
        ["BTCUSDT"], "2025-01-01", "2025-03-01",
        tmp_path / "state", tmp_path / "results",
        candidate_budget=1, source_sha="abc",
        feature_provider=_feature_provider, evaluator_fn=_evaluator,
    )
    second = run_generation(
        ["BTCUSDT"], "2025-01-01", "2025-03-02",
        tmp_path / "state", tmp_path / "results",
        candidate_budget=1, source_sha="abc",
        feature_provider=_feature_provider, evaluator_fn=_evaluator,
    )
    assert second.evidence_epoch_id != first.evidence_epoch_id
