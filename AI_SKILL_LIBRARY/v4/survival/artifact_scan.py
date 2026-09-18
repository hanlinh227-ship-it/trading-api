"""Task 3: artifact scan evidence parsing and fail-closed admission gate.

Trivy is optional evidence only. The adapter is invoked only when the binary is
installed; otherwise callers must supply fixture evidence. Admission fails closed
whenever evidence is missing, malformed, mismatched, or reports secrets.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


class ScanEvidenceError(ValueError):
    """Raised when scan evidence cannot be parsed or is inconsistent."""


@dataclass(frozen=True)
class ScanEvidence:
    """Normalized scan evidence for a single artifact."""

    scanner: str
    artifact_sha256: str
    vulnerabilities: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    secrets_found: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    passed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "vulnerabilities", tuple(self.vulnerabilities))
        object.__setattr__(self, "secrets_found", tuple(self.secrets_found))

    @property
    def has_secrets(self) -> bool:
        return len(self.secrets_found) > 0

    @property
    def is_clean(self) -> bool:
        return bool(self.passed) and not self.has_secrets

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scanner": self.scanner,
            "artifact_sha256": self.artifact_sha256,
            "vulnerabilities": [dict(v) for v in self.vulnerabilities],
            "secrets_found": [dict(s) for s in self.secrets_found],
            "passed": bool(self.passed),
        }


_REQUIRED_KEYS = ("scanner", "artifact_sha256", "vulnerabilities", "secrets_found", "passed")


def _coerce_sequence(value: Any, name: str) -> List[Mapping[str, Any]]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
        raise ScanEvidenceError(f"{name} must be a list of findings")
    out: List[Mapping[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ScanEvidenceError(f"{name} entries must be mappings")
        out.append(dict(item))
    return out


def parse_scan_evidence(payload: Any) -> ScanEvidence:
    """Parse raw scan evidence (mapping or JSON string) into ScanEvidence.

    Fails closed: any missing or malformed field raises ScanEvidenceError.
    """
    if isinstance(payload, (str, bytes, bytearray)):
        try:
            payload = json.loads(payload)
        except (TypeError, ValueError) as exc:
            raise ScanEvidenceError(f"scan evidence is not valid JSON: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ScanEvidenceError("scan evidence must be a mapping")
    missing = [k for k in _REQUIRED_KEYS if k not in payload]
    if missing:
        raise ScanEvidenceError(f"scan evidence missing keys: {', '.join(sorted(missing))}")
    scanner = payload["scanner"]
    if not isinstance(scanner, str) or not scanner.strip():
        raise ScanEvidenceError("scanner must be a non-empty string")
    artifact_sha256 = payload["artifact_sha256"]
    if not isinstance(artifact_sha256, str) or not artifact_sha256.strip():
        raise ScanEvidenceError("artifact_sha256 must be a non-empty string")
    passed = payload["passed"]
    if not isinstance(passed, bool):
        raise ScanEvidenceError("passed must be a boolean")
    vulnerabilities = _coerce_sequence(payload["vulnerabilities"], "vulnerabilities")
    secrets_found = _coerce_sequence(payload["secrets_found"], "secrets_found")
    return ScanEvidence(
        scanner=scanner.strip(),
        artifact_sha256=artifact_sha256.strip(),
        vulnerabilities=vulnerabilities,
        secrets_found=secrets_found,
        passed=passed,
    )


def trivy_available() -> bool:
    """True only when a Trivy binary is present on PATH."""
    return shutil.which("trivy") is not None


def scan_with_trivy(artifact_path: str, artifact_sha256: str, timeout: int = 120) -> ScanEvidence:
    """Invoke Trivy when installed; otherwise fail closed.

    Tests must not depend on this function; they use fixtures instead.
    """
    if not trivy_available():
        raise ScanEvidenceError("trivy is not installed; supply fixture evidence")
    cmd = [
        "trivy",
        "artifact",
        "--format",
        "json",
        "--quiet",
        artifact_path,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ScanEvidenceError(f"trivy invocation failed: {exc}") from exc
    if proc.returncode != 0:
        raise ScanEvidenceError(f"trivy exited with code {proc.returncode}")
    try:
        raw = json.loads(proc.stdout or "{}")
    except ValueError as exc:
        raise ScanEvidenceError(f"trivy output is not valid JSON: {exc}") from exc
    return _normalize_trivy(raw, artifact_sha256)


def _normalize_trivy(raw: Mapping[str, Any], artifact_sha256: str) -> ScanEvidence:
    vulnerabilities: List[Mapping[str, Any]] = []
    secrets_found: List[Mapping[str, Any]] = []
    results = raw.get("Results") or []
    if not isinstance(results, Iterable) or isinstance(results, (str, bytes)):
        raise ScanEvidenceError("trivy Results must be a list")
    for result in results:
        if not isinstance(result, Mapping):
            continue
        for vuln in result.get("Vulnerabilities") or []:
            if isinstance(vuln, Mapping):
                vulnerabilities.append(dict(vuln))
        for secret in result.get("Secrets") or []:
            if isinstance(secret, Mapping):
                secrets_found.append(dict(secret))
    passed = not secrets_found and not vulnerabilities
    return ScanEvidence(
        scanner="trivy",
        artifact_sha256=artifact_sha256,
        vulnerabilities=vulnerabilities,
        secrets_found=secrets_found,
        passed=passed,
    )


@dataclass(frozen=True)
class AdmissionDecision:
    """Fail-closed admission result for a protected artifact."""

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


def admit_artifact(
    artifact_sha256: str,
    evidence: Optional[ScanEvidence],
    *,
    protected: bool = True,
) -> AdmissionDecision:
    """Fail-closed admission gate for protected artifacts.

    Non-protected artifacts are admitted without scan evidence. Protected
    artifacts require clean, hash-matching evidence.
    """
    if not protected:
        return AdmissionDecision(admitted=True, reasons=())
    reasons: List[str] = []
    if not isinstance(artifact_sha256, str) or not artifact_sha256.strip():
        reasons.append("artifact hash missing")
    if evidence is None:
        reasons.append("scan evidence missing")
        return AdmissionDecision(admitted=False, reasons=reasons)
    if not isinstance(evidence, ScanEvidence):
        reasons.append("scan evidence malformed")
        return AdmissionDecision(admitted=False, reasons=reasons)
    if evidence.artifact_sha256 != artifact_sha256:
        reasons.append("scan evidence hash mismatch")
    if evidence.has_secrets:
        reasons.append("scan evidence reports secrets")
    if not evidence.passed:
        reasons.append("scan evidence did not pass")
    if not evidence.scanner:
        reasons.append("scan evidence scanner missing")
    return AdmissionDecision(admitted=not reasons, reasons=reasons)
