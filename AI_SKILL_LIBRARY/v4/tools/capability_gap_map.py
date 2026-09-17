"""What the admitted fleet can actually do, per capability, from measurements.

    python AI_SKILL_LIBRARY/v4/tools/capability_gap_map.py --evidence /tmp/gap.json

Wave 3 is capability-gap-driven, which only means anything if the gaps are
measured. This reads what the fleet has already been made to do - the canonical
Wave 0 wave and the frozen capability suite - and reports, per capability, the
best model, its score, the digest that score belongs to, what it cost in latency
and RAM, and whether the capability is a gap.

Four rules, because a gap map is exactly the artifact a hopeful number slips
into:

**Only measurements count.** The source is a recorded run against a frozen
suite, bound to an artifact digest. A vendor documentation page is not an input
here and there is no field it could enter through.

**A capability with no task is a gap in the measurement, not a pass.** Wave 0
has no long-context task, so long_context reports `NOT_MEASURED` rather than
inheriting a general score. Reporting it as covered because the models are
generally decent is the failure this file exists to avoid.

**A score is bound to the digest it was measured on.** Two models are compared
only through their own runs; nothing is inherited or averaged across artifacts.

**Coverage needs a threshold that was decided before looking.** A capability is
covered when the best measured score reaches `COVERAGE_FLOOR`, which is the
mesh's own hard capability floor rather than a number picked to make the fleet
look ready.

It decides nothing. It ranks nothing for routing, promotes nothing, and writes
to no registry: the output is evidence for a human and for the Wave 3 selection
step to read.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import yaml  # noqa: E402

BASELINE_GLOB = "CHECKPOINTS/evidence/*BASELINE*.json"
CAPABILITY_GLOB = "CHECKPOINTS/evidence/WAVE0_CAPABILITY_*.json"
REGISTRY_REL = "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"

#: The mesh's own hard capability floor. Imported as a number rather than
#: restated as a judgement, so "covered" means what the mesh means by usable.
COVERAGE_FLOOR = 0.35

#: Which Wave 0 categories evidence which capability. A capability with no
#: category behind it is NOT_MEASURED - never inferred from a neighbour.
CAPABILITY_TASKS: dict[str, tuple[str, ...]] = {
    "deep_reasoning": ("GENERAL_REASONING",),
    "coding": ("CODING",),
    "software_engineering": ("CODING",),
    "verifier_checker": ("STRUCTURED_OUTPUT",),
    "vietnamese_reasoning": ("VIETNAMESE",),
    "math_quant": ("MATH",),
    "synthesis_generalist": ("GENERAL_REASONING", "STRUCTURED_OUTPUT", "CODING",
                             "MATH", "VIETNAMESE"),
}

#: Named so the absence is visible rather than silently missing from the report.
UNMEASURED_CAPABILITIES: dict[str, str] = {
    "long_context": "Wave 0 has no long-context task; no run has exercised a "
                    "context beyond a few hundred tokens on any admitted model",
    "debugging": "no task presents broken code to repair; the CODING tasks are "
                 "write-from-scratch, which is a different skill",
    "code_review": "no task presents code to critique",
    "multilingual_reasoning": "only Vietnamese is exercised; a single non-English "
                              "language is not evidence about the rest",
    "tool_calling": "no task issues a tool call",
}


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _registry(root: Path) -> dict[str, dict[str, Any]]:
    document = yaml.safe_load((root / REGISTRY_REL).read_text(encoding="utf-8")) or {}
    return {
        str(model.get("model_id")): model
        for model in (document.get("models") or [])
        if isinstance(model, dict)
    }


def fleet_runs(root: Path) -> dict[str, dict[str, Any]]:
    """One Wave 0 result per model, keyed by model id.

    A model may have been run more than once; the most recent complete wave
    wins, because an older run measured an older suite or an older host.
    """
    runs: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob(BASELINE_GLOB)):
        document = _load_json(path)
        if not isinstance(document, dict):
            continue
        wave = document.get("wave_report")
        rows = wave.get("runs") if isinstance(wave, dict) else None
        if not isinstance(rows, list) or not rows:
            continue
        model_id = str(document.get("model_id") or "")
        if not model_id:
            continue
        previous = runs.get(model_id)
        if previous and str(previous["source"]) >= str(path.name):
            continue
        runs[model_id] = {
            "source": path.name,
            "model_id": model_id,
            "status": document.get("baseline_status"),
            "passed": document.get("passed"),
            "total": document.get("total"),
            "reproducible": document.get("reproducible"),
            "rows": rows,
        }
    return runs


def _category_score(rows: list[dict[str, Any]], categories: tuple[str, ...]) -> tuple[float, int, int]:
    selected = [row for row in rows if str(row.get("category")) in categories]
    if not selected:
        return 0.0, 0, 0
    passed = sum(1 for row in selected if row.get("verifier_passed") is True)
    return round(passed / len(selected), 6), passed, len(selected)


def _cost(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cold = [row.get("cold_metrics") or {} for row in rows]
    warm = [row.get("warm_metrics") or {} for row in rows]
    inference = [float(c["inference_latency_ms"]) for c in cold if c.get("inference_latency_ms")]
    warm_inference = [float(w["inference_latency_ms"]) for w in warm if w.get("inference_latency_ms")]
    load = [float(c["load_latency_ms"]) for c in cold if c.get("load_latency_ms")]
    ram = [float(c["peak_ram_mb"]) for c in cold if c.get("peak_ram_mb")]
    return {
        "cold_load_ms": round(min(load), 3) if load else None,
        "median_inference_ms": round(statistics.median(inference), 3) if inference else None,
        "median_warm_inference_ms": round(statistics.median(warm_inference), 3) if warm_inference else None,
        "peak_ram_mb": round(max(ram), 2) if ram else None,
    }


def build(root: Path) -> dict[str, Any]:
    registry = _registry(root)
    runs = fleet_runs(root)

    # The capability-suite score, which is a different measurement from the
    # wave: a frozen reasoning suite rather than the canonical 12 tasks. Both
    # are reported; neither stands in for the other.
    suite: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob(CAPABILITY_GLOB)):
        document = _load_json(path)
        if not isinstance(document, dict) or document.get("measured") is not True:
            continue
        run = document.get("benchmark_run") or {}
        suite[str(run.get("model_id"))] = {
            "score": float(run.get("score") or 0.0),
            "artifact_sha256": str(run.get("artifact_sha256") or ""),
            "suite": f"{run.get('suite_id')}@{run.get('suite_version')}",
            "source": path.name,
        }

    fleet: list[dict[str, Any]] = []
    for model_id, run in sorted(runs.items()):
        record = registry.get(model_id) or {}
        digest = str((record.get("artifact_identity") or {}).get("sha256") or "")
        fleet.append({
            "model_id": model_id,
            "artifact_sha256": digest,
            "lifecycle_state": record.get("lifecycle_state"),
            "wave0": {"passed": run["passed"], "total": run["total"],
                      "reproducible": run["reproducible"], "status": run["status"]},
            "per_capability": {
                name: dict(zip(("score", "passed", "attempted"),
                               _category_score(run["rows"], categories)))
                for name, categories in sorted(CAPABILITY_TASKS.items())
            },
            "cost": _cost(run["rows"]),
            "capability_suite": suite.get(model_id),
            "evidence_source": run["source"],
        })

    capabilities: dict[str, Any] = {}
    for name in sorted(CAPABILITY_TASKS):
        # Ties break on total Wave 0 passes, which is a measurement, then on
        # model_id only to stay deterministic. Breaking on model_id alone named
        # SmolLM2-360M - a model that scored 9 of 12 overall - as the fleet's
        # best at deep reasoning, because it passed the three tasks that exist
        # and sorts first alphabetically. An arbitrary winner among equal scores
        # is worse than no winner: it reads as a ranking and is not one.
        ranked = sorted(
            ((row["per_capability"][name]["score"], row) for row in fleet),
            key=lambda pair: (-pair[0], -int(pair[1]["wave0"]["passed"] or 0),
                              str(pair[1]["model_id"])),
        )
        if not ranked:
            capabilities[name] = {"state": "NOT_MEASURED",
                                  "reason": "no model has a recorded Wave 0 run"}
            continue
        best_score, best = ranked[0]
        detail = best["per_capability"][name]
        tied = [row["model_id"] for score, row in ranked if score == best_score]
        # Every task passed by more than one model means the suite has stopped
        # discriminating here. The capability is covered; what is not available
        # is any ordering within it, and a gap map that implied one would be
        # inviting a selection decision the evidence cannot support.
        saturated = best_score >= 1.0 and len(tied) > 1
        if best_score < COVERAGE_FLOOR:
            state = "NOT_COVERED_MEASURED"
        elif saturated:
            state = "COVERED_BUT_SATURATED"
        else:
            state = "COVERED_MEASURED"
        capabilities[name] = {
            "state": state,
            "saturated": saturated,
            "saturation_note": (
                f"{len(tied)} of {len(fleet)} models score {best_score} on "
                f"{detail['attempted']} task(s); this suite cannot rank them, so "
                f"'current best' is one of several equals, not a measured leader"
            ) if saturated else None,
            "capability_gap": best_score < COVERAGE_FLOOR,
            "current_best_model": best["model_id"],
            "measured_score": best_score,
            "passed": detail["passed"],
            "attempted": detail["attempted"],
            "artifact_digest": best["artifact_sha256"],
            "latency": best["cost"]["median_inference_ms"],
            "cold_load_ms": best["cost"]["cold_load_ms"],
            "peak_ram_mb": best["cost"]["peak_ram_mb"],
            "reliability": f"{best['wave0']['reproducible']}/{best['wave0']['total']} reproducible",
            "evidence_source": best["evidence_source"],
            "tied_with": tied[1:],
            # A perfect score on two tasks is a weak claim, and saying so is the
            # difference between a gap map and a scoreboard.
            "measurement_depth": f"{detail['attempted']} task(s)",
            "thin_evidence": detail["attempted"] < 3,
        }

    for name, reason in sorted(UNMEASURED_CAPABILITIES.items()):
        capabilities[name] = {
            "state": "NOT_MEASURED",
            "capability_gap": True,
            "reason": reason,
            "current_best_model": None,
            "measured_score": None,
            "artifact_digest": None,
            "evidence_source": None,
        }

    gaps = sorted(name for name, row in capabilities.items() if row.get("capability_gap"))
    # Saturation is not a capability gap - the fleet can do the thing - but it
    # is a measurement gap, and Wave 3 selection needs both stated separately.
    saturated = sorted(name for name, row in capabilities.items() if row.get("saturated"))
    thin = sorted(name for name, row in capabilities.items() if row.get("thin_evidence"))
    return {
        "tool": "capability_gap_map",
        "coverage_floor": COVERAGE_FLOOR,
        "fleet_size": len(fleet),
        "models_measured": [row["model_id"] for row in fleet],
        "capability_gaps": gaps,
        "saturated_capabilities": saturated,
        "thin_evidence_capabilities": thin,
        "measurement_gaps": sorted(set(gaps) | set(saturated) | set(thin)),
        "capabilities": capabilities,
        "fleet": fleet,
        "sources": {
            "wave0_runs": sorted({row["evidence_source"] for row in fleet}),
            "capability_suite": sorted({row["source"] for row in suite.values()}),
        },
        "no_documentation_scores": True,
        "routing_authority": False,
        "admission_authority": False,
        "note": (
            "Measured evidence only. NOT_MEASURED means no task exercises the capability, "
            "which is a gap in the measurement and never a pass."
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--evidence", default=None)
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    result = build(root)
    text = json.dumps(result, indent=2)
    if args.evidence:
        Path(args.evidence).write_text(text + "\n", encoding="utf-8")

    print(f"CAPABILITY_GAP_MAP fleet={result['fleet_size']} "
          f"gaps={len(result['capability_gaps'])} "
          f"saturated={len(result['saturated_capabilities'])} "
          f"thin={len(result['thin_evidence_capabilities'])}")
    for name, row in sorted(result["capabilities"].items()):
        best = row.get("current_best_model") or "-"
        score = row.get("measured_score")
        mark = "GAP " if row.get("capability_gap") else "    "
        thin = " (thin)" if row.get("thin_evidence") else ""
        print(f"  {mark}{name:<24} {row['state']:<20} "
              f"{'' if score is None else f'{score:.3f}'} {best}{thin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
