from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import yaml

RELEASE_ROOT = Path("AI_SKILL_LIBRARY/v4/releases")

# Files that form the currently active immutable capability release. Keep this
# list stable until a candidate has passed its dependency and promotion gates.
RELEASE_FILES: tuple[tuple[str, str], ...] = (
    ("AI_SKILL_LIBRARY/v4/stable/kernel.yaml", "kernel"),
    ("AI_SKILL_LIBRARY/v4/stable/runtime.yaml", "runtime"),
    ("AI_SKILL_LIBRARY/v4/stable/router.yaml", "router"),
    ("AI_SKILL_LIBRARY/v4/stable/budgets.yaml", "budgets"),
    ("AI_SKILL_LIBRARY/v4/stable/retrieval.yaml", "retrieval"),
    ("AI_SKILL_LIBRARY/v4/stable/context.yaml", "context"),
    ("AI_SKILL_LIBRARY/v4/stable/reliability.yaml", "reliability"),
    ("AI_SKILL_LIBRARY/v4/stable/reputation.yaml", "reputation"),
    ("AI_SKILL_LIBRARY/v4/stable/memory.yaml", "memory"),
    ("AI_SKILL_LIBRARY/v4/stable/evidence.yaml", "evidence"),
    ("AI_SKILL_LIBRARY/v4/stable/harmonization.yaml", "harmonization"),
    ("AI_SKILL_LIBRARY/v4/stable/continuous_intelligence.yaml", "continuous_intelligence"),
    ("AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml", "capability_fusion"),
    ("AI_SKILL_LIBRARY/v4/stable/creative_visual_fusion.yaml", "creative_visual_fusion"),
    ("AI_SKILL_LIBRARY/v4/stable/presentation.yaml", "presentation"),
    ("AI_SKILL_LIBRARY/v4/stable/display_names.yaml", "display_names"),
    ("AI_SKILL_LIBRARY/v4/mesh/graph.yaml", "mesh"),
    ("AI_SKILL_LIBRARY/v4/mesh/bridges.yaml", "bridges"),
    ("AI_SKILL_LIBRARY/v4/model_mesh/policy.yaml", "model_mesh_policy"),
    ("AI_SKILL_LIBRARY/v4/model_mesh/providers.yaml", "model_mesh_providers"),
    ("AI_SKILL_LIBRARY/v4/model_mesh/discovery.yaml", "model_mesh_discovery"),
    ("AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml", "model_mesh_domain_capabilities"),
    ("AI_SKILL_LIBRARY/v4/model_mesh/upstreams.yaml", "model_mesh_upstreams"),
    ("AI_SKILL_LIBRARY/v4/runtime/routing_aliases.yaml", "routing_aliases"),
    ("AI_SKILL_LIBRARY/v4/evergreen/policy.yaml", "evergreen"),
    ("AI_SKILL_LIBRARY/v4/stable/security.yaml", "security"),
    ("AI_SKILL_LIBRARY/evals.yaml", "evals"),
)

# Peer Tri-Layer AI Legion contracts are packaged as a non-promoting candidate
# until all declared dependencies (especially AFMM runtime/snapshot proof) are
# verified. This avoids mutating the active release pointer during development.
CANDIDATE_EXTENSION_FILES: tuple[tuple[str, str], ...] = (
    ("AI_SKILL_LIBRARY/v4/legion/policy.yaml", "legion_policy"),
    ("AI_SKILL_LIBRARY/v4/legion/agents.yaml", "legion_agents"),
    ("AI_SKILL_LIBRARY/v4/learning/policy.yaml", "learning_policy"),
    ("AI_SKILL_LIBRARY/v4/learning/sources.yaml", "learning_sources"),
    ("AI_SKILL_LIBRARY/v4/learning/skill_factory.yaml", "skill_factory"),
    ("AI_SKILL_LIBRARY/v4/learning/skill_evo.yaml", "skill_evo"),
    ("AI_SKILL_LIBRARY/v4/learning/idle.yaml", "idle_learning"),
)


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
        actual = sha256_file(path)
        if actual != expected:
            errors.append(f"sha256 mismatch for {rel}: expected={expected} actual={actual}")
    return errors, warnings


def set_release_pointer(root: Path, version: str, manifest_sha256: str) -> None:
    manifest_path = f"AI_SKILL_LIBRARY/v4/releases/{version}/manifest.yaml"
    path = inside(root, "AI_SKILL_LIBRARY/v4/releases/current.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": version, "manifest_path": manifest_path, "manifest_sha256": manifest_sha256}
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


def _rows_for(root: Path, files: tuple[tuple[str, str], ...]) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for rel, role in files:
        if rel in seen:
            continue
        seen.add(rel)
        path = inside(root, rel)
        if not path.is_file():
            raise FileNotFoundError(f"release file missing: {rel}")
        rows.append({"path": rel, "sha256": sha256_file(path), "role": role})
    return rows


def build_manifest(root: Path, version: str, *, promotion: dict | None = None) -> dict:
    """Generate a stable release manifest. This function may be used by build_release."""
    return {
        "version": version,
        "architecture": "GITHUB_BRAIN_V4",
        "files": _rows_for(Path(root), RELEASE_FILES),
        "compatibility": {"min_architecture": "4.0.0"},
        "promotion": dict(promotion or {"class": "feature", "validated": False, "source": "release_build"}),
    }


def build_candidate_manifest(
    root: Path,
    version: str,
    *,
    source_sha: str,
    dependencies: dict[str, bool],
) -> dict:
    """Hash Stable + candidate extension contracts without changing current.json.

    Candidate packaging is intentionally side-effect free. Promotion remains blocked
    until every declared dependency is explicitly verified.
    """
    root = Path(root).resolve()
    if not isinstance(source_sha, str) or len(source_sha) != 40 or any(c not in "0123456789abcdefABCDEF" for c in source_sha):
        raise ValueError("source_sha must be a 40-hex git SHA")
    deps = {str(key): bool(value) for key, value in sorted(dependencies.items())}
    blocked = not deps or not all(deps.values())
    return {
        "version": str(version),
        "architecture": "GITHUB_BRAIN_V4",
        "candidate": True,
        "source_sha": source_sha.lower(),
        "active_pointer_mutation": False,
        "files": _rows_for(root, RELEASE_FILES + CANDIDATE_EXTENSION_FILES),
        "compatibility": {"min_architecture": "4.0.0"},
        "dependencies": deps,
        "promotion": {
            "class": "architecture_candidate",
            "validated": False,
            "blocked": blocked,
            "reason": "dependency_verification_incomplete" if blocked else "awaiting_explicit_promotion",
        },
    }


def write_candidate_manifest(root: Path, manifest: dict, output: str) -> Path:
    """Write a candidate artifact only; never change current.json or history.yaml."""
    path = inside(Path(root).resolve(), output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_manifest(manifest), encoding="utf-8")
    return path


def _dump_manifest(manifest: dict) -> str:
    return yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=200)


def manifest_is_fresh(root: Path, manifest: dict) -> list[str]:
    """Every active canonical release file must be current; candidate-only files do not alter active checks."""
    root = Path(root)
    rows = {row.get("path"): row for row in manifest.get("files", []) if isinstance(row, dict)}
    stale = []
    for rel, role in RELEASE_FILES:
        row = rows.get(rel)
        if row is None:
            stale.append(f"missing {rel}")
            continue
        if row.get("sha256") != sha256_file(inside(root, rel)):
            stale.append(rel)
    return stale


def load_history(root: Path) -> dict:
    path = root / RELEASE_ROOT / "history.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("version", 4)
    data.setdefault("releases", [])
    data.setdefault("rollback", {"pointer_only": True, "require_known_good": True, "protected_regression_triggers": True})
    return data


def _dump_history(history: dict) -> str:
    return yaml.safe_dump(history, sort_keys=False, allow_unicode=True, width=200)


def record_history(root: Path, version: str, *, known_good: bool) -> dict:
    history = load_history(root)
    rows = [row for row in history["releases"] if isinstance(row, dict)]
    existing = next((row for row in rows if row.get("version") == version), None)
    if existing is not None:
        previous = existing.get("previous")
    else:
        previous = rows[-1]["version"] if rows else None
    entry = {
        "version": version,
        "known_good": known_good,
        "architecture": "GITHUB_BRAIN_V4",
        "manifest": f"AI_SKILL_LIBRARY/v4/releases/{version}/manifest.yaml",
        "previous": previous,
    }
    rows = [row for row in rows if row["version"] != version] + [entry]
    history["releases"] = rows
    (root / RELEASE_ROOT / "history.yaml").write_text(_dump_history(history), encoding="utf-8")
    return history


def build_release(root: Path, version: str, *, source: str, validated: bool, known_good: bool, promotion_class: str = "feature") -> dict:
    root = Path(root)
    version = str(version)
    manifest = build_manifest(root, version, promotion={"class": promotion_class, "validated": validated, "source": source})
    manifest_path = inside(root, f"AI_SKILL_LIBRARY/v4/releases/{version}/manifest.yaml")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(_dump_manifest(manifest), encoding="utf-8")
    errors, _ = verify_release(root, version)
    if errors:
        raise ValueError("release build produced an invalid manifest: " + "; ".join(errors))
    set_release_pointer(root, version, sha256_file(manifest_path))
    record_history(root, version, known_good=known_good)
    errors, _ = verify_active_pointer(root)
    if errors:
        raise ValueError("release build produced an invalid pointer: " + "; ".join(errors))
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GITHUB_BRAIN_V4 release tool (hash generation is automatic)")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="generate manifest + pointer + history for a stable version")
    build.add_argument("--version", required=True)
    build.add_argument("--source", default="release_build")
    build.add_argument("--class", dest="promotion_class", default="feature")
    build.add_argument("--validated", action="store_true")
    build.add_argument("--known-good", action="store_true")
    build.add_argument("--root", default=".")
    verify = sub.add_parser("verify", help="verify the active release pointer")
    verify.add_argument("--root", default=".")
    check = sub.add_parser("check", help="fail if the active manifest hashes are stale")
    check.add_argument("--root", default=".")
    candidate = sub.add_parser("candidate", help="package a non-promoting Legion candidate manifest")
    candidate.add_argument("--version", default="4.9.0-candidate")
    candidate.add_argument("--source-sha", required=True)
    candidate.add_argument("--afmm-verified", action="store_true")
    candidate.add_argument("--output", default="AI_SKILL_LIBRARY/v4/releases/candidates/peer-tri-layer-ai-legion/manifest.yaml")
    candidate.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if args.command == "build":
        manifest = build_release(root, args.version, source=args.source, validated=args.validated, known_good=args.known_good, promotion_class=args.promotion_class)
        print(f"RELEASE_BUILD=PASS version={manifest['version']} files={len(manifest['files'])}")
        return 0
    if args.command == "candidate":
        manifest = build_candidate_manifest(
            root,
            args.version,
            source_sha=args.source_sha,
            dependencies={"adaptive_free_model_mesh_verified": bool(args.afmm_verified)},
        )
        path = write_candidate_manifest(root, manifest, args.output)
        print(f"CANDIDATE_RELEASE=PASS version={manifest['version']} blocked={str(manifest['promotion']['blocked']).lower()} output={path.relative_to(root)}")
        return 0
    if args.command == "verify":
        errors, warnings = verify_active_pointer(root)
        for item in errors:
            print(f"[ERROR] {item}")
        print(f"Release verification summary: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1 if errors else 0
    pointer = load_release_pointer(root)
    on_disk = load_release_manifest(root, pointer["version"])
    stale = manifest_is_fresh(root, on_disk)
    errors, _ = verify_active_pointer(root)
    if stale or errors:
        print(f"[ERROR] release manifest stale/invalid for {pointer['version']}: {stale + errors}; run release.py build")
        return 1
    print(f"RELEASE_CHECK=PASS version={pointer['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
