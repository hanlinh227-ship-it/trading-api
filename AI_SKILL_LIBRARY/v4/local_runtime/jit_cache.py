"""Acquire an artifact when a worker needs it, and make room only when safe.

A worker that must fill its disk to run a model is one download away from
breaking everything else on the machine, and this container has already hit its
CRITICAL disk watermark once. So acquisition is planned before it starts: the
space required is computed, the space available is measured, and if the two do
not meet, eviction is considered *before* a byte is fetched rather than after.

The space required is not the artifact size. It is

    artifact + staging overhead + headroom

because the bytes land somewhere before they are verified and moved, and because
a disk filled to its last byte breaks the next writer rather than this one.

**Eviction can only ever remove something that can be got back.** Four
conditions, all required, and the first is the one that matters:

* the artifact is reacquirable - a recorded source and a pinned digest exist, so
  what is deleted can be restored byte-for-byte;
* it is not the only copy anywhere, unless reacquisition is proven;
* no worker currently holds it for a running task;
* it is not the artifact being acquired.

Canonical evidence is never a candidate. Evidence is not reacquirable: a
benchmark run deleted to make room for a download is gone, and re-running it
produces a different run, not the same one.

Nothing here decides *whether* a model should be acquired. The Model Mesh
selects and placement says where; this arranges the disk for a decision already
taken, and refuses when it cannot do so safely.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence


class AcquisitionPlanState(str, Enum):
    READY = "READY"                    # room already, nothing to evict
    EVICTION_REQUIRED = "EVICTION_REQUIRED"   # room after evicting the named set
    REFUSED_INSUFFICIENT_SPACE = "REFUSED_INSUFFICIENT_SPACE"  # cannot be made to fit
    ALREADY_CACHED = "ALREADY_CACHED"  # the worker already holds these bytes


#: Space the staging copy needs beyond the final artifact. An artifact is
#: fetched, verified, then moved into the cache, so for a moment both exist.
STAGING_OVERHEAD_RATIO = 1.0

#: Free space that must remain after the acquisition completes.
SAFETY_HEADROOM_MB = 3000


@dataclass(frozen=True)
class CachedArtifact:
    digest: str
    size_mb: int
    path: str
    model_id: str
    #: A recorded source this artifact can be fetched from again. Without one,
    #: deleting it destroys the only copy.
    reacquirable_from: str | None = None
    in_use: bool = False

    @property
    def evictable(self) -> bool:
        return bool(self.reacquirable_from) and not self.in_use


@dataclass(frozen=True)
class AcquisitionPlan:
    state: AcquisitionPlanState
    digest: str
    artifact_mb: int
    required_mb: int
    available_mb: int
    evict: tuple[CachedArtifact, ...]
    freed_mb: int
    refusals: tuple[str, ...]
    protected: tuple[str, ...]

    @property
    def may_proceed(self) -> bool:
        return self.state in {AcquisitionPlanState.READY,
                              AcquisitionPlanState.EVICTION_REQUIRED,
                              AcquisitionPlanState.ALREADY_CACHED}

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "state": self.state.value,
            "may_proceed": self.may_proceed,
            "digest": self.digest,
            "artifact_mb": self.artifact_mb,
            "required_mb": self.required_mb,
            "available_mb": self.available_mb,
            "evict": [
                {"digest": a.digest, "model_id": a.model_id, "size_mb": a.size_mb,
                 "path": a.path, "reacquirable_from": a.reacquirable_from}
                for a in self.evict
            ],
            "freed_mb": self.freed_mb,
            "refusals": list(self.refusals),
            "protected_from_eviction": list(self.protected),
            "policy": {
                "staging_overhead_ratio": STAGING_OVERHEAD_RATIO,
                "safety_headroom_mb": SAFETY_HEADROOM_MB,
                "evicts_only_reacquirable": True,
                "never_evicts_evidence": True,
            },
        }


def required_space_mb(artifact_mb: int) -> int:
    """Artifact plus staging plus headroom, which is what actually has to fit."""
    return int(artifact_mb * (1 + STAGING_OVERHEAD_RATIO)) + SAFETY_HEADROOM_MB


def plan_acquisition(
    digest: str,
    artifact_mb: int,
    *,
    available_mb: int,
    cached: Sequence[CachedArtifact],
    keep: Sequence[str] = (),
) -> AcquisitionPlan:
    """Decide whether this artifact can be acquired, and at what cost.

    `keep` names digests that must survive whatever happens - typically what
    other workers are relying on. They are reported as protected rather than
    silently skipped, so a refusal can be explained.
    """
    digest = digest.lower()
    if any(item.digest.lower() == digest for item in cached):
        return AcquisitionPlan(
            state=AcquisitionPlanState.ALREADY_CACHED,
            digest=digest, artifact_mb=artifact_mb,
            required_mb=0, available_mb=available_mb,
            evict=(), freed_mb=0, refusals=(), protected=(),
        )

    required = required_space_mb(artifact_mb)
    if available_mb >= required:
        return AcquisitionPlan(
            state=AcquisitionPlanState.READY,
            digest=digest, artifact_mb=artifact_mb,
            required_mb=required, available_mb=available_mb,
            evict=(), freed_mb=0, refusals=(), protected=(),
        )

    protected: list[str] = []
    candidates: list[CachedArtifact] = []
    keep_set = {d.lower() for d in keep}
    for item in cached:
        if item.digest.lower() in keep_set:
            protected.append(f"{item.model_id}: another worker depends on it")
            continue
        if item.in_use:
            protected.append(f"{item.model_id}: currently in use")
            continue
        if not item.reacquirable_from:
            # The rule that makes eviction safe. Deleting the only copy of
            # something with no recorded source is not making room, it is losing
            # an artifact.
            protected.append(
                f"{item.model_id}: no recorded source, so deleting it would destroy "
                f"the only copy"
            )
            continue
        candidates.append(item)

    # Largest first: fewer deletions to reach the same space, so less is lost.
    candidates.sort(key=lambda item: (-item.size_mb, item.digest))
    evict: list[CachedArtifact] = []
    freed = 0
    for item in candidates:
        if available_mb + freed >= required:
            break
        evict.append(item)
        freed += item.size_mb

    if available_mb + freed < required:
        return AcquisitionPlan(
            state=AcquisitionPlanState.REFUSED_INSUFFICIENT_SPACE,
            digest=digest, artifact_mb=artifact_mb,
            required_mb=required, available_mb=available_mb,
            evict=(), freed_mb=0,
            refusals=(
                f"needs {required} MB, has {available_mb} MB, and evicting every "
                f"reacquirable artifact would free only {freed} MB",
            ),
            protected=tuple(protected),
        )

    return AcquisitionPlan(
        state=AcquisitionPlanState.EVICTION_REQUIRED,
        digest=digest, artifact_mb=artifact_mb,
        required_mb=required, available_mb=available_mb,
        evict=tuple(evict), freed_mb=freed, refusals=(),
        protected=tuple(protected),
    )


def read_cache(cache_root: Path, *, sources: Mapping[str, str] | None = None,
               in_use: Sequence[str] = ()) -> tuple[CachedArtifact, ...]:
    """What this worker currently holds, from the cache's own manifests."""
    import json

    sources = sources or {}
    busy = {d.lower() for d in in_use}
    out: list[CachedArtifact] = []
    if not cache_root.is_dir():
        return ()
    for manifest in sorted(cache_root.rglob("*.manifest.json")):
        try:
            doc = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        digest = str(doc.get("artifact_sha256") or "").lower()
        if not digest:
            continue
        size_bytes = int(doc.get("artifact_size_bytes") or 0)
        artifact = manifest.parent / manifest.name.replace(".manifest.json", "")
        out.append(CachedArtifact(
            digest=digest,
            size_mb=round(size_bytes / (1024 * 1024)) if size_bytes else 0,
            path=str(artifact),
            model_id=str(doc.get("model_id") or "<unknown>"),
            reacquirable_from=sources.get(digest),
            in_use=digest in busy,
        ))
    return tuple(out)
