"""Governance clearance from real evidence.

The registry row for a new model starts quarantined with
`malware_scan_status: not_run`, and something has to move it. This module is
that something - it runs the checks, records exactly what ran, and proposes a
registry update built only from results it actually obtained.

The distinction it exists to hold is between two things that look alike:

* a **structural scan** parses the container and proves it is well-formed. It is
  real evidence, it is cheap, and it catches the malformed-header class of
  attack. It is not a malware scan and cannot stand in for one.
* a **signature scan** needs a real engine with real definitions. If no engine
  is installed, the honest result is `not_run`, not `pass`.

So `malware_scan_status` is set to `pass` only when a signature engine actually
ran and actually passed. With no engine present this module records which
engines it looked for, leaves the status at `not_run`, and **refuses to clear**.
That refusal is the feature. A clearance tool that quietly upgrades "nobody
looked" into "looks fine" is worse than no tool, because it launders an absence
of evidence into a positive finding and does it at machine speed.

Nothing here writes the registry on its own. It returns a proposed update and
the evidence behind it; applying it is a separate, explicit act.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .scanner import ScanStatus, scan_gguf

#: Signature engines this module knows how to drive, in preference order.
SIGNATURE_ENGINES = ("clamdscan", "clamscan")

#: Exit codes for the ClamAV family.
_CLAM_CLEAN = 0
_CLAM_INFECTED = 1


class ClearanceStatus(str, Enum):
    CLEARED = "CLEARED"                    # every check ran and passed
    #: Every runnable check passed, and an operator accepted the named gap that
    #: could not be checked here. A decision, recorded as one.
    CLEARED_WITH_ACCEPTED_RISK = "CLEARED_WITH_ACCEPTED_RISK"
    BLOCKED_INFECTED = "BLOCKED_INFECTED"  # a signature engine found something
    BLOCKED_MALFORMED = "BLOCKED_MALFORMED"  # structural scan failed
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"  # a required check could not run
    NO_ARTIFACT = "NO_ARTIFACT"


@dataclass(frozen=True)
class ScanEvidence:
    check: str
    ran: bool
    passed: bool | None
    engine: str | None = None
    detail: str | None = None

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "check": self.check, "ran": self.ran, "passed": self.passed,
            "engine": self.engine, "detail": self.detail,
        }


@dataclass(frozen=True)
class ClearanceResult:
    status: ClearanceStatus
    reason: str
    evidence: tuple[ScanEvidence, ...] = ()
    #: Registry fields this result justifies. Empty unless CLEARED.
    proposed_registry_update: Mapping[str, Any] = field(default_factory=dict)
    #: Engines looked for but not installed.
    engines_unavailable: tuple[str, ...] = ()

    #: The acceptance record, when one was used.
    risk_acceptance: Mapping[str, Any] | None = None

    @property
    def cleared(self) -> bool:
        return self.status in (
            ClearanceStatus.CLEARED, ClearanceStatus.CLEARED_WITH_ACCEPTED_RISK
        )

    @property
    def cleared_by_evidence_only(self) -> bool:
        return self.status is ClearanceStatus.CLEARED

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "status": self.status.value,
            "reason": self.reason,
            "cleared": self.cleared,
            "cleared_by_evidence_only": self.cleared_by_evidence_only,
            "risk_acceptance": dict(self.risk_acceptance) if self.risk_acceptance else None,
            "evidence": [e.to_dict() for e in self.evidence],
            "proposed_registry_update": dict(self.proposed_registry_update),
            "engines_unavailable": list(self.engines_unavailable),
            # A structural pass is never on its own a malware clearance.
            "structural_scan_is_not_a_malware_scan": True,
        }


def _default_which(name: str) -> str | None:
    return shutil.which(name)


def _default_run(argv: Sequence[str], timeout: float = 600.0) -> tuple[int, str]:
    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
        list(argv), capture_output=True, text=True, timeout=timeout, check=False
    )
    return completed.returncode, f"{completed.stdout}\n{completed.stderr}".strip()


def find_signature_engine(which: Callable[[str], str | None] = _default_which) -> str | None:
    for name in SIGNATURE_ENGINES:
        try:
            if which(name):
                return name
        except Exception:  # noqa: BLE001 - a failing lookup is "not installed"
            continue
    return None


def run_signature_scan(
    path: Path,
    *,
    which: Callable[[str], str | None] = _default_which,
    run: Callable[..., tuple[int, str]] = _default_run,
) -> ScanEvidence:
    """Drive a real signature engine, or report honestly that none exists."""
    engine = find_signature_engine(which)
    if engine is None:
        return ScanEvidence(
            check="signature_scan", ran=False, passed=None,
            detail=f"no signature engine installed (looked for: {', '.join(SIGNATURE_ENGINES)})",
        )
    try:
        code, output = run([engine, "--no-summary", str(path)])
    except Exception as exc:  # noqa: BLE001 - an engine that will not run has not run
        return ScanEvidence(check="signature_scan", ran=False, passed=None, engine=engine,
                            detail=f"{type(exc).__name__}: {exc}")
    if code == _CLAM_CLEAN:
        return ScanEvidence(check="signature_scan", ran=True, passed=True, engine=engine,
                            detail="no signatures matched")
    if code == _CLAM_INFECTED:
        return ScanEvidence(check="signature_scan", ran=True, passed=False, engine=engine,
                            detail=output[:500] or "signature match")
    # Any other exit is an engine error, which is not a pass.
    return ScanEvidence(check="signature_scan", ran=False, passed=None, engine=engine,
                        detail=f"engine exited {code}: {output[:300]}")


def run_structural_scan(path: Path, artifact_format: str) -> ScanEvidence:
    if artifact_format.lower() != "gguf":
        return ScanEvidence(check="structural_scan", ran=False, passed=None,
                            detail=f"no structural parser for format {artifact_format!r}")
    result = scan_gguf(path)
    return ScanEvidence(
        check="structural_scan", ran=True, passed=result.status is ScanStatus.PASS,
        engine="gguf_structural", detail="; ".join(result.findings) or result.status.value,
    )


def build_risk_acceptance(
    *,
    accepted_by: str,
    artifact_sha256: str,
    basis: str,
    missing_evidence: Sequence[str],
    accepted_at: str | None = None,
    covers: Sequence[str] = ("malware_scan_status",),
) -> Mapping[str, Any]:
    """Build an auditable acceptance record.

    Every field is supplied by the caller except the timestamp. Nothing here
    infers consent - an acceptance exists only because someone stated one.
    """
    import datetime

    if not accepted_by.strip():
        raise ValueError("accepted_by is required: an acceptance needs an accepting party")
    if not basis.strip():
        raise ValueError("basis is required: an acceptance needs a stated reason")
    if not missing_evidence:
        raise ValueError("missing_evidence is required: record what was not checked")
    return {
        "accepted_by": accepted_by.strip(),
        "accepted_at": accepted_at
        or datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "artifact_sha256": artifact_sha256.strip().lower(),
        "basis": basis.strip(),
        "missing_evidence": list(missing_evidence),
        "covers": list(covers),
        "scope": "single_artifact",
        # Said outright inside the record itself.
        "is_a_scan_result": False,
        "note": (
            "Operator risk acceptance. No signature-based malware scan was performed; "
            "malware_scan_status remains not_run."
        ),
    }


def evaluate_clearance(
    artifact_path: Path | str | None,
    *,
    artifact_format: str = "gguf",
    which: Callable[[str], str | None] = _default_which,
    run: Callable[..., tuple[int, str]] = _default_run,
    risk_acceptance: Mapping[str, Any] | None = None,
) -> ClearanceResult:
    """Run every available check and decide. Never raises, never assumes."""
    if artifact_path is None or not Path(artifact_path).is_file():
        return ClearanceResult(
            status=ClearanceStatus.NO_ARTIFACT,
            reason="no verified artifact to scan; clearance needs the bytes",
        )
    path = Path(artifact_path)

    structural = run_structural_scan(path, artifact_format)
    signature = run_signature_scan(path, which=which, run=run)
    evidence = (structural, signature)
    unavailable = tuple(
        name for name in SIGNATURE_ENGINES if not (which(name) if callable(which) else None)
    )

    if structural.ran and structural.passed is False:
        return ClearanceResult(
            status=ClearanceStatus.BLOCKED_MALFORMED,
            reason=f"structural scan failed: {structural.detail}",
            evidence=evidence, engines_unavailable=unavailable,
        )
    if signature.ran and signature.passed is False:
        return ClearanceResult(
            status=ClearanceStatus.BLOCKED_INFECTED,
            reason=f"signature engine {signature.engine} reported a match: {signature.detail}",
            evidence=evidence, engines_unavailable=unavailable,
        )
    if not structural.ran or structural.passed is not True:
        return ClearanceResult(
            status=ClearanceStatus.INSUFFICIENT_EVIDENCE,
            reason=f"structural scan did not run: {structural.detail}",
            evidence=evidence, engines_unavailable=unavailable,
        )
    if not signature.ran or signature.passed is not True:
        if risk_acceptance is not None:
            # An operator decision, and recorded as one. The scan still did not
            # run, so malware_scan_status is deliberately left at its true
            # value and the acceptance is carried beside it.
            return ClearanceResult(
                status=ClearanceStatus.CLEARED_WITH_ACCEPTED_RISK,
                reason=(
                    f"structural scan passed; no signature engine available "
                    f"({signature.detail}). Operator "
                    f"{risk_acceptance.get('accepted_by')!r} accepted the residual risk. "
                    "malware_scan_status remains 'not_run'."
                ),
                evidence=evidence, engines_unavailable=unavailable,
                risk_acceptance=risk_acceptance,
                proposed_registry_update={
                    # Note what is NOT here: malware_scan_status.
                    "admission_evidence": {"quarantine_status": "clear"},
                    "lifecycle_state": "AVAILABLE",
                    "model_mesh_local_candidate_eligible": True,
                    "operator_risk_acceptance": dict(risk_acceptance),
                },
            )
        # The refusal that matters. "Nobody looked" must never become "clean".
        return ClearanceResult(
            status=ClearanceStatus.INSUFFICIENT_EVIDENCE,
            reason=(
                "no signature scan result; malware_scan_status stays 'not_run'. "
                f"{signature.detail}"
            ),
            evidence=evidence, engines_unavailable=unavailable,
        )

    return ClearanceResult(
        status=ClearanceStatus.CLEARED,
        reason="structural and signature scans both ran and passed",
        evidence=evidence,
        engines_unavailable=unavailable,
        proposed_registry_update={
            "admission_evidence": {
                "malware_scan_status": "pass",
                "quarantine_status": "clear",
            },
            "lifecycle_state": "AVAILABLE",
            "model_mesh_local_candidate_eligible": True,
        },
    )


def apply_clearance(record: Mapping[str, Any], result: ClearanceResult) -> Mapping[str, Any]:
    """Return a copy of the record with a *cleared* result applied.

    Refuses anything else, so an uncleared result cannot be applied by mistake.
    The caller still has to write it; this only builds the new value.
    """
    import copy

    if not result.cleared:
        raise ValueError(f"cannot apply a non-cleared result ({result.status.value}): {result.reason}")
    updated = copy.deepcopy(dict(record))
    update = dict(result.proposed_registry_update)
    evidence_update = dict(update.pop("admission_evidence", {}))
    if "malware_scan_status" in evidence_update and not result.cleared_by_evidence_only:
        # Belt and braces: an accepted-risk clearance must never write a scan
        # status, whatever a future edit to the proposed update might contain.
        raise ValueError("an accepted-risk clearance may not set malware_scan_status")
    updated.setdefault("admission_evidence", {})
    updated["admission_evidence"] = {**updated["admission_evidence"], **evidence_update}
    updated.update(update)
    return updated
