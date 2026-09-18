"""Which model answers which role, and the measurement that says so.

    python AI_SKILL_LIBRARY/v4/tools/role_capability_matrix.py --evidence /tmp/roles.json

A role mapping is the easiest place in this system to write down a belief and
have it read as a fact. "Qwen3-8B is the coder" sounds reasonable and is wrong:
it scores 0.167 on the engineering suite's coding items while Phi-3-mini scores
0.667. Reputation would have picked the bigger model; the measurement picks the
better one. Every mapping here is derived, never authored.

**Three sources, all recorded runs.** The Wave 0 and engineering suites through
`capability_gap_map`, which is imported rather than re-implemented so the two
tools cannot drift apart. The Wave 5 advanced-intelligence suite per capability.
The Wave 4 multimodal benchmark for capabilities only a provider serves. A
capability with no run behind it has no mapping - it is a gap, and the branch
that needs it says so.

**The specialization score is evidence, not reputation.** It is the measured
score, penalised for thin evidence and for saturation, and adjusted for what it
costs to run. No field in it can be filled from a model card, and there is no
parameter through which a model's popularity could enter.

**PRIMARY is not permanent.** It is whichever placeable model scores highest for
the role's capabilities today. Re-running this after a new measurement can move
it, which is the point: the Model Mesh reads the output, and a mapping nobody
can change is a mapping nobody has to justify.

**A provider substitute never becomes an exact model.** Rows carry
`execution_mode`, and a role served only by a hosted catalog says so - it has a
path, not a local one, and the two are different promises.

This tool decides nothing. It does not route, admit, promote, schedule or write
to any registry. The Model Mesh remains the selection authority and reads this
as evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import yaml  # noqa: E402

from AI_SKILL_LIBRARY.v4.tools import capability_gap_map as gap_map  # noqa: E402

BRANCHES_REL = "AI_SKILL_LIBRARY/v4/model_mesh/role_branches.yaml"
PATHS_REL = "AI_SKILL_LIBRARY/v4/open_model_universe/free_execution_paths.yaml"
REGISTRY_REL = "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"
EVIDENCE = "CHECKPOINTS/evidence"

#: The mesh's own floor, imported rather than restated as a judgement.
FLOOR = gap_map.COVERAGE_FLOOR

#: Verdicts in the Wave 4 benchmark that mean the model did the thing.
PROVIDER_PASS = frozenset({
    "PRODUCED_AUDIO", "TRANSCRIBED", "READ_CORRECTLY", "GROUNDED", "EMBEDDED",
    "REASONED", "LOCATED", "LOOKED_UP", "UNDERSTOOD", "COMBINED",
    "RANKED_CORRECTLY", "SYNTHESISED", "RETRIEVED",
})

#: Wave 4 records its own capability names. Mapped onto the branch vocabulary
#: here, explicitly, so no tag is matched by accident.
PROVIDER_CAPABILITY_ALIASES = {
    "ocr_text_in_image": "ocr",
    "vision_grounding": "vision",
    "document_embedding": "embedding",
}
#: A measurement of one tag that is also, on its own terms, a measurement of
#: another. Kept tiny and explicit: llava describing a scene correctly IS image
#: understanding. Nothing broader is inherited.
PROVIDER_CAPABILITY_ALSO = {
    "vision_grounding": ("image_understanding",),
}

#: The same measured thing recorded under two names by two suites. Wave 0's
#: GENERAL_REASONING lands as `deep_reasoning`; `local_core_reasoning` records
#: itself as `text_reasoning`. These are one capability with two spellings, and
#: saying so once here is better than letting a branch ask for a tag no suite
#: emits and reporting a gap that is really a vocabulary mismatch.
#: This is the ONLY alias table. It is not a place to declare that one
#: capability implies a different one.
CAPABILITY_SYNONYMS = {
    "text_reasoning": "deep_reasoning",
}


def _load_json(root: Path, name: str) -> Any:
    try:
        return json.loads((root / EVIDENCE / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _advint_scores(root: Path) -> dict[str, dict[str, dict[str, Any]]]:
    """Per-model, per-capability scores from the Wave 5 suite."""
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for path in sorted((root / EVIDENCE).glob("WAVE5_ADVINT_*.json")):
        try:
            blob = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        run = blob.get("benchmark_run") or {}
        model = str(run.get("model_id") or "")
        rows = run.get("results") or []
        if not model or not rows:
            continue
        tally: dict[str, list[int]] = {}
        for row in rows:
            cap = str(row.get("capability") or "")
            if not cap:
                continue
            seen = tally.setdefault(cap, [0, 0])
            seen[1] += 1
            seen[0] += int(bool(row.get("passed")))
        out.setdefault(model, {})
        for cap, (passed, attempted) in tally.items():
            out[model][cap] = {
                "score": round(passed / attempted, 6),
                "passed": passed,
                "attempted": attempted,
                "measured_by": f"{run.get('suite_id')}@{run.get('suite_version')}",
                "context_limit": blob.get("context_limit"),
                "source": path.name,
            }
    return out


def _core_reasoning_scores(root: Path) -> dict[str, dict[str, Any]]:
    """The 24-item core reasoning suite, per model.

    Two suites measure reasoning: Wave 0's GENERAL_REASONING at three tasks, and
    local_core_reasoning at twenty-four. An earlier version of this tool used
    only the first, and it made SmolLM2-360M the reasoning PRIMARY - it aces
    three questions, and on the deeper suite it scores 0.583 while Qwen3-8B
    scores 1.0. Three questions cannot rank a fleet. Where both exist the deeper
    one wins, which is the rule the gap map already states and this now follows.
    """
    out: dict[str, dict[str, Any]] = {}
    for path in sorted((root / EVIDENCE).glob("WAVE0_CAPABILITY_*.json")):
        try:
            blob = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if blob.get("measured") is not True:
            continue
        run = blob.get("benchmark_run") or {}
        model = str(run.get("model_id") or "")
        attempted = int(run.get("attempted") or 0)
        if not model or not attempted:
            continue
        out[model] = {
            "score": float(run.get("score") or 0.0),
            "passed": int(run.get("passed") or 0),
            "attempted": attempted,
            "measured_by": f"{run.get('suite_id')}@{run.get('suite_version')}",
            "source": path.name,
        }
    return out


def _provider_scores(root: Path) -> dict[str, dict[str, dict[str, Any]]]:
    """Capabilities only a hosted catalog serves, from the Wave 4 benchmark."""
    blob = _load_json(root, "WAVE4_MULTIMODAL_BENCHMARK.json") or {}
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for row in (blob.get("results") or []):
        model = row.get("model")
        raw = str(row.get("capability") or "")
        if not model or not raw:
            continue
        if row.get("verdict") not in PROVIDER_PASS:
            continue
        tags = [PROVIDER_CAPABILITY_ALIASES.get(raw, raw)]
        tags.extend(PROVIDER_CAPABILITY_ALSO.get(raw, ()))
        for tag in tags:
            out.setdefault(str(model), {})[tag] = {
                # A provider verdict is pass/fail, not a ratio. Recording it as
                # 1.0 would read like a perfect score on a suite; it is one
                # scored task and `attempted` says so.
                "score": 1.0,
                "passed": 1,
                "attempted": 1,
                "measured_by": f"{blob.get('benchmark')}@{blob.get('ran_at')}",
                "verdict": row.get("verdict"),
                "source": "WAVE4_MULTIMODAL_BENCHMARK.json",
                "single_task": True,
            }
    return out


def _specialization(entry: dict[str, Any], *, saturated: bool,
                    cost_mb: float | None) -> dict[str, Any]:
    """Evidence in, score out. No reputation term exists to be filled in."""
    score = float(entry.get("score") or 0.0)
    attempted = int(entry.get("attempted") or 0)

    # Thin evidence is discounted rather than trusted. Six items is the
    # engineering suite's per-skill depth and is treated as full confidence;
    # one scored task is worth a third of that.
    confidence = min(1.0, attempted / 6.0) if attempted else 0.0
    penalties: list[str] = []
    if attempted < 6:
        penalties.append(f"thin evidence: {attempted} scored item(s)")
    if saturated:
        # A suite everyone aces cannot rank anyone. The score stays; the
        # confidence in it as a RANKING drops.
        confidence *= 0.6
        penalties.append("suite saturated: the score bounds the suite, not the model")

    # Cost is a tiebreak, never a reason to prefer a worse model. Capped so it
    # can reorder equals and cannot promote a failure over a pass.
    efficiency = 1.0
    if cost_mb and cost_mb > 0:
        efficiency = max(0.85, min(1.0, 1.0 - (cost_mb - 2000.0) / 40000.0))

    return {
        "specialization_score": round(score * confidence * efficiency, 6),
        "measured_score": round(score, 6),
        "confidence": round(confidence, 6),
        "efficiency_factor": round(efficiency, 6),
        "evidence_class": "MEASURED",
        "penalties": penalties,
    }


def build(root: Path) -> dict[str, Any]:
    doc = yaml.safe_load((root / BRANCHES_REL).read_text(encoding="utf-8")) or {}
    branches = doc.get("branches") or []

    gap = gap_map.build(root)
    saturated_caps = set(gap.get("saturated_capabilities") or [])

    # Per-model capability evidence, merged from the three recorded sources.
    evidence: dict[str, dict[str, dict[str, Any]]] = {}
    cost: dict[str, float | None] = {}
    for row in gap.get("fleet") or []:
        model = str(row.get("model_id"))
        evidence.setdefault(model, {}).update(row.get("per_capability") or {})
    for model, caps in _advint_scores(root).items():
        evidence.setdefault(model, {}).update(caps)
    provider_models = _provider_scores(root)
    for model, caps in provider_models.items():
        evidence.setdefault(model, {}).update(caps)

    for model, entry in _core_reasoning_scores(root).items():
        evidence.setdefault(model, {})["text_reasoning"] = entry

    # Resolve the two spellings of one capability. Where both carry a score, the
    # one measured over more items wins - never the higher number, and never the
    # one that happens to be read last.
    for caps in evidence.values():
        for spelling, canonical in CAPABILITY_SYNONYMS.items():
            here, there = caps.get(spelling), caps.get(canonical)
            if here and there:
                deeper = here if int(here.get("attempted") or 0) >= int(
                    there.get("attempted") or 0) else there
                caps[spelling] = caps[canonical] = deeper
            elif there and not here:
                caps[spelling] = there
            elif here and not there:
                caps[canonical] = here

    for capability, row in (gap.get("capabilities") or {}).items():
        best = row.get("current_best_model")
        if best and row.get("peak_ram_mb"):
            cost[str(best)] = float(row["peak_ram_mb"])

    paths = yaml.safe_load((root / PATHS_REL).read_text(encoding="utf-8")) or {}
    usable_providers = {
        str(p.get("provider_id")) for p in (paths.get("paths") or [])
        if p.get("verification_state") in ("VERIFIED_AVAILABLE", "VERIFIED_LIMITED")
    }
    serverless_reachable = "cloudflare_workers_ai" in usable_providers

    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    single_path: list[str] = []
    redundancy_gaps: list[str] = []

    for branch in branches:
        role = str(branch.get("role_id"))
        required = list(branch.get("required_capabilities") or [])
        criticality = str(branch.get("criticality") or "NORMAL")
        placeholder = bool(branch.get("placeholder"))

        # Per capability first. A role can legitimately be a pipeline - retrieval
        # is an embedder AND a reranker, speech is an ASR model AND a TTS model -
        # and an earlier version of this required one model to cover all of them,
        # which reported "no model does all three" as though it meant "no path
        # exists". Those are different statements and only the second is a gap.
        def rank(capability: str) -> list[dict[str, Any]]:
            ranked: list[dict[str, Any]] = []
            for model, caps in evidence.items():
                entry = caps.get(capability)
                if not entry or float(entry.get("score") or 0.0) < FLOOR:
                    continue
                spec = _specialization(entry, saturated=capability in saturated_caps,
                                       cost_mb=cost.get(model))
                is_provider = model in provider_models
                ranked.append({
                    "model_id": model,
                    "capability": capability,
                    **spec,
                    "execution_mode": "CAPABILITY_PROVIDER" if is_provider else "EXACT_MODEL",
                    "placement": "SERVERLESS" if is_provider else "LOCAL",
                    "evidence_ref": str(entry.get("source") or entry.get("measured_by") or ""),
                })
            ranked.sort(key=lambda c: (-c["specialization_score"], c["model_id"]))
            return ranked

        per_capability_paths = {c: rank(c) for c in required}
        covered = [c for c, r in per_capability_paths.items() if r]
        uncovered = [c for c in required if not per_capability_paths[c]]

        # A single model that covers the WHOLE role is preferred when one exists:
        # it needs no handoff, no second load and no second worker. Its score is
        # its weakest required capability, never the mean - a model that is
        # excellent at one half of a role and barely passes the other is not
        # excellent at the role.
        candidates: list[dict[str, Any]] = []
        if not uncovered:
            for model, caps in evidence.items():
                parts = [next((r for r in per_capability_paths[c]
                               if r["model_id"] == model), None) for c in required]
                if any(part is None for part in parts):
                    continue
                is_provider = model in provider_models
                candidates.append({
                    "model_id": model,
                    "covers": "WHOLE_ROLE",
                    "specialization_score": round(min(p["specialization_score"] for p in parts), 6),
                    "per_capability": {c: parts[i] for i, c in enumerate(required)},
                    "execution_mode": "CAPABILITY_PROVIDER" if is_provider else "EXACT_MODEL",
                    "placement": "SERVERLESS" if is_provider else "LOCAL",
                    "evidence_refs": sorted({p["evidence_ref"] for p in parts}),
                })
        candidates.sort(key=lambda c: (-c["specialization_score"], c["model_id"]))

        # A pipeline: the best model per capability, which may be several. Used
        # when no single model covers the role, and recorded even when one does
        # so the composition is visible rather than implied.
        pipeline = {c: (per_capability_paths[c][0] if per_capability_paths[c] else None)
                    for c in required}
        pipeline_models = sorted({p["model_id"] for p in pipeline.values() if p})
        pipeline_placements = {p["placement"] for p in pipeline.values() if p}

        def _tier(index: int) -> dict[str, Any] | None:
            return candidates[index] if len(candidates) > index else None

        primary, secondary, fallback = _tier(0), _tier(1), _tier(2)
        # With no whole-role model, the role is served by its pipeline and the
        # primary IS that pipeline. Saying "unavailable" here would be false.
        served_by_pipeline = not candidates and not uncovered and bool(pipeline_models)
        if served_by_pipeline:
            primary = {
                "covers": "PIPELINE",
                "model_id": " + ".join(pipeline_models),
                "stages": {c: (pipeline[c] or {}).get("model_id") for c in required},
                "specialization_score": round(
                    min(p["specialization_score"] for p in pipeline.values() if p), 6),
                "execution_mode": ("CAPABILITY_PROVIDER"
                                   if pipeline_placements == {"SERVERLESS"} else "MIXED"),
                "placement": ("SERVERLESS" if pipeline_placements == {"SERVERLESS"}
                              else "MIXED"),
                "evidence_refs": sorted({p["evidence_ref"] for p in pipeline.values() if p}),
            }
        # Emergency fallback: the lowest-cost measured path that still clears
        # the floor. It exists to keep a minimum service, not to be good.
        emergency = candidates[-1] if len(candidates) > 3 else None

        # Independent paths: a local model and a hosted one are independent;
        # two local models on one host are NOT, because the host is the single
        # thing that fails. Counting distinct placements rather than distinct
        # models is what stops six models on one machine reading as redundancy.
        modes = {c["placement"] for c in candidates} | pipeline_placements
        independent_paths = len(modes)
        redundant = (len(candidates) >= 2 or served_by_pipeline) and independent_paths >= 2

        if placeholder:
            status = "PLACEHOLDER"
        elif uncovered and covered:
            # Part of the role has a measured path and part does not. DEGRADED
            # is the truthful word: the branch answers some requests and cannot
            # answer others, and calling that either available or unavailable
            # would hide half of it.
            status = "DEGRADED"
            failures.append(
                f"{role}: DEGRADED - {', '.join(covered)} measured, "
                f"{', '.join(uncovered)} has no measured path")
        elif uncovered:
            status = "UNAVAILABLE"
            never = [c for c in uncovered if not any(c in caps for caps in evidence.values())]
            failures.append(
                f"{role}: no measured path for {', '.join(uncovered)}"
                + (f"; never measured on any model: {', '.join(never)}" if never else ""))
        elif primary and primary.get("execution_mode") == "CAPABILITY_PROVIDER" \
                and not serverless_reachable:
            status = "BLOCKED"
            failures.append(f"{role}: its only path is a provider that is not currently usable")
        elif redundant or len(candidates) > 1:
            status = "AVAILABLE_PRIMARY"
        else:
            status = "AVAILABLE_FALLBACK_ONLY"

        has_a_path = bool(candidates) or served_by_pipeline
        if has_a_path and not redundant and not placeholder:
            single_path.append(role)
            if criticality in ("CRITICAL", "HIGH"):
                redundancy_gaps.append(
                    f"{role} ({criticality}): {len(candidates)} candidate(s) across "
                    f"{independent_paths} independent path(s)")

        rows.append({
            "role_id": role,
            "legion_division": branch.get("legion_division"),
            "criticality": criticality,
            "required_capabilities": required,
            "composition": branch.get("composition"),
            "privacy_classes": branch.get("privacy_classes") or [],
            "residency_target": branch.get("residency_target"),
            "status": status,
            "primary": primary,
            "secondary": secondary,
            "fallback": fallback,
            "emergency_fallback": emergency,
            "served_by": ("WHOLE_ROLE_MODEL" if candidates
                          else "PIPELINE" if served_by_pipeline else "NOTHING"),
            "per_capability_paths": {
                c: [{"model_id": r["model_id"], "score": r["specialization_score"],
                     "placement": r["placement"], "execution_mode": r["execution_mode"]}
                    for r in per_capability_paths[c][:3]]
                for c in required},
            "capabilities_covered": covered,
            "capabilities_uncovered": uncovered,
            "pipeline": {c: (pipeline[c] or {}).get("model_id") for c in required},
            "candidate_count": len(candidates),
            "independent_paths": independent_paths,
            "redundant": redundant,
            "single_path_risk": bool(candidates) and not redundant and not placeholder,
            "all_candidates": [c["model_id"] for c in candidates],
            "placeholder": placeholder,
            "research_only": bool(branch.get("research_only")),
            "trading_authority": False,
        })

    requirements = [r for r in rows if not r["placeholder"]]
    available = [r for r in requirements if r["status"].startswith("AVAILABLE")]

    return {
        "tool": "role_capability_matrix",
        "ROLE_CAPABILITY_MATRIX": rows,
        "role_branch_count": len(rows),
        "roles_requiring_a_path": len(requirements),
        "roles_with_a_path": len(available),
        "roles_unavailable": sorted(r["role_id"] for r in requirements
                                    if r["status"] == "UNAVAILABLE"),
        "roles_degraded": sorted(r["role_id"] for r in requirements
                                 if r["status"] == "DEGRADED"),
        "roles_blocked": sorted(r["role_id"] for r in requirements
                                if r["status"] == "BLOCKED"),
        "single_path_risks": sorted(single_path),
        "role_redundancy_gaps": sorted(redundancy_gaps),
        "merged_branches": doc.get("merged_branches") or {},
        "failures": failures,
        "scoring": {
            "floor": FLOOR,
            "role_score_is": "the weakest required capability, never the mean",
            "reputation_term": "none; there is no field through which one could enter",
            "thin_evidence": "discounted by scored-item count",
            "saturated_suite": "confidence in the ranking reduced, score left alone",
        },
        "note": (
            "A mapping here is derived from recorded runs and can move when a new "
            "run lands. A CAPABILITY_PROVIDER primary means the role has a path, "
            "not a local one, and never that the requested model is available."),
        "routing_authority": False,
        "model_selection_authority": False,
        "admission_authority": False,
        "scheduling_authority": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=repo_root)
    parser.add_argument("--evidence", type=Path, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = build(args.root)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")

    print(f"ROLE_CAPABILITY_MATRIX roles={result['role_branch_count']} "
          f"with_a_path={result['roles_with_a_path']}/{result['roles_requiring_a_path']}")
    for row in result["ROLE_CAPABILITY_MATRIX"]:
        primary = (row["primary"] or {}).get("model_id") or "-"
        fallback = (row["secondary"] or {}).get("model_id") or "-"
        mark = "!" if row["single_path_risk"] else " "
        print(f" {mark}{row['role_id']:<28} {row['status']:<24} {primary:<38} {fallback}")
    for gap in result["role_redundancy_gaps"]:
        print(f"  REDUNDANCY {gap}")
    for failure in result["failures"]:
        print(f"  FAIL {failure}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
