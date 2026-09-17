"""B2: run the canonical route end to end and emit evidence.

    python AI_SKILL_LIBRARY/v4/tools/local_runtime_b2.py --evidence /tmp/b2.json

Nothing here decides anything. `run_canonical_route` owns the route; this is
the reproducible way to invoke it and keep what it produced. The prompt is a
plain user question with no model named in it, which is the property B2 exists
to demonstrate: the local model is reached because the router routed and the
mesh selected, not because anything wired it in.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_SKILL_LIBRARY.v4.local_runtime.canonical_route import run_canonical_route  # noqa: E402


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="B2 canonical route")
    parser.add_argument("--root", type=Path, default=repo_root)
    parser.add_argument("--cache", type=Path, default=repo_root / ".model-cache")
    parser.add_argument("--prompt", default="What is the capital of France?")
    parser.add_argument("--max-tokens", type=int, default=24)
    parser.add_argument("--evidence", type=Path, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = run_canonical_route(
        args.prompt, root=args.root, cache=args.cache, max_tokens=args.max_tokens
    )
    payload = {
        "b2_status": "PASS" if result.ok else "REFUSED",
        "prompt": args.prompt,
        "model_named_at_ingress": False,
        **result.to_dict(),
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
