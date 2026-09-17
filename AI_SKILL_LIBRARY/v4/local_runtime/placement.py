"""Where a model can actually run, and what to say when the answer is nowhere.

The Model Mesh selects a model. This answers the separate question of whether
any worker can execute it, and the two must not be collapsed: a model can be
fully admitted, measured and mesh-eligible while no machine currently online is
able to hold it. Reporting that as "unavailable" loses the distinction that
matters, because the fix for one is admission work and the fix for the other is
a machine.

So placement resolves to a state that says which of the two it is:

  AVAILABLE_LOCAL     a serving worker on this host can run it now
  AVAILABLE_REMOTE    a serving worker elsewhere can run it now
  AVAILABLE_JIT       a worker could run it after acquiring the artifact, and
                      has the disk to do so
  REMOTE_WORKER_REQUIRED
                      admitted and measured, but nothing online meets its
                      requirement - the blocker is named, with numbers
  NO_COMPATIBLE_WORKER_ONLINE
                      a worker class exists that would fit, and none of that
                      class is currently serving
  INCOMPATIBLE_WITH_SUPPORTED_RUNTIMES
                      no supported backend can load this artifact at all, which
                      no amount of hardware fixes

**Host limits are scoped, not global.** The ephemeral container this runs in has
about 16 GB of RAM and a disk that has already hit its CRITICAL watermark. That
is a fact about this container and nothing else. A model that does not fit here
is `REMOTE_WORKER_REQUIRED`, never "infeasible" - the earlier measurements stay
exactly as they were recorded, and only the conclusion drawn from them gains the
scope it always needed.

Requirements are derived from measurement where a measurement exists. A model
that has run on this fleet has a real peak RSS and a real artifact size, and
those are used in preference to any estimate. An estimate is labelled as one.

This module decides nothing about routing or model choice. It reports capacity
and names blockers; `task_router` and the Model Mesh keep their authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from .scheduler import Privacy
from .workers import WorkerClass, WorkerRecord, WorkerRegistry, WorkerRequirement


class PlacementState(str, Enum):
    AVAILABLE_LOCAL = "AVAILABLE_LOCAL"
    AVAILABLE_REMOTE = "AVAILABLE_REMOTE"
    AVAILABLE_JIT = "AVAILABLE_JIT"
    REMOTE_WORKER_REQUIRED = "REMOTE_WORKER_REQUIRED"
    NO_COMPATIBLE_WORKER_ONLINE = "NO_COMPATIBLE_WORKER_ONLINE"
    INCOMPATIBLE_WITH_SUPPORTED_RUNTIMES = "INCOMPATIBLE_WITH_SUPPORTED_RUNTIMES"


#: States in which a request may actually be executed now or after acquisition.
EXECUTABLE_STATES = frozenset({
    PlacementState.AVAILABLE_LOCAL,
    PlacementState.AVAILABLE_REMOTE,
    PlacementState.AVAILABLE_JIT,
})

#: Runtime memory beyond the weights: KV cache plus compute buffer. Derived from
#: this fleet's own measurements rather than assumed - Qwen3-4B is a 2382 MB
#: artifact that peaked at 4738 MB, Qwen3-8B is 4794 MB and peaked at 8655 MB.
#: Used only when a model has no measured peak of its own.
RUNTIME_RAM_MULTIPLIER = 2.0

#: Free disk that must remain after an acquisition. Filling the disk to the last
#: byte breaks whatever writes next, which on this host has already happened.
DISK_HEADROOM_MB = 3000


@dataclass(frozen=True)
class ModelPlacement:
    model_id: str
    state: PlacementState
    requirement: WorkerRequirement
    worker_id: str | None
    worker_class: str | None
    requires_acquisition: bool
    ram_basis: str
    blockers: Mapping[str, tuple[str, ...]]
    note: str | None = None

    @property
    def executable(self) -> bool:
        return self.state in EXECUTABLE_STATES

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "model_id": self.model_id,
            "state": self.state.value,
            "executable": self.executable,
            "worker_id": self.worker_id,
            "worker_class": self.worker_class,
            "requires_acquisition": self.requires_acquisition,
            "requirement": {
                "runtime": self.requirement.runtime,
                "ram_mb": self.requirement.ram_mb,
                "vram_mb": self.requirement.vram_mb,
                "disk_mb": self.requirement.disk_mb,
                "artifact_format": self.requirement.artifact_format,
                "quantization": self.requirement.quantization,
                "model_family": self.requirement.model_family,
                "context": self.requirement.context,
                "privacy": self.requirement.privacy.value,
                "free_only": self.requirement.free_only,
            },
            "ram_basis": self.ram_basis,
            "blockers": {k: list(v) for k, v in sorted(self.blockers.items())},
            "note": self.note,
            # Restated on every row: this is a capacity report.
            "routing_authority": False,
            "model_selection_authority": False,
        }


def requirement_for(
    record: Mapping[str, Any],
    *,
    measured_peak_ram_mb: float | None = None,
    runtime: str = "llama.cpp",
) -> tuple[WorkerRequirement, str]:
    """What a worker must have to run this model, and where the number came from.

    A measured peak beats an estimate every time. The basis string says which
    was used, because a requirement derived from a multiplier and one derived
    from a run are different kinds of claim and a reader should not have to
    guess which they are looking at.
    """
    identity = record.get("artifact_identity") or {}
    size_bytes = int(identity.get("size_bytes") or 0)
    artifact_mb = round(size_bytes / (1024 * 1024)) if size_bytes else 0

    if measured_peak_ram_mb:
        ram_mb = int(round(measured_peak_ram_mb))
        basis = f"measured peak RSS {ram_mb} MB on this fleet"
    elif artifact_mb:
        ram_mb = int(artifact_mb * RUNTIME_RAM_MULTIPLIER)
        basis = (
            f"estimated: {artifact_mb} MB artifact x{RUNTIME_RAM_MULTIPLIER} for KV cache "
            f"and compute buffer, the ratio measured on this fleet"
        )
    else:
        ram_mb = 0
        basis = "unknown: the record declares no artifact size"

    privacy = Privacy.CONFIDENTIAL if str(
        record.get("privacy_class") or "") == "local_only" else Privacy.PUBLIC

    return (
        WorkerRequirement(
            runtime=runtime,
            ram_mb=ram_mb,
            vram_mb=0,
            privacy=privacy,
            free_only=True,
            disk_mb=artifact_mb + DISK_HEADROOM_MB if artifact_mb else 0,
            artifact_format=str(identity.get("format") or "") or None,
            quantization=str(identity.get("quantization") or "") or None,
            model_family=str(record.get("family") or "") or None,
            context=None,
        ),
        basis,
    )


def _local(worker: WorkerRecord) -> bool:
    return worker.worker_class in {WorkerClass.EPHEMERAL_LOCAL, WorkerClass.PERSISTENT_LOCAL}


def resolve(
    record: Mapping[str, Any],
    registry: WorkerRegistry,
    *,
    cached_on: Sequence[str] = (),
    measured_peak_ram_mb: float | None = None,
    runtime_incompatible: bool = False,
) -> ModelPlacement:
    """Where this model can run right now.

    `cached_on` names workers that already hold the artifact. A worker holding
    it needs no acquisition disk, so it is matched against a requirement with
    the disk clause dropped - otherwise a worker that is already running a model
    could be judged unable to run it.
    """
    model_id = str(record.get("model_id") or "<unidentified>")
    requirement, basis = requirement_for(record, measured_peak_ram_mb=measured_peak_ram_mb)

    if runtime_incompatible:
        # No machine fixes a format the backend cannot read. Reported before
        # any capacity question, because capacity is irrelevant to it.
        return ModelPlacement(
            model_id=model_id,
            state=PlacementState.INCOMPATIBLE_WITH_SUPPORTED_RUNTIMES,
            requirement=requirement,
            worker_id=None,
            worker_class=None,
            requires_acquisition=False,
            ram_basis=basis,
            blockers={},
            note="no supported backend can load this artifact; hardware is not the blocker",
        )

    resident_requirement = WorkerRequirement(
        runtime=requirement.runtime,
        ram_mb=requirement.ram_mb,
        vram_mb=requirement.vram_mb,
        privacy=requirement.privacy,
        free_only=requirement.free_only,
        disk_mb=0,
        artifact_format=requirement.artifact_format,
        quantization=requirement.quantization,
        model_family=requirement.model_family,
        context=requirement.context,
    )

    cached = set(cached_on)
    already = [w for w in registry.eligible(resident_requirement) if w.worker_id in cached]
    if already:
        local = [w for w in already if _local(w)]
        chosen = (local or already)[0]
        return ModelPlacement(
            model_id=model_id,
            state=PlacementState.AVAILABLE_LOCAL if _local(chosen) else PlacementState.AVAILABLE_REMOTE,
            requirement=resident_requirement,
            worker_id=chosen.worker_id,
            worker_class=chosen.worker_class.value,
            requires_acquisition=False,
            ram_basis=basis,
            blockers={},
            note="artifact already cached on this worker",
        )

    # Nothing holds it. A worker must have the disk to acquire it first.
    acquirers = registry.eligible(requirement)
    if acquirers:
        local = [w for w in acquirers if _local(w)]
        chosen = (local or acquirers)[0]
        return ModelPlacement(
            model_id=model_id,
            state=PlacementState.AVAILABLE_JIT,
            requirement=requirement,
            worker_id=chosen.worker_id,
            worker_class=chosen.worker_class.value,
            requires_acquisition=True,
            ram_basis=basis,
            blockers={},
            note="no worker holds the artifact; the chosen one can acquire it",
        )

    blockers = registry.refusals(requirement)
    # Distinguish "nothing is online" from "what is online cannot fit it". The
    # first is a transient state; the second is a standing requirement for a
    # machine that does not exist yet, and only the second is something an
    # operator has to go and provision.
    any_serving = any(
        worker.state.value in {"ELIGIBLE", "ACTIVE"} for worker in registry.all()
    )
    state = (PlacementState.REMOTE_WORKER_REQUIRED if any_serving
             else PlacementState.NO_COMPATIBLE_WORKER_ONLINE)
    return ModelPlacement(
        model_id=model_id,
        state=state,
        requirement=requirement,
        worker_id=None,
        worker_class=None,
        requires_acquisition=True,
        ram_basis=basis,
        blockers=blockers,
        note=(
            f"needs a worker with at least {requirement.ram_mb} MB RAM and "
            f"{requirement.disk_mb} MB free disk; none online meets that. This is a "
            f"statement about the machines currently attached, not about the model."
        ),
    )
