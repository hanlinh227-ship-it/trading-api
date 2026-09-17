"""Accept a staged GGUF and verify it against the canonical registry record.

The operator-facing half of the staged-artifact path. Point it at a file and it
re-derives everything from the canonical registry - identity, expected size,
expected digest - recomputes the SHA-256 from the bytes on disk, runs the
structural scan, and caches the artifact under its full identity if and only if
all of that matches.

    python AI_SKILL_LIBRARY/v4/tools/local_runtime_intake.py \\
        --staged /path/to/Qwen3-0.6B-Q8_0.gguf

It prints machine-readable evidence and exits non-zero on any mismatch. It does
not clear quarantine, and says so in its own output: verifying bytes and
clearing a model to run are different questions, owned by different planes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_SKILL_LIBRARY.v4.local_runtime.projection import load_registry, project_record
from AI_SKILL_LIBRARY.v4.local_runtime.staging import intake_staged_artifact


def find_record(registry: Mapping[str, Any], model_id: str | None) -> Mapping[str, Any] | None:
    models = [m for m in (registry.get("models") or []) if isinstance(m, Mapping)]
    if model_id:
        return next((m for m in models if str(m.get("model_id")) == model_id), None)
    return models[0] if len(models) == 1 else None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--staged", required=True, help="path to the staged artifact")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--cache-root", default=None, help="cache root (default: <root>/.model-cache)")
    parser.add_argument("--model-id", default=None, help="which registry row (needed if several)")
    parser.add_argument("--move", action="store_true", help="consume the staged file instead of copying")
    parser.add_argument("--output", default=None, help="write evidence JSON here")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    cache = Path(args.cache_root).resolve() if args.cache_root else root / ".model-cache"

    registry = load_registry(root)
    record = find_record(registry, args.model_id)
    if record is None:
        print(json.dumps({"status": "NO_RECORD",
                          "reason": "no matching registry row; pass --model-id"}, indent=2))
        return 2

    result = intake_staged_artifact(args.staged, record, root=cache, move=args.move)
    projected = project_record(record)

    payload = {
        "tool": "local_runtime_intake",
        "registry_model_id": record.get("model_id"),
        "governance": {
            "lifecycle_state": record.get("lifecycle_state"),
            "admission_evidence": record.get("admission_evidence"),
            "placeable_now": projected.placeable,
            "exclusion_reasons": list(projected.exclusion_reasons),
        },
        "intake": result.to_dict(),
        # Stated plainly so a green intake is never read as a clearance.
        "note": (
            "Intake verifies bytes against the canonical record. It does not clear "
            "quarantine, set malware_scan_status, or make the model runnable."
        ),
    }
    text = json.dumps(payload, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        print(text)
    return 0 if result.verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
