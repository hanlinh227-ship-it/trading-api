from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

import yaml


AUTHORITY = {
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

_DEFAULT_PRIVACY = [
    "no_hidden_reasoning_persistence",
    "no_raw_private_prompt_persistence",
    "no_secret_persistence",
]

_DEFAULT_INVARIANTS = [
    "canonical_authority_topology",
    "permission_ceiling",
    "privacy_policy",
    "provenance_requirements",
    "protected_regression_tolerance_zero",
]


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _risk_class(manifest: dict) -> str:
    explicit = str(manifest.get("risk_class") or "").upper()
    if explicit in {"A", "B", "C", "D"}:
        return explicit
    if str(manifest.get("domain") or "").lower() == "trading":
        return "D"
    if manifest.get("project_authority_required") is True:
        return "D"
    ceiling = str(manifest.get("risk_ceiling") or "").lower()
    joined = " ".join(
        str(x).lower() for x in (manifest.get("permissions") or [])
    )
    text = f"{ceiling} {joined}"
    if any(token in text for token in ("financial", "trade", "wallet", "destructive", "credential", "secret")):
        return "D"
    if "reversible_write" in text or "write" in text:
        return "B"
    if text.strip():
        return "A"
    return "D"


def _skill_capabilities(
    skill_id: str,
    manifest: dict,
    domain: str,
    domain_capabilities: dict,
) -> list[str]:
    mapping = manifest.get("skill_capabilities")
    if isinstance(mapping, dict):
        row = mapping.get(skill_id)
        if isinstance(row, list):
            return sorted({str(x).strip() for x in row if str(x).strip()})
    caps = manifest.get("capabilities")
    if isinstance(caps, list):
        return sorted({str(x).strip() for x in caps if str(x).strip()})

    # No skill-specific capability metadata exists in the legacy manifests.
    # Reuse the Model Mesh's already-canonical hard capability requirements for
    # the domain rather than inventing a second skill->capability taxonomy.
    policy = domain_capabilities.get("policy") if isinstance(domain_capabilities, dict) else {}
    threshold = float((policy or {}).get("hard_capability_weight_threshold", 0.7))
    domains = domain_capabilities.get("domains") if isinstance(domain_capabilities, dict) else {}
    weights = ((domains or {}).get(domain) or {}).get("capabilities", {})
    if not isinstance(weights, dict):
        return []
    return sorted(
        str(capability)
        for capability, weight in weights.items()
        if isinstance(weight, (int, float)) and float(weight) >= threshold
    )


def _roles_for(capabilities: list[str], role_doc: dict) -> list[str]:
    if not capabilities:
        return []
    wanted = set(capabilities)
    roles: list[str] = []
    for row in role_doc.get("branches", []) if isinstance(role_doc, dict) else []:
        if not isinstance(row, dict):
            continue
        required = {str(x) for x in (row.get("required_capabilities") or [])}
        if wanted & required:
            role_id = str(row.get("role_id") or "").strip()
            if role_id:
                roles.append(role_id)
    return sorted(set(roles))


def _triggers_for(skill_id: str, manifest: dict) -> list[str]:
    triggers = manifest.get("triggers")
    if isinstance(triggers, dict):
        row = triggers.get(skill_id)
        if isinstance(row, list):
            return sorted({str(x).strip() for x in row if str(x).strip()})
    if isinstance(triggers, list):
        return sorted({str(x).strip() for x in triggers if str(x).strip()})
    return []


def _eval_rows(root: Path, manifest: dict) -> list[dict[str, Any]]:
    ids = [str(x).strip() for x in (manifest.get("evals") or []) if str(x).strip()]
    if not ids:
        return []
    source = root / "AI_SKILL_LIBRARY/evals.yaml"
    source_bytes = source.read_bytes() if source.is_file() else b""
    rows = []
    for eval_id in sorted(set(ids)):
        digest = hashlib.sha256(source_bytes + b"\0" + eval_id.encode("utf-8")).hexdigest()
        rows.append({
            "eval_id": eval_id,
            "suite_hash": digest,
            "replay_frozen": True,
            "source_ref": "AI_SKILL_LIBRARY/evals.yaml",
        })
    return rows


def compile_curriculum(root: Path) -> dict[str, Any]:
    """Compile canonical skill manifests into non-authoritative curriculum rows.

    The compiler never widens a permission and never invents model-selection or
    routing authority. Missing optional metadata stays empty; only the required
    output-contract marker is supplied when a manifest has no explicit one, and
    it points back to the canonical manifest rather than defining new behavior.
    """
    root = Path(root).resolve()
    skills_root = root / "AI_SKILL_LIBRARY/v4/skills"
    role_doc = _load_yaml(root / "AI_SKILL_LIBRARY/v4/model_mesh/role_branches.yaml")
    domain_capabilities = _load_yaml(root / "AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml")
    curricula: list[dict[str, Any]] = []

    manifests = sorted(skills_root.glob("*/manifest.yaml"))
    for manifest_path in manifests:
        manifest = _load_yaml(manifest_path)
        domain = str(manifest.get("domain") or manifest_path.parent.name).strip()
        skills = manifest.get("skills") or []
        if not isinstance(skills, list):
            continue
        permissions = sorted({str(x).strip() for x in (manifest.get("permissions") or []) if str(x).strip()})
        privacy = manifest.get("privacy_constraints")
        if not isinstance(privacy, list):
            privacy = list(_DEFAULT_PRIVACY)
        protected = manifest.get("protected_invariants")
        if not isinstance(protected, list):
            protected = list(_DEFAULT_INVARIANTS)

        rel_manifest = manifest_path.relative_to(root).as_posix()
        risk = _risk_class(manifest)
        output_contract = str(manifest.get("output_contract") or "defined_by_canonical_skill_manifest").strip()

        for raw_skill in sorted({str(x).strip() for x in skills if str(x).strip()}):
            caps = _skill_capabilities(raw_skill, manifest, domain, domain_capabilities)
            row: dict[str, Any] = {
                "skill_id": raw_skill,
                "domain": domain,
                "roles": _roles_for(caps, role_doc),
                "triggers": _triggers_for(raw_skill, manifest),
                "capabilities": caps,
                "permissions": {
                    "inherited_from": rel_manifest,
                    "permission_ceiling": permissions,
                    "widened_by_learning": False,
                },
                "privacy_constraints": sorted({str(x).strip() for x in privacy if str(x).strip()}),
                "protected_invariants": sorted({str(x).strip() for x in protected if str(x).strip()}),
                "risk_class": risk,
                "output_contract": output_contract,
                "evals": _eval_rows(root, manifest),
                "verifier_required": True,
                "promotion_class": risk,
                "authority": dict(AUTHORITY),
            }
            allowed_tools = manifest.get("allowed_tools")
            if isinstance(allowed_tools, list):
                row["allowed_tools"] = sorted({str(x).strip() for x in allowed_tools if str(x).strip()})
            input_contract = manifest.get("input_contract")
            if isinstance(input_contract, str) and input_contract.strip():
                row["input_contract"] = input_contract.strip()
            curricula.append(row)

    curricula.sort(key=lambda row: (row["domain"], row["skill_id"]))
    return {
        "version": 1,
        "purpose": "continuous_skill_learning_curriculum_material",
        "status": "CANONICAL",
        "authority": {
            **AUTHORITY,
            "note": (
                "Curriculum is training and evaluation material only. "
                "GITHUB_BRAIN_V4, task_router and Model Mesh retain authority."
            ),
        },
        "stable_write_allowed": False,
        "source_of_truth": {
            "skill_manifests": "AI_SKILL_LIBRARY/v4/skills",
            "role_vocabulary": "AI_SKILL_LIBRARY/v4/model_mesh/role_branches.yaml",
        },
        "curricula": curricula,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output = (root / args.output).resolve()
    output.relative_to(root)
    doc = compile_curriculum(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=160),
        encoding="utf-8",
    )
    print(f"SKILL_CURRICULUM_COMPILE=PASS skills={len(doc['curricula'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
