"""Safe-artifact admission at the runtime boundary.

Governance decides whether a *model* may be used. This decides whether an
*artifact file* may be handed to a loader. Those are different questions and
this lane owns only the second one.

The distinction matters because the dangerous step is local and specific:
loading weights executes a parser, and some weight formats are not just data.
A pickle-backed checkpoint runs arbitrary Python at load time, and
`trust_remote_code` hands execution to whatever the repository shipped. No
amount of upstream licence review makes those safe to load; conversely, a
format being safe says nothing about whether the licence allows use.

So this module does not re-decide governance. It consumes the admission result
the control plane produced and adds the one check that plane cannot make -
*this file, in this format, is safe for this loader to open* - and refuses when
the evidence is absent. Absent evidence is a refusal, not a warning: an
unreadable format field is exactly the case where guessing is worst.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

#: Formats whose loaders parse data and do not execute it.
SAFE_FORMATS = frozenset({"gguf", "safetensors", "ggml", "mlx"})

#: Formats that execute code at load time. Refused regardless of provenance.
EXECUTABLE_FORMATS = frozenset({"pickle", "pkl", "pt", "pth", "bin", "ckpt", "joblib", "dill", "torch"})

#: File extensions mapped to the format they imply.
EXTENSION_FORMATS: Mapping[str, str] = {
    ".gguf": "gguf",
    ".safetensors": "safetensors",
    ".ggml": "ggml",
    ".npz": "mlx",
    ".bin": "bin",
    ".pt": "pt",
    ".pth": "pth",
    ".ckpt": "ckpt",
    ".pkl": "pickle",
}


class AdmissionVerdict(str, Enum):
    ADMITTED = "ADMITTED"
    REFUSED = "REFUSED"


@dataclass(frozen=True)
class ArtifactEvidence:
    """What must be known about a file before a loader may open it.

    Every field is required. A `None` is not a permissive default - it is the
    thing `refusals()` reports.
    """

    model_id: str
    filename: str | None
    artifact_format: str | None
    sha256: str | None
    size_bytes: int | None
    quantization: str | None
    revision: str | None
    runtime: str | None
    runtime_support: frozenset[str] = frozenset()
    #: Verdicts from the governance plane, consumed rather than re-derived.
    license_verified: bool = False
    provenance_verified: bool = False
    #: Would loading this require executing repository-supplied code?
    trust_remote_code: bool = False
    custom_model_code: bool = False


@dataclass(frozen=True)
class AdmissionResult:
    model_id: str
    verdict: AdmissionVerdict
    refusals: tuple[str, ...] = ()
    resolved_format: str | None = None
    #: A refused artifact is quarantined rather than simply skipped, so the
    #: failure is recorded against the model instead of being retried forever.
    quarantine: bool = False

    @property
    def admitted(self) -> bool:
        return self.verdict is AdmissionVerdict.ADMITTED

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "model_id": self.model_id,
            "verdict": self.verdict.value,
            "refusals": list(self.refusals),
            "resolved_format": self.resolved_format,
            "quarantine": self.quarantine,
        }


def resolve_format(evidence: ArtifactEvidence) -> str | None:
    """The artifact's format, from its declaration or its extension.

    Where both are present and disagree, neither is trusted - a file called
    `.gguf` that declares itself a pickle is precisely the case to refuse.
    """
    declared = (evidence.artifact_format or "").strip().lower().lstrip(".") or None
    implied = None
    name = (evidence.filename or "").strip().lower()
    for extension, fmt in EXTENSION_FORMATS.items():
        if name.endswith(extension):
            implied = fmt
            break
    if declared and implied and declared != implied:
        return None
    return declared or implied


def evaluate(evidence: ArtifactEvidence) -> AdmissionResult:
    """Decide whether this artifact may be loaded. Never raises."""
    refusals: list[str] = []
    quarantine = False

    if not (evidence.revision or "").strip():
        refusals.append("revision is absent: the artifact is not pinned")
    if not (evidence.sha256 or "").strip():
        refusals.append("sha256 is absent: the artifact has no identity")
    if evidence.size_bytes is None or evidence.size_bytes <= 0:
        refusals.append("size_bytes is absent: the artifact has no expected length")
    if not (evidence.filename or "").strip():
        refusals.append("filename is absent")
    if not (evidence.quantization or "").strip():
        refusals.append("quantization is absent")

    if not evidence.license_verified:
        refusals.append("license is not verified by the governance plane")
    if not evidence.provenance_verified:
        refusals.append("provenance is not verified by the governance plane")

    resolved = resolve_format(evidence)
    if resolved is None:
        if evidence.artifact_format and evidence.filename:
            refusals.append(
                f"format {evidence.artifact_format!r} contradicts filename {evidence.filename!r}"
            )
            quarantine = True
        else:
            refusals.append("artifact format is unknown and cannot be inferred")
    elif resolved in EXECUTABLE_FORMATS:
        refusals.append(
            f"format {resolved!r} executes code at load time and is refused regardless of provenance"
        )
        quarantine = True
    elif resolved not in SAFE_FORMATS:
        refusals.append(f"format {resolved!r} is not on the safe-loader allowlist")

    if evidence.trust_remote_code:
        refusals.append("trust_remote_code is required; repository-supplied code is not executed here")
        quarantine = True
    if evidence.custom_model_code:
        refusals.append("artifact ships custom model code; execution is not permitted")
        quarantine = True

    if evidence.runtime and evidence.runtime_support and evidence.runtime not in evidence.runtime_support:
        refusals.append(
            f"runtime {evidence.runtime!r} is not among the artifact's supported runtimes "
            f"{sorted(evidence.runtime_support)}"
        )

    if refusals:
        return AdmissionResult(
            model_id=evidence.model_id,
            verdict=AdmissionVerdict.REFUSED,
            refusals=tuple(refusals),
            resolved_format=resolved,
            quarantine=quarantine,
        )
    return AdmissionResult(
        model_id=evidence.model_id,
        verdict=AdmissionVerdict.ADMITTED,
        resolved_format=resolved,
    )
