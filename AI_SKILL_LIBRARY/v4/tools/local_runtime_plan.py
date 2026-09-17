"""Read-only projection: Open Model Universe registry -> runtime placement plan.

The whole seam in one command. It reads the canonical registry, reads this
machine, projects every row into a `ModelProfile`, builds the `RegistryClaim`
and `AcquisitionRequest` each candidate would need, asks the scheduler where the
work would go, and prints the result as JSON evidence.

It writes nothing. Not the registry, not the cache, not a model file. It starts
no runtime and downloads no weights - `AcquisitionRequest` is *described*, never
executed, so this is safe to run anywhere including CI.

It also holds no authority. `task_router` routes and the Model Mesh nominates;
this only answers "given what is registered and what this box has, where could
that work land, and what is stopping the rest".

Run it:

    python AI_SKILL_LIBRARY/v4/tools/local_runtime_plan.py --root . --output plan.json

With an empty registry - which is the state today - it prints a plan with no
candidates and the exact external dependency that would unblock one. That is
the intended output, not a failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_SKILL_LIBRARY.v4.local_runtime.acquisition import AcquisitionRequest, precondition_refusals
from AI_SKILL_LIBRARY.v4.local_runtime.admission import ArtifactEvidence, evaluate as evaluate_artifact
from AI_SKILL_LIBRARY.v4.local_runtime.backends import detect_llama_cpp
from AI_SKILL_LIBRARY.v4.local_runtime.identity import artifact_block
from AI_SKILL_LIBRARY.v4.local_runtime.lifecycle import ModelState
from AI_SKILL_LIBRARY.v4.local_runtime.projection import (
    ProjectionResult,
    load_registry,
    project_registry,
)
from AI_SKILL_LIBRARY.v4.local_runtime.reconciliation import ENTRY_STATE, boundary_report
from AI_SKILL_LIBRARY.v4.local_runtime.resources import ResourceSnapshot, detect_resources
from AI_SKILL_LIBRARY.v4.local_runtime.runtime import RegistryClaim
from AI_SKILL_LIBRARY.v4.local_runtime.scheduler import (
    ModelProfile,
    PlacementAction,
    Priority,
    Privacy,
    QualityTier,
    RuntimeSlot,
    TaskRequest,
    plan_placement,
)

#: What a registry row must carry before this lane can acquire its artifact.
#: Printed in the plan so the gap is actionable rather than merely reported.
REQUIRED_ARTIFACT_FIELDS = (
    "artifact.filename",
    "artifact.format",
    "artifact.sha256",
    "artifact.size_bytes",
    "artifact.quantization",
    "immutable_revision",
)


def _first(values: Any) -> str | None:
    if isinstance(values, (list, tuple)) and values:
        return str(values[0])
    return None


def build_registry_claim(profile: ModelProfile) -> RegistryClaim:
    """The capability claim the runtime mesh negotiates against.

    Optimistic by construction - that is the point. The runtime's own probe
    overrides it, and the disagreement is what `negotiate()` records.
    """
    return RegistryClaim(
        model_id=profile.model_id,
        # A claim needs a number to be contradicted. 0 is the honest stand-in
        # for "the registry did not say": it cannot silently permit anything.
        context_limit=profile.context_limit or 0,
        modalities=frozenset(profile.capabilities) or frozenset({"text"}),
        tool_support=False,
        zero_cost=profile.zero_cost,
    )


def build_acquisition_request(
    record: Mapping[str, Any],
    profile: ModelProfile,
    *,
    root: Path,
    disk_budget_bytes: int | None,
) -> tuple[AcquisitionRequest | None, tuple[str, ...]]:
    """Describe the download this model would need, or say why it cannot.

    Never performs it. Returning `(None, reasons)` is the expected result for a
    registry that does not yet carry artifact identity.
    """
    artifact = artifact_block(record)
    filename = artifact.get("filename")
    if not filename or not profile.artifact_hash or profile.artifact_size_bytes is None:
        present = {
            "artifact.filename": artifact.get("filename"),
            "artifact.format": artifact.get("format"),
            "artifact.sha256": artifact.get("sha256"),
            "artifact.size_bytes": artifact.get("size_bytes"),
            "artifact.quantization": artifact.get("quantization"),
            "immutable_revision": record.get("immutable_revision") or record.get("upstream_revision"),
        }
        missing = [name for name, value in present.items() if not value]
        return None, (
            f"artifact identity incomplete; registry row lacks: {', '.join(missing) or 'artifact fields'}",
        )

    request = AcquisitionRequest(
        root=root,
        model_id=profile.model_id,
        revision=profile.revision or "",
        source_uri=str(record.get("weights_source") or ""),
        filename=str(filename),
        sha256=profile.artifact_hash,
        size_bytes=profile.artifact_size_bytes,
        lifecycle_state=ENTRY_STATE,
        runtime=profile.runtime,
        supported_runtimes=profile.runtime_support,
        disk_budget_bytes=disk_budget_bytes,
        artifact_format=artifact.get("format"),
        quantization=artifact.get("quantization") or profile.quantization,
        license_admission_ref=_first(record.get("admission_evidence")),
        provenance_ref=_first(record.get("source_evidence")),
        safe_format_verified=bool((record.get("safe_admission") or {}).get("safe_format")),
        remote_code_allowed=False,
        sandbox_required=True,
        egress_allowed=False,
    )
    return request, precondition_refusals(request)


def artifact_evidence(record: Mapping[str, Any], profile: ModelProfile) -> ArtifactEvidence:
    """Assemble what the safe-loader boundary needs to see.

    Planning asks a hypothetical - *would this load be admitted under the
    conditions the loader is required to provide* - so the sandbox and
    egress-denied flags are set here. They are conditions the plan reports, not
    permissions it grants: the real load re-evaluates against what it is
    actually given, and refuses if the caller did not honour them.
    """
    artifact = artifact_block(record)
    safe = record.get("safe_admission") or {}
    return ArtifactEvidence(
        model_id=profile.model_id,
        filename=artifact.get("filename"),
        artifact_format=artifact.get("format"),
        sha256=profile.artifact_hash,
        size_bytes=profile.artifact_size_bytes,
        quantization=artifact.get("quantization") or profile.quantization,
        revision=profile.revision,
        runtime=profile.runtime,
        runtime_support=profile.runtime_support,
        license_verified=bool(safe.get("license_verified", profile.license_verified)),
        provenance_verified=bool(safe.get("provenance_verified") or record.get("source_evidence")),
        trust_remote_code=bool(safe.get("trust_remote_code_required")),
        custom_model_code=bool(safe.get("custom_code_required")),
        sandbox_available=True,
        egress_denied=True,
    )


@dataclass(frozen=True)
class CandidatePlan:
    model_id: str
    admission_status: str
    runtime: str | None
    acquisition_possible: bool
    acquisition_refusals: tuple[str, ...]
    artifact_admitted: bool
    artifact_refusals: tuple[str, ...]
    exclusion_reasons: tuple[str, ...]
    unknown_fields: tuple[str, ...]
    unverified_claims: tuple[str, ...]

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "model_id": self.model_id,
            "admission_status": self.admission_status,
            "runtime": self.runtime,
            "acquisition_possible": self.acquisition_possible,
            "acquisition_refusals": list(self.acquisition_refusals),
            "artifact_admitted": self.artifact_admitted,
            "artifact_refusals": list(self.artifact_refusals),
            "exclusion_reasons": list(self.exclusion_reasons),
            "unknown_fields": list(self.unknown_fields),
            "unverified_claims": list(self.unverified_claims),
        }


@dataclass(frozen=True)
class PlacementPlan:
    selected_model: str | None = None
    selected_runtime: str | None = None
    selected_worker: str | None = None
    cold_or_warm: str | None = None
    load_required: bool | None = None
    estimated_ram_mb: int | None = None
    estimated_vram_mb: int | None = None
    disk_requirement_mb: int | None = None
    fallback_candidates: tuple[str, ...] = ()
    exclusion_reasons: Mapping[str, str] = field(default_factory=dict)
    #: How much of the decision rests on measured evidence rather than priors.
    confidence: str = "none"
    evidence: Mapping[str, Any] = field(default_factory=dict)
    reason: str = ""

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "selected_model": self.selected_model,
            "selected_runtime": self.selected_runtime,
            "selected_worker": self.selected_worker,
            "cold_or_warm": self.cold_or_warm,
            "load_required": self.load_required,
            "estimated_ram_mb": self.estimated_ram_mb,
            "estimated_vram_mb": self.estimated_vram_mb,
            "disk_requirement_mb": self.disk_requirement_mb,
            "fallback_candidates": list(self.fallback_candidates),
            "exclusion_reasons": dict(self.exclusion_reasons),
            "confidence": self.confidence,
            "evidence": dict(self.evidence),
            "reason": self.reason,
        }


_WARM_ACTIONS = {PlacementAction.SERVE_RUNNING, PlacementAction.USE_WARM}


def _confidence(profile: ModelProfile | None) -> tuple[str, dict[str, Any]]:
    """Confidence is about evidence, not about how good the model looks."""
    if profile is None:
        return "none", {}
    evidence = {
        "quality_measured": profile.quality is not None,
        "quality_class": profile.quality_class,
        "ram_requirement_known": profile.ram_mb is not None,
        "context_window_known": profile.context_limit is not None,
        "artifact_identity_known": bool(profile.artifact_hash) and profile.artifact_size_bytes is not None,
        "revision_pinned": bool(profile.revision),
        "license_verified": profile.license_verified,
    }
    proven = sum(1 for value in evidence.values() if value is True)
    total = len(evidence)
    level = "high" if proven == total else "medium" if proven >= total - 2 else "low"
    return level, evidence


def build_plan(
    registry: Mapping[str, Any],
    snapshot: ResourceSnapshot,
    *,
    root: Path,
    required_capabilities: frozenset[str] = frozenset({"text"}),
    available_runtimes: Sequence[str] | None = None,
    worker_id: str | None = None,
) -> tuple[PlacementPlan, tuple[CandidatePlan, ...]]:
    """Project the registry and plan a placement. Reads only."""
    results = project_registry(registry, snapshot=snapshot, available_runtimes=available_runtimes)
    records = {
        str(record.get("model_id")): record
        for record in (registry.get("models") or [])
        if isinstance(record, Mapping)
    }

    candidates: list[CandidatePlan] = []
    slots: list[RuntimeSlot] = []
    disk_budget = None if snapshot.disk_free_mb is None else snapshot.disk_free_mb * 1024 * 1024

    for result in results:
        record = records.get(result.model_id, {})
        acquisition_refusals: tuple[str, ...] = ()
        artifact_admitted = False
        artifact_refusals: tuple[str, ...] = ()
        request = None
        if result.profile is not None:
            request, acquisition_refusals = build_acquisition_request(
                record, result.profile, root=root, disk_budget_bytes=disk_budget
            )
            verdict = evaluate_artifact(artifact_evidence(record, result.profile))
            artifact_admitted = verdict.admitted
            artifact_refusals = verdict.refusals
            # A projected candidate enters residency at the one documented door,
            # whatever the registry row claimed about being warm or running.
            slots.append(RuntimeSlot(model=result.profile, state=ENTRY_STATE))

        candidates.append(
            CandidatePlan(
                model_id=result.model_id,
                admission_status=result.admission_status.value,
                runtime=result.profile.runtime if result.profile else None,
                acquisition_possible=bool(request) and not acquisition_refusals,
                acquisition_refusals=acquisition_refusals,
                artifact_admitted=artifact_admitted,
                artifact_refusals=artifact_refusals,
                exclusion_reasons=result.exclusion_reasons,
                unknown_fields=result.unknown_fields,
                unverified_claims=result.unverified_claims,
            )
        )

    if not slots:
        return (
            PlacementPlan(
                reason=(
                    "no placeable candidate: the registry carries no model this host can run"
                    if records
                    else "no placeable candidate: the canonical registry is empty"
                ),
                exclusion_reasons={c.model_id: "; ".join(c.exclusion_reasons) for c in candidates},
            ),
            tuple(candidates),
        )

    decision = plan_placement(
        TaskRequest(
            task_id="local-runtime-plan",
            priority=Priority.P2_STANDARD,
            quality_tier=QualityTier.STANDARD,
            privacy=Privacy.INTERNAL,
            required_capabilities=required_capabilities,
            free_only=True,
        ),
        slots,
        snapshot,
    )

    by_id = {result.model_id: result for result in results}
    if not decision.admitted:
        return (
            PlacementPlan(reason=decision.reason, exclusion_reasons=dict(decision.rejected)),
            tuple(candidates),
        )

    placement = decision.placements[0]
    profile = by_id[placement.model_id].profile
    level, evidence = _confidence(profile)
    return (
        PlacementPlan(
            selected_model=placement.model_id,
            selected_runtime=placement.runtime,
            selected_worker=worker_id or "local",
            cold_or_warm="WARM" if placement.action in _WARM_ACTIONS else "COLD",
            load_required=placement.action not in _WARM_ACTIONS,
            estimated_ram_mb=profile.ram_mb,
            estimated_vram_mb=profile.vram_mb,
            disk_requirement_mb=profile.disk_mb,
            fallback_candidates=tuple(p.model_id for p in decision.placements[1:]),
            exclusion_reasons=dict(decision.rejected),
            confidence=level,
            evidence=evidence,
            reason=decision.reason,
        ),
        tuple(candidates),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--output", help="write the plan here instead of stdout")
    parser.add_argument("--capability", action="append", default=None, help="required capability")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    snapshot = detect_resources(disk_path=str(root))
    binary = detect_llama_cpp()
    available = ["llama.cpp"] if binary else []

    registry = load_registry(root)
    plan, candidates = build_plan(
        registry,
        snapshot,
        root=root,
        required_capabilities=frozenset(args.capability or ["text"]),
        available_runtimes=available or None,
    )

    payload = {
        "generated_by": "AI_SKILL_LIBRARY/v4/tools/local_runtime_plan.py",
        "read_only": True,
        "routing_authority": False,
        "model_selection_authority": False,
        "registry": {
            "registry_id": registry.get("registry_id"),
            "cost_policy": (registry.get("policy") or {}).get("cost_policy"),
            "paid_fallback": (registry.get("policy") or {}).get("paid_fallback"),
            "model_count": len(registry.get("models") or []),
        },
        "boundary": boundary_report(),
        "host": snapshot.to_dict(),
        "runtimes_detected": {
            "llama.cpp": None
            if binary is None
            else {"path": binary.path, "version": binary.version, "build": binary.build_line}
        },
        "candidates": [candidate.to_dict() for candidate in candidates],
        "placement_plan": plan.to_dict(),
        "required_artifact_fields": list(REQUIRED_ARTIFACT_FIELDS),
    }
    text = json.dumps(payload, indent=2, sort_keys=False)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
