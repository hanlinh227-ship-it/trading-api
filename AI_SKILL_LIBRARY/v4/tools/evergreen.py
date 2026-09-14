from __future__ import annotations

import argparse
import base64
import hashlib
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
FORBIDDEN_FAILURE_FIELDS = {
    "chain_of_thought",
    "hidden_reasoning",
    "secrets",
    "credentials",
    "private_tool_payload",
    "raw_private_prompt",
}
FAILURE_REQUIRED_FIELDS = (
    "failure_id",
    "domain",
    "failure_class",
    "observable_symptom",
    "expected_outcome",
    "evidence_ref",
    "timestamp",
)


def lifecycle_decision(*, promotion_class: str, gates: dict[str, bool], protected_regressions: list[str]) -> str:
    if promotion_class == "D":
        return "manual_authorization_required"
    if promotion_class not in {"A", "B", "C"}:
        return "reject"
    if protected_regressions:
        return "reject"
    if any(gates.get(name) is not True for name in REQUIRED_GATES):
        return "reject"
    if promotion_class == "C":
        return "manual_authorization_required"
    return "promote"


def next_patch_version(version: str) -> str:
    parts = str(version).split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError("version must be semantic x.y.z")
    major, minor, patch = (int(part) for part in parts)
    if major != 4:
        raise ValueError("Evergreen automatic releases must remain on Brain V4")
    return f"{major}.{minor}.{patch + 1}"


def source_lifecycle(
    *,
    now: datetime,
    last_verified: datetime,
    stale_after_hours: float,
    deprecated: bool = False,
    archived: bool = False,
    reverify: bool = False,
) -> str:
    if archived:
        return "archived"
    if deprecated:
        return "deprecated"
    if reverify:
        return "reverify"
    if not isinstance(now, datetime) or not isinstance(last_verified, datetime):
        raise TypeError("now and last_verified must be datetime values")
    if now.tzinfo is None or last_verified.tzinfo is None:
        raise ValueError("source lifecycle datetimes must be timezone-aware")
    if stale_after_hours <= 0:
        raise ValueError("stale_after_hours must be positive")
    elapsed_hours = (now - last_verified).total_seconds() / 3600.0
    if elapsed_hours < 0:
        raise ValueError("last_verified cannot be in the future")
    return "stale" if elapsed_hours >= float(stale_after_hours) else "active"


def _bounded_severity(value: object) -> int:
    try:
        severity = int(value)
    except (TypeError, ValueError):
        severity = 1
    return max(1, min(5, severity))


def detect_gaps(evidence: list[dict]) -> list[dict]:
    gaps: list[dict] = []
    for row in evidence:
        if not isinstance(row, dict):
            continue
        domain = str(row.get("domain") or "").strip()
        signal_type = str(row.get("signal_type") or "").strip()
        evidence_ref = str(row.get("evidence_ref") or "").strip()
        created_at = str(row.get("created_at") or "").strip()
        if not domain or not signal_type or not evidence_ref or not created_at:
            continue
        digest = hashlib.sha256(f"{domain}|{signal_type}|{evidence_ref}".encode("utf-8")).hexdigest()[:12]
        gaps.append(
            {
                "gap_id": f"gap:{digest}",
                "domain": domain,
                "signal_type": signal_type,
                "severity": _bounded_severity(row.get("severity")),
                "evidence_refs": [evidence_ref],
                "recommended_capability": str(row.get("recommended_capability") or signal_type).strip(),
                "created_at": created_at,
            }
        )
    gaps.sort(key=lambda item: (-item["severity"], item["gap_id"]))
    return gaps


def failure_to_regression(failure: dict) -> dict:
    if not isinstance(failure, dict):
        raise TypeError("failure must be a mapping")
    sensitive = FORBIDDEN_FAILURE_FIELDS.intersection(failure)
    if sensitive:
        raise ValueError("failure contains forbidden sensitive fields: " + ", ".join(sorted(sensitive)))
    missing = [name for name in FAILURE_REQUIRED_FIELDS if not str(failure.get(name) or "").strip()]
    if missing:
        raise ValueError("failure evidence is incomplete: " + ", ".join(missing))
    failure_id = str(failure["failure_id"]).strip()
    return {
        "regression_id": f"regression:{failure_id}",
        "source_failure_id": failure_id,
        "domain": str(failure["domain"]).strip(),
        "failure_class": str(failure["failure_class"]).strip(),
        "observable_symptom": str(failure["observable_symptom"]).strip(),
        "expected_outcome": str(failure["expected_outcome"]).strip(),
        "evidence_ref": str(failure["evidence_ref"]).strip(),
        "timestamp": str(failure["timestamp"]).strip(),
        "state": "candidate_regression",
        "verified": True,
    }


def _finite_number(mapping: dict, key: str) -> float | None:
    value = mapping.get(key)
    if isinstance(value, bool):
        return None
    if not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number != number or number in {float("inf"), float("-inf")}:
        return None
    return number


def compare_candidate(baseline: dict, candidate: dict, policy: dict) -> str:
    if not isinstance(baseline, dict) or not isinstance(candidate, dict) or not isinstance(policy, dict):
        return "hold"
    if candidate.get("permission_expansion") is True or candidate.get("authority_expansion") is True:
        return "manual_authorization_required"

    protected = policy.get("protected_dimensions", [])
    if not isinstance(protected, list) or not protected:
        return "hold"
    required_metrics = ["quality", "latency", "cost", *protected]
    baseline_values: dict[str, float] = {}
    candidate_values: dict[str, float] = {}
    for key in required_metrics:
        before = _finite_number(baseline, key)
        after = _finite_number(candidate, key)
        if before is None or after is None:
            return "hold"
        baseline_values[key] = before
        candidate_values[key] = after

    for key in protected:
        if candidate_values[key] < baseline_values[key]:
            return "reject"

    max_latency = _finite_number(policy, "max_relative_latency_regression")
    max_cost = _finite_number(policy, "max_relative_cost_regression")
    min_gain = _finite_number(policy, "min_primary_quality_gain")
    if max_latency is None or max_cost is None or min_gain is None:
        return "hold"
    if baseline_values["latency"] <= 0 or baseline_values["cost"] <= 0:
        return "hold"
    latency_regression = (candidate_values["latency"] - baseline_values["latency"]) / baseline_values["latency"]
    cost_regression = (candidate_values["cost"] - baseline_values["cost"]) / baseline_values["cost"]
    if latency_regression > max_latency or cost_regression > max_cost:
        return "reject"
    if candidate_values["quality"] - baseline_values["quality"] + 1e-12 < min_gain:
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
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "state": "quarantine_scan",
        "routing_authority": False,
        "candidates": [],
        "errors": [],
    }
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
    new_version = next_patch_version(current)
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
    manifest = {
        "version": new_version,
        "architecture": "GITHUB_BRAIN_V4",
        "files": rows,
        "compatibility": {"min_architecture": "4.0.0"},
        "promotion": {"class": "A", "validated": False, "source": "evergreen_quarantine"},
    }
    manifest_path = release_dir / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    set_release_pointer(root, new_version, sha256_file(manifest_path))
    history_path = root / "AI_SKILL_LIBRARY/v4/releases/history.yaml"
    history = yaml.safe_load(history_path.read_text(encoding="utf-8")) or {"version": 4, "releases": []}
    history.setdefault("releases", []).append(
        {
            "version": new_version,
            "known_good": False,
            "architecture": "GITHUB_BRAIN_V4",
            "manifest": str(manifest_path.relative_to(root)).replace("\\", "/"),
            "previous": current,
        }
    )
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


def intelligence_audit(root: Path) -> dict:
    pointer = load_release_pointer(root)
    quarantine = root / "AI_SKILL_LIBRARY/v4/evergreen/quarantine"
    contract_path = root / "AI_SKILL_LIBRARY/v4/stable/continuous_intelligence.yaml"
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8")) if contract_path.is_file() else {}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "release": pointer.get("version"),
        "manifest_path": pointer.get("manifest_path"),
        "quarantine_count": len(list(quarantine.glob("*.yaml"))) if quarantine.is_dir() else 0,
        "mode": contract.get("mode") if isinstance(contract, dict) else None,
        "stable_request_dependency": contract.get("stable_request_dependency") if isinstance(contract, dict) else None,
        "class_c_unattended": bool((contract.get("autonomous_promotion") or {}).get("C")) if isinstance(contract, dict) else None,
        "class_d_unattended": bool((contract.get("autonomous_promotion") or {}).get("D")) if isinstance(contract, dict) else None,
    }


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
    audit = sub.add_parser("audit")
    audit.add_argument("--root", default=".")
    audit.add_argument("--output", required=True)
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
    elif args.command == "audit":
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(intelligence_audit(root), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
