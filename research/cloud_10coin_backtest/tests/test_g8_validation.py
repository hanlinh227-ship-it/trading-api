from g8.validation import cpcv_splits, purged_walk_forward


def test_purged_walk_forward_has_no_train_test_overlap():
    folds = purged_walk_forward(1000, n_splits=5, purge_bars=144, embargo_bars=12)
    assert len(folds) == 5
    for fold in folds:
        assert fold.train_idx
        assert fold.test_idx
        assert set(fold.train_idx).isdisjoint(fold.test_idx)
        assert max(fold.train_idx) < min(fold.test_idx) - 144


def test_cpcv_never_uses_blocked_rows_for_training():
    splits = cpcv_splits(1200, n_groups=6, test_groups=2, purge_bars=72, embargo_bars=12)
    assert splits
    for split in splits:
        blocked = set(split.blocked_idx)
        assert blocked.isdisjoint(split.train_idx)
        assert set(split.train_idx).isdisjoint(split.test_idx)
        assert set(split.test_idx).issubset(blocked)


def test_validation_splits_are_deterministic():
    a = cpcv_splits(600, n_groups=6, test_groups=2, purge_bars=24, embargo_bars=6)
    b = cpcv_splits(600, n_groups=6, test_groups=2, purge_bars=24, embargo_bars=6)
    assert a == b
