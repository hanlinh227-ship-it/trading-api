from __future__ import annotations

import argparse
import json
from pathlib import Path

from AI_SKILL_LIBRARY.v4.tools.skill_forge import promotion_decision


def evaluate_candidate(candidate: dict, eval_result: dict, *, replay_ref: str) -> dict:
    if not isinstance(candidate, dict) or not isinstance(eval_result, dict):
        raise ValueError("candidate_and_eval_required")
    ref = str(replay_ref or "").strip()
    if not ref or len(ref) > 500:
        raise ValueError("immutable_replay_ref_required")
    decision = promotion_decision(candidate, eval_result)
    return {
        **decision,
        "candidate_id": str(candidate.get("candidate_id") or candidate.get("gap_id") or "").strip() or None,
        "immutable_replay_ref": ref,
        "provenance": {
            "candidate_source": str(candidate.get("source") or "candidate_json"),
            "eval_source": str(eval_result.get("source") or "eval_json"),
        },
        "stable_write": False,
        "routing_authority": False,
        "reasoning_authority": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--eval", dest="eval_path", required=True)
    parser.add_argument("--replay-ref", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    try:
        candidate_path = (root / args.candidate).resolve(); candidate_path.relative_to(root)
        eval_path = (root / args.eval_path).resolve(); eval_path.relative_to(root)
        output_path = (root / args.output).resolve(); output_path.relative_to(root)
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
        eval_result = json.loads(eval_path.read_text(encoding="utf-8"))
        result = evaluate_candidate(candidate, eval_result, replay_ref=args.replay_ref)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        print(
            "SKILL_CANDIDATE_EVAL=PASS "
            f"class={result['promotion_class']} eligible={str(result['eligible']).lower()} "
            f"automatic={str(result['automatic']).lower()}"
        )
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
