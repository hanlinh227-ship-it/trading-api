from __future__ import annotations

import argparse
import base64
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

try:
    from .admission import admit_skill
    from .release import load_release_manifest, load_release_pointer, set_release_pointer, sha256_file
except ImportError:
    from admission import admit_skill
    from release import load_release_manifest, load_release_pointer, set_release_pointer, sha256_file

REQUIRED_GATES = ("provenance", "license", "security", "authority", "evals", "canary")
ALLOWED_DOMAINS = {"core", "engineering", "trading", "game", "design_2d", "design_3d", "adobe", "prompt_media", "writing", "academic", "data_docs", "business"}


def lifecycle_decision(*, promotion_class: str, gates: dict[str, bool], protected_regressions: list[str]) -> str:
    if promotion_class == "D":
        return "manual_authorization_required"
    if promotion_class not in {"A", "B", "C"}:
        return "reject"
    if protected_regressions:
        return "reject"
    if any(gates.get(name) is not True for name in REQUIRED_GATES):
        return "reject"
    if promotion_class == "C" and gates.get("second_canary") is not True:
        return "hold"
    return "promote"


def quarantine_candidate(candidate: dict) -> dict:
    return {"state": "quarantine", "routing_authority": False, "stable_mutation": False, "candidate": candidate}


def promotion_record(candidate_id: str, version: str, decision: str, evidence: list[str]) -> dict:
    return {"candidate_id": candidate_id, "version": version, "decision": decision, "evidence": list(evidence), "inflight_stable_mutation": False}


def _github_json(url: str, token: str | None) -> object:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "github-brain-v4-evergreen"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _try_skill_manifest(repo: str, default_branch: str, token: str | None) -> dict | None:
    for rel in ("skill.yaml", "SKILL.yaml", ".agents/skills/skill.yaml"):
        url = f"https://api.github.com/repos/{repo}/contents/{urllib.parse.quote(rel)}?ref={urllib.parse.quote(default_branch)}"
        try:
            data = _github_json(url, token)
        except Exception:
            continue
        if not isinstance(data, dict) or data.get("encoding") != "base64" or not data.get("content"):
            continue
        try:
            raw = base64.b64decode(data["content"]).decode("utf-8")
            manifest = yaml.safe_load(raw)
        except Exception:
            continue
        if isinstance(manifest, dict):
            manifest["_source_manifest_path"] = rel
            return manifest
    return None


def scan_github(root: Path, output: Path, *, token: str | None = None) -> dict:
    discovery_path = root / "AI_SKILL_LIBRARY/v4/evergreen/discovery.yaml"
    discovery = yaml.safe_load(discovery_path.read_text(encoding="utf-8")) or {}
    queries = discovery.get("github_queries", [])
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "state": "quarantine_scan", "routing_authority": False, "candidates": [], "errors": []}
    for row in queries:
        if not isinstance(row, dict) or not row.get("query"):
            continue
        domain = row.get("domain")
        if domain not in ALLOWED_DOMAINS:
            continue
        q = urllib.parse.quote(str(row["query"]))
        url = f"https://api.github.com/search/repositories?q={q}&sort=updated&order=desc&per_page=5"
        try:
            result = _github_json(url, token)
        except Exception as exc:
            report["errors"].append({"query": row["query"], "error": type(exc).__name__})
            continue
        for repo in result.get("items", []) if isinstance(result, dict) else []:
            if not isinstance(repo, dict):
                continue
            full_name = repo.get("full_name")
            branch = repo.get("default_branch") or "main"
            manifest = _try_skill_manifest(str(full_name), str(branch), token) if full_name else None
            license_id = (repo.get("license") or {}).get("spdx_id") if isinstance(repo.get("license"), dict) else None
            candidate = {
                "candidate_id": f"github:{full_name}",
                "domain": domain,
                "repo": full_name,
                "url": repo.get("html_url"),
                "updated_at": repo.get("updated_at"),
                "stars": repo.get("stargazers_count", 0),
                "license": license_id,
                "state": "quarantine",
                "routing_authority": False,
                "skill": manifest,
            }
            report["candidates"].append(candidate)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def materialize_quarantine(root: Path, scan_path: Path) -> list[Path]:
    report = json.loads(scan_path.read_text(encoding="utf-8"))
    destination = root / "AI_SKILL_LIBRARY/v4/evergreen/quarantine"
    destination.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for row in report.get("candidates", []):
        if not isinstance(row, dict) or not isinstance(row.get("skill"), dict):
            continue
        skill = dict(row["skill"])
        skill.pop("_source_manifest_path", None)
        if skill.get("domain") != row.get("domain"):
            continue
        skill.setdefault("provenance", {"source": row.get("url"), "verified": True})
        if not skill.get("license") and row.get("license"):
            skill["license"] = row["license"]
        skill.setdefault("compatibility", {"brain": "4.x"})
        admission = admit_skill(skill, existing_skills=[])
        record = {
            "candidate_id": row.get("candidate_id"),
            "state": "quarantine",
            "routing_authority": False,
            "stable_mutation": False,
            "domain": row.get("domain"),
            "source_repo": row.get("repo"),
            "promotion_class": admission["promotion_class"],
            "admission": admission,
            "skill": skill,
        }
        safe = str(skill.get("id", "candidate")).replace("/", "_")
        path = destination / f"{safe}.yaml"
        path.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")
        written.append(path)
    return written


def _next_release(version: str) -> str:
    major, minor, patch = (int(part) for part in version.split("."))
    if (major, minor) != (4, 0):
        raise ValueError("V4 LTS automatic capability releases must stay on 4.0.x")
    return f"4.0.{patch + 1}"


def promote_class_a(root: Path) -> str | None:
    quarantine = root / "AI_SKILL_LIBRARY/v4/evergreen/quarantine"
    candidates = []
    for path in sorted(quarantine.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("promotion_class") != "A" or not isinstance(data.get("skill"), dict):
            continue
        admission = admit_skill(data["skill"], existing_skills=[])
        if admission["admitted"]:
            candidates.append((path, data["skill"]))
    if not candidates:
        return None
    pointer = load_release_pointer(root)
    current = pointer["version"]
    new_version = _next_release(current)
    current_manifest = load_release_manifest(root, current)
    rows = list(current_manifest.get("files", []))
    for _, skill in candidates:
        domain = skill["domain"]
        if domain not in ALLOWED_DOMAINS:
            continue
        target = root / f"AI_SKILL_LIBRARY/v4/skills/{domain}/skills/{skill['id']}.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(yaml.safe_dump(skill, sort_keys=False), encoding="utf-8")
        rel = str(target.relative_to(root)).replace("\\", "/")
        rows = [row for row in rows if row.get("path") != rel]
        rows.append({"path": rel, "sha256": sha256_file(target), "role": f"skill:{domain}:{skill['id']}"})
    release_dir = root / f"AI_SKILL_LIBRARY/v4/releases/{new_version}"
    release_dir.mkdir(parents=True, exist_ok=False)
    manifest = {"version": new_version, "architecture": "GITHUB_BRAIN_V4", "files": rows, "compatibility": {"min_architecture": "4.0.0"}, "promotion": {"class": "A", "validated": False, "source": "evergreen_quarantine"}}
    manifest_path = release_dir / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    set_release_pointer(root, new_version, sha256_file(manifest_path))
    history_path = root / "AI_SKILL_LIBRARY/v4/releases/history.yaml"
    history = yaml.safe_load(history_path.read_text(encoding="utf-8")) or {"version": 4, "releases": []}
    history.setdefault("releases", []).append({"version": new_version, "known_good": False, "architecture": "GITHUB_BRAIN_V4", "manifest": str(manifest_path.relative_to(root)).replace("\\", "/"), "previous": current})
    history_path.write_text(yaml.safe_dump(history, sort_keys=False), encoding="utf-8")
    return new_version


def mark_known_good(root: Path) -> str:
    pointer = load_release_pointer(root)
    version = pointer["version"]
    manifest_path = root / pointer["manifest_path"]
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest.setdefault("promotion", {})["validated"] = True
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    set_release_pointer(root, version, sha256_file(manifest_path))
    history_path = root / "AI_SKILL_LIBRARY/v4/releases/history.yaml"
    history = yaml.safe_load(history_path.read_text(encoding="utf-8")) or {}
    found = False
    for row in history.get("releases", []):
        if isinstance(row, dict) and row.get("version") == version:
            row["known_good"] = True
            found = True
    if not found:
        raise ValueError("active release missing from history")
    history_path.write_text(yaml.safe_dump(history, sort_keys=False), encoding="utf-8")
    return version


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan")
    scan.add_argument("--root", default=".")
    scan.add_argument("--output", required=True)
    materialize = sub.add_parser("materialize")
    materialize.add_argument("--root", default=".")
    materialize.add_argument("--scan", required=True)
    promote = sub.add_parser("promote-class-a")
    promote.add_argument("--root", default=".")
    known = sub.add_parser("mark-known-good")
    known.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if args.command == "scan":
        scan_github(root, Path(args.output), token=os.getenv("GITHUB_TOKEN"))
    elif args.command == "materialize":
        materialize_quarantine(root, Path(args.scan))
    elif args.command == "promote-class-a":
        version = promote_class_a(root)
        print(version or "NO_PROMOTABLE_CLASS_A")
    elif args.command == "mark-known-good":
        print(mark_known_good(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
