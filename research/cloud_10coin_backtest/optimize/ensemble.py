from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass

from engine.execution import OrderCandidate
from optimize.selection import lock_profile


@dataclass(frozen=True)
class EnsembleMember:
    family: str
    params: dict
    profile_hash: str


@dataclass(frozen=True)
class LockedEnsemble:
    members: tuple[EnsembleMember, ...]
    ensemble_hash: str


def lock_ensemble(members) -> LockedEnsemble:
    frozen = []
    for raw in members:
        family = str(raw["family"])
        params = copy.deepcopy(raw["params"])
        locked = lock_profile({"family": family, **params})
        frozen.append(EnsembleMember(family, params, locked.profile_hash))
    payload = [{"family": m.family, "params": m.params, "profile_hash": m.profile_hash} for m in frozen]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return LockedEnsemble(tuple(frozen), digest)


def merge_candidates(candidate_sets) -> list[OrderCandidate]:
    by_signal: dict[int, OrderCandidate] = {}
    for candidates in candidate_sets:
        for c in candidates:
            current = by_signal.get(c.signal_index)
            if current is None:
                by_signal[c.signal_index] = c
                continue
            if c.quality > current.quality or (c.quality == current.quality and c.family < current.family):
                by_signal[c.signal_index] = c
    return [by_signal[i] for i in sorted(by_signal)]
