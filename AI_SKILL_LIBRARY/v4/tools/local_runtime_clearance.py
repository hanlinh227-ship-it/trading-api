"""Run governance clearance on a cached artifact and propose the registry update.

Closes the last step that used to be a hand-off. Given a verified artifact in
the cache, it runs the structural scan and a real signature engine, and writes
the registry update only if both actually ran and passed.

    python AI_SKILL_LIBRARY/v4/tools/local_runtime_clearance.py            # dry run
    python AI_SKILL_LIBRARY/v4/tools/local_runtime_clearance.py --apply    # write it

`--apply` is refused unless the result is CLEARED, so the flag cannot be used to
force a quarantined model through. On a host with no signature engine installed
this prints INSUFFICIENT_EVIDENCE and changes nothing, which is the correct
outcome: a clearance tool that upgrades "nobody looked" into "looks fine" is
worse than no tool at all.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import yaml

from AI_SKILL_LIBRARY.v4.local_runtime.clearance import (
    SIGNATURE_ENGINES,
    ClearanceStatus,
    apply_clearance,
    build_risk_acceptance,
    evaluate_clearance,
    find_signature_engine,
)
from AI_SKILL_LIBRARY.v4.local_runtime.identity import from_record
from AI_SKILL_LIBRARY.v4.local_runtime.projection import load_registry, project_record
from AI_SKILL_LIBRARY.v4.local_runtime.staging import resolve_cached

REGISTRY_REL = "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"


def _select(registry: Mapping[str, Any], model_id: str | None):
    models = [m for m in (registry.get("models") or []) if isinstance(m, Mapping)]
    if model_id:
        for index, model in enumerate(models):
            if str(model.get("model_id")) == model_id:
                return index, model
        return None, None
    return (0, models[0]) if len(models) == 1 else (None, None)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--cache-root", default=None)
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--apply", action="store_true", help="write the update (CLEARED only)")
    parser.add_argument(
        "--record-acceptance", action="store_true",
        help="record an operator risk acceptance on the row (needs --accepted-by and --basis)",
    )
    parser.add_argument("--accepted-by", default=None, help="the accepting party")
    parser.add_argument("--basis", default=None, help="why the risk is acceptable")
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    cache = Path(args.cache_root).resolve() if args.cache_root else root / ".model-cache"

    registry = load_registry(root)
    index, record = _select(registry, args.model_id)
    if record is None:
        print(json.dumps({"status": "NO_RECORD", "reason": "no matching row; pass --model-id"}, indent=2))
        return 2

    identity, identity_reasons = from_record(record)
    artifact = resolve_cached(cache, record, verify=True) if identity else None

    # Record a new acceptance, or reuse one already stored on the row. Storing
    # it is a pre-authorization: it is bound to the canonical digest, so it
    # applies only to bytes that match, and the checks it is predicated on
    # (size, digest, format, structure) still have to pass when they arrive.
    if args.record_acceptance:
        if not args.accepted_by or not args.basis:
            print(json.dumps({"status": "BAD_ARGS",
                              "reason": "--record-acceptance needs --accepted-by and --basis"},
                             indent=2))
            return 2
        if identity is None:
            print(json.dumps({"status": "NO_IDENTITY", "reason": "; ".join(identity_reasons)},
                             indent=2))
            return 2
        stored = build_risk_acceptance(
            accepted_by=args.accepted_by,
            artifact_sha256=identity.artifact_sha256,
            basis=args.basis,
            missing_evidence=["signature_based_malware_scan"],
        )
        registry["models"][index] = {**record, "operator_risk_acceptance": stored}
        (root / REGISTRY_REL).write_text(
            yaml.safe_dump(registry, sort_keys=False), encoding="utf-8"
        )
        record = registry["models"][index]

    acceptance = record.get("operator_risk_acceptance")
    result = evaluate_clearance(
        artifact,
        artifact_format=(identity.artifact_format if identity else "gguf"),
        risk_acceptance=acceptance,
    )

    payload: dict[str, Any] = {
        "tool": "local_runtime_clearance",
        "model_id": record.get("model_id"),
        "artifact_path": str(artifact) if artifact else None,
        "identity_reasons": list(identity_reasons),
        "signature_engine_installed": find_signature_engine(),
        "signature_engines_supported": list(SIGNATURE_ENGINES),
        "before": {
            "lifecycle_state": record.get("lifecycle_state"),
            "admission_evidence": record.get("admission_evidence"),
            "placeable": project_record(record).placeable,
        },
        "clearance": result.to_dict(),
        "stored_risk_acceptance": dict(acceptance) if acceptance else None,
        "acceptance_recorded_this_run": bool(args.record_acceptance),
        "applied": False,
    }

    if args.apply:
        if not result.cleared:
            payload["apply_refused"] = (
                f"--apply refused: clearance is {result.status.value}, not CLEARED. "
                "The registry is unchanged."
            )
        else:
            registry["models"][index] = apply_clearance(record, result)
            (root / REGISTRY_REL).write_text(
                yaml.safe_dump(registry, sort_keys=False), encoding="utf-8"
            )
            payload["applied"] = True
            payload["after"] = {
                "lifecycle_state": registry["models"][index]["lifecycle_state"],
                "admission_evidence": registry["models"][index]["admission_evidence"],
                "placeable": project_record(registry["models"][index]).placeable,
            }

    text = json.dumps(payload, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        print(text)
    return 0 if result.cleared else 1


if __name__ == "__main__":
    raise SystemExit(main())
