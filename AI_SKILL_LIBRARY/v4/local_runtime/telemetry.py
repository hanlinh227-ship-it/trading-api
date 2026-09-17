"""Runtime execution observation envelope.

What actually happened when a model answered: which revision of which artifact,
on which worker and backend, how long each phase took, how much memory it
peaked at, and how it failed if it did.

This is raw observation and nothing else. It carries no verdict, no baseline,
no champion/challenger comparison and no pass/fail - the evaluation layer
projects those from these fields later, and keeping the judgement out of here is
what lets the same envelope serve an eval harness, a latency dashboard and an
incident review without any of them inheriting another's opinion.

`None` means not measured. It is never 0, because a `peak_vram_mb` of 0 is a
real and interesting measurement (the model ran entirely on CPU) and an
unmeasured one must not be confusable with it. `missing_fields()` reports what
was not captured, so a consumer can decide whether an envelope is complete
enough for its purpose rather than silently averaging over holes.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping

from .resilience import FailureKind


class StartClass(str, Enum):
    """Whether the model had to be brought up for this task."""

    WARM = "WARM"      # already loaded; no load cost
    COLD = "COLD"      # loaded for this task
    UNKNOWN = "UNKNOWN"


#: Fields every envelope should carry for an execution that completed. Anything
#: here that is None is reported by `missing_fields()`.
REQUIRED_FOR_COMPLETE = (
    "request_id",
    "worker_id",
    "model_id",
    "family",
    "model_revision",
    "model_artifact_hash",
    "quantization",
    "runtime_id",
    "runtime_version",
    "start_class",
    "inference_latency_ms",
    "total_latency_ms",
    "start_time",
    "end_time",
    "runtime_health",
)


@dataclass(frozen=True)
class ObservationEnvelope:
    # -- identity ----------------------------------------------------------
    task_id: str
    request_id: str | None = None
    worker_id: str | None = None
    model_id: str | None = None
    family: str | None = None
    model_revision: str | None = None
    model_artifact_hash: str | None = None
    quantization: str | None = None

    # -- runtime -----------------------------------------------------------
    runtime_id: str | None = None
    runtime_version: str | None = None
    backend_version: str | None = None
    runtime_health: str | None = None

    # -- timing (milliseconds; None means not measured) --------------------
    start_class: StartClass = StartClass.UNKNOWN
    queue_wait_ms: float | None = None
    load_latency_ms: float | None = None
    inference_latency_ms: float | None = None
    total_latency_ms: float | None = None
    start_time: str | None = None
    end_time: str | None = None

    # -- resources ---------------------------------------------------------
    peak_ram_mb: float | None = None
    peak_vram_mb: float | None = None
    #: Whether the artifact was already on disk. Distinct from a warm start,
    #: which is about memory: a cache hit still pays a cold load.
    cache_hit: bool | None = None
    #: Why the model was loaded or released, for wake/sleep accounting.
    load_unload_reason: str | None = None

    # -- outcome -----------------------------------------------------------
    succeeded: bool | None = None
    fallback_used: bool = False
    #: Which runtimes were tried before this one answered.
    attempted_runtimes: tuple[str, ...] = ()
    normalized_failure_type: FailureKind | None = None
    failure_detail: str | None = None
    #: Set by the evaluation layer downstream, never by this lane. Present so
    #: the envelope has one shape whether or not a verifier has run.
    verification_status: str | None = None

    @property
    def cold_or_warm_start(self) -> str:
        """Alias for consumers that speak in those words."""
        return self.start_class.value

    @property
    def runtime(self) -> str | None:
        """Alias kept for callers that say `runtime` rather than `runtime_id`."""
        return self.runtime_id

    def missing_fields(self) -> tuple[str, ...]:
        """Required fields that were never measured."""
        return tuple(
            name
            for name in REQUIRED_FOR_COMPLETE
            if getattr(self, name) is None
            or (name == "start_class" and self.start_class is StartClass.UNKNOWN)
        )

    @property
    def complete(self) -> bool:
        return not self.missing_fields()

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "task_id": self.task_id,
            "request_id": self.request_id,
            "worker_id": self.worker_id,
            "model_id": self.model_id,
            "family": self.family,
            "model_revision": self.model_revision,
            "model_artifact_hash": self.model_artifact_hash,
            "quantization": self.quantization,
            "runtime_id": self.runtime_id,
            "runtime_version": self.runtime_version,
            "backend_version": self.backend_version,
            "runtime_health": self.runtime_health,
            "cold_or_warm_start": self.cold_or_warm_start,
            "queue_wait_ms": self.queue_wait_ms,
            "load_latency_ms": self.load_latency_ms,
            "inference_latency_ms": self.inference_latency_ms,
            "total_latency_ms": self.total_latency_ms,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "peak_ram_mb": self.peak_ram_mb,
            "peak_vram_mb": self.peak_vram_mb,
            "cache_hit": self.cache_hit,
            "load_unload_reason": self.load_unload_reason,
            "succeeded": self.succeeded,
            "verification_status": self.verification_status,
            "fallback_used": self.fallback_used,
            "attempted_runtimes": list(self.attempted_runtimes),
            "normalized_failure_type": (
                self.normalized_failure_type.value if self.normalized_failure_type else None
            ),
            "failure_detail": self.failure_detail,
            "complete": self.complete,
            "missing_fields": list(self.missing_fields()),
        }


def _iso(epoch_seconds: float) -> str:
    import datetime

    return datetime.datetime.fromtimestamp(epoch_seconds, datetime.timezone.utc).isoformat(
        timespec="milliseconds"
    )


class ObservationBuilder:
    """Accumulates one envelope across the phases of a single execution.

    Time is passed in rather than read, so an envelope is reproducible in tests
    and a worker on another machine can report its own clock without this code
    silently substituting the scheduler's.
    """

    def __init__(self, task_id: str, *, request_id: str | None = None,
                 enqueued_at: float | None = None) -> None:
        self._envelope = ObservationEnvelope(task_id=task_id, request_id=request_id)
        self._enqueued_at = enqueued_at
        self._started_at: float | None = None
        self._load_finished_at: float | None = None

    @property
    def envelope(self) -> ObservationEnvelope:
        return self._envelope

    def _update(self, **fields: Any) -> None:
        self._envelope = replace(self._envelope, **fields)

    def describe_model(
        self,
        *,
        model_id: str | None = None,
        family: str | None = None,
        revision: str | None = None,
        artifact_hash: str | None = None,
        quantization: str | None = None,
    ) -> "ObservationBuilder":
        self._update(
            model_id=model_id,
            family=family,
            model_revision=revision,
            model_artifact_hash=artifact_hash,
            quantization=quantization,
        )
        return self

    def describe_runtime(
        self,
        *,
        worker_id: str | None = None,
        runtime: str | None = None,
        runtime_version: str | None = None,
        backend_version: str | None = None,
        runtime_health: str | None = None,
    ) -> "ObservationBuilder":
        self._update(
            worker_id=worker_id,
            runtime_id=runtime,
            runtime_version=runtime_version,
            backend_version=backend_version,
            runtime_health=runtime_health,
        )
        return self

    def start(
        self,
        *,
        now: float,
        start_class: StartClass,
        cache_hit: bool | None = None,
        load_unload_reason: str | None = None,
    ) -> "ObservationBuilder":
        self._started_at = now
        queue_wait = None if self._enqueued_at is None else max(0.0, (now - self._enqueued_at) * 1000.0)
        self._update(
            start_class=start_class,
            start_time=_iso(now),
            queue_wait_ms=queue_wait,
            cache_hit=cache_hit,
            load_unload_reason=load_unload_reason,
        )
        return self

    def loaded(self, *, now: float) -> "ObservationBuilder":
        """Mark the end of the load phase. Skipped entirely for a warm start."""
        if self._started_at is not None:
            self._load_finished_at = now
            self._update(load_latency_ms=max(0.0, (now - self._started_at) * 1000.0))
        return self

    def finish(
        self,
        *,
        now: float,
        succeeded: bool,
        peak_ram_mb: float | None = None,
        peak_vram_mb: float | None = None,
        fallback_used: bool = False,
        attempted_runtimes: tuple[str, ...] = (),
        failure: FailureKind | None = None,
        failure_detail: str | None = None,
    ) -> ObservationEnvelope:
        total = None
        inference = None
        if self._started_at is not None:
            total = max(0.0, (now - self._started_at) * 1000.0)
            # Inference is what is left after the load, so a cold start's
            # inference time stays comparable with a warm one's.
            inference_start = self._load_finished_at or self._started_at
            inference = max(0.0, (now - inference_start) * 1000.0)
        self._update(
            end_time=_iso(now),
            total_latency_ms=total,
            inference_latency_ms=inference,
            succeeded=succeeded,
            peak_ram_mb=peak_ram_mb,
            peak_vram_mb=peak_vram_mb,
            fallback_used=fallback_used,
            attempted_runtimes=tuple(attempted_runtimes),
            normalized_failure_type=failure,
            failure_detail=failure_detail,
        )
        return self._envelope
