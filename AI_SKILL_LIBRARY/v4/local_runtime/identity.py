"""Immutable artifact identity.

The thing that has to survive every hop: registry -> active snapshot ->
ModelProfile -> AcquisitionRequest -> cache -> runtime load -> execution
evidence -> telemetry -> rollback record.

Keying on `model_id` alone is the failure this exists to prevent. "qwen3-0.6b"
is a name for a family of files that differ in the ways that matter most:
`Q4_K_M` and `Q8_0` are different weights with different memory footprints and
different output, and two revisions of the same quantization are different
bytes. A cache keyed by name serves whichever it happens to hold; an evaluation
keyed by name compares results from artifacts that were never the same thing.

So identity here is the tuple that actually distinguishes one file from
another - family, variant, immutable revision, format, quantization, and the
content hash - and `fingerprint` is its stable short form for use as a cache
key, an evidence reference and a telemetry field.

Everything is required except `size_bytes`, and nothing is inferred. An
identity that cannot be fully constructed is not constructed: `from_record`
returns the missing field names instead of an object with holes in it.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Mapping

#: Revision strings that look pinned but move.
FLOATING_REVISIONS = frozenset({"main", "master", "latest", "head", "trunk", "dev", "stable"})

#: A sha256 in hex.
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

#: Fields that must be present and well-formed for an identity to exist.
REQUIRED_FIELDS = (
    "model_id",
    "family",
    "variant",
    "immutable_revision",
    "artifact_sha256",
    "artifact_format",
    "quantization",
)


class IdentityError(ValueError):
    """An identity that cannot be constructed from what was supplied."""


@dataclass(frozen=True)
class ArtifactIdentity:
    model_id: str
    family: str
    variant: str
    immutable_revision: str
    artifact_sha256: str
    artifact_format: str
    quantization: str
    artifact_size_bytes: int | None = None
    artifact_filename: str | None = None

    def __post_init__(self) -> None:
        for name in REQUIRED_FIELDS:
            if not str(getattr(self, name) or "").strip():
                raise IdentityError(f"{name} is required for an artifact identity")
        revision = self.immutable_revision.strip().lower()
        if revision in FLOATING_REVISIONS:
            raise IdentityError(
                f"immutable_revision {self.immutable_revision!r} is a floating ref, not a revision"
            )
        if not _SHA256.match(self.artifact_sha256.strip().lower()):
            raise IdentityError("artifact_sha256 must be a 64-character hex sha256 digest")
        if self.artifact_size_bytes is not None and self.artifact_size_bytes <= 0:
            raise IdentityError("artifact_size_bytes must be positive when present")

    @property
    def fingerprint(self) -> str:
        """Stable short key over everything that distinguishes this artifact.

        Derived, never stored: two identities are the same artifact exactly when
        every distinguishing field matches, so the fingerprint cannot drift away
        from the thing it identifies.
        """
        material = "|".join(
            (
                self.model_id,
                self.family,
                self.variant,
                self.immutable_revision,
                self.artifact_format.lower(),
                self.quantization,
                self.artifact_sha256.lower(),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]

    @property
    def cache_key(self) -> str:
        """Filesystem-safe key. Never `model_id` alone."""
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", f"{self.model_id}-{self.quantization}")
        return f"{safe}@{self.immutable_revision[:16]}-{self.fingerprint[:12]}"

    def matches(self, other: "ArtifactIdentity") -> bool:
        return self.fingerprint == other.fingerprint

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "model_id": self.model_id,
            "family": self.family,
            "variant": self.variant,
            "immutable_revision": self.immutable_revision,
            "artifact_sha256": self.artifact_sha256,
            "artifact_format": self.artifact_format,
            "quantization": self.quantization,
            "artifact_size_bytes": self.artifact_size_bytes,
            "artifact_filename": self.artifact_filename,
            "fingerprint": self.fingerprint,
            "cache_key": self.cache_key,
        }


def artifact_block(record: Mapping[str, Any]) -> Mapping[str, Any]:
    """The record's artifact fields, from whichever shape the row uses.

    The canonical registry nests them under `artifact_identity:`, which is what
    `admission_policy.yaml` names as the source. Earlier shapes used `artifact:`
    or flat `artifact_*` keys. All three are read, newest first, so a schema
    revision never silently strips an identity down to a bare model name -
    losing a quantization or a revision here would let two different artifacts
    share one cache entry.
    """
    for key in ("artifact_identity", "artifact"):
        nested = record.get(key)
        if isinstance(nested, Mapping):
            return nested
    return {
        "filename": record.get("artifact_filename") or record.get("filename"),
        "format": record.get("artifact_format"),
        "sha256": record.get("artifact_sha256") or record.get("artifact_hash"),
        "size_bytes": record.get("artifact_size_bytes"),
        "quantization": record.get("quantization"),
    }


def _identity_mapping(record: Mapping[str, Any]) -> Mapping[str, Any]:
    artifact = artifact_block(record)
    return {
        # The identity block carries its own copies of these. They are the
        # authority when present, because the policy names that block as the
        # identity source; the row-level values are a fallback.
        "model_id": artifact.get("model_id") or record.get("model_id"),
        "family": artifact.get("family") or record.get("family"),
        "variant": artifact.get("variant") or record.get("variant"),
        "immutable_revision": (
            artifact.get("immutable_revision")
            or record.get("immutable_revision")
            or record.get("upstream_revision")
        ),
        "artifact_sha256": artifact.get("sha256"),
        "artifact_format": artifact.get("format"),
        "quantization": artifact.get("quantization") or record.get("quantization"),
    }


def missing_identity_fields(record: Mapping[str, Any]) -> tuple[str, ...]:
    """Which identity fields a registry row does not carry."""
    return tuple(name for name, value in _identity_mapping(record).items() if not str(value or "").strip())


def from_record(record: Mapping[str, Any]) -> tuple["ArtifactIdentity | None", tuple[str, ...]]:
    """Build an identity from a registry row, or report why it cannot be built.

    Returns `(None, reasons)` rather than raising: an incomplete row is the
    ordinary case today, not an exceptional one.
    """
    missing = missing_identity_fields(record)
    if missing:
        return None, tuple(f"artifact identity field {name} is absent" for name in missing)

    # The row states its revision in more than one place. If the copies ever
    # disagree, that is a corrupt row, not a preference to resolve - picking one
    # would silently pin a different artifact than the record describes.
    artifact = artifact_block(record)
    revisions = {
        str(value).strip()
        for value in (
            record.get("upstream_revision"),
            record.get("immutable_revision"),
            artifact.get("immutable_revision"),
        )
        if str(value or "").strip()
    }
    if len(revisions) > 1:
        return None, (f"revision fields disagree: {sorted(revisions)}",)

    # Same for identity fields duplicated between the row and the block.
    for row_key, block_key in (("model_id", "model_id"), ("family", "family"), ("variant", "variant")):
        row_value = str(record.get(row_key) or "").strip()
        block_value = str(artifact.get(block_key) or "").strip()
        if row_value and block_value and row_value != block_value:
            return None, (
                f"{row_key} disagrees between record ({row_value!r}) and identity block "
                f"({block_value!r})",
            )

    fields = _identity_mapping(record)
    try:
        identity = ArtifactIdentity(
            model_id=str(fields["model_id"]),
            family=str(fields["family"]),
            variant=str(fields["variant"]),
            immutable_revision=str(fields["immutable_revision"]),
            artifact_sha256=str(fields["artifact_sha256"]).lower(),
            artifact_format=str(fields["artifact_format"]).lower().lstrip("."),
            quantization=str(fields["quantization"]),
            artifact_size_bytes=artifact.get("size_bytes"),
            artifact_filename=artifact.get("filename"),
        )
    except IdentityError as exc:
        return None, (str(exc),)
    return identity, ()
