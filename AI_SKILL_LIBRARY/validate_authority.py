#!/usr/bin/env python3
"""Validate project authority uniqueness and checkpoint freshness for GITHUB_BRAIN V2/V3/V4."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROJECTS_PATH = HERE / "projects.yaml"
CHECKPOINT_PATH = HERE / "checkpoint.json"
PROJECT_SCHEMA = HERE / "schemas" / "project.schema.json"
CURRENT_STATUSES = {"CURRENT", "ACTIVE", "CURRENT_AUTHORITY"}


def _inside(root: Path, rel: object) -> Path | None:
    if not isinstance(rel, str) or not rel.strip():
        return None
    path = (root / rel).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return None
    return path


def validate_authority_data(projects: dict, checkpoint: dict, *, root: Path = ROOT) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    rows = projects.get("projects", []) if isinstance(projects, dict) else []
    if not isinstance(rows, list) or not rows:
        return ["projects registry must contain projects"], warnings

    grouped: dict[str, list[dict]] = {}
    for idx, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"project[{idx}] must be a mapping")
            continue
        pid = row.get("id")
        if not isinstance(pid, str) or not pid:
            errors.append(f"project[{idx}] id must be non-empty")
            continue
        grouped.setdefault(pid, []).append(row)
        if row.get("status") in CURRENT_STATUSES:
            authority = _inside(root, row.get("authority"))
            canonical = _inside(root, row.get("canonical_checkpoint"))
            if authority is None or not authority.is_file():
                errors.append(f"project[{pid}] authority missing: {row.get('authority')!r}")
            if canonical is None or not canonical.is_file():
                errors.append(f"project[{pid}] canonical checkpoint missing: {row.get('canonical_checkpoint')!r}")
            if authority and authority.is_file() and canonical and canonical.is_file() and authority != canonical:
                text = authority.read_text(encoding="utf-8", errors="replace")
                canonical_rel = row.get("canonical_checkpoint", "")
                if canonical_rel not in text and canonical.name not in text:
                    warnings.append(f"project[{pid}] authority does not explicitly name canonical checkpoint {canonical_rel!r}")

    for pid, entries in grouped.items():
        current = [row for row in entries if row.get("status") in CURRENT_STATUSES]
        if len(current) > 1:
            errors.append(f"multiple current authorities for project {pid!r}")
        elif not current:
            errors.append(f"no current authority for project {pid!r}")

    checkpoint_id = checkpoint.get("checkpoint_id")
    if checkpoint_id not in {"GITHUB_BRAIN_V2", "GITHUB_BRAIN_V3", "GITHUB_BRAIN_V4"}:
        errors.append("checkpoint_id must be GITHUB_BRAIN_V2, GITHUB_BRAIN_V3, or GITHUB_BRAIN_V4")
    aliases = set(checkpoint.get("activation_aliases", []))
    if "GITHUB_BRAIN_V1" not in aliases:
        errors.append("GITHUB_BRAIN_V1 compatibility alias is missing")
    if checkpoint_id in {"GITHUB_BRAIN_V3", "GITHUB_BRAIN_V4"} and "GITHUB_BRAIN_V2" not in aliases:
        errors.append("GITHUB_BRAIN_V2 compatibility alias is missing")
    if checkpoint_id == "GITHUB_BRAIN_V4" and "GITHUB_BRAIN_V3" not in aliases:
        errors.append("GITHUB_BRAIN_V3 compatibility alias is missing")

    required_checkpoint_paths = {
        "checkpoint_path", "router_path", "plugins_path", "registry_path", "projects_path",
        "skill_catalog_path", "router_validator_path", "authority_validator_path",
    }
    if checkpoint_id in {"GITHUB_BRAIN_V3", "GITHUB_BRAIN_V4"}:
        required_checkpoint_paths |= {
            "bootstrap_path", "kernel_path", "runtime_path", "context_path", "reliability_path",
            "evidence_path", "orchestration_path", "v3_validator_path",
        }
    if checkpoint_id == "GITHUB_BRAIN_V4":
        required_checkpoint_paths |= {
            "release_pointer_path", "stable_kernel_path", "stable_router_path", "stable_runtime_path",
            "mesh_graph_path", "mesh_bridges_path", "evergreen_policy_path", "v4_validator_path",
        }
    for key in required_checkpoint_paths:
        target = _inside(root, checkpoint.get(key))
        if target is None or not target.is_file():
            errors.append(f"checkpoint reference missing for {key}: {checkpoint.get(key)!r}")

    ai_rows = [row for row in rows if row.get("id") == "ai_brain" and row.get("status") in CURRENT_STATUSES]
    if len(ai_rows) == 1:
        expected = {
            "GITHUB_BRAIN_V2": "AI_SKILL_LIBRARY/GITHUB_BRAIN_V2.md",
            "GITHUB_BRAIN_V3": "AI_SKILL_LIBRARY/GITHUB_BRAIN_V3.md",
            "GITHUB_BRAIN_V4": "AI_SKILL_LIBRARY/GITHUB_BRAIN_V4.md",
        }.get(checkpoint_id)
        if expected and ai_rows[0].get("authority") != expected:
            errors.append(f"ai_brain authority must be {expected}")

    trading_rows = [row for row in rows if row.get("id") == "trading" and row.get("status") in CURRENT_STATUSES]
    if len(trading_rows) == 1:
        trading = trading_rows[0]
        if trading.get("authority") != "docs/checkpoints/CURRENT_HANDOFF.md":
            errors.append("trading authority must be docs/checkpoints/CURRENT_HANDOFF.md")
        if trading.get("canonical_checkpoint") != "docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md":
            errors.append("trading canonical checkpoint must be BYBIT_BTC_STATEFLOW_2_1_20260904.md")
        authority = _inside(root, trading.get("authority"))
        if authority and authority.is_file():
            text = authority.read_text(encoding="utf-8", errors="replace")
            if "BYBIT-BTC-STATEFLOW-2.1" not in text:
                errors.append("trading authority is stale: missing BYBIT-BTC-STATEFLOW-2.1")
            for retired in ("multi-coin", "Forex", "Meme", "Signal V10/V11"):
                if retired not in text:
                    warnings.append(f"trading authority does not explicitly mention retired family {retired!r}")

    return errors, warnings


def main() -> int:
    try:
        projects = yaml.safe_load(PROJECTS_PATH.read_text(encoding="utf-8"))
        checkpoint = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
        schema = json.loads(PROJECT_SCHEMA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"[ERROR] unable to load authority inputs: {exc}", file=sys.stderr)
        return 2
    errors, warnings = validate_authority_data(projects, checkpoint)
    errors.extend(f"project schema: {err.message}" for err in Draft202012Validator(schema).iter_errors(projects))
    for warning in warnings:
        print(f"[WARN ] {warning}")
    for error in errors:
        print(f"[ERROR] {error}", file=sys.stderr)
    print(f"Authority validation summary: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
