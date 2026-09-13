from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class LockedProfile:
    params: dict
    profile_hash: str


def lock_profile(params: dict) -> LockedProfile:
    frozen_copy = copy.deepcopy(params)
    canonical = json.dumps(frozen_copy, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return LockedProfile(frozen_copy, digest)
