from engine.splits import chronological_splits


def test_splits_do_not_overlap_and_cover_all_rows():
    s = chronological_splits(list(range(100)), 0.60, 0.20)
    assert len(s.development) == 60
    assert len(s.validation) == 20
    assert len(s.holdout) == 20
    assert set(s.development).isdisjoint(s.validation)
    assert set(s.validation).isdisjoint(s.holdout)
    assert set(s.development).isdisjoint(s.holdout)
    assert sorted(s.development + s.validation + s.holdout) == list(range(100))
