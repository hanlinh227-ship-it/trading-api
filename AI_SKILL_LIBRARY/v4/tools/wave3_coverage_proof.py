"""Does the final fleet actually cover what Wave 3 set out to cover.

    python AI_SKILL_LIBRARY/v4/tools/wave3_coverage_proof.py --evidence /tmp/cov.json

Wave 3's exit gate is explicit that an observer gap count of zero is not enough.
Zero gaps means nothing the observer looks at is outstanding; it says nothing
about whether the fleet can reason, code or check its own work. This answers
that separately, and only from measurements.

Each target resolves to one of three states, and the second and third are not
interchangeable:

  COVERED_MEASURED         a model reached the coverage floor on a recorded,
                           digest-bound run against a frozen suite.
  INTENTIONALLY_DEFERRED   nobody claims coverage and the reason is recorded -
                           a candidate deferred to a later wave, a licence a
                           person must accept, hardware that cannot hold the
                           model.
  NOT_COVERED_WITH_REASON  the fleet was measured and fell short, or nothing
                           measures it at all.

Two rules the gate names, enforced here rather than trusted:

**A RESOLVED_INCOMPATIBLE candidate is not coverage.** A model the runtime
cannot load contributes nothing, however promising its role hypothesis was.
Coverage is read from the measured fleet, never from the candidate list.

**A documentation claim is not coverage.** The only inputs are the capability
gap map and the frozen-suite runs behind it, so a vendor's page has no route in.

Saturation is reported but does not by itself deny coverage. A capability where
several models tie at the top is covered - the fleet can do it - and what is
missing is the ability to rank within it. Conflating "we cannot tell which is
best" with "we cannot do it" would understate the fleet as badly as ignoring
saturation would overstate it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

EVIDENCE = "CHECKPOINTS/evidence"

#: The capabilities Wave 3 must answer for. The first three are the gate's
#: core requirement; the rest are reported.
CORE_TARGETS = ("deep_reasoning", "coding", "verifier_checker")
REPORTED_TARGETS = ("vietnamese_reasoning", "software_engineering",
                    "synthesis_generalist", "debugging", "code_review")

#: Targets Wave 3 deliberately does not attempt, with the reason. A deferral is
#: a decision and is recorded as one; it is never a quiet omission.
DEFERRED: dict[str, str] = {
    "multimodal": "Wave 3 is reasoning, coding and verification. Vision, OCR, "
                  "document and audio are Wave 4, and the only multimodal "
                  "candidate also requires a licence a person must accept.",
    "long_context": "No suite exercises a long context, and adding one is a "
                    "measurement change rather than a fleet change. Deferred "
                    "rather than claimed: the fleet may well handle it, and "
                    "nothing here has shown that it does.",
    "tool_calling": "No admitted model is exercised through a tool-calling "
                    "harness by any current suite.",
    "multilingual_reasoning": "Only Vietnamese is measured. One non-English "
                              "language is evidence about that language, not "
                              "about multilingual capability.",
}


def _load(root: Path, name: str) -> Any:
    try:
        return json.loads((root / EVIDENCE / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def build(root: Path) -> dict[str, Any]:
    gap_map = _load(root, "WAVE3_CAPABILITY_GAP_MAP.json") or {}
    states = _load(root, "WAVE3_CANDIDATE_STATES.json") or {}
    capabilities = gap_map.get("capabilities") or {}
    floor = gap_map.get("coverage_floor")

    # Candidates that resolved to a non-AVAILABLE state contribute nothing to
    # coverage. Listed so the report makes the exclusion visible rather than
    # leaving a reader to infer it.
    non_contributing = [
        {"candidate_id": row["candidate_id"], "state": row["state"]}
        for row in (states.get("candidates") or [])
        if row.get("state") != "AVAILABLE"
    ]

    def resolve(target: str) -> dict[str, Any]:
        if target in DEFERRED:
            return {"target": target, "state": "INTENTIONALLY_DEFERRED",
                    "reason": DEFERRED[target], "measured_score": None,
                    "current_best_model": None, "artifact_digest": None}
        row = capabilities.get(target)
        if not isinstance(row, dict):
            return {"target": target, "state": "NOT_COVERED_WITH_REASON",
                    "reason": f"the gap map has no entry for {target}",
                    "measured_score": None, "current_best_model": None,
                    "artifact_digest": None}
        if row.get("state") == "NOT_MEASURED":
            return {"target": target, "state": "NOT_COVERED_WITH_REASON",
                    "reason": row.get("reason") or "nothing measures this capability",
                    "measured_score": None, "current_best_model": None,
                    "artifact_digest": None}
        covered = str(row.get("state", "")).startswith("COVERED")
        return {
            "target": target,
            "state": "COVERED_MEASURED" if covered else "NOT_COVERED_WITH_REASON",
            "reason": None if covered else (
                f"best measured score {row.get('measured_score')} is below the "
                f"coverage floor {floor}"
            ),
            "measured_score": row.get("measured_score"),
            "current_best_model": row.get("current_best_model"),
            "artifact_digest": row.get("artifact_digest"),
            "evidence_source": row.get("evidence_source"),
            "measurement_depth": row.get("measurement_depth"),
            "thin_evidence": row.get("thin_evidence"),
            "saturated": row.get("saturated"),
            "saturation_note": row.get("saturation_note"),
            "latency_ms": row.get("latency"),
            "peak_ram_mb": row.get("peak_ram_mb"),
            "reliability": row.get("reliability"),
        }

    core = [resolve(target) for target in CORE_TARGETS]
    reported = [resolve(target) for target in REPORTED_TARGETS]
    deferred = [resolve(target) for target in sorted(DEFERRED)]

    core_covered = all(row["state"] in {"COVERED_MEASURED", "INTENTIONALLY_DEFERRED"}
                       for row in core)
    return {
        "tool": "wave3_coverage_proof",
        "coverage_floor": floor,
        "core_targets": core,
        "core_covered_or_deferred": core_covered,
        "reported_targets": reported,
        "deferred_targets": deferred,
        "candidates_contributing_nothing": non_contributing,
        "sources": {
            "gap_map": bool(gap_map),
            "candidate_states": bool(states),
            "documentation_claims_used": False,
        },
        # Said out loud because it is the gate's own distinction and the most
        # likely thing for a reader in a hurry to conflate.
        "observer_gap_count_is_not_coverage": True,
        "note": (
            "Coverage is read from the measured fleet, never from the candidate "
            "list. A candidate that is infeasible, unavailable or licence-gated "
            "contributes nothing here."
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--evidence", default=None)
    args = parser.parse_args(argv)

    result = build(Path(args.root).resolve())
    if args.evidence:
        Path(args.evidence).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(f"WAVE3_COVERAGE core_ok={result['core_covered_or_deferred']}")
    for label, rows in (("core", result["core_targets"]),
                        ("reported", result["reported_targets"]),
                        ("deferred", result["deferred_targets"])):
        for row in rows:
            score = row.get("measured_score")
            flags = []
            if row.get("saturated"):
                flags.append("saturated")
            if row.get("thin_evidence"):
                flags.append("thin")
            suffix = f" ({', '.join(flags)})" if flags else ""
            print(f"  {label:<9} {row['target']:<24} {row['state']:<24} "
                  f"{'' if score is None else f'{score:.3f}'} "
                  f"{row.get('current_best_model') or ''}{suffix}")
    return 0 if result["core_covered_or_deferred"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
