"""Which model will the mesh pick? Ask it, before spending a download on a guess.

    python AI_SKILL_LIBRARY/v4/tools/golden_selection_preview.py

The production golden worker staged Qwen3-0.6B because it is the smallest
admitted model and the download is cheapest. That was the wrong question. The
workflow does not choose the model - Model Mesh does, from measured capability -
and on the current evidence it does not choose the small one. So the runtime
asked the cache for the model the mesh had selected, found nothing, and refused:
"no verified artifact cached for this identity". Correctly. Caching a model
nobody selected is not caching the model.

This runs the canonical chain as far as the selection and stops. Ingress,
task_router, AI Legion and Model Mesh are the same injected callables the golden
run uses - imported, never reimplemented - and no runtime is constructed, so it
needs no engine and no weights. It reports which model the mesh would execute,
so the worker can stage exactly that one.

**This selects nothing.** It reports the selection the mesh already makes. Model
Mesh remains the sole model-selection authority; this is a read of its answer.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_SKILL_LIBRARY.v4.tools.local_runtime_ai_core_e2e import (  # noqa: E402
    admitted_candidates, declared_identities, ingress, make_legion, make_router,
    make_selector)

AUTHORITY = False
MODEL_SELECTION_AUTHORITY = False

CANONICAL_REQUEST = "What is the capital city of Japan? Answer briefly."


def preview(root: Path, request: str = CANONICAL_REQUEST) -> dict[str, Any]:
    """The mesh's own answer, reached by the chain's own stages."""
    pairs = admitted_candidates(root)
    if not pairs:
        return {"status": "REFUSED", "reason": "no governance-admitted local model"}

    envelope = {"request": request, "profile": "STANDARD"}
    router = make_router(root)
    route = router(envelope)
    if not isinstance(route, dict) or route.get("routed_by") != "task_router":
        return {"status": "REFUSED", "reason": "task_router evidence is required"}
    prepared = ingress(envelope, route)

    # Legion runs because the chain runs it, and because a preview that skipped
    # a stage could preview a different selection from the one the real run makes.
    assignment = make_legion(root)(route, prepared)
    if not isinstance(assignment, dict) or assignment.get(
            "orchestration_authority") is not False:
        return {"status": "REFUSED",
                "reason": "AI Legion must not claim orchestration authority"}

    selection = make_selector(declared_identities(pairs))(
        prepared["selection_request"], [candidate for candidate, _ in pairs])
    primary = selection.get("primary_model") if isinstance(selection, dict) else None
    if not isinstance(primary, dict):
        return {"status": "REFUSED", "reason": "Model Mesh made no primary selection"}

    identity = primary.get("artifact_identity") or {}
    return {
        "status": "SELECTED",
        "tool": "golden_selection_preview",
        "request": request,
        "routed_by": route.get("routed_by"),
        "specialist_group": assignment.get("specialist_group"),
        # The primary carries its identity in `artifact_identity`; a bare
        # `model_id` at the top level is absent, and reading only that returned
        # None while the digest beside it named the model perfectly well.
        "selected_model_id": (identity.get("model_id")
                              or primary.get("model_id")
                              or primary.get("candidate_key")),
        "candidate_key": primary.get("candidate_key"),
        "artifact_sha256": identity.get("sha256"),
        "immutable_revision": identity.get("immutable_revision"),
        "candidates_considered": len(pairs),
        "authority": AUTHORITY,
        "model_selection_authority": MODEL_SELECTION_AUTHORITY,
        "note": ("reports the selection Model Mesh makes; it does not make one, "
                 "and staging a different model would not change this answer"),
    }


FEDERATED_REQUEST = "In one sentence, what does a worker contribute to a federation?"


def federated_plan_models(root: Path, request: str = FEDERATED_REQUEST) -> list[str]:
    """Every model the federated live round PLANS to run, maker and checker.

    The golden chain runs one model. The live rounds in the free-worker and
    24x7 proofs run a maker AND a checker, and a worker staged one model, so
    the checker came back "no verified artifact cached" - a correct refusal to
    a question nobody had prepared for. This replays the planning half of
    `run_federated` and stops: route, admit, select, plan. No backend is
    constructed and no weights are touched, so it needs no engine.
    """
    from AI_SKILL_LIBRARY.v4.local_runtime.multi_model import (  # noqa: PLC0415
        _worker_task, admitted, mesh, mesh_select, plan_execution, route_request)
    import datetime

    observed_at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    routed = route_request(request, root=root)
    domain, primary_skill = routed["domain"], routed["primary_skill"]
    pairs = admitted(root, observed_at)
    if not pairs:
        return []
    candidates = [candidate for candidate, _ in pairs]
    winner, _ = mesh_select(candidates, domain=domain, primary_skill=primary_skill)
    if winner is None:
        return []
    primary_key = "%s:%s" % (winner.get("provider_id"), winner.get("model_id"))
    supporting = [
        worker for worker in mesh.select_workers(
            _worker_task(domain, primary_skill, "STANDARD", candidates),
            list(candidates), max_workers=4)
        if "%s:%s" % (worker.get("provider_id"), worker.get("model_id")) != primary_key
    ]
    plan = plan_execution(
        "STANDARD",
        {"primary_model": {"candidate_key": primary_key,
                           "model_id": winner.get("model_id")},
         "supporting_models": [
             {"candidate_key": "%s:%s" % (w.get("provider_id"), w.get("model_id")),
              "model_id": w.get("model_id")} for w in supporting],
         "verifier": primary_skill},
        [primary_skill.upper()])
    out = []
    for entry in (plan.get("models") or []):
        # Entries carry a candidate_key and sometimes a bare model_id; the two
        # spellings are why the round-V role check had to be normalised too.
        raw = str(entry.get("model_id") or entry.get("candidate_key") or "")
        _, separator, remainder = raw.partition(":")
        bare = remainder if separator and remainder else raw
        if bare and bare not in out:
            out.append(bare)
    return out


def required_models(root: Path, request: str = CANONICAL_REQUEST) -> list[str]:
    """Everything a full production run needs staged, in one list.

    The golden primary first, then whatever the federated live rounds plan.
    Staging fewer than this is how a run reaches real inference and then fails
    on a round nobody provisioned for.
    """
    models: list[str] = []
    report = preview(root, request)
    if report.get("selected_model_id"):
        models.append(report["selected_model_id"])
    for model_id in federated_plan_models(root):
        if model_id not in models:
            models.append(model_id)
    return models


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=repo_root)
    parser.add_argument("--request", default=CANONICAL_REQUEST)
    parser.add_argument("--evidence", type=Path, default=None)
    parser.add_argument("--print-model-id", action="store_true",
                        help="print only the selected model_id, for shell capture")
    parser.add_argument("--print-required-models", action="store_true",
                        help="print every model a full run must stage, one per line")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.print_required_models:
        for model_id in required_models(args.root, args.request):
            print(model_id)
        return 0

    report = preview(args.root, args.request)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if report["status"] != "SELECTED":
        print("GOLDEN_SELECTION=REFUSED %s" % report["reason"], file=sys.stderr)
        return 1
    if args.print_model_id:
        print(report["selected_model_id"])
        return 0
    print("GOLDEN_SELECTION=%s" % report["selected_model_id"])
    print("  candidates_considered=%s" % report["candidates_considered"])
    print("  artifact_sha256=%s" % report["artifact_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
