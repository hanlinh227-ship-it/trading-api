from __future__ import annotations

import argparse
import json
from pathlib import Path

from AI_SKILL_LIBRARY.v4.tools.evaluate_skill_candidate import evaluate_candidate


def _refs(candidate: dict, replay_ref: str, evaluation: dict) -> list[str]:
    refs = [replay_ref]
    for ref in candidate.get("evidence_refs", []) if isinstance(candidate.get("evidence_refs"), list) else []:
        if not isinstance(ref, str) or not ref.strip() or len(ref) > 500:
            raise ValueError("invalid_learning_evidence_ref")
        refs.append(ref.strip())
    eval_ref = evaluation.get("evaluation_ref")
    if isinstance(eval_ref, str) and eval_ref.strip():
        refs.append(eval_ref.strip())
    return sorted(set(refs))


def run_learning_cycle(
    cycle: dict,
    *,
    curriculum: dict,
    competency: dict,
    candidate: dict,
    eval_result: dict,
) -> dict:
    if not all(isinstance(x, dict) for x in (cycle, curriculum, competency, candidate, eval_result)):
        raise ValueError("learning_cycle_inputs_must_be_objects")
    cycle_id = str(cycle.get("cycle_id") or "").strip()
    replay_ref = str(cycle.get("replay_ref") or "").strip()
    if not cycle_id:
        raise ValueError("cycle_id_required")
    if not replay_ref or len(replay_ref) > 500:
        raise ValueError("immutable_replay_ref_required")
    if eval_result.get("frozen_replay") is not True:
        raise ValueError("learning_cycle_requires_frozen_replay")

    evaluation = evaluate_candidate(candidate, eval_result, replay_ref=replay_ref)
    if not evaluation["eligible"]:
        state = "REJECTED"
    elif evaluation["explicit_authorization_required"]:
        state = "HUMAN_GATE"
    elif evaluation["automatic"]:
        state = "PROMOTION_CANDIDATE"
    else:
        state = "REJECTED"

    return {
        "cycle_id": cycle_id,
        "state": state,
        "candidate_id": evaluation.get("candidate_id"),
        "promotion_class": evaluation["promotion_class"],
        "eligible": evaluation["eligible"],
        "automatic": evaluation["automatic"],
        "explicit_authorization_required": evaluation["explicit_authorization_required"],
        "reasons": evaluation["reasons"],
        "evidence_refs": _refs(candidate, replay_ref, evaluation),
        "stable_write": False,
        "routing_authority": False,
        "reasoning_authority": False,
        "model_selection_authority": False,
        "admission_authority": False,
        "scheduling_authority": False,
        "merge_authority": False,
        "trading_authority": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycle", required=True)
    parser.add_argument("--curriculum", required=True)
    parser.add_argument("--competency", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--eval", dest="eval_path", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    def load_json(rel: str):
        path = (root / rel).resolve(); path.relative_to(root)
        return json.loads(path.read_text(encoding="utf-8"))

    cycle_doc = load_json(args.cycle)
    curriculum_path = (root / args.curriculum).resolve(); curriculum_path.relative_to(root)
    if curriculum_path.suffix in {".yaml", ".yml"}:
        import yaml
        curriculum = yaml.safe_load(curriculum_path.read_text(encoding="utf-8"))
    else:
        curriculum = json.loads(curriculum_path.read_text(encoding="utf-8"))
    competency = load_json(args.competency)
    candidate = load_json(args.candidate)
    eval_result = load_json(args.eval_path)
    result = run_learning_cycle(
        cycle_doc,
        curriculum=curriculum,
        competency=competency,
        candidate=candidate,
        eval_result=eval_result,
    )
    output = (root / args.output).resolve(); output.relative_to(root)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"LEARNING_CYCLE=PASS state={result['state']} class={result['promotion_class']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
