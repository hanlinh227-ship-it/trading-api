"""Decide whether a capability wave may close, and name what is still missing.

    python AI_SKILL_LIBRARY/v4/tools/wave_closure_gate.py --wave 4 --evidence /tmp/w4.json

Waves 4 and 5 are capability waves rather than candidate waves: nothing is
admitted, so there is no candidate list to walk. What closes them is whether
every capability the wave declared has reached a determination that is either a
measurement or an evidenced blocker - and, crucially, whether any of those
blockers is still work that this runtime could do at zero cost.

That last part is the whole gate. A wave does not close because the remaining
gaps have been written down nicely. It closes when nothing measurable is left
undone. So each uncovered capability must carry a `blocker_class`:

  NO_SUITE_YET                    nobody has written the task. **Actionable**,
                                  and therefore blocks closure: the honest
                                  response is to go and measure it.
  NO_MODEL_IN_VERIFIED_CATALOG    every verified zero-cost path was read and
                                  none serves this. Not actionable here.
  HUMAN_GATE_REQUIRED             a licence or an account only the operator can
                                  accept. Not actionable here, by design.
  OUT_OF_SCOPE_THIS_WAVE          deliberately deferred, with the reason stated.
  PLACEHOLDER_TAG                 a forward-looking name, not a requirement of
                                  this wave. Excluded from the denominator
                                  rather than counted as a failure.

Three flags, kept apart on purpose, exactly as Wave 3 keeps its two:

  WAVE{N}_OPERATIONAL_CLOSED       no measurable work remains and every gap is
                                   evidenced
  WAVE{N}_ALL_CAPABILITIES_COVERED whether every declared capability is actually
                                   covered by a measurement
  WAVE{N}_ALL_EXACT_MODELS_AVAILABLE whether every covered capability is served
                                   by the model that was asked for, rather than
                                   by a provider's own substitute

The second and third are expected to be false, and a report that let the first
imply either of them would be worthless.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import yaml  # noqa: E402

REQUIREMENTS_REL = "AI_SKILL_LIBRARY/v4/open_model_universe/wave{n}_capability_requirements.yaml"

#: Blocker classes that describe work this runtime could still do. A wave with
#: one of these outstanding is not closed; it is unfinished.
ACTIONABLE_BLOCKERS = frozenset({"NO_SUITE_YET"})

#: Blocker classes that are real answers rather than undone work.
TERMINAL_BLOCKERS = frozenset({
    "NO_MODEL_IN_VERIFIED_CATALOG", "HUMAN_GATE_REQUIRED",
    "OUT_OF_SCOPE_THIS_WAVE", "PLACEHOLDER_TAG",
})

#: Not a requirement of the wave, so it is not counted against coverage.
NOT_A_REQUIREMENT = frozenset({"PLACEHOLDER_TAG"})

#: A measured_model whose id starts with a provider prefix is that provider's
#: own model. Covering a capability with it is legitimate; calling it the
#: requested model is not, which is what the third flag tracks.
PROVIDER_PREFIXES = ("@cf/",)


def build(root: Path, wave: int) -> dict[str, Any]:
    path = root / REQUIREMENTS_REL.format(n=wave)
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    requirements = doc.get("capability_requirements") or []

    failures: list[str] = []
    rows: list[dict[str, Any]] = []
    for req in requirements:
        tag = str(req.get("tag"))
        covered = bool(req.get("measured_covered"))
        model = req.get("measured_model")
        blocker = req.get("blocker_class")
        evidence_class = str(req.get("evidence_class") or "NONE")

        if covered and evidence_class != "MEASURED":
            failures.append(
                f"{tag}: covered but evidence_class is {evidence_class!r}. Coverage "
                f"without a measurement is the claim this gate exists to refuse.")
        if covered and not model:
            failures.append(f"{tag}: covered but names no model, so nothing can be checked")
        if not covered and not blocker:
            failures.append(
                f"{tag}: uncovered with no blocker_class, so the gap is asserted "
                f"rather than classified")
        if blocker and blocker not in (ACTIONABLE_BLOCKERS | TERMINAL_BLOCKERS):
            failures.append(f"{tag}: blocker_class {blocker!r} is not a recognised class")
        if blocker in ACTIONABLE_BLOCKERS:
            failures.append(
                f"{tag}: {blocker} - a suite could be written and run at zero cost, so "
                f"this is work outstanding, not a closed gap")

        rows.append({
            "tag": tag,
            "measured_covered": covered,
            "measured_model": model,
            "evidence_class": evidence_class,
            "blocker_class": blocker,
            "is_a_requirement": blocker not in NOT_A_REQUIREMENT,
            "served_by_a_provider_substitute": bool(
                model and str(model).startswith(PROVIDER_PREFIXES)),
            "saturated": bool(req.get("saturated")),
        })

    requirements_only = [r for r in rows if r["is_a_requirement"]]
    uncovered = [r["tag"] for r in requirements_only if not r["measured_covered"]]
    actionable = [r["tag"] for r in rows if r["blocker_class"] in ACTIONABLE_BLOCKERS]
    substitutes = [r["tag"] for r in rows
                   if r["measured_covered"] and r["served_by_a_provider_substitute"]]
    saturated = [r["tag"] for r in rows if r["saturated"]]

    closed = not failures
    return {
        "tool": "wave_closure_gate",
        "wave": wave,
        f"WAVE{wave}_OPERATIONAL_CLOSED": closed,
        # Deliberately separate. Closing a wave means no measurable work is
        # left; it does not mean every capability is covered, and it certainly
        # does not mean the requested models are the ones running.
        f"WAVE{wave}_ALL_CAPABILITIES_COVERED": not uncovered,
        f"WAVE{wave}_ALL_EXACT_MODELS_AVAILABLE": not substitutes,
        "capabilities_total": len(requirements_only),
        "capabilities_covered": sum(1 for r in requirements_only if r["measured_covered"]),
        "capabilities_uncovered": sorted(uncovered),
        "measurable_work_outstanding": sorted(actionable),
        "covered_by_a_provider_substitute": sorted(substitutes),
        "covered_but_suite_saturated": sorted(saturated),
        "capabilities": rows,
        "failures": failures,
        "note": (
            "A wave closes when nothing measurable is left undone, not when the "
            "remaining gaps are written down well. Coverage by a provider's own "
            "model counts under that model's name and never makes the requested "
            "model available. A saturated suite is flagged because a perfect "
            "score on a thin suite bounds the suite, not the model."),
        "routing_authority": False,
        "admission_authority": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=repo_root)
    parser.add_argument("--wave", type=int, required=True, choices=(4, 5))
    parser.add_argument("--evidence", type=Path, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = build(args.root, args.wave)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")

    w = args.wave
    print(f"WAVE{w}_OPERATIONAL_CLOSED={result[f'WAVE{w}_OPERATIONAL_CLOSED']} "
          f"WAVE{w}_ALL_CAPABILITIES_COVERED={result[f'WAVE{w}_ALL_CAPABILITIES_COVERED']} "
          f"WAVE{w}_ALL_EXACT_MODELS_AVAILABLE={result[f'WAVE{w}_ALL_EXACT_MODELS_AVAILABLE']}")
    print(f"  covered {result['capabilities_covered']}/{result['capabilities_total']}")
    for row in result["capabilities"]:
        mark = "YES " if row["measured_covered"] else " no "
        print(f"  {mark} {row['tag']:<24} {str(row['measured_model'] or row['blocker_class'] or '-'):<44}"
              f"{' saturated' if row['saturated'] else ''}")
    for failure in result["failures"]:
        print(f"  FAIL {failure}")
    return 0 if result[f"WAVE{w}_OPERATIONAL_CLOSED"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
