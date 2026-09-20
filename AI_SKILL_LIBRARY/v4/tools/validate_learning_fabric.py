from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from AI_SKILL_LIBRARY.v4.tools.build_skill_competency import build_competency_matrix
from AI_SKILL_LIBRARY.v4.tools.compile_skill_curriculum import compile_curriculum


TOOL_KEYS = (
    "curriculum_compiler",
    "experience_intake_tool",
    "competency_builder",
    "learning_cycle_runner",
)


def _yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _schema_errors(schema: dict, document) -> list[str]:
    validator = Draft202012Validator(schema)
    return sorted(error.message for error in validator.iter_errors(document))


def validate(root: Path) -> list[str]:
    root = Path(root).resolve()
    errors: list[str] = []
    learning = root / "AI_SKILL_LIBRARY/v4/learning"
    schemas = root / "AI_SKILL_LIBRARY/v4/schemas"

    policy = _yaml(learning / "policy.yaml")
    fabric = (policy or {}).get("continuous_skill_learning") or {}
    for key in (
        "routing_authority", "reasoning_authority", "model_selection_authority",
        "admission_authority", "scheduling_authority", "evidence_authority",
        "stable_write_authority", "merge_authority", "trading_authority",
        "stable_write_allowed", "direct_model_mesh_write", "direct_stable_write",
    ):
        if fabric.get(key) is not False:
            errors.append(f"continuous_skill_learning.{key} must be false")
    if fabric.get("bounded_background_only") is not True:
        errors.append("continuous_skill_learning must be bounded_background_only")
    if fabric.get("stable_request_dependency") is not False:
        errors.append("continuous_skill_learning may not be a stable request dependency")
    for key in TOOL_KEYS:
        rel = fabric.get(key)
        if not isinstance(rel, str) or not (root / rel).is_file():
            errors.append(f"continuous_skill_learning.{key} missing tool: {rel!r}")

    evo = _yaml(learning / "skill_evo.yaml") or {}
    evo_fabric = evo.get("continuous_skill_learning") or {}
    if evo_fabric.get("direct_model_mesh_write") is not False:
        errors.append("learning cycle may not directly write Model Mesh")
    if evo_fabric.get("stable_write_allowed") is not False:
        errors.append("learning cycle may not write Stable")
    if evo_fabric.get("class_c_auto_promotion") is not False or evo_fabric.get("class_d_auto_promotion") is not False:
        errors.append("Class C/D learning may never auto-promote")

    factory = _yaml(learning / "skill_factory.yaml") or {}
    factory_fabric = factory.get("continuous_skill_learning") or {}
    if factory_fabric.get("competency_gap_requires_evidence_refs") is not True:
        errors.append("competency gaps must require evidence refs")
    if factory_fabric.get("stable_catalog_mutation") != "promotion_pipeline_only":
        errors.append("stable catalog mutation must remain promotion_pipeline_only")

    roles = _yaml(root / "AI_SKILL_LIBRARY/v4/model_mesh/role_branches.yaml") or {}
    evidence_input = roles.get("learning_evidence_input") or {}
    if evidence_input.get("path") != "AI_SKILL_LIBRARY/v4/learning/skill_competency_matrix.json":
        errors.append("role branches must reference the canonical competency matrix")
    if evidence_input.get("model_selection_authority") is not False:
        errors.append("learning evidence input may not select models")
    if evidence_input.get("direct_preference_write") is not False:
        errors.append("learning evidence input may not directly rewrite preferences")

    cognition = _yaml(root / "AI_SKILL_LIBRARY/v4/cognition/model_learning_policy.yaml") or {}
    cognition_authority = cognition.get("authority") or {}
    for key, value in cognition_authority.items():
        if key.endswith("_authority") and value is not False:
            errors.append(f"model cognition {key} must be false")
    token_economy = cognition.get("token_economy") or {}
    if token_economy.get("full_skill_scan_on_model_path") is not False:
        errors.append("model cognition must forbid full skill scan on model path")
    if token_economy.get("full_curriculum_stays_off_prompt") is not True:
        errors.append("full cognition curriculum must stay off the runtime prompt")
    model_learning = cognition.get("model_specific_learning") or {}
    if model_learning.get("consume_all_canonical_skills") is not True or model_learning.get("consume_all_role_branches") is not True:
        errors.append("model cognition must consume all canonical skills and role branches")
    loop = cognition.get("continuous_loop") or {}
    if loop.get("enabled") is not True or loop.get("scheduler") != "existing_continuous_intelligence_only":
        errors.append("model cognition loop must use the existing continuous intelligence scheduler")
    for key in ("direct_stable_write", "direct_model_mesh_write"):
        if loop.get(key) is not False:
            errors.append(f"model cognition loop {key} must be false")
    weights = cognition.get("weight_training") or {}
    if weights.get("automatic_weight_mutation") is not False:
        errors.append("automatic model weight mutation must remain forbidden")
    if weights.get("promotion") != "existing_evergreen_gates_only":
        errors.append("model training candidates must use existing Evergreen promotion gates")

    stable = _yaml(root / "AI_SKILL_LIBRARY/v4/stable/continuous_intelligence.yaml") or {}
    stable_learning = stable.get("continuous_skill_learning") or {}
    if stable_learning.get("plane") != "development_lab_only":
        errors.append("continuous learning must stay in the Development Lab")
    if stable_learning.get("stable_request_dependency") is not False:
        errors.append("Development Lab must not be a stable request dependency")
    lanes = stable_learning.get("lanes") or {}
    if ((lanes.get("development_lab") or {}).get("may_mutate_stable")) is not False:
        errors.append("Development Lab may not mutate Stable")
    if ((lanes.get("development_lab") or {}).get("may_self_merge")) is not False:
        errors.append("Development Lab may not self-merge")
    if ((lanes.get("stable_runtime") or {}).get("accepts_unpromoted_candidates")) is not False:
        errors.append("Stable Runtime may not accept unpromoted candidates")

    curriculum = compile_curriculum(root)
    curriculum_schema = _json(schemas / "skill_curriculum.schema.json")
    errors.extend(
        f"compiled curriculum schema: {item}"
        for item in _schema_errors(curriculum_schema, curriculum)
    )

    manifests = sorted((root / "AI_SKILL_LIBRARY/v4/skills").glob("*/manifest.yaml"))
    expected_skills = {
        str(skill)
        for path in manifests
        for skill in ((_yaml(path) or {}).get("skills") or [])
    }
    compiled_skills = {row["skill_id"] for row in curriculum.get("curricula", [])}
    if compiled_skills != expected_skills:
        missing = sorted(expected_skills - compiled_skills)
        extra = sorted(compiled_skills - expected_skills)
        errors.append(f"curriculum discovery mismatch missing={missing} extra={extra}")

    target = stable.get("canonical_skill_count_target")
    if isinstance(target, int) and len(compiled_skills) != target:
        errors.append(
            f"compiled canonical skill count {len(compiled_skills)} != target {target}"
        )

    experience = _json(learning / "experience_ledger.json")
    errors.extend(
        f"experience ledger schema: {item}"
        for item in _schema_errors(_json(schemas / "experience_ledger.schema.json"), experience)
    )

    capability = _json(root / "AI_SKILL_LIBRARY/v4/model_mesh/capability_evidence.json")
    matrix = build_competency_matrix(curriculum, capability, experience, roles)
    errors.extend(
        f"derived competency schema: {item}"
        for item in _schema_errors(_json(schemas / "skill_competency_matrix.schema.json"), matrix)
    )
    if any(row.get("state") in {"PRIMARY", "FALLBACK"} for row in matrix.get("rows", [])):
        errors.append("competency builder may not assign PRIMARY/FALLBACK directly")

    cycles = _yaml(learning / "learning_cycles.yaml")
    errors.extend(
        f"learning cycles schema: {item}"
        for item in _schema_errors(_json(schemas / "learning_cycles.schema.json"), cycles)
    )
    promotion = _json(learning / "promotion_evidence.json")
    errors.extend(
        f"promotion evidence schema: {item}"
        for item in _schema_errors(_json(schemas / "promotion_evidence.schema.json"), promotion)
    )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    errors = validate(Path(args.root))
    for item in errors:
        print(f"[ERROR] {item}")
    print(f"LEARNING_FABRIC_VALIDATE={'PASS' if not errors else 'FAIL'} failures={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
