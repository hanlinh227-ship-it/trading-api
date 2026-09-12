#!/usr/bin/env python3
"""Compile the validated V4 routing/skill authority into an exact-SHA hot snapshot."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SENSITIVE_KEY_RE = re.compile(r"secret|token|password|private_key|api_key|credential", re.I)


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _sha256(path: Path) -> str:
    return hashlib.sha256(_read_bytes(path)).hexdigest()


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


def normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value)).casefold().split())


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _git_head(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL, timeout=5
        ).strip().lower()
    except Exception:
        return ""


def validate_aliases(alias_data: dict[str, Any], skill_ids: set[str]) -> dict[str, list[str]]:
    raw = alias_data.get("aliases", {}) if isinstance(alias_data, dict) else {}
    if not isinstance(raw, dict):
        raise ValueError("aliases must be a mapping")
    normalized: dict[str, list[str]] = {}
    for skill_id, values in raw.items():
        if skill_id not in skill_ids:
            raise ValueError(f"alias references unknown skill: {skill_id}")
        if not isinstance(values, list) or not values:
            raise ValueError(f"aliases[{skill_id}] must be a non-empty list")
        items = sorted({normalize_text(v) for v in values if isinstance(v, str) and normalize_text(v)})
        if not items:
            raise ValueError(f"aliases[{skill_id}] has no usable entries")
        normalized[skill_id] = items
    return dict(sorted(normalized.items()))


def _load_domain_manifests(root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, str], dict[str, str]]:
    base = root / "AI_SKILL_LIBRARY" / "v4" / "skills"
    by_skill: dict[str, dict[str, Any]] = {}
    manifest_hashes: dict[str, str] = {}
    manifest_paths: dict[str, str] = {}
    for path in sorted(base.glob("*/manifest.yaml")):
        manifest = _load_yaml(path)
        rel = path.relative_to(root).as_posix()
        manifest_hashes[str(manifest.get("id") or path.parent.name)] = _sha256(path)
        for skill_id in manifest.get("skills", []):
            if not isinstance(skill_id, str) or not skill_id:
                continue
            if skill_id in by_skill:
                raise ValueError(f"skill appears in multiple V4 domain manifests: {skill_id}")
            by_skill[skill_id] = manifest
            manifest_paths[skill_id] = rel
    return by_skill, dict(sorted(manifest_hashes.items())), manifest_paths


def _domain_map(stable_router: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for domain, skill_ids in stable_router.get("domain_routes", {}).items():
        if not isinstance(skill_ids, list):
            continue
        for skill_id in skill_ids:
            if skill_id == "task_router" or not isinstance(skill_id, str):
                continue
            result.setdefault(skill_id, str(domain))
    result.setdefault("task_router", "core")
    return result


def _assert_no_sensitive_keys(value: Any, path: str = "snapshot") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if SENSITIVE_KEY_RE.search(str(key)):
                raise ValueError(f"sensitive-shaped key forbidden at {path}.{key}")
            _assert_no_sensitive_keys(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_no_sensitive_keys(item, f"{path}[{index}]")


def compile_snapshot(root: Path, source_sha: str, generated_at: str | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    source_sha = str(source_sha).strip().lower()
    if not SHA_RE.fullmatch(source_sha):
        raise ValueError("source_sha must be an exact 40-character lowercase git SHA")

    lib = root / "AI_SKILL_LIBRARY"
    checkpoint_path = lib / "checkpoint.json"
    router_path = lib / "v4" / "stable" / "router.yaml"
    runtime_path = lib / "v4" / "stable" / "runtime.yaml"
    registry_path = lib / "skills" / "registry" / "index.yaml"
    catalog_path = lib / "skills" / "catalog.yaml"
    security_path = lib / "v4" / "stable" / "security.yaml"
    authority_path = lib / "projects.yaml"
    aliases_path = lib / "v4" / "runtime" / "routing_aliases.yaml"
    pointer_path = lib / "v4" / "releases" / "current.json"

    checkpoint = _load_json(checkpoint_path)
    stable_router = _load_yaml(router_path)
    runtime = _load_yaml(runtime_path)
    registry = _load_yaml(registry_path)
    catalog = _load_yaml(catalog_path)
    aliases_data = _load_yaml(aliases_path)
    pointer = _load_json(pointer_path)

    manifest_path = root / str(pointer.get("manifest_path", ""))
    if not manifest_path.is_file():
        raise ValueError("active release manifest is missing")
    release_manifest = _load_yaml(manifest_path)

    rows = catalog.get("skills", [])
    if not isinstance(rows, list):
        raise ValueError("skill catalog skills must be a list")
    catalog_by_id = {
        row["id"]: row for row in rows
        if isinstance(row, dict) and isinstance(row.get("id"), str) and row.get("id")
    }
    skill_ids = set(catalog_by_id)
    if "core_reasoning" not in skill_ids or "task_router" not in skill_ids:
        raise ValueError("canonical core routing skills are missing")

    aliases = validate_aliases(aliases_data, skill_ids)
    manifests_by_skill, manifest_hashes, manifest_paths = _load_domain_manifests(root)
    domain_by_skill = _domain_map(stable_router)

    skills: dict[str, Any] = {}
    capsules: dict[str, Any] = {}
    for skill_id in sorted(skill_ids):
        row = catalog_by_id[skill_id]
        manifest = manifests_by_skill.get(skill_id)
        if manifest is None:
            raise ValueError(f"missing V4 domain manifest for skill: {skill_id}")
        domain = domain_by_skill.get(skill_id) or str(manifest.get("domain") or row.get("domain") or "core")
        triggers = sorted({normalize_text(v) for v in row.get("triggers", []) if isinstance(v, str) and normalize_text(v)})
        excludes = sorted({normalize_text(v) for v in row.get("excludes", []) if isinstance(v, str) and normalize_text(v)})
        skill_record = {
            "id": skill_id,
            "domain": domain,
            "triggers": triggers,
            "aliases": aliases.get(skill_id, []),
            "excludes": excludes,
            "requires": sorted(str(v) for v in row.get("requires", []) if isinstance(v, str)),
            "conflicts_with": sorted(str(v) for v in row.get("conflicts_with", []) if isinstance(v, str)),
            "priority": int(row.get("priority", 0)),
            "tools": sorted(str(v) for v in row.get("tools", []) if isinstance(v, str)),
            "sources": sorted(str(v) for v in row.get("sources", []) if isinstance(v, str)),
            "output_contract": str(row.get("output_contract") or "").strip(),
        }
        if not skill_record["output_contract"]:
            raise ValueError(f"empty output contract for skill: {skill_id}")
        skills[skill_id] = skill_record
        capsule_base = {
            "skill_id": skill_id,
            "domain": domain,
            "output_contract": skill_record["output_contract"],
            "requires": skill_record["requires"],
            "excludes": skill_record["excludes"],
            "conflicts_with": skill_record["conflicts_with"],
            "priority": skill_record["priority"],
            "tools": skill_record["tools"],
            "sources": skill_record["sources"],
            "permissions": sorted(str(v) for v in manifest.get("permissions", []) if isinstance(v, str)),
            "risk_ceiling": str(manifest.get("risk_ceiling") or "read_only"),
            "manifest_path": manifest_paths[skill_id],
            "response_checks": ["primary_skill_present", "capsule_applied", "output_contract_satisfied"],
        }
        capsules[skill_id] = {**capsule_base, "capsule_hash": _canonical_hash(capsule_base)}

    fallback = str(stable_router.get("policy", {}).get("fallback_primary_skill") or "")
    if fallback not in skills:
        raise ValueError("fallback primary skill is not canonical")

    profiles = {}
    for name in ("FAST", "STANDARD", "DEEP"):
        profile = runtime.get("profiles", {}).get(name, {})
        profiles[name] = {
            "primary_skill_count": int(profile.get("primary_skill_count", 0)),
            "skill_capsule_required": bool(profile.get("skill_capsule_required")),
            "max_supporting_skills": int(profile.get("max_supporting_skills", 0)),
            "max_bridge_nodes": int(profile.get("max_bridge_nodes", 0)),
            "max_parallel_tasks": int(profile.get("max_parallel_tasks", 1)),
            "tool_candidates": int(profile.get("tool_candidates", 0)),
            "durable_memory_items": int(profile.get("durable_memory_items", 0)),
        }

    hashes = {
        "checkpoint_hash": _sha256(checkpoint_path),
        "router_hash": _sha256(router_path),
        "runtime_hash": _sha256(runtime_path),
        "registry_index_hash": _sha256(registry_path),
        "skill_catalog_hash": _sha256(catalog_path),
        "routing_alias_hash": _sha256(aliases_path),
        "security_hash": _sha256(security_path),
        "authority_hash": _sha256(authority_path),
        "release_manifest_hash": _sha256(manifest_path),
        "domain_manifest_hashes": manifest_hashes,
    }

    snapshot = {
        "schema_version": 1,
        "source_sha": source_sha,
        "release_id": str(release_manifest.get("version") or pointer.get("version") or ""),
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "fallback_primary_skill": fallback,
        "profiles": profiles,
        "domains": {k: list(v) for k, v in sorted(stable_router.get("domain_routes", {}).items())},
        "skills": skills,
        "capsules": capsules,
        "aliases": aliases,
        "hashes": hashes,
        "routing_policy": {
            "primary_skill_required": True,
            "skill_execution_capsule_required": True,
            "fallback_primary_skill": fallback,
            "no_network_fast_selection": True,
            "authority_before_memory": bool(stable_router.get("policy", {}).get("authority_before_memory")),
        },
        "profile_selection": runtime.get("selection", {}),
        "registry_policy": {
            "lazy_provider_load": bool(registry.get("policy", {}).get("lazy_provider_load")),
            "provider_registry_is_reasoning_authority": bool(registry.get("policy", {}).get("provider_registry_is_reasoning_authority")),
        },
    }
    _assert_no_sensitive_keys(snapshot)
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--source-sha", default="")
    parser.add_argument("--output", default="AI_SKILL_LIBRARY/v4/runtime/generated/skill_gateway_snapshot.json")
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    source_sha = (args.source_sha or os.environ.get("GITHUB_SHA") or _git_head(root)).strip().lower()
    snapshot = compile_snapshot(root, source_sha, generated_at=args.generated_at)
    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(f"SKILL_GATEWAY_SNAPSHOT=PASS source_sha={snapshot['source_sha']} skills={len(snapshot['skills'])} capsules={len(snapshot['capsules'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
