"""Per-run execution evidence.

What the evaluator reads. Non-authoritative by construction: it records what
happened and renders no verdict, so an eval harness, a latency dashboard and an
incident review can share one structure without inheriting each other's
opinion. Benchmarking belongs to the evaluation lane and none of it is here.

Three rules the structure enforces rather than documents.

**Measured, not estimated.** Durations come from a monotonic clock taken around
the real call; the scheduler's `estimated_start_s` is a planning figure and
never appears in evidence. Timestamps are UTC and separate, because a monotonic
clock is right for durations and meaningless for audit.

**Null is unknown, zero is a measurement.** `peak_vram_mb: 0.0` means the run
was measured and used no VRAM. `null` means nobody measured. Collapsing those
would let a CPU run and an unmeasured GPU run average together.

**The artifact is identified, not named.** `model_id` alone does not say which
bytes ran - `artifact_sha256`, `model_revision` and `actual_quantization` do.
`actual_quantization` is the one that was loaded, never the list a runtime
could support: "supports Q4 and Q8" does not say which produced this output.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from .resilience import FailureKind


class ExecutionFailureType(str, Enum):
    """The evaluator's normalized failure vocabulary."""

    NONE = "NONE"
    OOM = "OOM"
    TIMEOUT = "TIMEOUT"
    RUNTIME_CRASH = "RUNTIME_CRASH"
    LOAD_FAILURE = "LOAD_FAILURE"
    DOWNLOAD_FAILURE = "DOWNLOAD_FAILURE"
    CHECKSUM_FAILURE = "CHECKSUM_FAILURE"
    CAPABILITY_MISMATCH = "CAPABILITY_MISMATCH"
    NETWORK_DEPENDENCY = "NETWORK_DEPENDENCY"
    WORKER_LOSS = "WORKER_LOSS"
    PROTOCOL = "PROTOCOL"
    UNKNOWN = "UNKNOWN"


#: Internal failure kinds -> the evaluator's vocabulary. DISK_FULL and QUOTA
#: have no evaluator equivalent, so they map to the nearest honest one rather
#: than inventing a category the consumer does not know.
_FAILURE_MAP: Mapping[FailureKind, ExecutionFailureType] = {
    FailureKind.OOM: ExecutionFailureType.OOM,
    FailureKind.TIMEOUT: ExecutionFailureType.TIMEOUT,
    FailureKind.CRASH: ExecutionFailureType.RUNTIME_CRASH,
    FailureKind.NETWORK: ExecutionFailureType.NETWORK_DEPENDENCY,
    FailureKind.WORKER_LOST: ExecutionFailureType.WORKER_LOSS,
    FailureKind.PROTOCOL: ExecutionFailureType.PROTOCOL,
    FailureKind.UNSUPPORTED: ExecutionFailureType.CAPABILITY_MISMATCH,
    FailureKind.DISK_FULL: ExecutionFailureType.DOWNLOAD_FAILURE,
    FailureKind.QUOTA: ExecutionFailureType.CAPABILITY_MISMATCH,
    FailureKind.UNKNOWN: ExecutionFailureType.UNKNOWN,
}


def normalize_failure(kind: FailureKind | None) -> ExecutionFailureType:
    if kind is None:
        return ExecutionFailureType.NONE
    return _FAILURE_MAP.get(kind, ExecutionFailureType.UNKNOWN)


def _rss_mb(pid: int) -> float | None:
    """Current resident set size in MB, or None where /proc is unavailable."""
    try:
        with open(f"/proc/{pid}/status", "r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024.0
    except (OSError, ValueError, IndexError):
        return None
    return None


class PeakSampler:
    """Samples RSS on a thread so the peak is run-specific.

    A before/after snapshot is not a peak: the interesting number is the
    high-water mark *during* the run, which a model that loads, allocates and
    frees will never show at either endpoint. Sampling is best-effort - on a
    platform without /proc this yields None rather than a fabricated figure.
    """

    def __init__(self, pid: int | None = None, *, interval: float = 0.05) -> None:
        self._pid = pid or os.getpid()
        self._interval = interval
        self._peak: float | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _run(self) -> None:
        while not self._stop.is_set():
            current = _rss_mb(self._pid)
            if current is not None and (self._peak is None or current > self._peak):
                self._peak = current
            self._stop.wait(self._interval)

    def __enter__(self) -> "PeakSampler":
        self._peak = _rss_mb(self._pid)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        final = _rss_mb(self._pid)
        if final is not None and (self._peak is None or final > self._peak):
            self._peak = final

    @property
    def peak_mb(self) -> float | None:
        return None if self._peak is None else round(self._peak, 2)


@dataclass(frozen=True)
class ExecutionEvidence:
    # -- identity ----------------------------------------------------------
    worker_id: str | None = None
    model_id: str | None = None
    model_revision: str | None = None
    artifact_sha256: str | None = None
    #: The quantization actually loaded for this run, not a supported list.
    actual_quantization: str | None = None
    artifact_fingerprint: str | None = None

    # -- runtime -----------------------------------------------------------
    runtime_id: str | None = None
    runtime_version: str | None = None
    backend: str | None = None
    backend_version: str | None = None

    # -- placement ---------------------------------------------------------
    placement_action: str | None = None
    cold_or_warm_start: str | None = None

    # -- timing (milliseconds, monotonic; UTC ISO-8601 for the stamps) ------
    queue_wait_ms: float | None = None
    load_latency_ms: float | None = None
    inference_latency_ms: float | None = None
    total_latency_ms: float | None = None
    start_time: str | None = None
    end_time: str | None = None

    # -- resources ---------------------------------------------------------
    peak_ram_mb: float | None = None
    peak_vram_mb: float | None = None

    # -- tokens ------------------------------------------------------------
    tokens_input: int | None = None
    tokens_output: int | None = None

    # -- outcome -----------------------------------------------------------
    failure_type: ExecutionFailureType = ExecutionFailureType.NONE
    failure_source: str | None = None
    fallback_used: bool = False
    attempted_runtimes: tuple[str, ...] = ()
    #: Where the generated text was written. The evidence references output; it
    #: does not embed a private payload.
    real_generated_output_ref: str | None = None

    #: Never authoritative. Present so no consumer has to infer it.
    authority: bool = False

    def missing_fields(self) -> tuple[str, ...]:
        required = (
            "worker_id", "model_id", "model_revision", "artifact_sha256",
            "actual_quantization", "runtime_id", "runtime_version", "backend",
            "backend_version", "placement_action", "cold_or_warm_start",
            "load_latency_ms", "inference_latency_ms", "total_latency_ms",
            "start_time", "end_time", "peak_ram_mb",
        )
        return tuple(name for name in required if getattr(self, name) is None)

    @property
    def complete(self) -> bool:
        return not self.missing_fields()

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "execution_evidence": {
                "authority": self.authority,
                "worker_id": self.worker_id,
                "model_id": self.model_id,
                "model_revision": self.model_revision,
                "artifact_sha256": self.artifact_sha256,
                "artifact_fingerprint": self.artifact_fingerprint,
                "actual_quantization": self.actual_quantization,
                "runtime_id": self.runtime_id,
                "runtime_version": self.runtime_version,
                "backend": self.backend,
                "backend_version": self.backend_version,
                "placement_action": self.placement_action,
                "cold_or_warm_start": self.cold_or_warm_start,
                "timing": {
                    "queue_wait_ms": self.queue_wait_ms,
                    "load_latency_ms": self.load_latency_ms,
                    "inference_latency_ms": self.inference_latency_ms,
                    "total_latency_ms": self.total_latency_ms,
                    "start_time": self.start_time,
                    "end_time": self.end_time,
                },
                "resources": {"peak_ram_mb": self.peak_ram_mb, "peak_vram_mb": self.peak_vram_mb},
                "tokens": {"input": self.tokens_input, "output": self.tokens_output},
                "failure": {"kind": self.failure_type.value, "source": self.failure_source},
                "fallback_used": self.fallback_used,
                "attempted_runtimes": list(self.attempted_runtimes),
                "real_generated_output_ref": self.real_generated_output_ref,
                "complete": self.complete,
                "missing_fields": list(self.missing_fields()),
            }
        }


def _utc(epoch: float) -> str:
    import datetime

    return datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).isoformat(timespec="milliseconds")


class EvidenceRecorder:
    """Builds one `ExecutionEvidence` around a real invocation.

    Durations use `time.monotonic` because a wall clock can step backwards over
    an NTP correction and produce a negative latency. Stamps use the wall clock
    because a monotonic value is not a time anyone can audit. Both, separately.
    """

    def __init__(
        self,
        *,
        monotonic=time.monotonic,
        wall=time.time,
        admitted_at: float | None = None,
    ) -> None:
        self._monotonic = monotonic
        self._wall = wall
        self._admitted_at = admitted_at
        self._fields: dict[str, Any] = {}
        self._started: float | None = None
        self._load_done: float | None = None
        self._inference_started: float | None = None

    def describe(self, **fields: Any) -> "EvidenceRecorder":
        self._fields.update({key: value for key, value in fields.items() if value is not None})
        return self

    def begin(self, *, cold_or_warm: str, placement_action: str | None = None) -> "EvidenceRecorder":
        self._started = self._monotonic()
        self._fields["cold_or_warm_start"] = cold_or_warm
        if placement_action:
            self._fields["placement_action"] = placement_action
        self._fields["start_time"] = _utc(self._wall())
        if self._admitted_at is not None:
            self._fields["queue_wait_ms"] = round(max(0.0, (self._started - self._admitted_at) * 1000.0), 3)
        return self

    def load_finished(self) -> "EvidenceRecorder":
        if self._started is not None:
            self._load_done = self._monotonic()
            self._fields["load_latency_ms"] = round((self._load_done - self._started) * 1000.0, 3)
        return self

    def inference_started(self) -> "EvidenceRecorder":
        self._inference_started = self._monotonic()
        return self

    def finish(
        self,
        *,
        failure: FailureKind | None = None,
        failure_source: str | None = None,
        peak_ram_mb: float | None = None,
        peak_vram_mb: float | None = None,
        tokens_input: int | None = None,
        tokens_output: int | None = None,
        fallback_used: bool = False,
        attempted_runtimes: tuple[str, ...] = (),
        output_ref: str | None = None,
    ) -> ExecutionEvidence:
        end = self._monotonic()
        if self._started is not None:
            self._fields["total_latency_ms"] = round((end - self._started) * 1000.0, 3)
            anchor = self._inference_started or self._load_done or self._started
            self._fields["inference_latency_ms"] = round((end - anchor) * 1000.0, 3)
        self._fields["end_time"] = _utc(self._wall())
        return ExecutionEvidence(
            failure_type=normalize_failure(failure),
            failure_source=failure_source,
            peak_ram_mb=peak_ram_mb,
            peak_vram_mb=peak_vram_mb,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            fallback_used=fallback_used,
            attempted_runtimes=tuple(attempted_runtimes),
            real_generated_output_ref=output_ref,
            **self._fields,
        )
