"""B3/B4: run the canonical golden-trace gate against the real local runtime.

    python AI_SKILL_LIBRARY/v4/tools/local_runtime_b3b4.py --evidence /tmp/b3b4.json

The gate is `v4/control_plane/e2e.py` and it is unchanged. This supplies the
real callables and keeps what it returned. B4 is not a separate run: the same
execution either carries observed offline evidence or it does not.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_SKILL_LIBRARY.v4.control_plane.e2e import run_golden_e2e  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.golden_e2e import (  # noqa: E402
    GoldenE2EError,
    admitted_candidates,
    declared_identities,
    records_by_key,
    ingress,
    make_router,
    make_runtime,
    make_selector,
    synthesis,
    verifier,
)


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="B3/B4 golden E2E")
    parser.add_argument("--root", type=Path, default=repo_root)
    parser.add_argument("--cache", type=Path, default=repo_root / ".model-cache")
    parser.add_argument("--request", default="What is the capital of France?")
    parser.add_argument("--max-tokens", type=int, default=24)
    parser.add_argument("--evidence", type=Path, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    pairs = admitted_candidates(args.root)
    if not pairs:
        payload = {"B3_pass": False, "B4_pass": False,
                   "refused_at": "governance_admission",
                   "reason": "no governance-admitted local model"}
    else:
        candidates = [candidate for candidate, _ in pairs]
        try:
            result = run_golden_e2e(
                {"request": args.request, "profile": "STANDARD"},
                candidates,
                ingress=ingress,
                router=make_router(args.root),
                selector=make_selector(declared_identities(pairs)),
                runtime=make_runtime(args.root, args.cache, records_by_key(pairs),
                                     max_tokens=args.max_tokens),
                verifier=verifier,
                synthesis=synthesis,
            )
            payload = {"request": args.request, "model_named_at_ingress": False, **result}
        except (GoldenE2EError, ValueError) as exc:
            # A refusal is reported, never converted into a pass.
            payload = {"B2_pass": False, "B3_pass": False, "B4_pass": False,
                       "refused_at": "real_runtime", "reason": f"{type(exc).__name__}: {exc}"}

    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if payload.get("B3_pass") and payload.get("B4_pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
