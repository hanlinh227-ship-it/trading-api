from __future__ import annotations

import copy
import fnmatch
from pathlib import Path

import yaml


_ALLOWED_MODES = {"plan", "explore", "research", "patch", "test", "review"}
_IMMUTABLE_DENIES = {
    "git_push",
    "external_directory",
    "financial_execution",
    "credential_mutation",
    "permission_widening",
    "destructive_production",
}


def _policy() -> dict:
    root = Path(__file__).resolve().parents[3]
    return yaml.safe_load((root / "AI_SKILL_LIBRARY/v4/legion/opencode.yaml").read_text(encoding="utf-8"))


def translate_brain_permissions(task: dict) -> dict:
    mode = str(task.get("mode", "")).strip()
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"unsupported OpenCode mode: {mode}")

    policy = _policy()
    base = copy.deepcopy(policy["modes"][mode])
    permissions = dict(base)

    # Explicit Brain denies are immutable. Overrides can only reduce permissions.
    denied = set(policy.get("always_deny", [])) | set(task.get("denied_actions", []))
    for action in denied:
        permissions[action] = "deny"

    overrides = task.get("permission_overrides", {}) or {}
    rank = {"deny": 0, "ask": 1, "allow": 2}
    for action, requested in overrides.items():
        current = permissions.get(action, "deny")
        if action in denied:
            permissions[action] = "deny"
            continue
        if requested not in rank:
            raise ValueError(f"invalid permission action: {requested}")
        permissions[action] = requested if rank[requested] <= rank.get(current, 0) else current

    if task.get("permission_ceiling") == "read_only":
        permissions["edit"] = "deny"
        if mode != "test":
            permissions["bash"] = "deny"

    for action in _IMMUTABLE_DENIES:
        if action in denied or action in _IMMUTABLE_DENIES:
            permissions[action] = "deny"
    return permissions


def build_opencode_job(task: dict, repo: dict) -> dict:
    mode = task.get("mode")
    permissions = translate_brain_permissions(task)
    source_sha = str(repo.get("source_sha", ""))
    if len(source_sha) != 40:
        raise ValueError("repo source_sha must be a 40-character commit SHA")
    task_id = str(task.get("task_id", "")).strip()
    if not task_id:
        raise ValueError("task_id is required")
    return {
        "schema_version": 1,
        "worker": "opencode",
        "task_id": task_id,
        "mode": mode,
        "repository": repo.get("repository"),
        "source_sha": source_sha,
        "branch": repo.get("branch"),
        "workspace": repo.get("workspace"),
        "allowed_paths": list(task.get("allowed_paths", [])),
        "permissions": permissions,
        "timeout_seconds": int(task.get("timeout_seconds", 300)),
        "output_schema": task.get("output_schema", "legion_worker_result_v1"),
        "risk_class": task.get("risk_class", "A"),
        "data_class": task.get("data_class", "PUBLIC"),
        "routing_authority": False,
        "reasoning_authority": False,
        "auto_mode_can_override_denies": False,
    }


def _path_allowed(path: str, patterns: list[str]) -> bool:
    normalized = path.lstrip("./")
    return any(fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch(normalized, pattern.replace("/**", "/*")) for pattern in patterns)


def validate_opencode_result(result: dict, task: dict) -> list[str]:
    errors: list[str] = []
    if result.get("task_id") != task.get("task_id"):
        errors.append("task_id mismatch")
    expected_sha = task.get("source_sha")
    if expected_sha and result.get("source_sha") != expected_sha:
        errors.append("source_sha mismatch")
    if result.get("credentials_present"):
        errors.append("credential material present in OpenCode result")

    allowed_paths = list(task.get("allowed_paths", []))
    for changed in result.get("changed_paths", []) or []:
        if not _path_allowed(str(changed), allowed_paths):
            errors.append(f"changed path outside allowed paths: {changed}")

    baseline = translate_brain_permissions(task)
    requested = result.get("requested_permissions", {}) or {}
    rank = {"deny": 0, "ask": 1, "allow": 2}
    for action, value in requested.items():
        base = baseline.get(action, "deny")
        if value not in rank or rank[value] > rank.get(base, 0):
            errors.append(f"permission expansion requested: {action}")

    if result.get("status") not in {"completed", "failed", "blocked"}:
        errors.append("invalid result status")
    return sorted(set(errors))
