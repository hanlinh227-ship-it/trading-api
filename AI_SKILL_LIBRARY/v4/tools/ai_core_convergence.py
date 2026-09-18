"""Has the AI Core converged? One verdict, from the gates that already exist.

    python AI_SKILL_LIBRARY/v4/tools/ai_core_convergence.py --evidence /tmp/conv.json

Three waves closed on their own terms and the release gate passed on its own
terms. Nothing asked whether they add up to a core that is done, which is
exactly the state in which a system is most easily declared finished: every
report says PASS, and nobody has asked what each PASS is a PASS *of*.

So this reads the recorded verdicts and combines them under one rule:

    AI_CORE_DONE is true only when every wave is operationally closed, the
    release gate passes, the worker fabric is proven, and no capability gap is
    still work that could be done at zero cost.

Three facts are reported separately and none may imply another:

  AI_CORE_DONE                     nothing measurable is left undone
  AI_CORE_ALL_CAPABILITIES_COVERED every declared capability is measured
  AI_CORE_ALL_EXACT_MODELS_AVAILABLE every capability is served by the model
                                   that was asked for

The first is expected true and the other two false. A core can be finished and
still not cover everything, because some gaps are a licence the operator has
not accepted and some are a model that does not exist on any free tier. Saying
"done" while quietly meaning "covered" is the failure this file exists to
prevent.

This gate observes. It closes nothing, promotes nothing, and grants nothing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

EVIDENCE = "CHECKPOINTS/evidence"


def _load(root: Path, name: str) -> Any:
    try:
        return json.loads((root / EVIDENCE / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def build(root: Path) -> dict[str, Any]:
    failures: list[str] = []
    waves: list[dict[str, Any]] = []

    # -- the three waves, each read from its own gate's output --------------
    wave3 = _load(root, "WAVE3_CLOSURE.json")
    if wave3 is None:
        failures.append("WAVE3_CLOSURE.json is absent or unreadable, and absent is not passing")
    else:
        waves.append({
            "wave": 3,
            "kind": "candidate wave",
            "operational_closed": bool(wave3.get("WAVE3_OPERATIONAL_CLOSED")),
            "all_exact_models_available": bool(wave3.get("WAVE3_ALL_EXACT_MODELS_AVAILABLE")),
            "all_capabilities_covered": None,  # Wave 3 closes on candidates, not tags
            "outstanding": wave3.get("exact_models_without_an_executable_path") or [],
        })
        if not wave3.get("WAVE3_OPERATIONAL_CLOSED"):
            failures.append("Wave 3 is not operationally closed")

    for n in (4, 5):
        blob = _load(root, f"WAVE{n}_CLOSURE.json")
        if blob is None:
            failures.append(f"WAVE{n}_CLOSURE.json is absent or unreadable")
            continue
        waves.append({
            "wave": n,
            "kind": "capability wave",
            "operational_closed": bool(blob.get(f"WAVE{n}_OPERATIONAL_CLOSED")),
            "all_capabilities_covered": bool(blob.get(f"WAVE{n}_ALL_CAPABILITIES_COVERED")),
            "all_exact_models_available": bool(blob.get(f"WAVE{n}_ALL_EXACT_MODELS_AVAILABLE")),
            "covered": f"{blob.get('capabilities_covered')}/{blob.get('capabilities_total')}",
            "outstanding": blob.get("measurable_work_outstanding") or [],
            "uncovered": blob.get("capabilities_uncovered") or [],
            "covered_by_a_substitute": blob.get("covered_by_a_provider_substitute") or [],
            "suite_saturated": blob.get("covered_but_suite_saturated") or [],
        })
        if not blob.get(f"WAVE{n}_OPERATIONAL_CLOSED"):
            failures.append(f"Wave {n} is not operationally closed")
        for tag in (blob.get("measurable_work_outstanding") or []):
            failures.append(
                f"wave {n}/{tag}: measurable at zero cost and not measured, so this is "
                f"work outstanding rather than a closed gap")

    # -- the fabric and the release, read rather than assumed ---------------
    release = _load(root, "AI_CORE_RELEASE_GATE.json") or {}
    mesh = _load(root, "FREE_WORKER_MESH_PROOF.json") or {}
    federation = _load(root, "WAVE3_FEDERATION_PROOF.json") or {}
    capacity = _load(root, "WORKER_CAPACITY_MATRIX.json") or {}

    release_pass = release.get("verdict") == "PASS" or release.get("status") == "PASS"
    mesh_proven = mesh.get("mesh_status") == "PROVEN"
    federation_proven = federation.get("federation_status") == "PROVEN"
    capacity_read = bool(capacity.get("WORKER_CAPACITY_MATRIX"))

    for name, ok in (("AI_CORE_RELEASE_GATE", release_pass),
                     ("FREE_WORKER_MESH", mesh_proven),
                     ("WAVE3_FEDERATION", federation_proven),
                     ("WORKER_CAPACITY_MATRIX", capacity_read)):
        if not ok:
            failures.append(f"{name} does not hold in the recorded evidence")

    covered_flags = [w["all_capabilities_covered"] for w in waves
                     if w["all_capabilities_covered"] is not None]
    exact_flags = [w["all_exact_models_available"] for w in waves]

    done = not failures
    return {
        "tool": "ai_core_convergence",
        "AI_CORE_DONE": done,
        # Separate facts. "Done" means nothing measurable is left; it does not
        # mean covered, and it certainly does not mean the requested models run.
        "AI_CORE_ALL_CAPABILITIES_COVERED": bool(covered_flags) and all(covered_flags),
        "AI_CORE_ALL_EXACT_MODELS_AVAILABLE": bool(exact_flags) and all(exact_flags),
        "waves": waves,
        "fabric": {
            "AI_CORE_RELEASE_GATE": "PASS" if release_pass else "NOT_PASS",
            "FREE_WORKER_MESH": "PROVEN" if mesh_proven else "NOT_PROVEN",
            "WAVE3_FEDERATION": "PROVEN" if federation_proven else "NOT_PROVEN",
            "WORKER_CAPACITY_MATRIX": "READ" if capacity_read else "ABSENT",
        },
        "remaining_not_actionable_here": sorted({
            tag for w in waves for tag in (w.get("uncovered") or [])}),
        "failures": failures,
        "note": (
            "A core that is done is not a core that covers everything. Gaps that "
            "remain are a licence the operator has not accepted, or a model that "
            "exists on no verified free tier - neither of which this runtime may "
            "close on its own. Reporting one of those as coverage, or reporting "
            "'done' while meaning 'covered', is the failure this gate prevents."),
        "routing_authority": False,
        "admission_authority": False,
        "merge_authority": False,
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

    print(f"AI_CORE_DONE={result['AI_CORE_DONE']} "
          f"ALL_CAPABILITIES_COVERED={result['AI_CORE_ALL_CAPABILITIES_COVERED']} "
          f"ALL_EXACT_MODELS_AVAILABLE={result['AI_CORE_ALL_EXACT_MODELS_AVAILABLE']}")
    for w in result["waves"]:
        print(f"  wave {w['wave']} ({w['kind']:<16}) closed={w['operational_closed']} "
              f"covered={w.get('covered') or '-'}")
    for name, state in result["fabric"].items():
        print(f"  {name:<24} {state}")
    for failure in result["failures"]:
        print(f"  FAIL {failure}")
    return 0 if result["AI_CORE_DONE"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
