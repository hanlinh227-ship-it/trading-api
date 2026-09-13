from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations


@dataclass(frozen=True)
class TimeFold:
    train_idx: tuple[int, ...]
    test_idx: tuple[int, ...]
    blocked_idx: tuple[int, ...]


def _validate_common(n: int, purge_bars: int, embargo_bars: int) -> None:
    if int(n) <= 0:
        raise ValueError("n must be positive")
    if int(purge_bars) < 0 or int(embargo_bars) < 0:
        raise ValueError("purge_bars and embargo_bars must be non-negative")


def _group_bounds(n: int, groups: int) -> list[tuple[int, int]]:
    if int(groups) <= 0 or int(groups) > int(n):
        raise ValueError("invalid group count")
    base, extra = divmod(int(n), int(groups))
    bounds: list[tuple[int, int]] = []
    start = 0
    for i in range(int(groups)):
        size = base + (1 if i < extra else 0)
        end = start + size
        bounds.append((start, end))
        start = end
    return bounds


def purged_walk_forward(
    n: int,
    *,
    n_splits: int,
    purge_bars: int,
    embargo_bars: int,
) -> list[TimeFold]:
    _validate_common(n, purge_bars, embargo_bars)
    if int(n_splits) <= 0:
        raise ValueError("n_splits must be positive")
    bounds = _group_bounds(int(n), int(n_splits) + 1)
    folds: list[TimeFold] = []
    for split_id in range(1, len(bounds)):
        test_start, test_end = bounds[split_id]
        train_end = max(0, test_start - int(purge_bars))
        train = tuple(range(0, train_end))
        test = tuple(range(test_start, test_end))
        blocked_start = train_end
        blocked_end = min(int(n), test_end + int(embargo_bars))
        blocked = tuple(range(blocked_start, blocked_end))
        if not train or not test:
            raise ValueError("insufficient rows for requested purged walk-forward split")
        folds.append(TimeFold(train, test, blocked))
    return folds


def cpcv_splits(
    n: int,
    *,
    n_groups: int,
    test_groups: int,
    purge_bars: int,
    embargo_bars: int,
) -> list[TimeFold]:
    _validate_common(n, purge_bars, embargo_bars)
    n_groups = int(n_groups)
    test_groups = int(test_groups)
    if n_groups < 2 or test_groups <= 0 or test_groups >= n_groups:
        raise ValueError("invalid CPCV group configuration")
    bounds = _group_bounds(int(n), n_groups)
    all_idx = set(range(int(n)))
    result: list[TimeFold] = []
    for chosen in combinations(range(n_groups), test_groups):
        test_set: set[int] = set()
        blocked: set[int] = set()
        for group_id in chosen:
            start, end = bounds[group_id]
            test_set.update(range(start, end))
            blocked_start = max(0, start - int(purge_bars))
            blocked_end = min(int(n), end + int(purge_bars) + int(embargo_bars))
            blocked.update(range(blocked_start, blocked_end))
        blocked.update(test_set)
        train_set = all_idx - blocked
        if not train_set or not test_set:
            continue
        result.append(
            TimeFold(
                train_idx=tuple(sorted(train_set)),
                test_idx=tuple(sorted(test_set)),
                blocked_idx=tuple(sorted(blocked)),
            )
        )
    if not result:
        raise ValueError("CPCV configuration produced no valid split")
    return result
