from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml


AUTHORITY_FLAGS = {
    "routing_authority": False,
    "reasoning_authority": False,
    "model_selection_authority": False,
    "admission_authority": False,
    "scheduling_authority": False,
    "evidence_authority": False,
    "stable_write_authority": False,
    "merge_authority": False,
    "trading_authority": False,
}


def _capability_records(capability_evidence: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for row in capability_evidence.get("records", []) if isinstance(capability_evidence, dict) else []:
        if not isinstance(row, dict):
            continue
        capability = str(row.get("capability") or "").strip()
        model_id = str(row.get("model_id") or "").strip()
        if capability and model_id:
            out[capability].append(row)
    return out


def _experience_index(experience_ledger: dict) -> dict[tuple[str, str, str], list[dict]]:
    out: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in experience_ledger.get("experiences", []) if isinstance(experience_ledger, dict) else []:
        if not isinstance(row, dict):
            continue
        model_id = str(row.get("model_id") or "")
        role_id = str(row.get("role_id") or "")
        for skill_id in row.get("skill_ids", []) if isinstance(row.get("skill_ids"), list) else []:
            out[(model_id, str(skill_id), role_id)].append(row)
    return out


def _roles_for_curriculum(row: dict, role_branches: dict) -> list[str]:
    roles = [str(x) for x in (row.get("roles") or []) if str(x)]
    if roles:
        return sorted(set(roles))
    caps = set(str(x) for x in (row.get("capabilities") or []))
    inferred = []
    for branch in role_branches.get("branches", []) if isinstance(role_branches, dict) else []:
        if not isinstance(branch, dict):
            continue
        required = set(str(x) for x in (branch.get("required_capabilities") or []))
        if caps & required:
            role_id = str(branch.get("role_id") or "")
            if role_id:
                inferred.append(role_id)
    return sorted(set(inferred))


def build_competency_matrix(
    curriculum: dict,
    capability_evidence: dict,
    experience_ledger: dict,
    role_branches: dict,
) -> dict:
    """Build measured MODEL x SKILL x ROLE evidence without selecting any model.

    Capability evidence can establish MEASURED state. It cannot by itself claim
    protected-regression PASS, PRIMARY or FALLBACK. Those operational labels
    remain promotion outputs owned by the existing Model Mesh/evidence gates.
    """
    by_cap = _capability_records(capability_evidence)
    exp = _experience_index(experience_ledger)
    rows: dict[tuple[str, str, str], dict[str, Any]] = {}

    for cur in curriculum.get("curricula", []) if isinstance(curriculum, dict) else []:
        if not isinstance(cur, dict):
            continue
        skill_id = str(cur.get("skill_id") or "")
        capabilities = [str(x) for x in (cur.get("capabilities") or []) if str(x)]
        roles = _roles_for_curriculum(cur, role_branches)
        if not skill_id or not roles:
            continue

        model_evidence: dict[str, list[dict]] = defaultdict(list)
        for capability in capabilities:
            for evidence in by_cap.get(capability, []):
                model_evidence[str(evidence["model_id"])].append(evidence)

        models = set(model_evidence)
        for (model_id, exp_skill, exp_role), _ in exp.items():
            if exp_skill == skill_id and exp_role in roles:
                models.add(model_id)

        for role_id in roles:
            for model_id in sorted(models):
                ev_rows = model_evidence.get(model_id, [])
                exp_rows = exp.get((model_id, skill_id, role_id), [])
                refs = {
                    str((row.get("provenance") or {}).get("reference") or "").strip()
                    for row in ev_rows
                    if isinstance(row.get("provenance"), dict)
                }
                refs.update(
                    str(row.get("evidence_ref") or "").strip()
                    for row in exp_rows
                )
                refs.discard("")

                scores = [
                    float(row["score"]) for row in ev_rows
                    if isinstance(row.get("score"), (int, float))
                ]
                measured_score = max(scores) if scores else None
                verifier_rows = [row for row in exp_rows if row.get("verifier_passed") in (True, False)]
                verifier_rate = (
                    sum(1 for row in verifier_rows if row.get("verifier_passed") is True) / len(verifier_rows)
                    if verifier_rows else None
                )

                measured_times = [
                    str(row.get("measured_at"))
                    for row in ev_rows
                    if row.get("measured_at")
                ]
                measured_times.extend(
                    str(row.get("timestamp"))
                    for row in exp_rows
                    if row.get("timestamp")
                )

                if measured_score is None and not exp_rows:
                    state = "ELIGIBLE"
                else:
                    state = "MEASURED"

                row: dict[str, Any] = {
                    "model_id": model_id,
                    "skill_id": skill_id,
                    "role_id": role_id,
                    "state": state,
                    "evidence_refs": sorted(refs),
                    "protected_regression_status": "NOT_RUN",
                    "promotion_state": "NONE",
                }
                if measured_score is not None:
                    row["measured_score"] = round(measured_score, 6)
                if verifier_rate is not None:
                    row["verifier_pass_rate"] = round(verifier_rate, 6)
                if measured_times:
                    row["last_measured_at"] = sorted(measured_times)[-1]
                latencies = [
                    float(x["latency_ms"]) for x in exp_rows
                    if isinstance(x.get("latency_ms"), (int, float))
                ]
                if latencies:
                    row["latency_observation_ms"] = round(sum(latencies) / len(latencies), 3)
                rows[(model_id, skill_id, role_id)] = row

    return {
        "version": 1,
        "matrix_id": "SKILL_COMPETENCY_MATRIX",
        "purpose": "measured MODEL x SKILL x ROLE competence; evidence input only",
        "authority": False,
        "stable_write": False,
        "authority_flags": dict(AUTHORITY_FLAGS),
        "rows": [rows[key] for key in sorted(rows)],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()

    curriculum = yaml.safe_load((root / "AI_SKILL_LIBRARY/v4/learning/skill_curriculum.yaml").read_text(encoding="utf-8"))
    capability = json.loads((root / "AI_SKILL_LIBRARY/v4/model_mesh/capability_evidence.json").read_text(encoding="utf-8"))
    experience = json.loads((root / "AI_SKILL_LIBRARY/v4/learning/experience_ledger.json").read_text(encoding="utf-8"))
    roles = yaml.safe_load((root / "AI_SKILL_LIBRARY/v4/model_mesh/role_branches.yaml").read_text(encoding="utf-8"))
    out = build_competency_matrix(curriculum, capability, experience, roles)
    output = (root / args.output).resolve(); output.relative_to(root)
    output.write_text(json.dumps(out, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"SKILL_COMPETENCY_BUILD=PASS rows={len(out['rows'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
