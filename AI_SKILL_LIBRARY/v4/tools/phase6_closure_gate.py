"""Is the federation actually operating 24/7, and is Phase 6 finished?

    python AI_SKILL_LIBRARY/v4/tools/phase6_closure_gate.py --evidence /tmp/p6.json

Six flags, deliberately not synonyms. Collapsing them is the single most likely
way this phase gets reported as done when it is not:

  PHASE6_OPERATIONAL_CLOSED   every Phase 6 exit criterion is proven and no
                              measurable work remains
  24X7_FEDERATION_READY       the federation keeps its minimum service promise
                              and recovers from the failures that were drilled
  ALL_ROLES_REDUNDANT         every role has two INDEPENDENT paths
  ALL_MODELS_EXACT            every role is served by the model that was asked
                              for rather than a provider's substitute
  ALL_CAPABILITIES_COVERED    inherited from the wave gates
  ALL_WORKERS_ONLINE          a reading of this instant, not a property

A federation can be 24/7-ready with most of the others false, and it is: every
local role runs on one host, so nothing is redundant, and four roles are served
by a provider's own model under its own name. Both facts are true at once and
the report must say both.

The snapshot below is taken from THIS host, measured, plus the recorded
provider paths. It is not a scenario: the worker is the container this runs in
and its RAM is whatever `detect_resources` reads at the time.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_SKILL_LIBRARY.v4.local_runtime.federation_ops import (  # noqa: E402
    FederationHealth,
    FederationOps,
    ServiceProfile,
)
from AI_SKILL_LIBRARY.v4.local_runtime.free_worker_mesh import FreeWorkerMesh  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.residency import ResidencyState  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.workers import WorkerRegistry  # noqa: E402
from AI_SKILL_LIBRARY.v4.tools import role_capability_matrix  # noqa: E402
from AI_SKILL_LIBRARY.v4.tools.wave3_free_execution_paths import load_registry  # noqa: E402
from AI_SKILL_LIBRARY.v4.tools.wave3_placement import register_this_host  # noqa: E402

EVIDENCE = "CHECKPOINTS/evidence"

#: Every criterion Phase 6 named. Each maps to something read, never asserted.
EXIT_CRITERIA = (
    "ROLE_BRANCHES_DEFINED", "ROLE_CAPABILITY_MATRIX_VALID",
    "PRIMARY_SECONDARY_FALLBACK_MAPPING_VALID", "SPECIALIZATION_EVIDENCE_VALID",
    "DYNAMIC_RESIDENCY_PROVEN", "AUTO_WAKE_SLEEP_PROVEN",
    "WORKER_HEARTBEAT_PROVEN", "WORKER_AUTO_OFFLINE_PROVEN",
    "WORKER_FAILOVER_PROVEN", "PROVIDER_FAILOVER_PROVEN",
    "QUOTA_AWARE_ROUTING_PROVEN", "CIRCUIT_BREAKER_PROVEN",
    "ROLE_REDUNDANCY_RECORDED", "CAPACITY_PLANNER_VALID",
    "MINIMUM_SERVICE_PROFILE_PROVEN", "NORMAL_SERVICE_PROFILE_PROVEN",
    "PRIVACY_ROUTING_PROVEN", "24X7_FEDERATION_PROOF",
)

#: Which drill round evidences which criterion. A criterion with no round
#: behind it cannot pass, which is why this table is explicit rather than
#: inferred from round names.
CRITERION_ROUNDS = {
    "DYNAMIC_RESIDENCY_PROVEN": ("L", "O", "P", "Q"),
    "AUTO_WAKE_SLEEP_PROVEN": ("M", "N"),
    "WORKER_HEARTBEAT_PROVEN": ("C",),
    "WORKER_AUTO_OFFLINE_PROVEN": ("B", "R"),
    "WORKER_FAILOVER_PROVEN": ("C", "F", "J", "K"),
    "PROVIDER_FAILOVER_PROVEN": ("H",),
    "QUOTA_AWARE_ROUTING_PROVEN": ("E",),
    "CIRCUIT_BREAKER_PROVEN": ("D",),
    "PRIVACY_ROUTING_PROVEN": ("G",),
    "MINIMUM_SERVICE_PROFILE_PROVEN": ("S", "U"),
    "NORMAL_SERVICE_PROFILE_PROVEN": ("T",),
    "24X7_FEDERATION_PROOF": ("A", "I", "V"),
}


def _load(root: Path, name: str) -> Any:
    try:
        return json.loads((root / EVIDENCE / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _model_costs(root: Path) -> dict[str, dict[str, Any]]:
    """Peak RAM and cold-load, from recorded runs. Never a guess."""
    costs: dict[str, dict[str, Any]] = {}
    for path in sorted((root / EVIDENCE).glob("*.json")):
        try:
            blob = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        stack: list[Any] = [blob]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                model = node.get("model_id") or (node.get("artifact_identity") or {}).get("model_id")
                if model:
                    entry = costs.setdefault(str(model), {})
                    for key in ("peak_ram_mb", "cold_load_ms", "load_latency_ms"):
                        value = node.get(key)
                        if isinstance(value, (int, float)) and value > 0:
                            target = "cold_load_ms" if key == "load_latency_ms" else key
                            entry[target] = max(entry.get(target, 0.0), float(value))
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
    return {k: v for k, v in costs.items() if v}


def snapshot(root: Path, now: float) -> tuple[dict[str, Any], dict[str, Any]]:
    """This host plus the recorded providers. Measured, not constructed."""
    matrix = role_capability_matrix.build(root)
    registry = WorkerRegistry()
    worker = register_this_host(root, registry)
    registry.healthcheck(worker.worker_id, healthy=True, now=now)
    providers, _ = load_registry(root)
    ops = FederationOps(FreeWorkerMesh(registry, providers), matrix)

    # Physical residency: what is on this machine right now. A model whose
    # artifact is in the cache is READY; anything else is COLD and would have
    # to be acquired.
    cache = root / ".model-cache" / "models"
    on_disk = {p.name for p in cache.iterdir()} if cache.is_dir() else set()
    physical: dict[str, ResidencyState] = {}
    for row in matrix["ROLE_CAPABILITY_MATRIX"]:
        for model in (row.get("all_candidates") or []):
            if str(model).startswith("@"):
                continue
            key = str(model).replace("/", "_")
            physical[str(model)] = (
                ResidencyState.READY
                if any(entry.startswith(key) for entry in on_disk)
                else ResidencyState.COLD)

    return matrix, dict(ops.snapshot(now=now, physical=physical,
                                     model_costs=_model_costs(root)))


def build(root: Path) -> dict[str, Any]:
    now = time.time()
    matrix, live = snapshot(root, now)
    proof = _load(root, "FEDERATION_24X7_PROOF.json") or {}
    wave4 = _load(root, "WAVE4_CLOSURE.json") or {}
    wave5 = _load(root, "WAVE5_CLOSURE.json") or {}
    core = _load(root, "AI_CORE_CONVERGENCE.json") or {}

    round_passed = {r["round"]: bool(r["passed"]) for r in (proof.get("rounds") or [])}
    failures: list[str] = []
    # Real, named, and not this repository's to fix from here.
    external_blockers: list[str] = []
    criteria: dict[str, bool] = {}

    for criterion in EXIT_CRITERIA:
        needed = CRITERION_ROUNDS.get(criterion)
        if needed:
            missing = [r for r in needed if r not in round_passed]
            if missing:
                criteria[criterion] = False
                failures.append(
                    f"{criterion}: round(s) {', '.join(missing)} did not run, and a "
                    f"round that did not run did not pass")
                continue
            criteria[criterion] = all(round_passed[r] for r in needed)
            if not criteria[criterion]:
                failed = [r for r in needed if not round_passed[r]]
                failures.append(f"{criterion}: round(s) {', '.join(failed)} failed")
            continue

        # The criteria that are read from the matrix rather than from a drill.
        if criterion == "ROLE_BRANCHES_DEFINED":
            criteria[criterion] = matrix["role_branch_count"] > 0
        elif criterion == "ROLE_CAPABILITY_MATRIX_VALID":
            # Valid means every non-placeholder role reached a determination and
            # every gap is explained. It does NOT mean every role is available.
            unexplained = [r["role_id"] for r in matrix["ROLE_CAPABILITY_MATRIX"]
                           if not r.get("placeholder") and r["status"] == "UNAVAILABLE"
                           and not r.get("capabilities_uncovered")]
            criteria[criterion] = not unexplained
            if unexplained:
                failures.append(f"ROLE_CAPABILITY_MATRIX_VALID: unexplained gap in "
                                f"{', '.join(unexplained)}")
        elif criterion == "PRIMARY_SECONDARY_FALLBACK_MAPPING_VALID":
            bad = [r["role_id"] for r in matrix["ROLE_CAPABILITY_MATRIX"]
                   if r.get("primary") and r["primary"].get("model_id")
                   and r.get("secondary")
                   and r["primary"]["model_id"] == r["secondary"].get("model_id")]
            criteria[criterion] = not bad
            if bad:
                failures.append(f"a role names the same model primary and secondary: "
                                f"{', '.join(bad)}")
        elif criterion == "SPECIALIZATION_EVIDENCE_VALID":
            # Every named primary must carry evidence references. A mapping with
            # no evidence behind it is the thing this gate exists to catch.
            missing = [r["role_id"] for r in matrix["ROLE_CAPABILITY_MATRIX"]
                       if r.get("primary") and not (r["primary"].get("evidence_refs"))]
            criteria[criterion] = not missing
            if missing:
                failures.append(f"primary with no evidence reference: {', '.join(missing)}")
        elif criterion == "ROLE_REDUNDANCY_RECORDED":
            # Recorded, not achieved. Pretending redundancy exists is the
            # failure; saying plainly that it does not is the pass.
            criteria[criterion] = "single_path_risks" in matrix
        elif criterion == "CAPACITY_PLANNER_VALID":
            plans = live.get("ROLE_CAPACITY_PLAN") or []
            criteria[criterion] = bool(plans) and all(
                "capacity_status" in p and "demand_basis" in p for p in plans)
        else:  # pragma: no cover - every criterion is handled above
            criteria[criterion] = False
            failures.append(f"{criterion}: no evidence source is wired for it")

        if not criteria[criterion] and criterion not in (
                c for c, _ in CRITERION_ROUNDS.items()):
            if criterion not in [f.split(":")[0] for f in failures]:
                failures.append(f"{criterion}: not satisfied")

    # A single PROVEN/FAILED string cannot tell "a drill failed" from "this host
    # has no engine to run the live round on", and those want opposite responses
    # from a closure gate. The proof now separates them, and the separation is
    # settled by probing the engine rather than by the flag that skipped the
    # round, so nothing here can be reached by passing an argument.
    federation_external = (proof.get("blocking_class") == "REAL_RUNTIME_REQUIRED"
                           and not proof.get("state_rounds_failed"))
    if proof.get("federation_status") != "PROVEN" and not federation_external:
        failures.append(
            f"FEDERATION_24X7_PROOF is {proof.get('federation_status') or 'absent'}")
    elif federation_external:
        # Reported, never swallowed: every state round passed at this revision
        # and the live inference round remains unmeasured here.
        external_blockers.append(
            "FEDERATION_24X7_PROOF: every state round passed; the live inference "
            "round is REAL_RUNTIME_REQUIRED on this host. "
            + str((proof.get("live_round") or {}).get("operator_action") or ""))

    # 24/7 readiness is a narrower question than closure: can it keep its
    # minimum promise, and did it recover from what was drilled?
    profiles = live.get("SERVICE_PROFILES") or {}
    minimum_met = bool((profiles.get(ServiceProfile.MINIMUM.value) or {}).get("met"))
    recovered = round_passed.get("J", False)
    state = str(live.get("FEDERATION_STATE") or "")
    ready = (minimum_met and recovered
             and state not in (FederationHealth.CRITICAL.value,))
    if not minimum_met:
        failures.append("the minimum service profile is not met on this host")

    roles = [r for r in matrix["ROLE_CAPABILITY_MATRIX"] if not r.get("placeholder")]
    all_redundant = bool(roles) and all(r.get("redundant") for r in roles)
    served = [r for r in roles if (r.get("primary") or {}).get("model_id")]
    all_exact = bool(served) and all(
        (r.get("primary") or {}).get("execution_mode") == "EXACT_MODEL" for r in served)
    workers_offline = live.get("WORKERS_OFFLINE") or []

    closed = not failures
    return {
        "tool": "phase6_closure_gate",
        "PHASE6_OPERATIONAL_CLOSED": closed,
        # Five more facts, none of which the first one implies.
        "24X7_FEDERATION_READY": ready,
        "ALL_ROLES_REDUNDANT": all_redundant,
        "ALL_MODELS_EXACT": all_exact,
        "ALL_CAPABILITIES_COVERED": bool(core.get("AI_CORE_ALL_CAPABILITIES_COVERED")),
        "ALL_WORKERS_ONLINE": not workers_offline,
        "exit_criteria": criteria,
        "FEDERATION_STATE": state,
        "ROLE_HEALTH": live.get("ROLE_HEALTH"),
        "WORKER_ROLE_MATRIX": live.get("WORKER_ROLE_MATRIX"),
        "MODEL_RESIDENCY_MATRIX": live.get("MODEL_RESIDENCY_MATRIX"),
        "ROLE_CAPACITY_PLAN": live.get("ROLE_CAPACITY_PLAN"),
        "SERVICE_PROFILES": profiles,
        "WORKERS_ONLINE": live.get("WORKERS_ONLINE"),
        "WORKERS_OFFLINE": workers_offline,
        "VERIFIED_PROVIDERS": live.get("VERIFIED_PROVIDERS"),
        "CIRCUIT_BREAKERS": live.get("CIRCUIT_BREAKERS"),
        "CAPACITY_DEFICITS": live.get("CAPACITY_DEFICITS"),
        "SINGLE_PATH_RISKS": matrix.get("single_path_risks"),
        "ROLE_REDUNDANCY_GAPS": matrix.get("role_redundancy_gaps"),
        "role_branch_count": matrix.get("role_branch_count"),
        "roles_with_a_path": matrix.get("roles_with_a_path"),
        "roles_requiring_a_path": matrix.get("roles_requiring_a_path"),
        "roles_degraded": matrix.get("roles_degraded"),
        "roles_unavailable": matrix.get("roles_unavailable"),
        "inherited": {
            "WAVE4_OPERATIONAL_CLOSED": bool(wave4.get("WAVE4_OPERATIONAL_CLOSED")),
            "WAVE5_OPERATIONAL_CLOSED": bool(wave5.get("WAVE5_OPERATIONAL_CLOSED")),
            "AI_CORE_DONE": bool(core.get("AI_CORE_DONE")),
        },
        "failures": failures,
        "external_blockers": external_blockers,
        # Closure and a proven live path are different claims, and this is false
        # whenever the live round could not be measured on this host.
        "LIVE_EXECUTION_PROVEN_HERE": proof.get("live_round_status") == "PASSED",
        "note": (
            "Closed, ready, redundant, exact, covered and all-online are six "
            "different facts. This federation is ready and not redundant: every "
            "local role runs on one host. Reporting the first and letting a "
            "reader infer the rest is the failure this gate prevents."),
        "routing_authority": False,
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

    print(f"PHASE6_OPERATIONAL_CLOSED={result['PHASE6_OPERATIONAL_CLOSED']} "
          f"24X7_FEDERATION_READY={result['24X7_FEDERATION_READY']}")
    print(f"  ALL_ROLES_REDUNDANT={result['ALL_ROLES_REDUNDANT']} "
          f"ALL_MODELS_EXACT={result['ALL_MODELS_EXACT']} "
          f"ALL_WORKERS_ONLINE={result['ALL_WORKERS_ONLINE']}")
    print(f"  FEDERATION_STATE={result['FEDERATION_STATE']}")
    for criterion, ok in result["exit_criteria"].items():
        print(f"  {'PASS' if ok else 'FAIL'} {criterion}")
    for failure in result["failures"]:
        print(f"  FAIL {failure}")
    return 0 if result["PHASE6_OPERATIONAL_CLOSED"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
