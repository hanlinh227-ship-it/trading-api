from g8.candidate import candidate_hash, seed_baseline_candidates
from g9.hypothesis import FailureMemory, generate_hypotheses


def test_hypothesis_generation_is_deterministic_bounded_and_single_dimension(tmp_path):
    parent = seed_baseline_candidates("BTCUSDT")[0]
    memory = FailureMemory(tmp_path / "failures.jsonl")
    first = generate_hypotheses(
        parent,
        research_dimension="calibration",
        seed=91,
        budget=3,
        failure_memory=memory,
    )
    second = generate_hypotheses(
        parent,
        research_dimension="calibration",
        seed=91,
        budget=3,
        failure_memory=memory,
    )
    assert [item.hypothesis_hash for item in first] == [item.hypothesis_hash for item in second]
    assert len(first) <= 3
    assert all(len(item.changed_fields) == 1 for item in first)
    assert all(item.parent_hash == candidate_hash(parent) for item in first)


def test_failure_memory_blocks_equivalent_rejected_hypothesis(tmp_path):
    parent = seed_baseline_candidates("SOLUSDT")[0]
    memory = FailureMemory(tmp_path / "failures.jsonl")
    original = generate_hypotheses(
        parent,
        research_dimension="regime",
        seed=7,
        budget=2,
        failure_memory=memory,
    )
    assert original
    memory.record_rejection(original[0].hypothesis_hash, reason="UNSTABLE_FOLDS")

    repeated = generate_hypotheses(
        parent,
        research_dimension="regime",
        seed=7,
        budget=2,
        failure_memory=memory,
    )
    assert original[0].hypothesis_hash not in {item.hypothesis_hash for item in repeated}
