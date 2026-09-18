"""The full AI CORE golden run, and the fresh-session resume that proves it stuck.

    python AI_SKILL_LIBRARY/v4/tools/local_runtime_ai_core_e2e.py --evidence /tmp/e2e.json
    python AI_SKILL_LIBRARY/v4/tools/local_runtime_ai_core_e2e.py --resume

The chain is the canonical one in `control_plane/e2e.py`, unchanged in
ownership: this supplies the callables it injects and keeps what it returned.

Two invocations, deliberately. The first routes a request through the whole
chain and writes a checkpoint. The second runs in a **different process** with
no memory of the first and resumes from that checkpoint alone. Continuity
asserted inside one process proves only that a variable survived a function
call; the second process is the evidence, which is why resume is a separate
command rather than a step.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_SKILL_LIBRARY.v4.control_plane.e2e import run_golden_e2e  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.golden_e2e import (  # noqa: E402
    GoldenE2EError,
    admitted_candidates,
    declared_identities,
    ingress,
    make_legion,
    make_memory,
    make_router,
    make_runtime,
    make_selector,
    make_verifier,
    records_by_key,
    synthesis,
)
from AI_SKILL_LIBRARY.v4.tools.memory_continuity import select_continuation  # noqa: E402

SESSIONS_REL = "CHECKPOINTS/evidence/sessions"


def resume(root: Path) -> dict[str, Any]:
    """Pick up the last checkpoint using Memory Continuity's own selection.

    Reads only what is on disk. Nothing from the run that wrote it is in this
    process, which is the whole point - a resume that consulted in-memory state
    would prove nothing about a new session.
    """
    directory = root / SESSIONS_REL
    files = sorted(directory.glob("*.json")) if directory.is_dir() else []
    if not files:
        return {"resume_status": "NOTHING_TO_RESUME",
                "reason": f"no checkpoint under {SESSIONS_REL}"}

    records = []
    for path in files:
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue

    latest = max(records, key=lambda r: str(r.get("written_at") or ""))
    selection = select_continuation([latest.get("work_state") or {}])
    return {
        "resume_status": "RESUMED" if selection.get("selected") else "REFUSED",
        "reason": selection.get("reason"),
        "process_id": os.getpid(),
        "checkpoint_id": latest.get("checkpoint_id"),
        "checkpoints_on_disk": len(records),
        "resumed_state": selection.get("state"),
        "recovered_answer": latest.get("answer"),
        "selected_by": "memory_continuity.select_continuation",
        # Restated: resuming reads context. It does not re-grant anything.
        "memory_authority": False,
        "routing_authority": False,
    }


def run(root: Path, cache: Path, request: str, max_tokens: int) -> dict[str, Any]:
    pairs = admitted_candidates(root)
    if not pairs:
        return {"ai_core_e2e": "REFUSED", "reason": "no governance-admitted local model"}
    try:
        result = run_golden_e2e(
            {"request": request, "profile": "STANDARD"},
            [candidate for candidate, _ in pairs],
            ingress=ingress,
            router=make_router(root),
            legion=make_legion(root),
            selector=make_selector(declared_identities(pairs)),
            runtime=make_runtime(root, cache, records_by_key(pairs), max_tokens=max_tokens),
            verifier=make_verifier(request),
            synthesis=synthesis,
            memory=make_memory(root),
        )
    except (GoldenE2EError, ValueError) as exc:
        return {"ai_core_e2e": "REFUSED", "refused_at": "chain",
                "reason": f"{type(exc).__name__}: {exc}"}

    passed = bool(result.get("B3_pass") and result.get("B4_pass")
                  and result.get("continuity_pass"))
    return {"ai_core_e2e": "PASS" if passed else "INCOMPLETE",
            "request": request, "process_id": os.getpid(), **result}


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="AI CORE golden E2E")
    parser.add_argument("--root", type=Path, default=repo_root)
    parser.add_argument("--cache", type=Path, default=repo_root / ".model-cache")
    parser.add_argument("--request", default="What is the capital city of Japan? Answer briefly.")
    parser.add_argument("--max-tokens", type=int, default=24)
    parser.add_argument("--resume", action="store_true",
                        help="resume from a checkpoint only; runs no model")
    parser.add_argument("--evidence", type=Path, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    payload = resume(args.root) if args.resume \
        else run(args.root, args.cache, args.request, args.max_tokens)

    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(text + "\n", encoding="utf-8")
    print(text)
    ok = payload.get("ai_core_e2e") == "PASS" or payload.get("resume_status") == "RESUMED"
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
