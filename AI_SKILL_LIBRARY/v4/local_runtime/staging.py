"""Staged-artifact intake.

When acquisition cannot reach the source, the artifact can instead be placed on
disk by some other route and handed to this module. Intake then does what the
downloader would have done, with one difference that matters: it trusts the file
even less.

A downloaded artifact at least arrived from the pinned URL. A staged one arrived
from somewhere this process cannot see, so provenance is entirely carried by the
canonical evidence, and every check is run against the registry record rather
than against anything the file says about itself:

* exact `size_bytes`, byte for byte;
* SHA-256 recomputed here, from the bytes on disk, and compared to the record;
* GGUF magic and a bounded structural scan;
* declared format consistent with the filename.

A mismatch is not a retry. The staged file is quarantined - moved aside, not
silently deleted, because a file that fails its digest is evidence about how it
got there - and intake stops.

**Intake does not clear anything.** It produces verification evidence and puts a
verified artifact in the cache. Whether the *model* may run is governance's
call: `lifecycle_state` and `malware_scan_status` live in the registry, and a
successful intake of a `QUARANTINED` model leaves it exactly as quarantined as
it was. The two questions are "are these the right bytes" and "is this model
cleared to run", and this answers only the first.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping

from .identity import ArtifactIdentity, from_record
from .scanner import ScanStatus, scan_gguf

_CHUNK = 1024 * 1024


class IntakeStatus(str, Enum):
    VERIFIED = "VERIFIED"                # bytes match the canonical record
    ALREADY_CACHED = "ALREADY_CACHED"
    MISSING = "MISSING"                  # nothing staged at that path
    SIZE_MISMATCH = "SIZE_MISMATCH"
    DIGEST_MISMATCH = "DIGEST_MISMATCH"
    FORMAT_REJECTED = "FORMAT_REJECTED"  # not a well-formed artifact of its type
    IDENTITY_INCOMPLETE = "IDENTITY_INCOMPLETE"
    ERROR = "ERROR"


@dataclass(frozen=True)
class IntakeResult:
    status: IntakeStatus
    reason: str
    identity: ArtifactIdentity | None = None
    cached_path: str | None = None
    quarantined_path: str | None = None
    expected_size: int | None = None
    observed_size: int | None = None
    expected_sha256: str | None = None
    recomputed_sha256: str | None = None
    scan: Mapping[str, Any] | None = None

    @property
    def verified(self) -> bool:
        return self.status in (IntakeStatus.VERIFIED, IntakeStatus.ALREADY_CACHED)

    @property
    def digest_match(self) -> bool:
        return bool(
            self.expected_sha256
            and self.recomputed_sha256
            and self.expected_sha256 == self.recomputed_sha256
        )

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "status": self.status.value,
            "reason": self.reason,
            "verified": self.verified,
            "digest_match": self.digest_match,
            "artifact_identity": self.identity.to_dict() if self.identity else None,
            "cached_path": self.cached_path,
            "quarantined_path": self.quarantined_path,
            "expected_size_bytes": self.expected_size,
            "observed_size_bytes": self.observed_size,
            "expected_sha256": self.expected_sha256,
            "recomputed_sha256": self.recomputed_sha256,
            "structural_scan": dict(self.scan) if self.scan else None,
            # Intake answers "are these the right bytes", never "may this run".
            "clears_governance": False,
            "clears_quarantine": False,
        }


def sha256_file(path: Path, *, chunk: int = _CHUNK,
                progress: Callable[[int], None] | None = None) -> str:
    """Digest of the bytes actually on disk. Streamed, never loaded whole."""
    digest = hashlib.sha256()
    read = 0
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
            read += len(block)
            if progress:
                progress(read)
    return digest.hexdigest()


def cache_root(root: Path) -> Path:
    return Path(root) / "models"


def cached_artifact_path(root: Path, identity: ArtifactIdentity) -> Path:
    """Keyed by full identity, never by model_id alone."""
    filename = identity.artifact_filename or f"{identity.quantization}.{identity.artifact_format}"
    return cache_root(root) / identity.cache_key / filename


def manifest_path(root: Path, identity: ArtifactIdentity) -> Path:
    return cached_artifact_path(root, identity).with_suffix(
        cached_artifact_path(root, identity).suffix + ".manifest.json"
    )


def quarantine_dir(root: Path) -> Path:
    return Path(root) / "quarantine"


def _quarantine(path: Path, root: Path, identity: ArtifactIdentity | None) -> str | None:
    """Move a failed file aside. Kept, not deleted: it is evidence."""
    try:
        target_dir = quarantine_dir(root)
        target_dir.mkdir(parents=True, exist_ok=True)
        key = identity.fingerprint if identity else "unidentified"
        target = target_dir / f"{key}-{path.name}"
        shutil.move(str(path), str(target))
        return str(target)
    except OSError:
        return None


def intake_staged_artifact(
    staged_path: Path | str,
    record: Mapping[str, Any],
    *,
    root: Path | str,
    move: bool = False,
) -> IntakeResult:
    """Verify a staged file against the canonical record and cache it.

    `move=False` copies, leaving the staged file in place; the default is the
    safer one for an operator who may want to retry.
    """
    root = Path(root)
    staged = Path(staged_path)

    identity, identity_reasons = from_record(record)
    if identity is None:
        return IntakeResult(
            status=IntakeStatus.IDENTITY_INCOMPLETE,
            reason="; ".join(identity_reasons) or "artifact identity could not be built",
        )
    if identity.artifact_size_bytes is None:
        return IntakeResult(
            status=IntakeStatus.IDENTITY_INCOMPLETE,
            reason="canonical record carries no size_bytes; a staged file cannot be verified",
            identity=identity,
        )

    cached = cached_artifact_path(root, identity)
    cache_is_good = False
    if cached.is_file():
        if sha256_file(cached) == identity.artifact_sha256:
            cache_is_good = True
        else:
            # A cached file that no longer matches is corruption, not a cache hit.
            _quarantine(cached, root, identity)

    # A populated cache is not a reason to skip examining what was staged. If an
    # operator hands over a corrupt file, they need to hear that - returning
    # ALREADY_CACHED would accept bad input silently and leave them believing
    # the file they supplied was good.
    if cache_is_good and not staged.is_file():
        return IntakeResult(
            status=IntakeStatus.ALREADY_CACHED,
            reason="an artifact with this exact identity is already cached and verified",
            identity=identity, cached_path=str(cached),
            expected_size=identity.artifact_size_bytes,
            observed_size=cached.stat().st_size,
            expected_sha256=identity.artifact_sha256,
            recomputed_sha256=identity.artifact_sha256,
        )

    if not staged.is_file():
        return IntakeResult(
            status=IntakeStatus.MISSING,
            reason=f"no staged artifact at {staged}",
            identity=identity, expected_size=identity.artifact_size_bytes,
            expected_sha256=identity.artifact_sha256,
        )

    try:
        observed_size = staged.stat().st_size
    except OSError as exc:
        return IntakeResult(status=IntakeStatus.ERROR, reason=f"cannot stat staged file: {exc}",
                            identity=identity)

    if observed_size != identity.artifact_size_bytes:
        # Checked before hashing: a size mismatch is decisive and cheap, and
        # there is no reason to read a gigabyte to learn what stat already said.
        return IntakeResult(
            status=IntakeStatus.SIZE_MISMATCH,
            reason=(
                f"size mismatch: canonical record says {identity.artifact_size_bytes} B, "
                f"staged file is {observed_size} B"
            ),
            identity=identity,
            quarantined_path=_quarantine(staged, root, identity),
            expected_size=identity.artifact_size_bytes, observed_size=observed_size,
            expected_sha256=identity.artifact_sha256,
        )

    try:
        recomputed = sha256_file(staged)
    except OSError as exc:
        return IntakeResult(status=IntakeStatus.ERROR, reason=f"cannot read staged file: {exc}",
                            identity=identity)

    if recomputed != identity.artifact_sha256:
        return IntakeResult(
            status=IntakeStatus.DIGEST_MISMATCH,
            reason=(
                f"digest mismatch: canonical record says {identity.artifact_sha256}, "
                f"staged bytes hash to {recomputed}"
            ),
            identity=identity,
            quarantined_path=_quarantine(staged, root, identity),
            expected_size=identity.artifact_size_bytes, observed_size=observed_size,
            expected_sha256=identity.artifact_sha256, recomputed_sha256=recomputed,
        )

    if cache_is_good:
        # The staged file verified and the cache already holds those exact
        # bytes; there is nothing to write, but the staged file was checked.
        return IntakeResult(
            status=IntakeStatus.ALREADY_CACHED,
            reason="staged artifact verified and matches the already-cached artifact",
            identity=identity, cached_path=str(cached),
            expected_size=identity.artifact_size_bytes, observed_size=observed_size,
            expected_sha256=identity.artifact_sha256, recomputed_sha256=recomputed,
        )

    scan = None
    if identity.artifact_format == "gguf":
        scan_result = scan_gguf(staged)
        scan = scan_result.to_dict()
        if scan_result.status is not ScanStatus.PASS:
            return IntakeResult(
                status=IntakeStatus.FORMAT_REJECTED,
                reason=f"structural scan did not pass: {'; '.join(scan_result.findings)}",
                identity=identity,
                quarantined_path=_quarantine(staged, root, identity),
                expected_size=identity.artifact_size_bytes, observed_size=observed_size,
                expected_sha256=identity.artifact_sha256, recomputed_sha256=recomputed,
                scan=scan,
            )

    try:
        cached.parent.mkdir(parents=True, exist_ok=True)
        staging_copy = cached.with_suffix(cached.suffix + ".incoming")
        if move:
            shutil.move(str(staged), str(staging_copy))
        else:
            shutil.copy2(str(staged), str(staging_copy))
        # Publish in one rename, so no reader ever sees a partial file.
        os.replace(staging_copy, cached)
        manifest_path(root, identity).write_text(
            json.dumps(
                {
                    **identity.to_dict(),
                    "verified_sha256": recomputed,
                    "verified_size_bytes": observed_size,
                    "source": "staged_intake",
                    "structural_scan": scan,
                    "clears_governance": False,
                },
                indent=2, sort_keys=True,
            ),
            encoding="utf-8",
        )
    except OSError as exc:
        return IntakeResult(status=IntakeStatus.ERROR, reason=f"could not cache artifact: {exc}",
                            identity=identity, recomputed_sha256=recomputed)

    return IntakeResult(
        status=IntakeStatus.VERIFIED,
        reason="staged artifact matches the canonical record byte for byte",
        identity=identity, cached_path=str(cached),
        expected_size=identity.artifact_size_bytes, observed_size=observed_size,
        expected_sha256=identity.artifact_sha256, recomputed_sha256=recomputed,
        scan=scan,
    )


def resolve_cached(root: Path | str, record: Mapping[str, Any], *, verify: bool = True) -> Path | None:
    """The verified cached artifact for this record, or None."""
    identity, _ = from_record(record)
    if identity is None:
        return None
    path = cached_artifact_path(Path(root), identity)
    if not path.is_file():
        return None
    if verify and sha256_file(path) != identity.artifact_sha256:
        return None
    return path
