from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from AI_SKILL_LIBRARY.v4.tools.compile_model_cognitive_packs import compile_model_cognitive_packs


def run_model_learning_loop(root: Path) -> dict:
    packs = compile_model_cognitive_packs(root)
    models = []
    for pack in packs.get("models", []):
        states = Counter(
            str(row.get("state") or "UNKNOWN")
            for row in pack.get("training_units", [])
            if isinstance(row, dict)
        )
        models.append({
            "model_id": pack.get("model_id"),
            "model_family": pack.get("model_family"),
            "provider_id": pack.get("provider_id"),
            "pack_hash": pack.get("pack_hash"),
            "priority_units": list((pack.get("runtime_delta") or {}).get("priority_units") or []),
            "training_state_counts": dict(sorted(states.items())),
            "weight_candidate_generation_eligible": bool(
                (pack.get("weight_training") or {}).get("candidate_generation_eligible")
            ),
            "automatic_weight_mutation": False,
            "automatic_apply": False,
        })
    return {
        "version": 1,
        "cycle_type": "MODEL_COGNITIVE_LEARNING_LOOP",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "brain_release": packs.get("brain_release"),
        "cognitive_core_hash": (packs.get("cognitive_core") or {}).get("cognitive_core_hash"),
        "model_count": len(models),
        "models": models,
        "candidate_output_only": True,
        "stable_write": False,
        "model_mesh_write": False,
        "routing_authority": False,
        "reasoning_authority": False,
        "merge_authority": False,
        "trading_authority": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output = Path(args.output)
    if not output.is_absolute():
        output = root / output
    doc = run_model_learning_loop(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"MODEL_LEARNING_LOOP=PASS models={doc['model_count']} "
        f"core={str(doc['cognitive_core_hash'])[:12]} stable_write={doc['stable_write']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
