from dataclasses import fields

from g8.candidate import CandidateSpec, candidate_hash, mutate_candidate, seed_baseline_candidates


def test_mutation_is_deterministic_for_same_seed():
    parent = seed_baseline_candidates("BTCUSDT")[0]
    a = mutate_candidate(parent, seed=77, budget=6)
    b = mutate_candidate(parent, seed=77, budget=6)
    assert [candidate_hash(x) for x in a] == [candidate_hash(x) for x in b]


def test_candidate_hash_changes_when_geometry_changes():
    parent = seed_baseline_candidates("BTCUSDT")[0]
    child = parent.with_updates(risk_atr=parent.risk_atr + 0.4)
    assert candidate_hash(parent) != candidate_hash(child)


def test_each_mutation_changes_only_one_typed_dimension():
    parent = seed_baseline_candidates("BTCUSDT")[0]
    children = mutate_candidate(parent, seed=12, budget=8)
    assert children
    for child in children:
        changed = []
        for field in fields(CandidateSpec):
            if field.name == "parent_hash":
                continue
            if getattr(parent, field.name) != getattr(child, field.name):
                changed.append(field.name)
        assert len(changed) == 1
        assert child.parent_hash == candidate_hash(parent)


def test_mutation_dedupes_candidate_hashes():
    parent = seed_baseline_candidates("BTCUSDT")[0]
    children = mutate_candidate(parent, seed=99, budget=50)
    hashes = [candidate_hash(x) for x in children]
    assert len(hashes) == len(set(hashes))
