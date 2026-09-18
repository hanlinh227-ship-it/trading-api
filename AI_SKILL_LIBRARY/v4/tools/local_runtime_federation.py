"""Run a bounded multi-model federation round against the admitted models.

    python AI_SKILL_LIBRARY/v4/tools/local_runtime_federation.py --profile STANDARD --evidence /tmp/f.json

Routing, selection and the execution plan all belong elsewhere; this invokes
them and keeps what came back. STANDARD plans a maker and a checker, FAST plans
one model and no verifier - those caps are `plan_execution`'s, not this tool's.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_SKILL_LIBRARY.v4.local_runtime.multi_model import (  # noqa: E402
    FederationError,
    run_federated,
)


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="multi-model federation round")
    parser.add_argument("--root", type=Path, default=repo_root)
    parser.add_argument("--cache", type=Path, default=repo_root / ".model-cache")
    parser.add_argument("--request", default="What is the capital city of Japan? Answer briefly.")
    parser.add_argument("--profile", default="STANDARD", choices=["FAST", "STANDARD", "DEEP"])
    parser.add_argument("--max-tokens", type=int, default=24)
    parser.add_argument("--evidence", type=Path, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        result = run_federated(args.request, root=args.root, cache=args.cache,
                               profile=args.profile, max_tokens=args.max_tokens)
        payload = {"federation_status": "RAN", **result.to_dict()}
    except FederationError as exc:
        payload = {"federation_status": "REFUSED", "reason": str(exc)}

    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if payload.get("federation_status") == "RAN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
