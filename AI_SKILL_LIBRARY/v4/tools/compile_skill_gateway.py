from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
LIB = ROOT / "AI_SKILL_LIBRARY"
V4 = LIB / "v4"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def _yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected YAML mapping: {path}")
    return data


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _norm(text: object) -> str:
    value = unicodedata.normalize("NFKC", str(text or "")).casefold()
    return " ".join(value.split())


def _term(value: object, *, where: str) -> str:
    """Normalize a routing term and reject terms whose casefold differs from lower().

    The Cloudflare runtime lowercases with toLocaleLowerCase('und'); the compiler uses
    casefold(). Terms where the two differ (e.g. containing U+00DF) would be present in
    the snapshot but could never match at runtime, so they are rejected at compile time.
    """
    normalized = _norm(value)
    runtime_form = " ".join(unicodedata.normalize("NFKC", str(value or "")).lower().split())
    if normalized and normalized != runtime_form:
        raise ValueError(f"routing term is not lowercase-stable ({where}): {value!r}")
    return normalized


def _canonical_hash(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _domain_manifests(root: Path) -> tuple[dict[str, dict], dict[str, str]]:
    base = root / "AI_SKILL_LIBRARY/v4/skills"
    manifests: dict[str, dict] = {}
    hashes: dict[str, str] = {}
    for path in sorted(base.glob("*/manifest.yaml")):
        row = _yaml(path)
        domain = str(row.get("id") or row.get("domain") or "").strip()
        if not domain:
            raise ValueError(f"domain manifest missing id: {path}")
        if domain in manifests:
            raise ValueError(f"duplicate domain manifest: {domain}")
        manifests[domain] = row
        hashes[domain] = _sha(path)
    if not manifests:
        raise ValueError("no V4 domain manifests found")
    return manifests, hashes


def compile_snapshot(root: Path = ROOT, source_sha: str = "", generated_at: str | None = None) -> dict:
    root = Path(root).resolve()
    source_sha = str(source_sha).strip().lower()
    if not SHA_RE.fullmatch(source_sha):
        raise ValueError("source_sha must be exactly 40 lowercase hex characters")

    checkpoint_path = root / "AI_SKILL_LIBRARY/checkpoint.json"
    pointer_path = root / "AI_SKILL_LIBRARY/v4/releases/current.json"
    router_path = root / "AI_SKILL_LIBRARY/v4/stable/router.yaml"
    runtime_path = root / "AI_SKILL_LIBRARY/v4/stable/runtime.yaml"
    registry_path = root / "AI_SKILL_LIBRARY/skills/registry/index.yaml"
    catalog_path = root / "AI_SKILL_LIBRARY/skills/catalog.yaml"
    security_path = root / "AI_SKILL_LIBRARY/v4/stable/security.yaml"
    authority_path = root / "AI_SKILL_LIBRARY/projects.yaml"
    aliases_path = root / "AI_SKILL_LIBRARY/v4/runtime/routing_aliases.yaml"

    checkpoint = _json(checkpoint_path)
    pointer = _json(pointer_path)
    router = _yaml(router_path)
    runtime = _yaml(runtime_path)
    registry = _yaml(registry_path)
    catalog = _yaml(catalog_path)
    aliases_data = _yaml(aliases_path)
    manifests, manifest_hashes = _domain_manifests(root)

    release_version = str(pointer.get("version") or "").strip()
    release_manifest_path = root / str(pointer.get("manifest_path") or "")
    if not release_version or not release_manifest_path.is_file():
        raise ValueError("active release pointer is invalid")

    skills_rows = catalog.get("skills", [])
    if not isinstance(skills_rows, list):
        raise ValueError("skill catalog skills must be a list")
    catalog_by_id: dict[str, dict] = {}
    for row in skills_rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError("invalid skill catalog row")
        sid = row["id"]
        if sid in catalog_by_id:
            raise ValueError(f"duplicate skill id: {sid}")
        catalog_by_id[sid] = row

    # Alias rows never become primary skills; their triggers fold into the canonical skill.
    skill_aliases: dict[str, str] = {}
    for sid, row in catalog_by_id.items():
        target = row.get("alias_of")
        if target is None:
            continue
        if not isinstance(target, str) or target not in catalog_by_id:
            raise ValueError(f"skill {sid} alias_of unknown skill {target!r}")
        if catalog_by_id[target].get("alias_of"):
            raise ValueError(f"skill {sid} aliases another alias {target}")
        skill_aliases[sid] = target

    domain_routes = router.get("domain_routes", {})
    if not isinstance(domain_routes, dict):
        raise ValueError("stable router domain_routes must be a mapping")
    skill_domain: dict[str, str] = {}
    normalized_domains: dict[str, list[str]] = {}
    for domain, ids in domain_routes.items():
        if not isinstance(ids, list):
            raise ValueError(f"domain route must be a list: {domain}")
        domain = str(domain)
        if domain not in manifests:
            raise ValueError(f"stable router references domain without V4 manifest: {domain}")
        normalized_domains[domain] = []
        for sid in ids:
            sid = str(sid)
            if sid == "task_router":
                continue
            if sid not in catalog_by_id:
                raise ValueError(f"domain {domain} references unknown skill {sid}")
            if sid in skill_aliases:
                raise ValueError(f"domain {domain} routes alias skill {sid}; route {skill_aliases[sid]} instead")
            if sid in skill_domain and skill_domain[sid] != domain:
                raise ValueError(f"skill {sid} appears in multiple primary domains")
            skill_domain[sid] = domain
            normalized_domains[domain].append(sid)

    if "task_router" not in catalog_by_id:
        raise ValueError("task_router missing from canonical catalog")
    # Infrastructure skill receives a capsule but is never a primary candidate.
    skill_domain["task_router"] = "core"
    selectable_ids = set(skill_domain)

    alias_rows = aliases_data.get("aliases", {})
    if not isinstance(alias_rows, dict):
        raise ValueError("routing aliases must be a mapping")
    for sid in alias_rows:
        if sid not in catalog_by_id:
            raise ValueError(f"routing alias references unknown skill: {sid}")
        if sid not in selectable_ids and sid not in skill_aliases:
            raise ValueError(f"routing alias references non-routable skill: {sid}")

    normalized_aliases: dict[str, list[str]] = {
        sid: sorted({_term(value, where=f"alias:{sid}") for value in values if _norm(value)})
        for sid, values in alias_rows.items()
        if isinstance(values, list)
    }
    for alias_id, target in skill_aliases.items():
        if target not in selectable_ids:
            raise ValueError(f"alias {alias_id} targets non-routable skill {target}")
        manifest_aliases = {str(v) for v in manifests[skill_domain[target]].get("legacy_aliases", [])}
        if alias_id not in manifest_aliases:
            raise ValueError(f"domain manifest {skill_domain[target]} does not declare legacy alias {alias_id}")
        folded = set(normalized_aliases.get(target, []))
        folded.update(_term(v, where=f"trigger:{alias_id}") for v in catalog_by_id[alias_id].get("triggers", []) if _norm(v))
        folded.update(normalized_aliases.get(alias_id, []))
        normalized_aliases[target] = sorted(folded)
        normalized_aliases.pop(alias_id, None)

    skills: dict[str, dict] = {}
    capsules: dict[str, dict] = {}
    for sid in sorted(selectable_ids):
        row = catalog_by_id[sid]
        domain = skill_domain[sid]
        manifest = manifests.get(domain)
        if manifest is None:
            raise ValueError(f"missing V4 manifest for domain {domain} (skill {sid})")
        manifest_skills = {str(value) for value in manifest.get("skills", [])}
        if sid not in manifest_skills:
            raise ValueError(f"domain manifest {domain} does not declare skill {sid}")

        meta = {
            "id": sid,
            "domain": domain,
            "triggers": sorted({_term(value, where=f"trigger:{sid}") for value in row.get("triggers", []) if _norm(value)}),
            "aliases": normalized_aliases.get(sid, []),
            "excludes": sorted({_term(value, where=f"exclude:{sid}") for value in row.get("excludes", []) if _norm(value)}),
            "priority": int(row.get("priority", 0)),
            "requires": sorted(str(value) for value in row.get("requires", [])),
            "conflicts_with": sorted(str(value) for value in row.get("conflicts_with", [])),
            "tools": sorted(str(value) for value in row.get("tools", [])),
            "sources": sorted(str(value) for value in row.get("sources", [])),
            "output_contract": str(row.get("output_contract") or "").strip(),
            "primary_selectable": sid != "task_router",
        }
        if not meta["output_contract"]:
            raise ValueError(f"skill {sid} has empty output_contract")
        skills[sid] = meta

        capsule = {
            "skill_id": sid,
            "domain": domain,
            "output_contract": meta["output_contract"],
            "requires": meta["requires"],
            "excludes": meta["excludes"],
            "conflicts_with": meta["conflicts_with"],
            "permissions": sorted(str(value) for value in manifest.get("permissions", [])),
            "risk_ceiling": str(manifest.get("risk_ceiling") or "read_only"),
            "evals": sorted(str(value) for value in manifest.get("evals", [])),
            "tools": meta["tools"],
            "sources": meta["sources"],
        }
        capsule["capsule_hash"] = _canonical_hash(capsule)
        capsules[sid] = capsule

    trigger_owner: dict[str, str] = {}
    for sid, meta in skills.items():
        if not meta["primary_selectable"]:
            continue
        for term in meta["triggers"]:
            if term in trigger_owner:
                raise ValueError(f"ambiguous trigger {term!r}: owned by {trigger_owner[term]} and {sid}")
            trigger_owner[term] = sid
    # A folded/declared alias term never competes with another skill's trigger: the trigger owner wins.
    alias_owner: dict[str, str] = {}
    for sid in sorted(skills):
        meta = skills[sid]
        if not meta["primary_selectable"]:
            continue
        kept = [term for term in meta["aliases"] if trigger_owner.get(term, sid) == sid]
        for term in kept:
            if term in alias_owner and alias_owner[term] != sid:
                raise ValueError(f"ambiguous alias {term!r}: owned by {alias_owner[term]} and {sid}")
            alias_owner[term] = sid
        meta["aliases"] = kept
        normalized_aliases[sid] = kept

    fallback = str(router.get("policy", {}).get("fallback_primary_skill") or "")
    if fallback != "core_reasoning" or fallback not in skills:
        raise ValueError("fallback primary skill must be core_reasoning")

    profiles = runtime.get("profiles", {})
    if not isinstance(profiles, dict):
        raise ValueError("runtime profiles must be a mapping")
    profile_snapshot = {
        name: {
            "primary_skill_count": int(row.get("primary_skill_count", 0)),
            "skill_capsule_required": bool(row.get("skill_capsule_required")),
            "max_supporting_skills": int(row.get("max_supporting_skills", 0)),
            "tool_candidates": int(row.get("tool_candidates", 0)),
            "durable_memory_items": int(row.get("durable_memory_items", 0)),
            "max_bridge_nodes": int(row.get("max_bridge_nodes", 0)),
        }
        for name, row in profiles.items()
        if isinstance(row, dict)
    }

    escalation = aliases_data.get("profile_escalation", {})
    profile_escalation = {
        str(name): sorted({_norm(value) for value in values if _norm(value)})
        for name, values in escalation.items()
        if isinstance(values, list)
    } if isinstance(escalation, dict) else {}
    fresh_state_terms = sorted({_norm(value) for value in aliases_data.get("fresh_state_terms", []) if _norm(value)})

    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "schema_version": 1,
        "source_sha": source_sha,
        "release_id": release_version,
        "generated_at": generated_at,
        "fallback_primary_skill": fallback,
        "profiles": profile_snapshot,
        "domains": normalized_domains,
        "skills": skills,
        "capsules": capsules,
        "routing_aliases": normalized_aliases,
        "skill_aliases": dict(sorted(skill_aliases.items())),
        "profile_escalation": profile_escalation,
        "fresh_state_terms": fresh_state_terms,
        "hashes": {
            "checkpoint": _sha(checkpoint_path),
            "release_manifest": _sha(release_manifest_path),
            "router": _sha(router_path),
            "runtime": _sha(runtime_path),
            "registry_index": _sha(registry_path),
            "skill_catalog": _sha(catalog_path),
            "security": _sha(security_path),
            "authority": _sha(authority_path),
            "routing_aliases": _sha(aliases_path),
            "domain_manifests": manifest_hashes,
        },
        "checkpoint_id": checkpoint.get("checkpoint_id"),
        "registry_version": registry.get("version"),
    }


def write_snapshot(root: Path, source_sha: str, output: Path) -> Path:
    snapshot = compile_snapshot(root, source_sha)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()
    write_snapshot(Path(args.root), args.source_sha, Path(args.output))
    print(f"SKILL_GATEWAY_SNAPSHOT=PASS source_sha={args.source_sha} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
