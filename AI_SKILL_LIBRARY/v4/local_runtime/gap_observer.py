"""OBSERVE: find gaps in the runtime/model plane from evidence already recorded.

Controlled self-development starts with OBSERVE and PROPOSE, and the machinery
either side of that already exists - `selfdev.AutoDevState` runs a change through
its gates, `skill_factory` proposes skills from experience. What was missing is
the step that looks at the *runtime and model* evidence and says what is
incomplete.

This is deliberately the weakest possible component:

* it **reads**. It opens the registry and the committed evidence files and
  nothing else. It cannot edit a record, run a model, start an AutoDev run,
  advance a gate or approve anything, and it has no code path that could;
* it **proposes**, and a proposal is a sentence and a pointer to the existing
  tool that would address the gap. It never writes the change, because a
  component that both decides what should change and makes the change is the
  self-approval the policy forbids;
* it **cites**. Every proposal names the evidence it came from, so a wrong
  proposal can be traced to the file that misled it rather than argued about.

What it deliberately does not do is rank proposals by importance. Ordering them
would be a judgement about what the system should do next, and that judgement
belongs to the Brain and the operator - not to the thing that noticed.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

EVIDENCE_DIR = "CHECKPOINTS/evidence"
REGISTRY_REL = "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"
INCOMPATIBILITY_REL = f"{EVIDENCE_DIR}/RUNTIME_INCOMPATIBILITY_EVIDENCE.json"
MANIFEST_REL = "AI_SKILL_LIBRARY/v4/open_model_universe/staging_manifest.json"


@dataclass(frozen=True)
class Gap:
    """One observed gap, and the existing tool that would close it."""

    kind: str
    subject: str
    detail: str
    evidence_ref: str
    suggested_tool: str | None = None

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "kind": self.kind,
            "subject": self.subject,
            "detail": self.detail,
            "evidence_ref": self.evidence_ref,
            "suggested_tool": self.suggested_tool,
            # Restated per gap so a consumer cannot read a proposal as a change.
            "is_a_proposal_not_a_change": True,
        }


@dataclass(frozen=True)
class Resolution:
    """A finding that is closed, and stays visible so the limit is not forgotten.

    A model whose bytes are intact but which no available runtime can load is not
    work waiting to be done. Reporting it forever as an open admission gap teaches
    the operator to skim past the observer, and admitting it anyway would claim
    something runs that does not. So it is reported here instead: still named,
    still evidenced, but not counted as work.

    It is bound to the artifact digest deliberately. A resolution describes bytes
    that were actually tried, so different bytes reopen the gap, and it lists the
    runtimes that were tried, so adding a runtime reopens it too.
    """

    subject: str
    artifact_sha256: str
    verdict: str
    detail: str
    evidence_ref: str
    revisit_if: Sequence[str]
    suppresses: Sequence[str]

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "subject": self.subject,
            "artifact_sha256": self.artifact_sha256,
            "verdict": self.verdict,
            "detail": self.detail,
            "evidence_ref": self.evidence_ref,
            "revisit_if": list(self.revisit_if),
            "suppresses": list(self.suppresses),
            "is_resolved_not_available": True,
        }


# The kinds a verified runtime incompatibility closes. Everything else about the
# model stays observable: an incompatibility says nothing about its licence or scan.
_INCOMPATIBILITY_SUPPRESSES = ("model_not_admitted", "capability_unmeasured")


def load_resolutions(root: Path) -> dict[str, Resolution]:
    """Verified incompatibilities, keyed by the digest they were observed on."""
    doc = _load_json(root / INCOMPATIBILITY_REL)
    if not doc:
        return {}
    resolutions: dict[str, Resolution] = {}
    for record in doc.get("records") or []:
        digest = str(record.get("artifact_sha256") or "").lower()
        # No digest, no resolution: an unbound finding could silence any model.
        if not digest or record.get("verdict") != "INCOMPATIBLE_WITH_AVAILABLE_RUNTIMES":
            continue
        tried = ", ".join(
            f"{t.get('runtime')} {t.get('runtime_version')}"
            for t in record.get("runtimes_tried") or []
        )
        resolutions[digest] = Resolution(
            subject=str(record.get("model_id")),
            artifact_sha256=digest,
            verdict=str(record.get("verdict")),
            detail=(f"artifact intact, but {tried} cannot load it: "
                    f"{record.get('cause') or record.get('runtime_diagnostic')}"),
            evidence_ref=INCOMPATIBILITY_REL,
            revisit_if=tuple(record.get("revisit_if") or ()),
            suppresses=_INCOMPATIBILITY_SUPPRESSES,
        )
    return resolutions


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def observe_models(registry: Mapping[str, Any],
                   resolutions: Mapping[str, "Resolution"] | None = None) -> list[Gap]:
    """Gaps visible in the canonical registry itself.

    A gap whose kind is closed by a resolution bound to *this* artifact's digest is
    not emitted: it is reported as resolved instead. The digest match is the whole
    safeguard, so re-quantized bytes are observed afresh.
    """
    resolutions = resolutions or {}
    gaps: list[Gap] = []
    for record in registry.get("models") or []:
        model_id = str(record.get("model_id"))
        digest = str((record.get("artifact_identity") or {}).get("sha256") or "")
        resolved = resolutions.get(digest.lower())
        suppressed = set(resolved.suppresses) if resolved else set()
        admission = record.get("admission_evidence") or {}
        evidence = (record.get("capability_evidence") or {}).get("text_reasoning") or {}

        if record.get("lifecycle_state") != "AVAILABLE" and "model_not_admitted" not in suppressed:
            gaps.append(Gap(
                kind="model_not_admitted", subject=model_id,
                detail=f"lifecycle_state is {record.get('lifecycle_state')}; it has not cleared admission",
                evidence_ref=REGISTRY_REL,
                suggested_tool="AI_SKILL_LIBRARY/v4/tools/local_runtime_admit.py",
            ))

        if admission.get("malware_scan_status") != "pass":
            gaps.append(Gap(
                kind="no_signature_scan", subject=model_id,
                detail=(f"malware_scan_status is {admission.get('malware_scan_status')}; "
                        "it rests on an operator acceptance rather than a scan"),
                evidence_ref=REGISTRY_REL,
                # Branch-qualified, because this one is not on the
                # implementation branch: the scan runs in CI on the ops lane,
                # where a signature engine and database are reachable. An
                # unqualified path here pointed at a file that does not exist
                # on the branch doing the observing.
                suggested_tool=("ops/publish-model-release:"
                                ".github/workflows/scan-staged-models.yml"),
            ))

        unmeasured = str(evidence.get("artifact_sha256") or "") != digest or not digest
        if unmeasured and "capability_unmeasured" not in suppressed:
            gaps.append(Gap(
                kind="capability_unmeasured", subject=model_id,
                detail="no capability measurement bound to this artifact's digest",
                evidence_ref=REGISTRY_REL,
                suggested_tool="AI_SKILL_LIBRARY/v4/tools/local_runtime_wave0.py",
            ))
    return gaps


def observe_baseline(baseline: Mapping[str, Any] | None) -> list[Gap]:
    """Gaps in the frozen baseline, including the tasks a model got wrong."""
    if not baseline:
        return []
    ref = f"{EVIDENCE_DIR}/WAVE0_BASELINE_EVIDENCE.json"
    gaps: list[Gap] = []
    if baseline.get("baseline_status") != "READY":
        gaps.append(Gap(
            kind="baseline_not_frozen", subject=str(baseline.get("model_id")),
            detail=(f"{baseline.get('passed')}/{baseline.get('total')} verifiers passed; "
                    "a baseline freezes only at a full pass"),
            evidence_ref=ref,
            suggested_tool="AI_SKILL_LIBRARY/v4/tools/local_runtime_baseline.py",
        ))
    for run in (baseline.get("wave_report") or {}).get("runs") or []:
        if not run.get("verifier_passed"):
            gaps.append(Gap(
                kind="task_failed", subject=f"{run.get('model_id')}:{run.get('task_id')}",
                detail=("failed its verifier: "
                        + ", ".join((run.get("failure") or {}).get("verifier_failures") or [])),
                evidence_ref=ref, suggested_tool=None,
            ))
        if not run.get("reproducible"):
            gaps.append(Gap(
                kind="task_not_reproducible", subject=f"{run.get('model_id')}:{run.get('task_id')}",
                detail="two identical greedy runs disagreed",
                evidence_ref=ref, suggested_tool=None,
            ))
    return gaps


def observe_transport(manifest: Mapping[str, Any] | None,
                      registry: Mapping[str, Any]) -> list[Gap]:
    """Staged models that never became registry rows."""
    if not manifest:
        return []
    registered = {str((m.get("artifact_identity") or {}).get("sha256") or "")
                  for m in registry.get("models") or []}
    gaps: list[Gap] = []
    for entry in manifest.get("entries") or []:
        digest = str(entry.get("expected_sha256") or "").lower()
        if digest in registered:
            continue
        detail = "staged and verified in transport, but not yet a registry record"
        # Read from what the entry actually records now, not from a note written
        # when the licence was still unknown. The first version keyed off a
        # `license_gap` marker, so it went on reporting "its licence is not yet
        # established" after the licences had been fetched - the observer
        # faithfully repeating stale input, which is the failure mode an
        # observer is most prone to and least likely to be blamed for.
        if not entry.get("license_declared"):
            detail += "; its licence is not yet established"
        gaps.append(Gap(
            kind="staged_not_admitted", subject=str(entry.get("id")),
            detail=detail, evidence_ref=MANIFEST_REL,
            suggested_tool="AI_SKILL_LIBRARY/v4/tools/local_runtime_admit.py",
        ))
    return gaps


def observe_residency(plan: Mapping[str, Any] | None) -> list[Gap]:
    if not plan:
        return []
    ref = f"{EVIDENCE_DIR}/RESIDENCY_PLAN.json"
    gaps: list[Gap] = []
    for assignment in plan.get("assignments") or []:
        if assignment.get("tier") == "COLD" and assignment.get("measured_capability") is None:
            gaps.append(Gap(
                kind="residency_withheld", subject=str(assignment.get("model_id")),
                detail="held at COLD because nothing about it has been measured",
                evidence_ref=ref,
                suggested_tool="AI_SKILL_LIBRARY/v4/tools/local_runtime_residency_profile.py",
            ))
    return gaps


def observe(root: Path) -> Mapping[str, Any]:
    """Every gap this plane can see, with no opinion about their order."""
    import yaml

    registry = yaml.safe_load((root / REGISTRY_REL).read_text(encoding="utf-8")) or {}
    manifest = _load_json(root / MANIFEST_REL)
    baseline = _load_json(root / EVIDENCE_DIR / "WAVE0_BASELINE_EVIDENCE.json")
    plan = _load_json(root / EVIDENCE_DIR / "RESIDENCY_PLAN.json")

    resolutions = load_resolutions(root)

    gaps: list[Gap] = []
    gaps += observe_models(registry, resolutions=resolutions)
    gaps += observe_baseline(baseline)
    gaps += observe_transport(manifest, registry)
    gaps += observe_residency(plan)

    by_kind: dict[str, int] = {}
    for gap in gaps:
        by_kind[gap.kind] = by_kind.get(gap.kind, 0) + 1

    # Only resolutions that actually match a model in the registry are reported, so a
    # stale record for bytes no longer tracked cannot pad the report.
    tracked = {str((m.get("artifact_identity") or {}).get("sha256") or "").lower()
               for m in registry.get("models") or []}
    resolved = [r for digest, r in sorted(resolutions.items()) if digest in tracked]

    return {
        "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        # Actionable work only. A resolved finding is reported separately rather than
        # counted here, so the count answers "what is left to do".
        "gap_count": len(gaps),
        "resolved_count": len(resolved),
        "resolved": [r.to_dict() for r in resolved],
        "by_kind": dict(sorted(by_kind.items())),
        "gaps": [gap.to_dict() for gap in gaps],
        # The capability boundary, stated rather than assumed by the reader.
        "capabilities": {
            "reads_evidence": True,
            "writes_code": False,
            "edits_registry": False,
            "runs_models": False,
            "starts_autodev_runs": False,
            "approves_anything": False,
            "ranks_by_importance": False,
        },
        "note": ("Proposals only. Ordering these is a judgement about what the system should "
                 "do next, and that belongs to the Brain and the operator, not to the "
                 "component that noticed."),
    }
