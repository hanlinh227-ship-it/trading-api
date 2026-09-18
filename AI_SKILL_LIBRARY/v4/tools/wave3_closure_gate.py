"""Decide whether Wave 3 may close, and say plainly what did not become available.

    python AI_SKILL_LIBRARY/v4/tools/wave3_closure_gate.py --evidence /tmp/close.json

Wave 3 closing and every candidate being available are two different facts, and
the whole point of this gate is to report both without letting either stand in
for the other. A wave closes when every candidate has reached a terminal state
whose blocker is exact and evidenced, no authorized zero-cost path is left
unexplored, and the capabilities the wave set out to cover are actually covered
by something measured. It does not close by relaxing a rule until the awkward
candidates pass.

So two flags, deliberately separate:

  WAVE3_OPERATIONAL_CLOSED          every candidate terminal, every blocker
                                    evidenced, capabilities covered
  WAVE3_ALL_EXACT_MODELS_AVAILABLE  whether every candidate's own weights can
                                    actually execute somewhere

The second is expected to be false here, and saying so is the honest part.
Three candidates end without an executable exact path: two quarantined on
provenance and one needing a machine no attached worker provides. A closure
report that hid that behind "closed" would be worth nothing.

**A capability fallback never counts as its model being available.** It counts
towards capability coverage, under the substitute's own name, and the row says
which model would actually run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import yaml  # noqa: E402

WAVE3_REL = "AI_SKILL_LIBRARY/v4/open_model_universe/wave3_knowledge_candidates.yaml"
EVIDENCE = "CHECKPOINTS/evidence"

#: Terminal states a candidate may legitimately close in. Each one is a real
#: answer; none of them is "we gave up".
TERMINAL_STATES = frozenset({
    "AVAILABLE_LOCAL", "AVAILABLE_SERVERLESS", "AVAILABLE_REMOTE", "AVAILABLE_JIT",
    "PROVIDER_CAPABILITY_FALLBACK", "QUARANTINED_PROVENANCE",
    "REMOTE_WORKER_REQUIRED", "INCOMPATIBLE",
    "HUMAN_LICENSE_GATE_REQUIRED", "DEFERRED_TO_WAVE4",
})

#: States in which the candidate's OWN weights can execute somewhere.
EXACT_AVAILABLE_STATES = frozenset({
    "AVAILABLE_LOCAL", "AVAILABLE_SERVERLESS", "AVAILABLE_REMOTE", "AVAILABLE_JIT",
})

#: What Wave 3 set out to cover. Coverage is satisfied by a measured model or a
#: proven provider path - never by a model that is merely admitted.
WAVE3_CAPABILITIES = ("deep_reasoning", "coding", "debugging", "code_review",
                      "verifier_checker", "vietnamese_reasoning", "synthesis_generalist")


def _load(root: Path, name: str) -> Any:
    try:
        return json.loads((root / EVIDENCE / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def build(root: Path) -> dict[str, Any]:
    wave3 = yaml.safe_load((root / WAVE3_REL).read_text(encoding="utf-8")) or {}
    candidates = wave3.get("candidates", [])

    failures: list[str] = []
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        state = str(candidate.get("state") or "")
        finding = candidate.get("terminal_finding")
        row = {
            "candidate_id": candidate.get("id"),
            "upstream": candidate.get("upstream"),
            "terminal_state": state,
            "is_terminal": bool(candidate.get("wave3_terminal")),
            "exact_model_executable": state in EXACT_AVAILABLE_STATES,
            "blocker_is_evidenced": bool(finding),
            "capability_fallback": candidate.get("capability_fallback"),
        }
        if state not in TERMINAL_STATES:
            failures.append(f"{candidate.get('id')}: state {state!r} is not terminal")
        if not candidate.get("wave3_terminal"):
            failures.append(f"{candidate.get('id')}: not marked wave3_terminal")
        # A blocker without evidence is an opinion, and closing on one would be
        # the failure this gate exists to prevent.
        if not row["exact_model_executable"] and not finding:
            failures.append(
                f"{candidate.get('id')}: closes unavailable with no terminal_finding, "
                f"so its blocker is asserted rather than evidenced")
        rows.append(row)

    # Proofs, read rather than assumed.
    mesh = _load(root, "FREE_WORKER_MESH_PROOF.json") or {}
    federation = _load(root, "WAVE3_FEDERATION_PROOF.json") or {}
    probe = _load(root, "WORKERS_AI_FREE_TIER_PROBE.json") or {}
    paths = _load(root, "WAVE3_FREE_EXECUTION_PATHS.json") or {}

    mesh_proven = mesh.get("mesh_status") == "PROVEN"
    federation_proven = federation.get("federation_status") == "PROVEN"
    gpt_oss_served = any(
        r.get("provider_model_id") == "@cf/openai/gpt-oss-20b"
        and r.get("verdict") == "FREE_TIER_SERVES_IT"
        and r.get("returned_a_completion") is True
        for r in (probe.get("results") or []))
    # The fallback path is proven by the mesh round that takes one, not by the
    # existence of a fallback record.
    fallback_proven = any(
        row.get("scenario") == "quota_exhaustion_is_bypassed_not_retried" and row.get("passed")
        for row in (mesh.get("rounds") or []))

    for name, ok in (("FREE_WORKER_MESH", mesh_proven),
                     ("WAVE3_FEDERATION", federation_proven),
                     ("GPT_OSS_SERVERLESS", gpt_oss_served),
                     ("FALLBACK_PATH", fallback_proven)):
        if not ok:
            failures.append(f"{name} is not proven in the recorded evidence")

    # Capability coverage: every Wave 3 capability answered by a round that
    # actually ran and passed.
    covered = {
        str(row.get("capability")): bool(row.get("passed"))
        for row in (federation.get("rounds") or []) if row.get("capability")
    }
    uncovered = [c for c in WAVE3_CAPABILITIES if not covered.get(c)]
    if uncovered:
        failures.append(f"capabilities not covered by a passing round: {', '.join(uncovered)}")

    # No authorized zero-cost path left unexplored.
    unexplored = [
        p["provider_id"] for p in (paths.get("providers") or [])
        if p.get("verification_state") in (None, "DISCOVERED")
    ]
    if unexplored:
        failures.append(f"authorized paths still unexplored: {', '.join(unexplored)}")

    exact_unavailable = [r["upstream"] for r in rows if not r["exact_model_executable"]]
    closed = not failures

    return {
        "tool": "wave3_closure_gate",
        "WAVE3_OPERATIONAL_CLOSED": closed,
        # Recorded separately and expected to be false. These are different
        # facts and the report must never let one imply the other.
        "WAVE3_ALL_EXACT_MODELS_AVAILABLE": not exact_unavailable,
        "exact_models_without_an_executable_path": sorted(exact_unavailable),
        "candidates": rows,
        "proofs": {
            "FREE_WORKER_MESH": "PROVEN" if mesh_proven else "NOT_PROVEN",
            "WAVE3_FEDERATION": "PROVEN" if federation_proven else "NOT_PROVEN",
            "GPT_OSS_SERVERLESS": "PROVEN" if gpt_oss_served else "NOT_PROVEN",
            "FALLBACK_PATH": "PROVEN" if fallback_proven else "NOT_PROVEN",
        },
        "capability_coverage": {c: covered.get(c, False) for c in WAVE3_CAPABILITIES},
        "authorized_paths_explored": [
            {"provider_id": p["provider_id"], "verification_state": p.get("verification_state")}
            for p in (paths.get("providers") or [])
        ],
        "failures": failures,
        "note": (
            "Closing Wave 3 and every candidate being available are different "
            "facts. This gate reports both and lets neither stand in for the "
            "other. A capability fallback counts towards coverage under the "
            "substitute's own name, never as the requested model's availability."
        ),
        "routing_authority": False,
        "admission_authority": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=repo_root)
    parser.add_argument("--evidence", type=Path, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = build(args.root)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")

    print(f"WAVE3_OPERATIONAL_CLOSED={result['WAVE3_OPERATIONAL_CLOSED']} "
          f"WAVE3_ALL_EXACT_MODELS_AVAILABLE={result['WAVE3_ALL_EXACT_MODELS_AVAILABLE']}")
    for row in result["candidates"]:
        mark = "exact-executable" if row["exact_model_executable"] else "no exact path"
        print(f"  {row['terminal_state']:<30} {row['upstream']:<46} {mark}")
    for name, state in result["proofs"].items():
        print(f"  {name:<22} {state}")
    for failure in result["failures"]:
        print(f"  FAIL {failure}")
    return 0 if result["WAVE3_OPERATIONAL_CLOSED"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
