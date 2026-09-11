from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

RELEASE_ROOT = Path("AI_SKILL_LIBRARY/v4/releases")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inside(root: Path, rel: str) -> Path:
    if not isinstance(rel, str) or not rel.strip():
        raise ValueError("path must be a non-empty repository-relative string")
    candidate = Path(rel)
    if candidate.is_absolute():
        raise ValueError("absolute paths are forbidden")
    path = (root / candidate).resolve()
    path.relative_to(root.resolve())
    return path


def load_release_pointer(root: Path) -> dict:
    path = root / RELEASE_ROOT / "current.json"
    if not path.is_file():
        raise FileNotFoundError(f"missing release pointer: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("release pointer must be an object")
    return data


def load_release_manifest(root: Path, version: str) -> dict:
    path = root / RELEASE_ROOT / version / "manifest.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"missing release manifest for {version}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("release manifest must be a mapping")
    return data


def verify_release(root: Path, version: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    release_dir = root / RELEASE_ROOT / version
    if not release_dir.is_dir():
        return [f"missing release directory for {version}"], warnings
    try:
        manifest = load_release_manifest(root, version)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return [str(exc)], warnings
    if manifest.get("version") != version:
        errors.append("manifest version mismatch")
    if manifest.get("architecture") != "GITHUB_BRAIN_V4":
        errors.append("manifest architecture must be GITHUB_BRAIN_V4")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        errors.append("manifest files must be a non-empty list")
        files = []
    for row in files:
        if not isinstance(row, dict):
            errors.append("manifest file entry must be a mapping")
            continue
        rel = row.get("path")
        expected = row.get("sha256")
        try:
            path = inside(root, rel)
        except (TypeError, ValueError) as exc:
            errors.append(f"invalid release path {rel!r}: {exc}")
            continue
        if not path.is_file():
            errors.append(f"missing release file: {rel}")
            continue
        if not isinstance(expected, str) or len(expected) != 64:
            errors.append(f"invalid sha256 for {rel}")
            continue
        if sha256_file(path) != expected:
            errors.append(f"sha256 mismatch for {rel}")
    return errors, warnings


def set_release_pointer(root: Path, version: str, manifest_sha256: str) -> None:
    manifest_path = f"AI_SKILL_LIBRARY/v4/releases/{version}/manifest.yaml"
    path = inside(root, "AI_SKILL_LIBRARY/v4/releases/current.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": version,
        "manifest_path": manifest_path,
        "manifest_sha256": manifest_sha256,
    }
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def verify_active_pointer(root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        pointer = load_release_pointer(root)
        version = pointer.get("version")
        manifest_rel = pointer.get("manifest_path")
        manifest_hash = pointer.get("manifest_sha256")
        if not isinstance(version, str):
            return ["release pointer version missing"], warnings
        manifest_path = inside(root, manifest_rel)
        expected_rel = f"AI_SKILL_LIBRARY/v4/releases/{version}/manifest.yaml"
        if manifest_rel != expected_rel:
            errors.append("release pointer manifest_path/version mismatch")
        if not manifest_path.is_file():
            errors.append("release pointer manifest is missing")
        elif sha256_file(manifest_path) != manifest_hash:
            errors.append("release pointer manifest hash mismatch")
        release_errors, release_warnings = verify_release(root, version)
        errors.extend(release_errors)
        warnings.extend(release_warnings)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
    return errors, warnings


def rollback_release(root: Path) -> str:
    pointer = load_release_pointer(root)
    current = pointer.get("version")
    history_path = root / RELEASE_ROOT / "history.yaml"
    data = yaml.safe_load(history_path.read_text(encoding="utf-8")) if history_path.is_file() else {}
    rows = data.get("releases", []) if isinstance(data, dict) else []
    known_good = [row.get("version") for row in rows if isinstance(row, dict) and row.get("known_good") is True]
    if current not in known_good:
        raise ValueError("current release is not present in known-good history")
    index = known_good.index(current)
    if index == 0:
        raise ValueError("no previous known-good release available")
    target = known_good[index - 1]
    manifest_path = root / RELEASE_ROOT / target / "manifest.yaml"
    if not manifest_path.is_file():
        raise ValueError("previous known-good manifest missing")
    set_release_pointer(root, target, sha256_file(manifest_path))
    return target
