#!/usr/bin/env python3
"""Validate the lazy provider skill registry and its safety invariants."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "AI_SKILL_LIBRARY"
INDEX_PATH = LIB / "skills/registry/index.yaml"
REGISTRY_PATH = LIB / "skills/providers/crypto_agents.yaml"
CONFLICT_PATH = LIB / "skills/registry/conflict_policy.yaml"
CHECKPOINT_PATH = LIB / "checkpoint.json"
SOURCE_REGISTRY_PATH = LIB / "sources/crypto_agent_official.yaml"
CORE_MANIFEST_PATH = LIB / "v4/skills/core/manifest.yaml"
TRADING_MANIFEST_PATH = LIB / "v4/skills/trading/manifest.yaml"
TRADING_DOMAIN_PATH = LIB / "v4/mesh/domains/trading.yaml"

VALID_MODES = {"RESEARCH_SAFE", "AUTH_READ_ONLY", "HIGH_RISK"}
VALID_RISKS = {"LOW", "MEDIUM", "HIGH"}


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected mapping: {path}")
    return data


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def validate_registry_data(
    index: dict[str, Any],
    registry: dict[str, Any],
    conflict: dict[str, Any],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    index_policy = index.get("policy") if isinstance(index.get("policy"), dict) else {}
    if index.get("version") != 1:
        errors.append("registry index version must be 1")
    if index_policy.get("lookup_every_request") is not True:
        errors.append("registry index must lookup every request")
    if index_policy.get("lazy_provider_load") is not True:
        errors.append("registry index must lazy-load provider detail")
    if index_policy.get("preload_provider_details") is not False:
        errors.append("registry index preload_provider_details must be false")
    if index_policy.get("provider_registry_is_reasoning_authority") is not False:
        errors.append("provider registry cannot be reasoning authority")
    if index_policy.get("project_authority_precedes_registry") is not True:
        errors.append("project authority must precede provider registry")
    if index_policy.get("stable_security_precedes_registry") is not True:
        errors.append("Stable security must precede provider registry")
    max_index_candidates = index_policy.get("max_provider_candidates_per_request")
    if not isinstance(max_index_candidates, int) or isinstance(max_index_candidates, bool) or not 1 <= max_index_candidates <= 3:
        errors.append("max_provider_candidates_per_request must be an integer from 1 to 3")

    registries = index.get("registries")
    if not isinstance(registries, list) or not registries:
        errors.append("registry index must contain registries")
    else:
        seen_registry_ids: set[str] = set()
        for row in registries:
            if not isinstance(row, dict):
                errors.append("registry index contains a non-mapping registry row")
                continue
            rid = row.get("id")
            if not isinstance(rid, str) or not rid:
                errors.append("registry row id must be non-empty")
                continue
            if rid in seen_registry_ids:
                errors.append(f"duplicate registry id: {rid}")
            seen_registry_ids.add(rid)
            if rid != "canonical_skills" and row.get("routing_authority") is not False:
                errors.append(f"provider registry {rid} routing_authority must be false")

    registry_policy = registry.get("policy") if isinstance(registry.get("policy"), dict) else {}
    if registry.get("version") != 1:
        errors.append("crypto provider registry version must be 1")
    if registry_policy.get("provider_capabilities_are_reasoning_authority") is not False:
        errors.append("provider capabilities cannot be reasoning authority")
    if registry_policy.get("default_unclassified_action") != "quarantine_no_routing":
        errors.append("unclassified provider skills must default to quarantine_no_routing")
    if registry_policy.get("research_only_default") is not True:
        errors.append("crypto provider registry must default to research-only")
    if registry_policy.get("high_risk_routing_authority") is not False:
        errors.append("HIGH_RISK global routing authority must be false")
    if registry_policy.get("high_risk_auto_activate") is not False:
        errors.append("HIGH_RISK global auto activation must be false")

    max_registry_candidates = registry_policy.get("max_selected_provider_capabilities")
    if not isinstance(max_registry_candidates, int) or isinstance(max_registry_candidates, bool) or not 1 <= max_registry_candidates <= 3:
        errors.append("max_selected_provider_capabilities must be an integer from 1 to 3")
    elif isinstance(max_index_candidates, int) and max_registry_candidates > max_index_candidates:
        errors.append("provider registry candidate limit cannot exceed registry-index limit")

    providers = registry.get("providers")
    provider_ids: set[str] = set()
    if not isinstance(providers, list) or not providers:
        errors.append("crypto provider registry must contain providers")
        providers = []
    for row in providers:
        if not isinstance(row, dict):
            errors.append("provider row must be a mapping")
            continue
        pid = row.get("id")
        if not isinstance(pid, str) or not pid:
            errors.append("provider id must be non-empty")
            continue
        if pid in provider_ids:
            errors.append(f"duplicate provider id: {pid}")
        provider_ids.add(pid)
        repo = row.get("official_repo")
        if not isinstance(repo, str) or not repo.startswith("https://github.com/"):
            errors.append(f"provider {pid} must declare an official GitHub source repository")
        if row.get("default_unclassified_action") not in {None, "quarantine_no_routing"}:
            errors.append(f"provider {pid} may not auto-route unclassified upstream skills")

    capabilities = registry.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        errors.append("crypto provider registry must contain capabilities")
        capabilities = []
    capability_ids: set[str] = set()
    for row in capabilities:
        if not isinstance(row, dict):
            errors.append("capability row must be a mapping")
            continue
        cid = row.get("id")
        if not isinstance(cid, str) or not cid:
            errors.append("capability id must be non-empty")
            continue
        if cid in capability_ids:
            errors.append(f"duplicate capability id: {cid}")
        capability_ids.add(cid)

        bundle = row.get("provider_bundle")
        if bundle not in provider_ids:
            errors.append(f"capability {cid} references unknown provider bundle {bundle!r}")

        mode = row.get("mode")
        risk = row.get("risk")
        if mode not in VALID_MODES:
            errors.append(f"capability {cid} has invalid mode {mode!r}")
        if risk not in VALID_RISKS:
            errors.append(f"capability {cid} has invalid risk {risk!r}")

        routing_authority = row.get("routing_authority")
        auto_activate = row.get("auto_activate")
        affects_funds = row.get("can_affect_real_funds")
        if routing_authority is not False:
            errors.append(f"capability {cid} routing_authority must be false")
        if not isinstance(affects_funds, bool):
            errors.append(f"capability {cid} can_affect_real_funds must be boolean")

        if mode == "HIGH_RISK":
            if risk != "HIGH":
                errors.append(f"HIGH_RISK capability {cid} risk must be HIGH")
            if routing_authority is not False:
                errors.append(f"HIGH_RISK capability {cid} routing_authority must be false")
            if auto_activate is not False:
                errors.append(f"HIGH_RISK capability {cid} auto_activate must be false")
            if affects_funds is not True:
                warnings.append(f"HIGH_RISK capability {cid} does not declare real-funds impact; review classification")
        elif mode == "AUTH_READ_ONLY":
            if auto_activate is not False:
                errors.append(f"AUTH_READ_ONLY capability {cid} auto_activate must be false")
            if affects_funds is True:
                errors.append(f"AUTH_READ_ONLY capability {cid} cannot affect real funds")
        elif mode == "RESEARCH_SAFE" and affects_funds is True:
            errors.append(f"RESEARCH_SAFE capability {cid} cannot affect real funds")

        if affects_funds is True and risk == "LOW":
            errors.append(f"capability {cid} can affect real funds but is marked LOW risk")
        if affects_funds is True and mode != "HIGH_RISK":
            errors.append(f"capability {cid} can affect real funds and must be HIGH_RISK")

    principles = conflict.get("principles") if isinstance(conflict.get("principles"), dict) else {}
    if conflict.get("version") != 1:
        errors.append("conflict policy version must be 1")
    if principles.get("provider_outputs_are_evidence_not_votes") is not True:
        errors.append("provider outputs must be treated as evidence, not votes")
    if principles.get("majority_vote_for_truth") is not False:
        errors.append("majority vote for provider truth must be disabled")
    if principles.get("silent_averaging_of_conflicts") is not False:
        errors.append("silent averaging of provider conflicts must be disabled")
    if principles.get("current_project_authority_precedes_provider_guidance") is not True:
        errors.append("current project authority must precede provider guidance")
    if principles.get("stable_security_precedes_provider_guidance") is not True:
        errors.append("Stable security must precede provider guidance")

    precedence = conflict.get("source_precedence")
    expected_prefix = ["current_runtime", "current_project_authority", "current_first_party"]
    if not isinstance(precedence, list) or precedence[:3] != expected_prefix:
        errors.append("conflict source precedence must begin with current_runtime, current_project_authority, current_first_party")

    return errors, warnings


def validate_registry_files(root: Path = ROOT) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    paths = [INDEX_PATH, REGISTRY_PATH, CONFLICT_PATH, CHECKPOINT_PATH, SOURCE_REGISTRY_PATH, CORE_MANIFEST_PATH, TRADING_MANIFEST_PATH, TRADING_DOMAIN_PATH]
    missing = [str(path.relative_to(ROOT)) for path in paths if not path.is_file()]
    if missing:
        return [f"missing registry integration file: {path}" for path in missing], warnings

    try:
        index = _load_yaml(INDEX_PATH)
        registry = _load_yaml(REGISTRY_PATH)
        conflict = _load_yaml(CONFLICT_PATH)
        checkpoint = _load_json(CHECKPOINT_PATH)
        source_registry = _load_yaml(SOURCE_REGISTRY_PATH)
        core_manifest = _load_yaml(CORE_MANIFEST_PATH)
        trading_manifest = _load_yaml(TRADING_MANIFEST_PATH)
        trading_domain = _load_yaml(TRADING_DOMAIN_PATH)
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        return [f"unable to load registry integration files: {exc}"], warnings

    data_errors, data_warnings = validate_registry_data(index, registry, conflict)
    errors.extend(data_errors)
    warnings.extend(data_warnings)

    expected_pointers = {
        "skill_registry_index_path": "AI_SKILL_LIBRARY/skills/registry/index.yaml",
        "crypto_provider_registry_path": "AI_SKILL_LIBRARY/skills/providers/crypto_agents.yaml",
        "provider_conflict_policy_path": "AI_SKILL_LIBRARY/skills/registry/conflict_policy.yaml",
        "skill_registry_validator_path": "AI_SKILL_LIBRARY/validate_skill_registry.py",
        "crypto_agent_source_registry_path": "AI_SKILL_LIBRARY/sources/crypto_agent_official.yaml",
    }
    for key, expected in expected_pointers.items():
        if checkpoint.get(key) != expected:
            errors.append(f"checkpoint.{key} must be {expected!r}")

    if core_manifest.get("registry_index") != expected_pointers["skill_registry_index_path"]:
        errors.append("core skill pack must point to registry index")
    if core_manifest.get("registry_lookup_every_request") is not True:
        errors.append("core skill pack must require registry lookup every request")
    if core_manifest.get("provider_registry_reasoning_authority") is not False:
        errors.append("core skill pack must deny provider reasoning authority")

    if trading_manifest.get("provider_registry") != expected_pointers["crypto_provider_registry_path"]:
        errors.append("trading skill pack must point to crypto provider registry")
    if trading_manifest.get("provider_registry_reasoning_authority") is not False:
        errors.append("trading skill pack must deny provider reasoning authority")
    if trading_manifest.get("high_risk_auto_activate") is not False:
        errors.append("trading skill pack must disable HIGH_RISK auto activation")
    if trading_manifest.get("project_authority_required") is not True:
        errors.append("trading skill pack must continue requiring project authority")

    if trading_domain.get("provider_registry") != expected_pointers["crypto_provider_registry_path"]:
        errors.append("trading domain must point to crypto provider registry")
    if trading_domain.get("provider_registry_preload") is not False:
        errors.append("trading domain must not preload provider registry")
    if trading_domain.get("provider_registry_reasoning_authority") is not False:
        errors.append("trading domain must deny provider reasoning authority")
    if trading_domain.get("authority") != "docs/checkpoints/CURRENT_HANDOFF.md":
        errors.append("trading domain authority must remain CURRENT_HANDOFF.md")

    source_policy = source_registry.get("policy") if isinstance(source_registry.get("policy"), dict) else {}
    if source_policy.get("training") is not False:
        errors.append("crypto agent source registry must disable training")
    if source_policy.get("official_sources_only") is not True:
        errors.append("crypto agent source registry must be official-sources-only")
    if source_policy.get("vendor_full_upstream_repo") is not False:
        errors.append("crypto agent source registry must not vendor full upstream repositories")

    source_ids = {
        row.get("id")
        for row in source_registry.get("sources", [])
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    provider_ids = {
        row.get("id")
        for row in registry.get("providers", [])
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    missing_sources = sorted(provider_ids - source_ids)
    if missing_sources:
        errors.append(f"provider bundles missing official source registry entries: {missing_sources}")

    return errors, warnings


def main() -> int:
    errors, warnings = validate_registry_files()
    for warning in warnings:
        print(f"[WARN ] {warning}")
    for error in errors:
        print(f"[ERROR] {error}", file=sys.stderr)
    print(f"Skill registry validation summary: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
