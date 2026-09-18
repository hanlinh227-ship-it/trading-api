#!/usr/bin/env python3
"""Validate bounded upstream capability knowledge fusion.

This registry is evidence/reference metadata only. It must never become a second
Brain, router, Model Mesh, Legion, memory authority, or an executable dependency
by accident.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
LIB = ROOT / "AI_SKILL_LIBRARY"
REGISTRY_PATH = LIB / "v4/integrations/upstream_knowledge_fusion.yaml"
INDEX_PATH = LIB / "skills/registry/index.yaml"
CHECKPOINT_PATH = LIB / "checkpoint.json"

EXPECTED_IDS = {
    "agent_desktop",
    "munder_difflin",
    "dify",
    "autogpt",
    "sim",
    "openclaw",
    "open_webui",
    "ollama",
    "vllm",
    "transformers",
    "unsloth",
    "openpipe_art",
    "opik",
    "airweave",
    "firecrawl",
    "chandra",
    "comfyui",
    "langchain",
    "opencode",
    "remotion_cuongit_template",
    "auto_video_gen",
    "auto_compare_video",
}

STRENGTHEN_EXISTING = {"ollama", "vllm", "transformers", "comfyui", "opencode"}
LEARNING_LAB_ONLY = {"unsloth", "openpipe_art"}
ALLOWED_STATUS = {
    "approved_reference",
    "manual_review_reference",
    "historical_reference",
    "reference_only_license_restricted",
}
ALLOWED_LICENSE_STATUS = {"verified", "manual_review", "verified_restrictive"}
ALLOWED_MODE = {"reference_pattern", "strengthen_existing"}


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


def validate_fusion_data(
    fusion: dict[str, Any], index: dict[str, Any], checkpoint: dict[str, Any]
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if fusion.get("version") != 1:
        errors.append("fusion registry version must be 1")
    if fusion.get("brain_authority") != "GITHUB_BRAIN_V4":
        errors.append("fusion registry must name GITHUB_BRAIN_V4 as brain_authority")
    for key in ("routing_authority", "reasoning_authority", "model_selection_authority", "stable_mutation"):
        if fusion.get(key) is not False:
            errors.append(f"fusion {key} must be false")

    selection = fusion.get("selection") if isinstance(fusion.get("selection"), dict) else {}
    if selection.get("load_after_domain_selection") is not True:
        errors.append("fusion must load only after domain selection")
    if selection.get("preload_all_entries") is not False:
        errors.append("fusion must not preload all entries")
    max_candidates = selection.get("max_candidates_per_request")
    if not isinstance(max_candidates, int) or isinstance(max_candidates, bool) or not 1 <= max_candidates <= 3:
        errors.append("fusion max_candidates_per_request must be an integer from 1 to 3")
    if selection.get("unknown_entry_action") != "quarantine_no_routing":
        errors.append("unknown upstream entries must quarantine_no_routing")

    safety = fusion.get("safety") if isinstance(fusion.get("safety"), dict) else {}
    required_true = (
        "upstream_is_reference_not_authority",
        "provider_or_framework_cannot_replace_task_router",
        "provider_or_framework_cannot_replace_model_mesh",
        "provider_or_framework_cannot_replace_legion",
        "provider_or_framework_cannot_replace_memory_continuity",
        "project_authority_precedes_upstream_patterns",
        "stable_security_precedes_upstream_patterns",
        "development_lab_cannot_write_stable_directly",
        "manual_review_licenses_never_enable_code_reuse",
        "archived_upstreams_never_become_runtime_dependencies",
    )
    for key in required_true:
        if safety.get(key) is not True:
            errors.append(f"fusion safety.{key} must be true")
    for key in ("code_reuse_default", "executable_dependency_default", "auto_activate_default", "permission_expansion"):
        if safety.get(key) is not False:
            errors.append(f"fusion safety.{key} must be false")

    targets = fusion.get("canonical_targets")
    if not isinstance(targets, dict) or not targets:
        errors.append("fusion must define canonical_targets")
        targets = {}

    entries = fusion.get("entries")
    if not isinstance(entries, list):
        errors.append("fusion entries must be a list")
        entries = []

    seen_ids: set[str] = set()
    seen_repos: set[str] = set()
    for row in entries:
        if not isinstance(row, dict):
            errors.append("fusion entry must be a mapping")
            continue
        entry_id = row.get("id")
        repo = row.get("repo")
        if not isinstance(entry_id, str) or not entry_id:
            errors.append("fusion entry id must be non-empty")
            continue
        if entry_id in seen_ids:
            errors.append(f"duplicate fusion entry id: {entry_id}")
        seen_ids.add(entry_id)

        if not isinstance(repo, str) or "/" not in repo:
            errors.append(f"{entry_id}: repo must be owner/name")
        elif repo in seen_repos:
            errors.append(f"duplicate fusion repo: {repo}")
        else:
            seen_repos.add(repo)

        if row.get("routing_authority") is not False:
            errors.append(f"{entry_id}: routing_authority must be false")
        if row.get("reasoning_authority") is not False:
            errors.append(f"{entry_id}: reasoning_authority must be false")
        if row.get("code_reuse") is not False:
            errors.append(f"{entry_id}: code_reuse must be false")
        if row.get("executable_dependency_added") is not False:
            errors.append(f"{entry_id}: executable_dependency_added must be false")
        if row.get("auto_activate") is not False:
            errors.append(f"{entry_id}: auto_activate must be false")

        mode = row.get("mode")
        if mode not in ALLOWED_MODE:
            errors.append(f"{entry_id}: invalid mode {mode!r}")
        if entry_id in STRENGTHEN_EXISTING and mode != "strengthen_existing":
            errors.append(f"{entry_id}: existing capability must use strengthen_existing mode")

        status = row.get("status")
        if status not in ALLOWED_STATUS:
            errors.append(f"{entry_id}: invalid status {status!r}")
        license_status = row.get("license_status")
        if license_status not in ALLOWED_LICENSE_STATUS:
            errors.append(f"{entry_id}: invalid license_status {license_status!r}")
        if license_status == "manual_review" and status != "manual_review_reference":
            errors.append(f"{entry_id}: manual-review license must remain manual_review_reference")
        if license_status == "verified_restrictive" and status != "reference_only_license_restricted":
            errors.append(f"{entry_id}: restrictive license must remain reference-only")

        archived = row.get("archived")
        if not isinstance(archived, bool):
            errors.append(f"{entry_id}: archived must be boolean")
        if archived is True and status != "historical_reference":
            errors.append(f"{entry_id}: archived upstream must be historical_reference")

        domains = row.get("domains")
        if not isinstance(domains, list) or not domains or not all(isinstance(v, str) and v for v in domains):
            errors.append(f"{entry_id}: domains must be a non-empty list of strings")
        absorbs = row.get("absorbs")
        if not isinstance(absorbs, list) or not absorbs or not all(isinstance(v, str) and v for v in absorbs):
            errors.append(f"{entry_id}: absorbs must be a non-empty list of strings")

        target = row.get("integration_target")
        if target not in targets:
            errors.append(f"{entry_id}: integration_target {target!r} is not canonical")
        if entry_id in LEARNING_LAB_ONLY and row.get("development_lab_only") is not True:
            errors.append(f"{entry_id}: learning/training reference must be development_lab_only")

    missing = EXPECTED_IDS - seen_ids
    unexpected = seen_ids - EXPECTED_IDS
    if missing:
        errors.append("missing expected upstream entries: " + ", ".join(sorted(missing)))
    if unexpected:
        errors.append("unexpected upstream entries: " + ", ".join(sorted(unexpected)))

    registries = index.get("registries") if isinstance(index.get("registries"), list) else []
    fusion_rows = [r for r in registries if isinstance(r, dict) and r.get("id") == "upstream_capability_knowledge"]
    if len(fusion_rows) != 1:
        errors.append("skill registry index must contain exactly one upstream_capability_knowledge registry")
    else:
        row = fusion_rows[0]
        expected_path = "AI_SKILL_LIBRARY/v4/integrations/upstream_knowledge_fusion.yaml"
        if row.get("path") != expected_path:
            errors.append(f"upstream capability registry path must be {expected_path}")
        if row.get("load") != "after_domain_match":
            errors.append("upstream capability registry must lazy-load after_domain_match")
        if row.get("routing_authority") is not False:
            errors.append("upstream capability registry cannot have routing authority")
        if row.get("reasoning_authority") is not False:
            errors.append("upstream capability registry cannot have reasoning authority")
        if row.get("max_candidates") not in (None, 3):
            errors.append("upstream capability registry max_candidates may not exceed 3")

    expected_checkpoint = {
        "upstream_knowledge_fusion_path": "AI_SKILL_LIBRARY/v4/integrations/upstream_knowledge_fusion.yaml",
        "upstream_knowledge_fusion_validator_path": "AI_SKILL_LIBRARY/v4/tools/validate_upstream_knowledge_fusion.py",
    }
    for key, value in expected_checkpoint.items():
        if checkpoint.get(key) != value:
            errors.append(f"checkpoint.{key} must be {value!r}")

    return errors, warnings


def validate_fusion_files(root: Path = ROOT) -> tuple[list[str], list[str]]:
    registry_path = root / "AI_SKILL_LIBRARY/v4/integrations/upstream_knowledge_fusion.yaml"
    index_path = root / "AI_SKILL_LIBRARY/skills/registry/index.yaml"
    checkpoint_path = root / "AI_SKILL_LIBRARY/checkpoint.json"
    missing = [str(p.relative_to(root)) for p in (registry_path, index_path, checkpoint_path) if not p.is_file()]
    if missing:
        return [f"missing upstream knowledge fusion file: {p}" for p in missing], []
    try:
        fusion = _load_yaml(registry_path)
        index = _load_yaml(index_path)
        checkpoint = _load_json(checkpoint_path)
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        return [f"unable to load upstream knowledge fusion files: {exc}"], []
    return validate_fusion_data(fusion, index, checkpoint)


def main() -> int:
    errors, warnings = validate_fusion_files()
    for warning in warnings:
        print(f"WARN upstream_knowledge_fusion: {warning}")
    if errors:
        for error in errors:
            print(f"FAIL upstream_knowledge_fusion: {error}")
        return 1
    print(f"PASS upstream_knowledge_fusion: {len(EXPECTED_IDS)} bounded upstream references validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
