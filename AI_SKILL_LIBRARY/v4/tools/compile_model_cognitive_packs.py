from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from AI_SKILL_LIBRARY.v4.tools.build_skill_competency import build_competency_matrix
from AI_SKILL_LIBRARY.v4.tools.compile_skill_curriculum import compile_curriculum


AUTHORITY_FALSE = {
    "routing_authority": False,
    "reasoning_authority": False,
    "model_selection_authority": False,
    "admission_authority": False,
    "scheduling_authority": False,
    "stable_write_authority": False,
    "merge_authority": False,
    "trading_authority": False,
}


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _measured_capabilities(capability: dict) -> dict[str, dict[str, dict[str, Any]]]:
    out: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in capability.get("records", []) if isinstance(capability, dict) else []:
        if not isinstance(row, dict):
            continue
        model_id = str(row.get("model_id") or "").strip()
        cap = str(row.get("capability") or "").strip()
        if not model_id or not cap or row.get("passed") is not True:
            continue
        score = row.get("score")
        current = out[model_id].get(cap)
        if current is None or (
            isinstance(score, (int, float))
            and float(score) > float(current.get("score") or 0.0)
        ):
            out[model_id][cap] = {
                "score": round(float(score), 6) if isinstance(score, (int, float)) else None,
                "evidence_id": row.get("evidence_id"),
                "measured_at": row.get("measured_at"),
                "provider_id": row.get("provider_id"),
                "model_family": row.get("model_family"),
            }
    return out


def _active_models(active: dict) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for model in active.get("models", []) if isinstance(active, dict) else []:
        if not isinstance(model, dict):
            continue
        model_id = str(model.get("model_id") or "").strip()
        if model_id:
            rows[model_id] = model
    return rows


def _declared_caps(model: dict) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    caps = model.get("capabilities") if isinstance(model, dict) else {}
    for cap, detail in caps.items() if isinstance(caps, dict) else []:
        if isinstance(detail, dict) and detail.get("supported") is True:
            score = detail.get("score")
            out[str(cap)] = round(float(score), 6) if isinstance(score, (int, float)) else None
    return out


def _skill_score(model_id: str, skill_id: str, competency: dict, measured: dict[str, dict]) -> float | None:
    scores = [
        float(row["measured_score"])
        for row in competency.get("rows", [])
        if isinstance(row, dict)
        and row.get("model_id") == model_id
        and row.get("skill_id") == skill_id
        and isinstance(row.get("measured_score"), (int, float))
    ]
    if scores:
        return max(scores)
    return None


def _unit_state(score: float | None, capabilities: list[str], measured_caps: dict[str, dict]) -> tuple[str, int]:
    if score is not None:
        if score < 0.70:
            return "REPLAY_PRIORITY", 0
        if score < 0.90:
            return "REINFORCE", 1
        return "MAINTAIN", 3
    if capabilities and not any(cap in measured_caps for cap in capabilities):
        return "MEASURE_FIRST", 0
    if capabilities and not all(cap in measured_caps for cap in capabilities):
        return "COVERAGE_GAP", 1
    return "BASELINE_REPLAY", 2


def _branch_coverage(role_doc: dict, measured_caps: dict[str, dict]) -> list[dict[str, Any]]:
    rows = []
    for branch in role_doc.get("branches", []) if isinstance(role_doc, dict) else []:
        if not isinstance(branch, dict):
            continue
        role_id = str(branch.get("role_id") or "").strip()
        required = [str(x) for x in (branch.get("required_capabilities") or []) if str(x)]
        if not role_id:
            continue
        covered = [cap for cap in required if cap in measured_caps]
        if not required:
            state = "NO_REQUIREMENT"
        elif len(covered) == len(required):
            state = "MEASURED_COVERED"
        elif covered:
            state = "PARTIAL"
        else:
            state = "UNMEASURED"
        rows.append({
            "role_id": role_id,
            "state": state,
            "required_capabilities": required,
            "measured_capabilities": covered,
        })
    return rows


def compile_model_cognitive_packs(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    policy = _yaml(root / "AI_SKILL_LIBRARY/v4/cognition/model_learning_policy.yaml")
    pointer = _json(root / "AI_SKILL_LIBRARY/v4/releases/current.json")
    active = _json(root / "AI_SKILL_LIBRARY/v4/model_mesh/active.json")
    capability = _json(root / "AI_SKILL_LIBRARY/v4/model_mesh/capability_evidence.json")
    experience = _json(root / "AI_SKILL_LIBRARY/v4/learning/experience_ledger.json")
    roles = _yaml(root / "AI_SKILL_LIBRARY/v4/model_mesh/role_branches.yaml")
    curriculum = compile_curriculum(root)
    competency = build_competency_matrix(curriculum, capability, experience, roles)

    shared = policy.get("shared_cognitive_core") or {}
    core_payload = {
        "brain_release": str(pointer.get("version") or ""),
        "rules": list(shared.get("rules") or []),
        "model_agnostic": shared.get("model_agnostic") is True,
    }
    core_hash = _hash(core_payload)

    measured_by_model = _measured_capabilities(capability)
    active_by_model = _active_models(active)
    model_ids = sorted(set(active_by_model) | set(measured_by_model))
    max_runtime_units = int(
        ((policy.get("token_economy") or {}).get("maximum_runtime_priority_units_per_model") or 6)
    )

    packs = []
    for model_id in model_ids:
        active_row = active_by_model.get(model_id, {})
        measured_caps = measured_by_model.get(model_id, {})
        declared_caps = _declared_caps(active_row)
        provider_id = str(
            active_row.get("provider_id")
            or next((v.get("provider_id") for v in measured_caps.values() if v.get("provider_id")), "")
        )
        model_family = str(
            active_row.get("model_family")
            or next((v.get("model_family") for v in measured_caps.values() if v.get("model_family")), "")
        )

        units = []
        for row in curriculum.get("curricula", []):
            if not isinstance(row, dict):
                continue
            skill_id = str(row.get("skill_id") or "")
            capabilities = [str(x) for x in (row.get("capabilities") or []) if str(x)]
            score = _skill_score(model_id, skill_id, competency, measured_caps)
            state, rank = _unit_state(score, capabilities, measured_caps)
            unit = {
                "skill_id": skill_id,
                "domain": str(row.get("domain") or ""),
                "state": state,
                "capabilities": capabilities,
                "priority_rank": rank,
                "risk_class": str(row.get("risk_class") or "D"),
            }
            if score is not None:
                unit["measured_score"] = round(score, 6)
            units.append(unit)
        units.sort(key=lambda row: (row["priority_rank"], row.get("measured_score", -1), row["domain"], row["skill_id"]))

        branch_rows = _branch_coverage(roles, measured_caps)
        local_open_weight_candidate = provider_id == "local_runtime"
        runtime_priority = [
            {
                "skill_id": row["skill_id"],
                "state": row["state"],
                "domain": row["domain"],
            }
            for row in units[:max_runtime_units]
        ]
        pack = {
            "model_id": model_id,
            "model_family": model_family,
            "provider_id": provider_id,
            "cognitive_core_hash": core_hash,
            "measured_capabilities": measured_caps,
            "declared_capabilities_training_hint_only": declared_caps,
            "branch_coverage": branch_rows,
            "training_units": units,
            "runtime_delta": {
                "priority_units": runtime_priority,
                "full_curriculum_on_prompt": False,
                "hidden_reasoning_persistence": False,
            },
            "weight_training": {
                "candidate_generation_eligible": local_open_weight_candidate,
                "automatic_weight_mutation": False,
                "automatic_apply": False,
                "promotion_required": True,
            },
            "authority": dict(AUTHORITY_FALSE),
        }
        pack["pack_hash"] = _hash(pack)
        packs.append(pack)

    return {
        "version": 1,
        "purpose": "compile-once shared cognition plus per-model training material",
        "status": "DEVELOPMENT_LAB",
        "brain_release": core_payload["brain_release"],
        "cognitive_core": {**core_payload, "cognitive_core_hash": core_hash},
        "runtime_contract": {
            "full_skill_scan_on_model_path": False,
            "model_visible_material": "cognitive_core_hash_plus_compact_delta",
            "stable_write": False,
        },
        "authority": dict(AUTHORITY_FALSE),
        "model_count": len(packs),
        "canonical_skill_count": len(curriculum.get("curricula", [])),
        "role_branch_count": len(roles.get("branches", [])) if isinstance(roles, dict) else 0,
        "models": packs,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output = (root / args.output).resolve() if not Path(args.output).is_absolute() else Path(args.output)
    doc = compile_model_cognitive_packs(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        "MODEL_COGNITIVE_PACKS=PASS "
        f"models={doc['model_count']} skills={doc['canonical_skill_count']} roles={doc['role_branch_count']} "
        f"core={doc['cognitive_core']['cognitive_core_hash'][:12]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
