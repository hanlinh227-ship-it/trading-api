from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .solvers.base import SolverResult

_SECRET_PATTERNS = (
    re.compile(r"tb_live_[A-Za-z0-9_-]{8,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(seed phrase|mnemonic|private key)\b\s*[:=]"),
)


@dataclass(frozen=True)
class ArtifactVerification:
    passed: bool
    checks: tuple[str, ...]
    reason: str | None = None


def verify_solver_result(result: SolverResult) -> ArtifactVerification:
    checks: list[str] = []
    reference = result.artifact.reference.strip()
    if not reference:
        return ArtifactVerification(False, tuple(checks), "empty_artifact_reference")
    checks.append("non_empty_artifact")

    serialized = json.dumps(
        {"artifact": result.artifact.metadata, "evidence": result.evidence},
        default=str,
        sort_keys=True,
    )
    if any(pattern.search(serialized) for pattern in _SECRET_PATTERNS):
        return ArtifactVerification(False, tuple(checks), "secret_detected")
    checks.append("secret_scan_passed")

    if not result.evidence:
        return ArtifactVerification(False, tuple(checks), "missing_evidence")
    checks.append("evidence_present")
    return ArtifactVerification(True, tuple(checks), None)
