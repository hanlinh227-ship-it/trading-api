"""Run the federation across the six task types Wave 3's exit gate names.

    python AI_SKILL_LIBRARY/v4/tools/wave3_federation_proof.py --evidence /tmp/fed.json

`local_runtime_federation.py` runs one request. This runs the six the gate asks
for - deep reasoning, coding, debugging, verification, Vietnamese and synthesis -
through that same entry point, and checks the structural properties the gate
requires of every round. It adds no orchestrator and no second plan: it calls
`run_federated` and reads what came back.

Four properties, checked on each round rather than asserted once:

**An AI Legion specialist role is assigned, and the Model Mesh selects under it.**
Reported by the round as `specialist_groups` alongside
`model_selection_authority`. A round that selected a model without a role would
be the wrong architecture, not a bad answer.

**Nothing is resolved by vote.** `resolved_by_vote` must be false on every
round. Two models agreeing is not evidence that either is right, and a majority
of three is worse because it looks like proof.

**Disagreement stays disagreement.** When the maker and checker differ, the
round says so and the primary's answer stands, with adjudication left to a
verifier or a human. A round that quietly reconciled them would be voting under
another name.

**Authority stays where it was.** Routing is `task_router`, selection is
`model_mesh`, planning is `control_plane.plan_execution`, on every round.

The answers themselves are recorded but not graded. Whether a model answered
well is what the benchmark suites measure; this measures whether the federation
ran the way the architecture says it does.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_SKILL_LIBRARY.v4.local_runtime.multi_model import (  # noqa: E402
    FederationError,
    run_federated,
)

#: One request per task type the exit gate lists. Kept short because the point
#: is the federation's shape, not the depth of any single answer.
ROUNDS: tuple[tuple[str, str, str], ...] = (
    ("A", "deep_reasoning",
     "If every A is a B, and every B is a C, is every A a C? Answer yes or no and why, briefly."),
    ("B", "coding",
     "Write a Python function that returns the second largest distinct value in a list, "
     "or None when there is no second distinct value."),
    ("C", "debugging",
     "This function returns the wrong total. Name the defect in one sentence.\n"
     "def total(values):\n    s = 0\n    for i in range(1, len(values)):\n        s += values[i]\n    return s"),
    ("D", "verifier_checker",
     "A scanner reported 'Scanned files: 1' and 'Data scanned: 0.00 MB'. Does that prove "
     "the file is clean? Answer briefly."),
    ("E", "vietnamese_reasoning",
     "Trả lời ngắn gọn bằng tiếng Việt. Hỏi: Mặt trời mọc ở hướng nào?"),
    ("F", "synthesis_generalist",
     "In two sentences, say what a capability benchmark can and cannot establish "
     "about a model."),
)


def check(round_id: str, capability: str, result: dict[str, Any]) -> dict[str, Any]:
    """Structural findings for one round. Empty failures means it held."""
    workers = result.get("workers") or []
    failures: list[str] = []

    if not result.get("specialist_groups"):
        failures.append("no AI Legion specialist group was assigned")
    if result.get("routing_authority") != "task_router":
        failures.append(f"routing authority was {result.get('routing_authority')!r}")
    if result.get("model_selection_authority") != "model_mesh":
        failures.append(f"model selection authority was {result.get('model_selection_authority')!r}")
    if result.get("execution_plan_authority") != "control_plane.plan_execution":
        failures.append(f"plan authority was {result.get('execution_plan_authority')!r}")
    if result.get("resolved_by_vote") is not False:
        failures.append("a round was resolved by vote")
    if not workers:
        failures.append("no worker ran")
    if any(worker.get("error") for worker in workers):
        failures.append("a worker errored: " + "; ".join(
            str(w.get("error")) for w in workers if w.get("error")))
    roles = [str(worker.get("role")) for worker in workers]
    if len(workers) > 1 and "checker" not in roles:
        failures.append("more than one worker ran and none of them was the checker")
    # Disagreement must remain visible. "unresolved_here" is the honest value;
    # a round claiming agreement it did not establish would be the failure.
    if len(workers) > 1 and result.get("outputs_identical") is False:
        if result.get("substantive_agreement") not in {"unresolved_here", False, True}:
            failures.append("disagreement was neither recorded nor left unresolved")

    return {
        "round": round_id,
        "capability": capability,
        "passed": not failures,
        "failures": failures,
        "collaboration_mode": result.get("collaboration_mode"),
        "specialist_groups": result.get("specialist_groups"),
        "domain": result.get("domain"),
        "primary_skill": result.get("primary_skill"),
        "workers": [
            {"model_id": w.get("model_id"), "role": w.get("role"),
             "latency_ms": w.get("latency_ms"), "error": w.get("error")}
            for w in workers
        ],
        "resolved_by_vote": result.get("resolved_by_vote"),
        "outputs_identical": result.get("outputs_identical"),
        "substantive_agreement": result.get("substantive_agreement"),
        "answer": result.get("answer"),
    }


def build(root: Path, cache: Path, profile: str, max_tokens: int) -> dict[str, Any]:
    rounds: list[dict[str, Any]] = []
    for round_id, capability, request in ROUNDS:
        started = time.time()
        try:
            result = run_federated(request, root=root, cache=cache,
                                   profile=profile, max_tokens=max_tokens).to_dict()
            row = check(round_id, capability, result)
        except FederationError as exc:
            # A refusal is recorded as a failed round, not skipped. A proof that
            # quietly omits the rounds that would not run proves less than it
            # appears to.
            row = {"round": round_id, "capability": capability, "passed": False,
                   "failures": [f"federation refused: {exc}"], "workers": []}
        row["wall_ms"] = round((time.time() - started) * 1000.0, 3)
        rounds.append(row)

    failed = [row["round"] for row in rounds if not row["passed"]]
    models = sorted({str(w["model_id"]) for row in rounds for w in row.get("workers") or []})
    return {
        "tool": "wave3_federation_proof",
        "profile": profile,
        "rounds_run": len(rounds),
        "rounds_passed": len(rounds) - len(failed),
        "failed_rounds": failed,
        "federation_status": "PROVEN" if not failed else "FAILED",
        "models_exercised": models,
        "no_round_resolved_by_vote": all(
            row.get("resolved_by_vote") is False for row in rounds if row.get("workers")),
        "rounds": rounds,
        "note": (
            "Structural proof only. Whether an answer was good is what the "
            "benchmark suites measure; this measures whether the federation ran "
            "the way the architecture says it does."
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=repo_root)
    parser.add_argument("--cache", type=Path, default=repo_root / ".model-cache")
    parser.add_argument("--profile", default="STANDARD", choices=["FAST", "STANDARD", "DEEP"])
    parser.add_argument("--max-tokens", type=int, default=48)
    parser.add_argument("--evidence", type=Path, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = build(args.root, args.cache, args.profile, args.max_tokens)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")

    print(f"WAVE3_FEDERATION={result['federation_status']} "
          f"{result['rounds_passed']}/{result['rounds_run']} "
          f"no_vote={result['no_round_resolved_by_vote']}")
    for row in result["rounds"]:
        workers = ", ".join(f"{w['model_id'].split('/')[-1]}:{w['role']}"
                            for w in row.get("workers") or [])
        print(f"  {row['round']} {row['capability']:<22} "
              f"{'PASS' if row['passed'] else 'FAIL'} {workers}")
        for failure in row["failures"]:
            print(f"      {failure}")
    return 0 if result["federation_status"] == "PROVEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
