"""Task 4: artifact provenance validation and fail-closed admission gate.

Cosign, CycloneDX, and SPDX outputs are treated as evidence only. No external
binaries are required; callers supply fixture evidence. Validation requires a
consistent artifact hash, signer/provenance reference, source revision, and SBOM
reference before a protected artifact may be admitted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence


class ProvenanceError(ValueError):
    """Raised when provenance evidence cannot be parsed or is inconsistent."""


@dataclass(frozen=True)
class ArtifactProvenance:
    """Normalized provenance evidence for a single artifact."""

    sha256: str
    source_revision: str
    signer_ref: str
    sbom_ref: str
    verified: bool = False

    def to_dict(self) -> dict:
        return {
            "sha256": self.sha256,
            "source_revision": self.source_revision,
            "signer_ref": self.signer_ref,
            "sbom_ref": self.sbom_ref,
            "verified": bool(self.verified),
        }


_REQUIRED_KEYS = ("sha256", "source_revision", "signer_ref", "sbom_ref", "verified")


def _require_nonempty_str(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ProvenanceError(f"{key} must be a non-empty string")
    return value.strip()


def parse_provenance(payload: Any) -> ArtifactProvenance:
    """Parse raw provenance evidence (mapping or JSON string).

    Fails closed: any missing or malformed field raises ProvenanceError.
    """
    if isinstance(payload, (str, bytes, bytearray)):
        try:
            payload = json.loads(payload)
        except (TypeError, ValueError) as exc:
            raise ProvenanceError(f"provenance is not valid JSON: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ProvenanceError("provenance must be a mapping")
    missing = [k for k in _REQUIRED_KEYS if k not in payload]
    if missing:
        raise ProvenanceError(f"provenance missing keys: {', '.join(sorted(missing))}")
    verified = payload["verified"]
    if not isinstance(verified, bool):
        raise ProvenanceError("verified must be a boolean")
    return ArtifactProvenance(
        sha256=_require_nonempty_str(payload, "sha256"),
        source_revision=_require_nonempty_str(payload, "source_revision"),
        signer_ref=_require_nonempty_str(payload, "signer_ref"),
        sbom_ref=_require_nonempty_str(payload, "sbom_ref"),
        verified=verified,
    )


def validate_provenance(
    artifact_sha256: str,
    provenance: Optional[ArtifactProvenance],
    *,
    expected_source_revision: Optional[str] = None,
    expected_signer_ref: Optional[str] = None,
    expected_sbom_ref: Optional[str] = None,
) -> Sequence[str]:
    """Return a tuple of failure reasons; empty means provenance is valid.

    Fails closed on missing, unverified, or inconsistent evidence.
    """
    reasons = []
    if not isinstance(artifact_sha256, str) or not artifact_sha256.strip():
        reasons.append("artifact hash missing")
    if provenance is None:
        reasons.append("provenance missing")
        return tuple(reasons)
    if not isinstance(provenance, ArtifactProvenance):
        reasons.append("provenance malformed")
        return tuple(reasons)
    if provenance.sha256 != artifact_sha256:
        reasons.append("provenance hash mismatch")
    if not provenance.verified:
        reasons.append("provenance unverified")
    if not provenance.signer_ref:
        reasons.append("signer reference missing")
    if not provenance.source_revision:
        reasons.append("source revision missing")
    if not provenance.sbom_ref:
        reasons.append("sbom reference missing")
    if expected_source_revision is not None and provenance.source_revision != expected_source_revision:
        reasons.append("source revision mismatch")
    if expected_signer_ref is not None and provenance.signer_ref != expected_signer_ref:
        reasons.append("signer reference mismatch")
    if expected_sbom_ref is not None and provenance.sbom_ref != expected_sbom_ref:
        reasons.append("sbom reference mismatch")
    return tuple(reasons)


@dataclass(frozen=True)
class ProvenanceDecision:
    """Fail-closed provenance admission result for a protected artifact."""

    admitted: bool
    reasons: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reasons", tuple(self.reasons))

    @property
    def routing_authority(self) -> bool:
        return False

    @property
    def reasoning_authority(self) -> bool:
        return False

    @property
    def scheduling_authority(self) -> bool:
        return False

    @property
    def merge_authority(self) -> bool:
        return False

    @property
    def deployment_authority(self) -> bool:
        return False

    @property
    def trading_authority(self) -> bool:
        return False


def admit_with_provenance(
    artifact_sha256: str,
    provenance: Optional[ArtifactProvenance],
    *,
    protected: bool = True,
    expected_source_revision: Optional[str] = None,
    expected_signer_ref: Optional[str] = None,
    expected_sbom_ref: Optional[str] = None,
) -> ProvenanceDecision:
    """Fail-closed provenance admission gate for protected artifacts."""
    if not protected:
        return ProvenanceDecision(admitted=True, reasons=())
    reasons = validate_provenance(
        artifact_sha256,
        provenance,
        expected_source_revision=expected_source_revision,
        expected_signer_ref=expected_signer_ref,
        expected_sbom_ref=expected_sbom_ref,
    )
    return ProvenanceDecision(admitted=not reasons, reasons=reasons)
