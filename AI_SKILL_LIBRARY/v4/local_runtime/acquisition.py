"""Just-in-time model acquisition.

Downloading a model is the one part of this runtime that reaches outside the
machine and writes something the rest of the system will later execute. So the
gate in front of it is deliberately unforgiving:

* only an approved model, at a **pinned** revision - `main` and `latest` are
  refused, because "the weights that were there on Tuesday" is not a revision;
* only with a declared size and checksum, so completion is verifiable rather
  than assumed;
* only into a disk budget that was proven before the first byte;
* only for a runtime that can actually load the result.

While bytes are landing they live in a `.partial` file that nothing else can
resolve. The artifact becomes visible in one `os.replace` after the checksum
matches, so there is no window in which a half-written file looks usable.

Failure handling splits on cause, because the two cases want opposite things: a
transport failure keeps the partial so the next attempt resumes from the
offset, while a checksum failure deletes it - resuming corrupt bytes only
rebuilds the corruption.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from .lifecycle import ModelState

#: States from which acquisition is allowed at all. A model has to have cleared
#: approval, and EVICTED/BROKEN artifacts are legitimately re-fetched.
ACQUIRABLE_STATES = frozenset(
    {ModelState.APPROVED, ModelState.AVAILABLE, ModelState.EVICTED, ModelState.DOWNLOADING, ModelState.BROKEN}
)

#: Revision strings that look pinned but move under you.
_FLOATING_REVISIONS = {"main", "master", "latest", "head", "trunk", "dev", "stable"}

_CHUNK = 1024 * 1024


class TransportError(RuntimeError):
    """The source could not be read: offline, DNS, reset, 5xx, timeout."""


class AcquisitionStatus(str, Enum):
    COMPLETED = "COMPLETED"
    ALREADY_CACHED = "ALREADY_CACHED"
    REFUSED = "REFUSED"
    FAILED_TRANSPORT = "FAILED_TRANSPORT"
    FAILED_CHECKSUM = "FAILED_CHECKSUM"
    FAILED_SIZE = "FAILED_SIZE"


@dataclass(frozen=True)
class AcquisitionRequest:
    root: Path
    model_id: str
    revision: str
    source_uri: str
    filename: str
    sha256: str | None
    size_bytes: int | None
    lifecycle_state: ModelState
    runtime: str
    supported_runtimes: frozenset[str]
    disk_budget_bytes: int | None

    # -- safety evidence ---------------------------------------------------
    #
    # Consumed, not derived. Each is a reference to a decision made elsewhere -
    # governance for licence and provenance, the safe-loader boundary for
    # format - so acquisition cannot accidentally become the place that grants
    # its own permissions. All default to the refusing value.
    artifact_format: str | None = None
    quantization: str | None = None
    license_admission_ref: str | None = None
    provenance_ref: str | None = None
    safe_format_verified: bool = False
    remote_code_allowed: bool = False
    sandbox_required: bool = True
    egress_allowed: bool = False


@dataclass(frozen=True)
class AcquisitionResult:
    model_id: str
    revision: str
    status: AcquisitionStatus
    reason: str
    path: Path | None = None
    bytes_written: int = 0
    resumed_from: int = 0
    manifest: Mapping[str, Any] | None = None

    @property
    def ok(self) -> bool:
        return self.status in (AcquisitionStatus.COMPLETED, AcquisitionStatus.ALREADY_CACHED)


# -- paths -----------------------------------------------------------------


def artifact_dir(request: AcquisitionRequest) -> Path:
    # Revision-scoped: two revisions of one model never share a directory, so a
    # supersede never overwrites weights something else is still loading.
    return Path(request.root) / "models" / request.model_id / request.revision


def artifact_path(request: AcquisitionRequest) -> Path:
    return artifact_dir(request) / request.filename


def partial_path(request: AcquisitionRequest) -> Path:
    return artifact_dir(request) / f"{request.filename}.partial"


def manifest_path(request: AcquisitionRequest) -> Path:
    return artifact_dir(request) / f"{request.filename}.manifest.json"


# -- preconditions ---------------------------------------------------------


def precondition_refusals(request: AcquisitionRequest) -> tuple[str, ...]:
    """Everything that must hold before a single byte is fetched."""
    refusals: list[str] = []
    if request.lifecycle_state not in ACQUIRABLE_STATES:
        refusals.append(
            f"lifecycle state {request.lifecycle_state.value} is not approved for acquisition"
        )
    revision = (request.revision or "").strip()
    if not revision:
        refusals.append("revision is not pinned: a revision is required")
    elif revision.lower() in _FLOATING_REVISIONS:
        refusals.append(f"revision {revision!r} is a floating ref, not a pinned revision")
    if not (request.source_uri or "").strip():
        refusals.append("official source metadata is missing: no source_uri")
    if request.size_bytes is None or request.size_bytes <= 0:
        refusals.append("artifact size is unknown: completion could not be verified")
    if not (request.sha256 or "").strip():
        refusals.append("checksum is missing: integrity could not be verified")
    if request.runtime not in request.supported_runtimes:
        refusals.append(
            f"runtime {request.runtime!r} is not in the model's supported runtimes"
        )
    if not request.safe_format_verified:
        refusals.append("safe artifact format has not been verified by the admission boundary")
    if not (request.artifact_format or "").strip():
        refusals.append("artifact_format is missing")
    if not (request.quantization or "").strip():
        refusals.append("quantization is missing")
    if not (request.license_admission_ref or "").strip():
        refusals.append("license_admission_ref is missing: no governance licence decision to consume")
    if not (request.provenance_ref or "").strip():
        refusals.append("provenance_ref is missing: no governance provenance decision to consume")
    if request.egress_allowed and request.sandbox_required:
        refusals.append("egress is allowed while a sandbox is required; the combination is refused")
    if request.size_bytes and request.disk_budget_bytes is not None:
        if request.size_bytes > request.disk_budget_bytes:
            refusals.append(
                f"disk budget exceeded: needs {request.size_bytes} B, "
                f"{request.disk_budget_bytes} B budgeted"
            )
    elif request.disk_budget_bytes is None:
        refusals.append("disk budget unknown: cannot prove the artifact fits")
    return tuple(refusals)


# -- verification ----------------------------------------------------------


def _digest(path: Path) -> str | None:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(_CHUNK), b""):
                digest.update(block)
    except OSError:
        return None
    return digest.hexdigest()


def verify_cached_artifact(request: AcquisitionRequest) -> bool:
    """Re-read a finalised artifact and confirm it still matches its manifest.

    Bit rot, a truncating disk-full, and a half-restored backup all look like a
    perfectly ordinary file until someone checks.
    """
    path, manifest = artifact_path(request), manifest_path(request)
    if not path.is_file() or not manifest.is_file():
        return False
    try:
        recorded = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not recorded.get("complete"):
        return False
    try:
        if path.stat().st_size != recorded.get("size_bytes"):
            return False
    except OSError:
        return False
    return _digest(path) == recorded.get("sha256")


def resolve_artifact(request: AcquisitionRequest, *, verify: bool = False) -> Path | None:
    """The usable artifact, or None. A partial download never resolves."""
    path, manifest = artifact_path(request), manifest_path(request)
    if not path.is_file() or not manifest.is_file():
        return None
    try:
        if not json.loads(manifest.read_text(encoding="utf-8")).get("complete"):
            return None
    except (OSError, ValueError):
        return None
    if verify and not verify_cached_artifact(request):
        return None
    return path


def _discard(*paths: Path) -> None:
    for path in paths:
        try:
            path.unlink()
        except OSError:
            pass


# -- acquisition -----------------------------------------------------------


def acquire(
    request: AcquisitionRequest,
    fetch: Callable[..., Iterable[bytes]],
    *,
    verify_cached: bool = False,
) -> AcquisitionResult:
    """Fetch, verify and publish one artifact. Never raises.

    `fetch(uri, offset=n)` yields the bytes from `n` onward, and raises
    `TransportError` when the source cannot be read.
    """
    refusals = precondition_refusals(request)
    if refusals:
        return AcquisitionResult(
            model_id=request.model_id,
            revision=request.revision,
            status=AcquisitionStatus.REFUSED,
            reason="; ".join(refusals),
        )

    existing = resolve_artifact(request, verify=verify_cached)
    if existing is not None:
        return AcquisitionResult(
            model_id=request.model_id,
            revision=request.revision,
            status=AcquisitionStatus.ALREADY_CACHED,
            reason="artifact already present and verified",
            path=existing,
            bytes_written=0,
        )

    directory = artifact_dir(request)
    partial, final, manifest = partial_path(request), artifact_path(request), manifest_path(request)
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return AcquisitionResult(
            model_id=request.model_id,
            revision=request.revision,
            status=AcquisitionStatus.FAILED_TRANSPORT,
            reason=f"cannot create cache directory: {exc}",
        )

    # A finalised-but-unverifiable artifact is corruption, not a cache hit.
    if final.exists():
        _discard(final, manifest)

    offset = partial.stat().st_size if partial.is_file() else 0
    written = offset
    try:
        with partial.open("ab" if offset else "wb") as handle:
            for chunk in fetch(request.source_uri, offset=offset):
                if not chunk:
                    continue
                handle.write(chunk)
                written += len(chunk)
            handle.flush()
            os.fsync(handle.fileno())
    except TransportError as exc:
        # Keep the partial: the next attempt picks up where this one stopped.
        return AcquisitionResult(
            model_id=request.model_id,
            revision=request.revision,
            status=AcquisitionStatus.FAILED_TRANSPORT,
            reason=str(exc),
            bytes_written=written,
            resumed_from=offset,
        )
    except OSError as exc:
        return AcquisitionResult(
            model_id=request.model_id,
            revision=request.revision,
            status=AcquisitionStatus.FAILED_TRANSPORT,
            reason=f"write failed: {exc.strerror or exc}",
            bytes_written=written,
            resumed_from=offset,
        )

    actual_size = partial.stat().st_size if partial.is_file() else 0
    if request.size_bytes is not None and actual_size != request.size_bytes:
        # Short or overlong: the source disagrees with its own metadata, and
        # neither half of that disagreement is safe to keep.
        _discard(partial)
        return AcquisitionResult(
            model_id=request.model_id,
            revision=request.revision,
            status=AcquisitionStatus.FAILED_SIZE,
            reason=f"size mismatch: expected {request.size_bytes} B, received {actual_size} B",
            bytes_written=written,
            resumed_from=offset,
        )

    digest = _digest(partial)
    if digest != request.sha256:
        _discard(partial)
        return AcquisitionResult(
            model_id=request.model_id,
            revision=request.revision,
            status=AcquisitionStatus.FAILED_CHECKSUM,
            reason=f"checksum mismatch: expected {request.sha256}, computed {digest}",
            bytes_written=written,
            resumed_from=offset,
        )

    payload = {
        "model_id": request.model_id,
        "revision": request.revision,
        "filename": request.filename,
        "source_uri": request.source_uri,
        "sha256": digest,
        "size_bytes": actual_size,
        "runtime": request.runtime,
        "complete": True,
    }
    try:
        # Rename first, manifest second: the manifest is what makes the artifact
        # resolvable, so it is written only once the bytes are already in place.
        os.replace(partial, final)
        manifest.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    except OSError as exc:
        _discard(partial, final, manifest)
        return AcquisitionResult(
            model_id=request.model_id,
            revision=request.revision,
            status=AcquisitionStatus.FAILED_TRANSPORT,
            reason=f"finalize failed: {exc.strerror or exc}",
            bytes_written=written,
            resumed_from=offset,
        )

    return AcquisitionResult(
        model_id=request.model_id,
        revision=request.revision,
        status=AcquisitionStatus.COMPLETED,
        reason="artifact verified and finalized",
        path=final,
        bytes_written=written,
        resumed_from=offset,
        manifest=payload,
    )
