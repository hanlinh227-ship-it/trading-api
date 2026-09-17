"""Model artifact cache and eviction.

Disk is the one resource the personal AI federation runs out of quietly: a few
hundred gigabytes of weights accumulate without anything failing, right up
until a download cannot finalize. So eviction is continuous and scored rather
than a panic at the end.

Two boundaries matter more than the scoring:

* **Only weights are evictable.** Quantizations, adapters and embedding models
  are weights too; registry history, evidence and manifests are not. Deleting
  those to reclaim space would trade a re-downloadable file for a record that
  cannot be recovered at all.
* **Nothing in use is touched.** A loaded, pinned or in-flight artifact is off
  the table at any disk pressure, because freeing space by yanking the weights
  out from under a running task costs more than the space is worth.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence

from .lifecycle import LOADED_STATES, ModelState
from .resources import ResourceSnapshot

_MB = 1024 * 1024


class ArtifactKind(str, Enum):
    WEIGHTS = "WEIGHTS"
    QUANTIZATION = "QUANTIZATION"
    ADAPTER = "ADAPTER"
    EMBEDDING = "EMBEDDING"
    #: Canonical, non-reconstructable record. Never evicted.
    REGISTRY_HISTORY = "REGISTRY_HISTORY"
    EVIDENCE = "EVIDENCE"


#: Weight-class artifacts: re-acquirable from an official source at a pinned
#: revision, therefore safe to delete.
EVICTABLE_KINDS = frozenset(
    {ArtifactKind.WEIGHTS, ArtifactKind.QUANTIZATION, ArtifactKind.ADAPTER, ArtifactKind.EMBEDDING}
)


@dataclass(frozen=True)
class CachePolicy:
    #: Fraction of the disk kept free. Below this, eviction runs without anyone
    #: having to ask for space.
    target_free_ratio: float = 0.15
    #: Idle time at which the recency term reaches half its range.
    recency_half_life_seconds: float = 7 * 86_400.0
    #: Use count at which the rarity term bottoms out.
    use_count_reference: int = 500
    #: Artifact size at which the size term reaches half its range.
    size_reference_bytes: int = 16_000 * _MB
    #: A superseded artifact is dead weight whatever its other scores say.
    superseded_bonus: float = 1.0
    weights: Mapping[str, float] = field(
        default_factory=lambda: {
            "recency": 0.30,       # how long since anything wanted it
            "rarity": 0.15,        # how seldom it has been wanted
            "size": 0.20,          # how much reclaiming it actually buys
            "quality": 0.15,       # protect the models that answer well
            "specialization": 0.10,  # protect the only model that can do a thing
            "replacement": 0.10,   # prefer artifacts something else can cover
        }
    )


@dataclass(frozen=True)
class CacheEntry:
    model_id: str
    revision: str
    kind: ArtifactKind
    size_bytes: int
    idle_seconds: float
    use_count: int
    quality: float
    state: ModelState
    #: 0..1 - how specialized this model is for work nothing else covers.
    specialization_score: float = 0.0
    #: Another cached model could take its traffic.
    replacement_available: bool = True
    #: Held by policy or by the user; eviction may not consider it.
    pinned: bool = False
    in_flight: int = 0


@dataclass(frozen=True)
class EvictionAction:
    model_id: str
    revision: str
    source: ModelState
    target: ModelState
    freed_bytes: int
    score: float
    reason: str


def is_evictable(entry: CacheEntry) -> bool:
    if entry.kind not in EVICTABLE_KINDS:
        return False
    if entry.pinned or entry.in_flight > 0:
        return False
    if entry.state in LOADED_STATES:
        return False
    # Only states from which EVICTED is a legal lifecycle hop.
    return entry.state in (ModelState.CACHED, ModelState.SLEEPING, ModelState.SUPERSEDED, ModelState.BROKEN,
                           ModelState.QUARANTINED)


def reclaimable_bytes(entries: Sequence[CacheEntry]) -> int:
    """Space eviction could actually free right now."""
    return sum(entry.size_bytes for entry in entries if is_evictable(entry))


def eviction_score(entry: CacheEntry, policy: CachePolicy | None = None) -> float:
    """How evictable this artifact is. Higher goes first."""
    policy = policy or CachePolicy()
    weights = policy.weights

    idle = max(0.0, entry.idle_seconds)
    recency = idle / (idle + policy.recency_half_life_seconds)

    ceiling = math.log1p(max(1, policy.use_count_reference))
    rarity = 1.0 - min(1.0, math.log1p(max(0, entry.use_count)) / ceiling)

    size = entry.size_bytes / (entry.size_bytes + policy.size_reference_bytes) if entry.size_bytes else 0.0

    quality = 1.0 - min(1.0, max(0.0, entry.quality))
    specialization = 1.0 - min(1.0, max(0.0, entry.specialization_score))
    replacement = 1.0 if entry.replacement_available else 0.0

    score = (
        weights["recency"] * recency
        + weights["rarity"] * rarity
        + weights["size"] * size
        + weights["quality"] * quality
        + weights["specialization"] * specialization
        + weights["replacement"] * replacement
    )
    if entry.state is ModelState.SUPERSEDED:
        score += policy.superseded_bonus
    return score


def _disk_shortfall_bytes(snapshot: ResourceSnapshot, policy: CachePolicy) -> int:
    """Bytes short of the target free ratio, or 0 when the disk is unreadable.

    An unknown disk is not evidence of pressure. Evicting on a guess would
    delete weights to solve a problem that may not exist.
    """
    if snapshot.disk_total_mb is None or snapshot.disk_free_mb is None:
        return 0
    desired_mb = snapshot.disk_total_mb * policy.target_free_ratio
    return max(0, int((desired_mb - snapshot.disk_free_mb) * _MB))


def plan_eviction(
    entries: Sequence[CacheEntry],
    need_bytes: int,
    snapshot: ResourceSnapshot,
    policy: CachePolicy | None = None,
) -> tuple[EvictionAction, ...]:
    """Pick artifacts to delete to satisfy `need_bytes` plus any disk shortfall.

    Returns as much as it can and stops; a shortfall it cannot cover is visible
    in the freed total rather than raised, so the caller can decide whether to
    refuse the acquisition that prompted it.
    """
    policy = policy or CachePolicy()
    target = max(int(need_bytes), _disk_shortfall_bytes(snapshot, policy))
    if target <= 0:
        return ()

    scored = sorted(
        ((entry, eviction_score(entry, policy)) for entry in entries if is_evictable(entry)),
        key=lambda pair: pair[1],
        reverse=True,
    )

    actions: list[EvictionAction] = []
    freed = 0
    for entry, score in scored:
        if freed >= target:
            break
        freed += entry.size_bytes
        actions.append(
            EvictionAction(
                model_id=entry.model_id,
                revision=entry.revision,
                source=entry.state,
                target=ModelState.EVICTED,
                freed_bytes=entry.size_bytes,
                score=round(score, 6),
                reason=(
                    f"eviction score {score:.3f}: idle {entry.idle_seconds / 3600:.1f}h, "
                    f"{entry.use_count} use(s), {entry.size_bytes // _MB} MB"
                ),
            )
        )
    return tuple(actions)
