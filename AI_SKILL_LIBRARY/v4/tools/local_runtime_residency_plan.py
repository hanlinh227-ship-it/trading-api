"""Plan HOT/WARM/COLD residency from measured evidence. Loads nothing.

    python AI_SKILL_LIBRARY/v4/tools/local_runtime_residency_plan.py --evidence /tmp/p.json

Reads the registry for admitted models and the residency profile for what each
one actually cost and how fast it actually answered, then assigns tiers under
the host's real memory budget. It is a plan: no model is loaded, unloaded or
promoted by running it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_SKILL_LIBRARY.v4.local_runtime.projection import load_registry, project_record  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.residency_policy import (  # noqa: E402
    ResidencyCandidate,
    plan_residency,
)
from AI_SKILL_LIBRARY.v4.local_runtime.resources import detect_resources  # noqa: E402

PROFILE_REL = "CHECKPOINTS/evidence/RESIDENCY_LATENCY_PROFILE.json"


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="residency tier plan")
    parser.add_argument("--root", type=Path, default=repo_root)
    parser.add_argument("--profile", type=Path, default=repo_root / PROFILE_REL)
    parser.add_argument("--evidence", type=Path, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    profile_rows = {}
    if args.profile.is_file():
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
        profile_rows = {row["model_id"]: row for row in profile.get("models", [])
                        if row.get("measured")}

    candidates = []
    for record in load_registry(args.root).get("models") or []:
        if not project_record(record, available_runtimes=["llama.cpp"]).placeable:
            continue
        model_id = str(record.get("model_id"))
        digest = str((record.get("artifact_identity") or {}).get("sha256") or "")
        evidence = (record.get("capability_evidence") or {}).get("text_reasoning") or {}
        # A capability only counts for residency if it was measured on these
        # exact bytes - the same rule the mesh and the validator apply.
        capability = (float(evidence["score"])
                      if str(evidence.get("artifact_sha256") or "") == digest and digest
                      else None)
        row = profile_rows.get(model_id) or {}
        candidates.append(ResidencyCandidate(
            model_id=model_id,
            family=str(record.get("family") or ""),
            peak_ram_mb=row.get("peak_ram_mb"),
            capability=capability,
            warm_inference_ms=row.get("warm_inference_ms"),
            cold_load_ms=row.get("cold_load_ms"),
        ))

    snapshot = detect_resources(disk_path=str(args.root))
    plan = plan_residency(candidates, host_ram_mb=snapshot.ram_total_mb)
    text = json.dumps(plan.to_dict(), indent=2, ensure_ascii=False)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
