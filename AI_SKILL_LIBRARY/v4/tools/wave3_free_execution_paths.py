"""Resolve every Wave 3 model against the recorded zero-cost execution paths.

    python AI_SKILL_LIBRARY/v4/tools/wave3_free_execution_paths.py --evidence /tmp/paths.json

`wave3_placement.py` answers "can a machine of ours hold this". That leaves
REMOTE_WORKER_REQUIRED sitting on models nobody has actually gone looking for a
home for, which is a shortfall report mistaken for a conclusion. This asks the
next question: of the zero-cost paths this repository is *already* authorised to
use, does any of them run this model?

The paths are read from `free_execution_paths.yaml`, where each fact carries how
it was verified. Nothing is inferred here - if the file says a free tier is
unverified, the model fails closed rather than being reported available.

Two answers, kept apart on purpose:

**AVAILABLE_SERVERLESS** - the provider serves the same model. The local RAM
shortfall stops being the binding constraint, because the provider holds the
weights.

**PROVIDER_CAPABILITY_FALLBACK** - the provider serves a different model that
covers the capability. The request can be answered; *this* model still runs
nowhere. Every row says which model would actually execute, so the distinction
survives being read quickly.

A path's blockers are reported even when it is rejected, because "no zero-cost
path serves it" and "the one that does needs a credential this container does
not hold" send an operator to different work.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import yaml  # noqa: E402

from AI_SKILL_LIBRARY.v4.local_runtime.providers import (  # noqa: E402
    CostClass,
    ExecutionType,
    ModelOffering,
    OfferingMatch,
    ProviderRecord,
    ProviderRegistry,
    ProviderResolution,
    ProviderVerification,
)

PATHS_REL = "AI_SKILL_LIBRARY/v4/open_model_universe/free_execution_paths.yaml"
WAVE3_REL = "AI_SKILL_LIBRARY/v4/open_model_universe/wave3_knowledge_candidates.yaml"


def load_registry(root: Path) -> tuple[ProviderRegistry, dict[str, Any]]:
    """Build the provider registry from the recorded file.

    Offerings are attached to their provider here rather than being stored
    inside it, because the file is organised by model - which is how it is read
    when the question is "where can this one run" - and by provider, which is
    how it is read when the question is "what can this path do".
    """
    document = yaml.safe_load((root / PATHS_REL).read_text(encoding="utf-8")) or {}

    by_provider: dict[str, list[ModelOffering]] = {}
    for row in document.get("offerings", []):
        match = OfferingMatch(str(row.get("match")))
        if match in {OfferingMatch.ABSENT, OfferingMatch.UNVERIFIED}:
            # Recorded in the file so the check is visible, but carrying no
            # offering: an ABSENT row must not look like a candidate, and an
            # UNVERIFIED one must not look like an ABSENT one.
            continue
        offering = ModelOffering(
            requested_model_id=str(row.get("requested_model_id")),
            match=match,
            provider_model_id=row.get("provider_model_id"),
            substitution_reason=row.get("substitution_reason"),
            context_window=row.get("context_window"),
            free_tier_eligible=row.get("free_tier_eligible"),
            unit_pricing=row.get("unit_pricing"),
            license_note=row.get("license_note"),
            evidence=tuple(row.get("evidence") or ()),
        )
        by_provider.setdefault(str(row.get("provider_id")), []).append(offering)

    registry = ProviderRegistry()
    for row in document.get("paths", []):
        provider_id = str(row.get("provider_id"))
        registry.register(ProviderRecord(
            provider_id=provider_id,
            execution_type=ExecutionType(str(row.get("execution_type"))),
            cost_class=CostClass(str(row.get("cost_class"))),
            custom_weights=bool(row.get("custom_weights", False)),
            supported_artifact_formats=frozenset(row.get("supported_artifact_formats") or ()),
            authentication_required=bool(row.get("authentication_required", True)),
            credential_available_here=bool(row.get("credential_available_here", False)),
            operator_authorized=bool(row.get("operator_authorized", False)),
            operator_evidence=row.get("operator_evidence"),
            credential_held_by_worker=row.get("credential_held_by_worker"),
            verification_state=ProviderVerification(
                str(row.get("verification_state") or "DISCOVERED")),
            verification_evidence=row.get("verification_evidence"),
            operator_action_required=row.get("operator_action_required"),
            model_cache_capability=str(row.get("model_cache_capability") or "none"),
            cold_start_ms=row.get("cold_start_ms"),
            max_job_seconds=row.get("max_job_seconds"),
            max_ram_mb=row.get("max_ram_mb"),
            max_disk_mb=row.get("max_disk_mb"),
            quota=row.get("quota"),
            quota_resets=row.get("quota_resets"),
            egress_note=row.get("egress_note"),
            inference_provable_by=row.get("inference_provable_by"),
            offerings=tuple(by_provider.get(provider_id, ())),
            notes=str(row.get("notes") or "").strip(),
            evidence=tuple(row.get("evidence") or ()),
        ))
    return registry, document


def _state(resolution: ProviderResolution, registry: ProviderRegistry) -> str:
    """One label per model, and the pending cases keep their own.

    Collapsing "the provider serves it, one probe away" into "no zero-cost path"
    would be the same shape of error as calling a RAM shortfall infeasibility:
    it reports a fact about what has been checked as if it were a fact about
    what exists.
    """
    if resolution.has_exact:
        return "EXACT_MODEL_ON_ZERO_COST_PROVIDER"
    if resolution.capability:
        return "CAPABILITY_FALLBACK_AVAILABLE"
    if not resolution.pending:
        return "NO_ZERO_COST_PROVIDER_PATH"
    exact_pending = any(
        (offering := registry.get(provider_id).offering_for(resolution.model_id)) is not None
        and offering.match is OfferingMatch.EXACT
        for provider_id in resolution.pending
    )
    return ("EXACT_MODEL_PENDING_FREE_TIER_PROOF" if exact_pending
            else "CAPABILITY_FALLBACK_PENDING_FREE_TIER_PROOF")


def build(root: Path) -> dict[str, Any]:
    registry, document = load_registry(root)
    wave3 = yaml.safe_load((root / WAVE3_REL).read_text(encoding="utf-8")) or {}

    unverified = {
        str(row.get("requested_model_id")): row
        for row in document.get("offerings", [])
        if str(row.get("match")) in {"UNVERIFIED", "ABSENT"}
    }

    rows: list[dict[str, Any]] = []
    for candidate in wave3.get("candidates", []):
        upstream = str(candidate.get("upstream"))
        resolution = registry.resolve(upstream, free_only=True)
        checked = unverified.get(upstream)
        rows.append({
            "candidate_id": candidate.get("id"),
            "upstream": upstream,
            "local_status": candidate.get("status"),
            "estimated_runtime_ram_mb": (candidate.get("worker_requirement") or {}).get("runtime_ram_mb"),
            "zero_cost_path_state": _state(resolution, registry),
            **dict(resolution.to_dict()),
            "catalog_check": None if checked is None else {
                "match": checked.get("match"),
                "why": checked.get("unverified_reason") or checked.get("absent_reason"),
            },
        })

    providers = [dict(p.to_dict()) for p in registry.all()]
    # A path that cannot take our weights can never resolve a REMOTE_WORKER_REQUIRED
    # model into running *our* artifact, however many models it serves. Stated
    # once, as a number, so it is not left implicit in prose.
    weight_accepting = [p["provider_id"] for p in providers if p["custom_weights"]]

    return {
        "tool": "wave3_free_execution_paths",
        "paths_inspected": len(providers),
        "paths_accepting_our_weights": weight_accepting,
        "providers": providers,
        "models": rows,
        "by_state": {
            state: sorted(r["upstream"] for r in rows if r["zero_cost_path_state"] == state)
            for state in sorted({r["zero_cost_path_state"] for r in rows})
        },
        "routing_authority": False,
        "model_selection_authority": False,
        "admission_authority": False,
        "note": (
            "A capability fallback is not availability. Where this report names a "
            "fallback, the requested model still runs nowhere and any measurement "
            "taken on the substitute belongs to the substitute."
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--evidence", default=None)
    args = parser.parse_args(argv)

    result = build(Path(args.root).resolve())
    if args.evidence:
        Path(args.evidence).write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    counts = " ".join(f"{state}={len(ids)}" for state, ids in result["by_state"].items())
    print(f"WAVE3_FREE_PATHS paths={result['paths_inspected']} {counts}")
    for provider in result["providers"]:
        weights = "takes our weights" if provider["custom_weights"] else "hosted catalog only"
        print(f"  {provider['provider_id']:<32} {provider['execution_type']:<28} "
              f"{provider['cost_class']:<18} {weights}")
        for blocker in provider["blockers"]:
            print(f"      blocked: {blocker}")
    for row in result["models"]:
        print(f"  {row['zero_cost_path_state']:<34} {row['upstream']}")
        for served in row["exact"]:
            print(f"      exact on {served['provider_id']}: {served['provider_model_id']}")
        for served in row["capability_fallback"]:
            print(f"      fallback on {served['provider_id']}: {served['provider_model_id']}"
                  f"  (NOT {row['upstream']})")
        for provider_id, why in row["pending_verification"].items():
            print(f"      pending on {provider_id}: {'; '.join(why)}")
        for provider_id, why in row["rejected_paths"].items():
            print(f"      rejected {provider_id}: {'; '.join(why)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
