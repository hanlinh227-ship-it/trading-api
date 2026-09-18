"""Which model serves which role, and what happens when it cannot.

    python AI_SKILL_LIBRARY/v4/tools/role_specialization.py --evidence /tmp/roles.json

A role is a *view* over the capability tags the waves already measured. It is
not a second capability vocabulary and not a second registry: every role here
names canonical tags from WAVE4_CLOSURE and WAVE5_CLOSURE, and every score is a
measurement some suite already recorded against an artifact digest. Nothing is
re-measured here and nothing new is claimed.

The rule that shapes the whole file: **a role with no measured evidence gets no
PRIMARY.** It is far easier to write a plausible model name beside every role
than to admit that six of them have never been measured, and a matrix that
looks complete is worth less than one that says where it is empty. An uncovered
tag carries its blocker class through verbatim from the wave that classified it.

Depth, for a role that has candidates:

  PRIMARY              best measured score for the role's tag
  SECONDARY            next best, for load and for a second opinion
  FALLBACK             third, or the best on another execution path
  EMERGENCY_FALLBACK   deliberately on a *different* execution path from the
                       primary where one exists, so that losing the host does
                       not take the role out with it

Ties break on score, then on lower measured warm latency, then on model_id.
The last step is determinism, not a judgement, and the row says so.

**This tool decides nothing.** It does not route, admit, promote, schedule or
evict. task_router remains the only routing authority and the Model Mesh the
only model-selection authority; this prints what their own evidence adds up to.
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

EVIDENCE = "CHECKPOINTS/evidence"

#: A role names canonical capability tags. Nothing here invents a tag: each one
#: appears in WAVE4_CLOSURE or WAVE5_CLOSURE, which is where coverage is decided.
#: `suite_key` is the per-model measured signal used to rank candidates, when a
#: local suite measured that capability per model. Without one, the role can
#: still be covered - by the substitute the wave named - but it cannot be
#: *ranked*, and the matrix says so rather than inventing an order.
ROLES: tuple[dict[str, Any], ...] = (
    {"role": "GENERAL_FAST", "tags": ("deep_reasoning",), "suite_key": "text_reasoning",
     "rank_by": "latency", "note": "the cheapest answer that clears the floor, not the best one"},
    {"role": "REASONING", "tags": ("deep_reasoning",), "suite_key": "text_reasoning"},
    {"role": "HEAVY_REASONING", "tags": ("deep_reasoning", "large_model_synthesis"),
     "suite_key": "text_reasoning"},
    # There is no canonical `coding` tag - the waves record software_engineering.
    # Coverage therefore comes from that tag, while the ordering uses the coding
    # sub-score the engineering suite measures per model.
    {"role": "CODING", "tags": ("software_engineering",), "suite_key": "coding"},
    {"role": "SOFTWARE_ENGINEERING", "tags": ("software_engineering",), "suite_key": "software_engineering"},
    {"role": "VERIFICATION", "tags": ("verifier",), "suite_key": "verifier_checker"},
    {"role": "SYSTEMS_ENGINEERING", "tags": ("software_engineering", "debugging"),
     "suite_key": "debugging"},
    {"role": "PLANNING", "tags": ("agentic_planning",), "suite_key": None},
    {"role": "TOOL_USE", "tags": ("tool_calling",), "suite_key": None},
    {"role": "RESEARCH", "tags": ("large_model_synthesis",), "suite_key": None},
    {"role": "RETRIEVAL", "tags": ("retrieval", "embedding", "reranking"), "suite_key": None},
    {"role": "MULTILINGUAL", "tags": ("multilingual",), "suite_key": None},
    {"role": "VIETNAMESE", "tags": ("vietnamese",), "suite_key": "vietnamese"},
    {"role": "SCIENCE_TECH", "tags": ("scientific_reasoning",), "suite_key": None},
    {"role": "VISION", "tags": ("vision", "image_understanding"), "suite_key": None},
    {"role": "DOCUMENT_OCR", "tags": ("ocr",), "suite_key": None},
    {"role": "SPEECH", "tags": ("speech_to_text", "text_to_speech"), "suite_key": None},
    {"role": "AUDIO", "tags": ("audio_understanding",), "suite_key": None},
    {"role": "CREATIVE_MULTIMODAL", "tags": ("multimodal_reasoning",), "suite_key": None},
    {"role": "FINANCE_ANALYSIS", "tags": ("finance_analysis",), "suite_key": None,
     "note": "analysis only; this role grants no broker, order or execution authority"},
)

DEPTH = ("PRIMARY", "SECONDARY", "FALLBACK", "EMERGENCY_FALLBACK")

#: Roles a minimum service profile tries to keep answering. Chosen because each
#: one is load-bearing for the core loop: reason, check the reasoning, write and
#: fix code, and find what the answer needs.
MINIMUM_SERVICE_ROLES = ("REASONING", "VERIFICATION", "CODING", "RETRIEVAL")


def _load(root: Path, name: str) -> Any:
    path = root / EVIDENCE / name
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def measured_scores(root: Path) -> dict[str, dict[str, Any]]:
    """Per-model measured signals, read from the runs that produced them.

    Every number here came out of a suite bound to an artifact digest. A model
    that was never run does not appear, rather than appearing with a zero -
    unmeasured and bad are different facts and a zero would merge them.
    """
    models: dict[str, dict[str, Any]] = {}

    for path in sorted(glob.glob(str(root / EVIDENCE / "WAVE3_ENGJUDG_*.json"))):
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        identity = doc.get("artifact_identity") or {}
        model_id = identity.get("model_id")
        run = doc.get("benchmark_run") or {}
        if not model_id or not isinstance(run.get("results"), list):
            continue
        tally: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
        latencies: list[float] = []
        for record in run["results"]:
            bucket = tally[str(record.get("capability"))]
            bucket[1] += 1
            bucket[0] += 1 if record.get("passed") else 0
            if isinstance(record.get("latency_ms"), (int, float)):
                latencies.append(float(record["latency_ms"]))
        entry = models.setdefault(model_id, {"model_id": model_id, "scores": {}})
        entry["artifact_sha256"] = identity.get("artifact_sha256")
        entry["context_limit"] = doc.get("context_limit")
        for capability, (passed, attempted) in tally.items():
            entry["scores"][capability] = {
                "score": round(passed / attempted, 6),
                "passed": passed,
                "attempted": attempted,
                "source": "MEASURED",
                "suite": run.get("suite_id"),
            }
        # A composite role needs a composite signal, and averaging the three
        # engineering capabilities is a derivation - it is labelled as one.
        parts = [tally[k] for k in ("debugging", "code_review", "coding") if k in tally]
        if len(parts) == 3:
            passed = sum(p[0] for p in parts)
            attempted = sum(p[1] for p in parts)
            entry["scores"]["software_engineering"] = {
                "score": round(passed / attempted, 6),
                "passed": passed,
                "attempted": attempted,
                "source": "DERIVED",
                "derivation": "debugging + code_review + coding items, pooled",
                "suite": run.get("suite_id"),
            }
        if latencies:
            entry["median_item_latency_ms"] = round(sorted(latencies)[len(latencies) // 2], 1)

    for path in sorted(glob.glob(str(root / EVIDENCE / "WAVE0_CAPABILITY_*.json"))):
        if path.endswith("WAVE0_CAPABILITY_EVIDENCE.json"):
            continue
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        model_id = (doc.get("artifact_identity") or {}).get("model_id")
        run = doc.get("benchmark_run") or {}
        if not model_id or run.get("score") is None:
            continue
        entry = models.setdefault(model_id, {"model_id": model_id, "scores": {}})
        entry["scores"]["text_reasoning"] = {
            "score": run["score"], "passed": run.get("passed"), "attempted": run.get("attempted"),
            "source": "MEASURED", "suite": run.get("suite_id"),
        }

    for path in sorted(glob.glob(str(root / EVIDENCE / "WAVE0_BASELINE_*.json"))):
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        frozen = doc.get("baseline") or {}
        runs = frozen.get("wave0_results") or (doc.get("wave_report") or {}).get("runs") or []
        model_id = frozen.get("model_id") or doc.get("model_id")
        if not model_id or not runs:
            continue
        passed = sum(1 for r in runs if r.get("category") == "VIETNAMESE" and r.get("verifier_passed"))
        attempted = sum(1 for r in runs if r.get("category") == "VIETNAMESE")
        if not attempted:
            continue
        entry = models.setdefault(model_id, {"model_id": model_id, "scores": {}})
        entry["scores"]["vietnamese"] = {
            "score": round(passed / attempted, 6), "passed": passed, "attempted": attempted,
            "source": "MEASURED", "suite": "wave0_canonical",
        }

    profile = _load(root, "RESIDENCY_LATENCY_PROFILE.json") or {}
    for row in profile.get("models") or []:
        model_id = row.get("model_id")
        if not model_id:
            continue
        entry = models.setdefault(model_id, {"model_id": model_id, "scores": {}})
        entry["warm_inference_ms"] = row.get("warm_inference_ms")
        entry["cold_load_ms"] = row.get("cold_load_ms")
        entry["peak_ram_mb"] = row.get("peak_ram_mb")
    return models


def covered_tags(root: Path) -> dict[str, dict[str, Any]]:
    """The canonical coverage record, exactly as the waves closed it."""
    tags: dict[str, dict[str, Any]] = {}
    for name in ("WAVE4_CLOSURE.json", "WAVE5_CLOSURE.json"):
        doc = _load(root, name) or {}
        for row in doc.get("capabilities") or []:
            tags[str(row.get("tag"))] = {
                "covered": bool(row.get("measured_covered")),
                "model": row.get("measured_model"),
                "substitute": bool(row.get("served_by_a_provider_substitute")),
                "blocker_class": row.get("blocker_class"),
                "wave": doc.get("wave"),
                "is_a_requirement": row.get("is_a_requirement"),
                "suite_saturated": bool(row.get("suite_saturated")),
            }
    return tags


#: The manifest's own `candidate_roles` vocabulary, mapped onto the role names
#: here. The mapping is a rename, not a judgement: the repository already
#: recorded what each candidate was wanted for, and this reuses that rather
#: than letting this tool decide what a hosted model is good at.
CANDIDATE_ROLE_ALIASES: dict[str, tuple[str, ...]] = {
    "deep_reasoning": ("REASONING", "HEAVY_REASONING"),
    "synthesis_generalist": ("RESEARCH", "HEAVY_REASONING"),
    "verifier_checker": ("VERIFICATION",),
    "software_engineering": ("SOFTWARE_ENGINEERING", "SYSTEMS_ENGINEERING"),
    "coding_agent": ("CODING",),
    "multilingual": ("MULTILINGUAL",),
    "vietnamese_multilingual": ("VIETNAMESE", "MULTILINGUAL"),
    "fast_low_resource_worker": ("GENERAL_FAST",),
}


def provider_fallbacks(root: Path) -> dict[str, list[dict[str, Any]]]:
    """Hosted models proven to execute, indexed by the role they were wanted for.

    These earn a place for one reason only: a probe called them on the free tier
    and got a real completion back, on an execution path that does not die with
    this container. No suite has scored them, so they can never be a PRIMARY and
    never outrank a measured model - an emergency fallback answers the question
    "is there any path left", not "which answer is best".
    """
    path = root / "AI_SKILL_LIBRARY/v4/open_model_universe/free_execution_paths.yaml"
    if not path.is_file():
        return {}
    import yaml  # local import: only this function needs it

    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    manifest_path = root / "AI_SKILL_LIBRARY/v4/open_model_universe/wave3_knowledge_candidates.yaml"
    intents: dict[str, list[str]] = {}
    if manifest_path.is_file():
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        for candidate in manifest.get("candidates") or []:
            if candidate.get("upstream"):
                intents[candidate["upstream"]] = list(candidate.get("candidate_roles") or [])

    by_role: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for offering in document.get("offerings") or []:
        if not offering.get("free_tier_eligible") or not offering.get("provider_model_id"):
            continue
        requested = offering.get("requested_model_id")
        for candidate_role in intents.get(requested, []):
            for role_name in CANDIDATE_ROLE_ALIASES.get(candidate_role, ()):
                by_role[role_name].append({
                    "model_id": offering["provider_model_id"],
                    "score": None,
                    "score_source": "EXECUTION_PROVEN_UNSCORED",
                    "score_detail": (
                        "returned HTTP 200 with a real completion on the free tier; "
                        "no capability suite has scored it"
                    ),
                    "suite": None,
                    "warm_inference_ms": None,
                    "execution_path": "SERVERLESS_HOSTED_CATALOG",
                    "provider_id": offering.get("provider_id"),
                    "serves_this_role_because": (
                        f"the Wave 3 manifest records {requested} as a {candidate_role} candidate, "
                        f"and this provider model is its {offering.get('match')} match"
                    ),
                    "match": offering.get("match"),
                    "context_window": offering.get("context_window"),
                    "may_be_primary": False,
                })
    return by_role


def _execution_path(model_id: str | None, local_models: frozenset[str]) -> str:
    if not model_id:
        return "NONE"
    if model_id in local_models:
        return "LOCAL_PROCESS"
    if str(model_id).startswith("@cf/"):
        return "SERVERLESS_HOSTED_CATALOG"
    return "UNKNOWN"


def rank_role(role: dict[str, Any], models: dict[str, dict[str, Any]],
              tags: dict[str, dict[str, Any]],
              hosted: dict[str, list[dict[str, Any]]] | None = None) -> dict[str, Any]:
    """Order the candidates for one role, or explain why it has none."""
    tag_rows = [tags.get(tag) for tag in role["tags"]]
    present = [row for row in tag_rows if row]
    covered = [row for row in present if row["covered"]]
    local_models = frozenset(models)

    result: dict[str, Any] = {
        "role": role["role"],
        "capability_tags": list(role["tags"]),
        "assignments": [],
        "single_path_risk": False,
        "redundancy_depth": 0,
    }
    if role.get("note"):
        result["note"] = role["note"]

    if not covered:
        blockers = sorted({str(row.get("blocker_class")) for row in present if row.get("blocker_class")})
        result["evidence_class"] = "UNCOVERED"
        result["blocker_class"] = blockers[0] if len(blockers) == 1 else (blockers or ["UNKNOWN"])[0]
        result["all_blocker_classes"] = blockers
        result["why_no_primary"] = (
            "no capability tag for this role is covered, so there is nothing to assign. "
            "The blocker is carried through from the wave that classified it, not restated here."
        )
        return result

    suite_key = role.get("suite_key")
    ranked: list[dict[str, Any]] = []
    if suite_key:
        for model_id, entry in models.items():
            score_row = entry["scores"].get(suite_key)
            if not score_row:
                continue
            ranked.append({
                "model_id": model_id,
                "score": score_row["score"],
                "score_source": score_row["source"],
                "score_detail": f"{score_row.get('passed')}/{score_row.get('attempted')}",
                "suite": score_row.get("suite"),
                "warm_inference_ms": entry.get("warm_inference_ms"),
                "median_item_latency_ms": entry.get("median_item_latency_ms"),
                "execution_path": "LOCAL_PROCESS",
            })
        latency_first = role.get("rank_by") == "latency"

        def sort_key(row: dict[str, Any]) -> tuple:
            latency = row.get("warm_inference_ms") or row.get("median_item_latency_ms") or float("inf")
            if latency_first:
                return (latency, -row["score"], row["model_id"])
            return (-row["score"], latency, row["model_id"])

        ranked.sort(key=sort_key)
        result["ranked_by"] = (
            "lowest measured warm latency first, then score, then model_id"
            if latency_first else
            "highest measured score first, then lowest measured warm latency, then model_id"
        )
        result["tie_break_note"] = "model_id breaks a remaining tie for determinism, never as a quality claim"

    # Whatever the wave named as serving the tag belongs in the list even when
    # no per-model suite can rank it - that is how a provider substitute earns
    # its place without being mistaken for a locally measured model.
    for row in covered:
        serving = row.get("model")
        if serving and not any(r["model_id"] == serving for r in ranked):
            ranked.append({
                "model_id": serving,
                "score": None,
                "score_source": "WAVE_COVERAGE",
                "score_detail": "covered by the wave; no per-model suite ranks this capability",
                "suite": None,
                "warm_inference_ms": None,
                "execution_path": _execution_path(serving, local_models),
                "is_provider_substitute": row.get("substitute"),
            })

    for row in ranked:
        row["execution_path"] = _execution_path(row["model_id"], local_models)

    # Proven-but-unscored hosted models go on the end, always behind everything
    # measured. They add a path, not a ranking.
    for row in (hosted or {}).get(role["role"], []):
        if not any(existing["model_id"] == row["model_id"] for existing in ranked):
            ranked.append(dict(row))

    # Emergency fallback deliberately prefers a different execution path: a
    # fourth local model is depth on paper only, because one dead container
    # takes all four with it.
    # Nothing unscored may hold PRIMARY. If the only candidates left are hosted
    # models a probe merely proved reachable, the role has paths but no ranked
    # owner, and it says that instead of promoting one on availability alone.
    rankable = [row for row in ranked if row.get("may_be_primary") is not False]
    if not rankable and ranked:
        result["evidence_class"] = "PATHS_ONLY_NO_RANKED_OWNER"
        result["why_no_primary"] = (
            "every candidate for this role is proven reachable but unscored, so none may hold "
            "PRIMARY: availability is not quality"
        )
        result["assignments"] = [dict(row, depth="FALLBACK") for row in ranked[:len(DEPTH)]]
        result["redundancy_depth"] = len(result["assignments"])
        paths = {row["execution_path"] for row in result["assignments"]}
        result["execution_paths"] = sorted(paths)
        result["single_path_risk"] = len(paths) <= 1
        return result

    # The wave closure is the canonical record of which model covers a tag. This
    # view orders the bench beneath that decision; it does not overturn it. When
    # a pooled score disagrees with the named model the disagreement is printed,
    # because a derived average quietly outranking the canonical record is how a
    # reporting tool turns into an unaccountable second authority.
    named = [row.get("model") for row in covered if row.get("model")]
    canonical = next((m for m in named if any(r["model_id"] == m for r in rankable)), None)
    has_measurement = bool(suite_key) and any(
        r.get("score_source") in ("MEASURED", "DERIVED") for r in rankable)

    if canonical and rankable and rankable[0]["model_id"] != canonical:
        if has_measurement:
            # Measured evidence dominates. The wave's pick is kept in view as a
            # cross-check, because a silent disagreement between two records of
            # the same fleet is worse than a stated one.
            result["differs_from_wave_coverage"] = {
                "wave_named": canonical,
                "this_ordering_picks": rankable[0]["model_id"],
                "resolution": "the measured score holds PRIMARY",
                "why": (
                    "this role ranks on a per-model suite score measured against an artifact "
                    "digest, and a measurement outranks a coverage note. The wave's model is "
                    "named here so the difference is visible and checkable, not hidden."
                ),
                "ranked_on": "latency" if role.get("rank_by") == "latency" else suite_key,
            }
        else:
            # Nothing comparable was measured, so the canonical record leads
            # rather than an order this tool cannot justify.
            rankable = ([next(r for r in rankable if r["model_id"] == canonical)]
                        + [r for r in rankable if r["model_id"] != canonical])
            ranked = rankable + [r for r in ranked if r.get("may_be_primary") is False]
            result["ordered_by_wave_coverage"] = (
                f"no per-model suite ranks this role, so {canonical} leads because the wave "
                "closure named it as covering the capability"
            )

    ordered: list[dict[str, Any]] = []
    remaining = list(ranked)
    for depth in DEPTH:
        if not remaining:
            break
        pick = remaining[0]
        if depth == "PRIMARY" and pick.get("may_be_primary") is False:
            pick = next(row for row in remaining if row.get("may_be_primary") is not False)
        if depth == "EMERGENCY_FALLBACK" and ordered:
            primary_path = ordered[0]["execution_path"]
            offpath = [r for r in remaining if r["execution_path"] != primary_path]
            if offpath:
                pick = offpath[0]
                pick = dict(pick)
                pick["chosen_because"] = (
                    f"different execution path from the primary ({primary_path}), so a host "
                    "failure does not remove this role"
                )
        else:
            pick = dict(pick)
        pick["depth"] = depth
        ordered.append(pick)
        remaining = [r for r in remaining if r["model_id"] != pick["model_id"]]

    # A tie broken on latency reads like a quality verdict unless the tie is
    # named. The baseline freeze set this precedent: say who tied and say what
    # actually separated them.
    top = ordered[0]
    if top.get("score") is not None:
        tied = [row["model_id"] for row in ranked if row.get("score") == top["score"]]
        if len(tied) > 1:
            result["tied_at_top"] = {
                "score": top["score"],
                "models": sorted(tied),
                "separated_by": ("lowest measured warm latency"
                                 if role.get("rank_by") != "latency" else "score, then model_id"),
                "meaning": (
                    "these models are indistinguishable on this suite. The order below is a "
                    "deterministic tie-break, not a measured quality difference."
                ),
            }
            if top.get("score_source") == "DERIVED":
                result["tied_at_top"]["caution"] = (
                    "the tied score is a pooled derivation, so the tie may be an artifact of "
                    "pooling sub-capabilities the models differ on individually"
                )

    paths = {row["execution_path"] for row in ordered}
    result["assignments"] = ordered
    result["redundancy_depth"] = len(ordered)
    result["execution_paths"] = sorted(paths)
    result["single_path_risk"] = len(paths) <= 1
    result["evidence_class"] = (
        "MEASURED" if any(r.get("score_source") in ("MEASURED", "DERIVED") for r in ordered)
        else "COVERED_UNRANKED"
    )
    if result["evidence_class"] == "COVERED_UNRANKED":
        result["why_unranked"] = (
            "the capability is covered, but no per-model suite measured it, so these are "
            "listed in coverage order and not ranked by quality"
        )
    saturated = sorted({tag for tag, row in tags.items()
                        if tag in role["tags"] and row.get("suite_saturated")})
    if saturated:
        result["suite_saturated_tags"] = saturated
        result["saturation_note"] = (
            "a suite several models tie at the top of bounds the suite, not the models: "
            "this ordering cannot separate them"
        )
    return result


def build(root: Path) -> dict[str, Any]:
    models = measured_scores(root)
    tags = covered_tags(root)
    hosted = provider_fallbacks(root)
    roles = [rank_role(role, models, tags, hosted) for role in ROLES]

    residency = _load(root, "RESIDENCY_PLAN.json") or {}
    primary_of: dict[str, list[str]] = collections.defaultdict(list)
    for role in roles:
        for row in role["assignments"]:
            if row["depth"] == "PRIMARY":
                primary_of[row["model_id"]].append(role["role"])

    residency_matrix = []
    for assignment in residency.get("assignments") or []:
        model_id = assignment.get("model_id")
        residency_matrix.append({
            "model_id": model_id,
            "tier": assignment.get("tier"),
            "target_residency_state": assignment.get("target_residency_state"),
            "tier_reason": assignment.get("reason"),
            "peak_ram_mb": assignment.get("peak_ram_mb"),
            "roles_served_as_primary": sorted(primary_of.get(model_id, [])),
            "residency_authority": "local_runtime residency policy",
        })
    for model_id in sorted(set(primary_of) - {row["model_id"] for row in residency_matrix}):
        residency_matrix.append({
            "model_id": model_id,
            "tier": "NOT_IN_LOCAL_PLAN",
            "target_residency_state": "SERVERLESS" if str(model_id).startswith("@cf/") else "UNKNOWN",
            "tier_reason": "served by a hosted catalog; it holds no residency on this host",
            "roles_served_as_primary": sorted(primary_of[model_id]),
            "residency_authority": "provider",
        })

    capacity = _load(root, "WORKER_CAPACITY_MATRIX.json") or {}
    worker_roles = []
    for worker in capacity.get("WORKER_CAPACITY_MATRIX") or []:
        holds_weights = bool(worker.get("holds_custom_weights"))
        serves = []
        for role in roles:
            for row in role["assignments"]:
                path = row["execution_path"]
                if holds_weights and path == "LOCAL_PROCESS":
                    serves.append(role["role"])
                    break
                if not holds_weights and path == "SERVERLESS_HOSTED_CATALOG" \
                        and worker.get("execution_type") == "SERVERLESS_HOSTED_CATALOG":
                    serves.append(role["role"])
                    break
        worker_roles.append({
            "worker_id": worker.get("worker_id"),
            "execution_type": worker.get("execution_type"),
            "verification_state": worker.get("verification_state"),
            "holds_custom_weights": holds_weights,
            "roles_it_can_serve": sorted(set(serves)),
            "basis": "the execution paths of the models assigned to each role; capacity is not permission",
        })

    covered_roles = [r for r in roles if r["assignments"]]
    single_path = sorted(r["role"] for r in covered_roles if r["single_path_risk"])
    thin = sorted(r["role"] for r in covered_roles if r["redundancy_depth"] < 2)
    uncovered = [{"role": r["role"], "blocker_class": r.get("blocker_class")}
                 for r in roles if not r["assignments"]]

    minimum = []
    for name in MINIMUM_SERVICE_ROLES:
        role = next((r for r in roles if r["role"] == name), None)
        minimum.append({
            "role": name,
            "has_a_path": bool(role and role["assignments"]),
            "depth": role["redundancy_depth"] if role else 0,
            "primary": role["assignments"][0]["model_id"] if role and role["assignments"] else None,
        })

    return {
        "tool": "role_specialization",
        "ROLE_CAPABILITY_MATRIX": roles,
        "MODEL_RESIDENCY_MATRIX": residency_matrix,
        "WORKER_ROLE_MATRIX": worker_roles,
        "roles_total": len(roles),
        "roles_with_a_primary": len(covered_roles),
        "roles_measured": sum(1 for r in covered_roles if r["evidence_class"] == "MEASURED"),
        "roles_covered_but_unranked": sum(1 for r in covered_roles
                                          if r["evidence_class"] == "COVERED_UNRANKED"),
        "ROLE_REDUNDANCY_GAPS": thin,
        "SINGLE_PATH_RISKS": single_path,
        "UNCOVERED_ROLES": uncovered,
        "MINIMUM_SERVICE_PROFILE": {
            "roles": minimum,
            "satisfied": all(row["has_a_path"] for row in minimum),
            "basis": "a path existing is not a guarantee of capacity; the capacity matrix holds that",
        },
        "routing_authority": False,
        "model_selection_authority": False,
        "admission_authority": False,
        "scheduling_authority": False,
        "note": (
            "Roles are a view over capability tags the waves measured, not a second capability "
            "vocabulary. A role with no measured evidence gets no PRIMARY and carries its "
            "blocker through unchanged; a covered-but-unranked role says so rather than "
            "implying an order its evidence cannot support."
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--evidence", help="write the matrices to this path as JSON")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = build(root)
    if args.evidence:
        out = Path(args.evidence)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(
        f"ROLE_SPECIALIZATION=BUILT roles={report['roles_total']} "
        f"with_primary={report['roles_with_a_primary']} "
        f"measured={report['roles_measured']} "
        f"single_path_risks={len(report['SINGLE_PATH_RISKS'])} "
        f"uncovered={len(report['UNCOVERED_ROLES'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
