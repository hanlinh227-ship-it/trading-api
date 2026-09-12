"""Build the tiered (HOT / WARM / COLD) metadata retrieval index for GITHUB_BRAIN_V4.

The index is a deterministic function of the repository. It contains pointers and
metadata only — never authority, never runtime state, never secrets. FAST requests use
exact lookups against HOT entries; WARM/COLD are loaded only by STANDARD/DEEP and only
after routing. CI fails when the committed index is stale (see test_v4_consolidation).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
INDEX_REL = "AI_SKILL_LIBRARY/v4/index/retrieval_index.yaml"
MAX_HOT = 200

HOT_STATIC: tuple[tuple[str, str, str, list[str]], ...] = (
    # path, source_type, authority_level, tags
    ("AGENTS.md", "brain_entrypoint", "canonical", ["bootstrap", "entrypoint"]),
    ("CLAUDE.md", "brain_entrypoint", "canonical", ["bootstrap", "entrypoint"]),
    ("AI_SKILL_LIBRARY/checkpoint.json", "checkpoint", "canonical", ["discovery_root", "bootstrap"]),
    ("AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md", "global_checkpoint", "canonical", ["runtime_state", "deployment_contract"]),
    ("AI_SKILL_LIBRARY/GITHUB_BRAIN_V4.md", "brain_authority", "canonical", ["authority", "v4"]),
    ("AI_SKILL_LIBRARY/v4/releases/current.json", "release_pointer", "canonical", ["release", "pointer"]),
    ("AI_SKILL_LIBRARY/v4/stable/router.yaml", "stable_router", "canonical", ["router", "domain_routes"]),
    ("AI_SKILL_LIBRARY/v4/stable/runtime.yaml", "stable_runtime", "canonical", ["profiles", "fast", "standard", "deep"]),
    ("AI_SKILL_LIBRARY/v4/stable/budgets.yaml", "budgets", "canonical", ["budgets", "performance"]),
    ("AI_SKILL_LIBRARY/v4/stable/retrieval.yaml", "retrieval", "canonical", ["retrieval", "index", "tiers"]),
    ("AI_SKILL_LIBRARY/v4/stable/security.yaml", "stable_security", "canonical", ["security", "risk"]),
    ("AI_SKILL_LIBRARY/v4/stable/kernel.yaml", "stable_kernel", "canonical", ["kernel", "planes"]),
    ("AI_SKILL_LIBRARY/v4/runtime/routing_aliases.yaml", "routing_aliases", "canonical", ["aliases", "vietnamese"]),
    ("AI_SKILL_LIBRARY/skills/registry/index.yaml", "registry_index", "canonical", ["registry", "discovery"]),
    ("AI_SKILL_LIBRARY/projects.yaml", "project_registry", "canonical", ["projects", "authority_pointers"]),
    ("AI_SKILL_LIBRARY/v4/index/workspace_map.yaml", "workspace_map", "canonical", ["workspace", "layout"]),
)

WARM_STATIC: tuple[tuple[str, str, str, list[str]], ...] = (
    ("AI_SKILL_LIBRARY/v4/stable/context.yaml", "supporting_policy", "supporting", ["context", "cache"]),
    ("AI_SKILL_LIBRARY/v4/stable/memory.yaml", "supporting_policy", "supporting", ["memory"]),
    ("AI_SKILL_LIBRARY/v4/stable/evidence.yaml", "supporting_policy", "supporting", ["evidence", "precedence"]),
    ("AI_SKILL_LIBRARY/v4/stable/harmonization.yaml", "supporting_policy", "supporting", ["harmonization", "dedupe"]),
    ("AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml", "supporting_policy", "supporting", ["capability_fusion"]),
    ("AI_SKILL_LIBRARY/v4/stable/creative_visual_fusion.yaml", "supporting_policy", "supporting", ["creative", "visual"]),
    ("AI_SKILL_LIBRARY/v4/stable/reliability.yaml", "supporting_policy", "supporting", ["reliability"]),
    ("AI_SKILL_LIBRARY/v4/stable/observability.yaml", "supporting_policy", "supporting", ["observability"]),
    ("AI_SKILL_LIBRARY/v4/stable/reputation.yaml", "supporting_policy", "supporting", ["reputation", "provider"]),
    ("AI_SKILL_LIBRARY/v4/mesh/graph.yaml", "mesh", "supporting", ["mesh", "domains"]),
    ("AI_SKILL_LIBRARY/v4/mesh/bridges.yaml", "bridge", "supporting", ["mesh", "bridges"]),
    ("AI_SKILL_LIBRARY/v4/evergreen/policy.yaml", "evergreen_policy", "supporting", ["evergreen"]),
    ("AI_SKILL_LIBRARY/v4/evergreen/discovery.yaml", "evergreen_policy", "supporting", ["evergreen", "discovery"]),
    ("AI_SKILL_LIBRARY/v4/evergreen/promotion.yaml", "evergreen_policy", "supporting", ["evergreen", "promotion"]),
    ("AI_SKILL_LIBRARY/evals.yaml", "evals", "supporting", ["evals"]),
    ("AI_SKILL_LIBRARY/skills/catalog.yaml", "skill_catalog", "supporting", ["catalog"]),
    ("AI_SKILL_LIBRARY/skills/registry/conflict_policy.yaml", "conflict_policy", "supporting", ["conflict", "provider"]),
    ("AI_SKILL_LIBRARY/skills/registry/runtime_policy.yaml", "runtime_policy", "supporting", ["cloud_runtime"]),
    ("AI_SKILL_LIBRARY/skills/registry/live_price_policy.yaml", "live_price_policy", "supporting", ["live_price", "trading"]),
    ("AI_SKILL_LIBRARY/skills/providers/crypto_agents.yaml", "provider_registry", "reference", ["provider", "crypto"]),
    ("AI_SKILL_LIBRARY/sources/crypto_agent_official.yaml", "provider_registry", "reference", ["provider", "crypto", "sources"]),
    ("AI_SKILL_LIBRARY/plugins.yaml", "plugin_registry", "reference", ["plugins", "tools"]),
    ("AI_SKILL_LIBRARY/runtime/cloud_runtime.yaml", "runtime_manifest", "supporting", ["cloud_runtime", "zero_local"]),
    ("AI_SKILL_LIBRARY/v4/skills/legacy_catalog_adapter.yaml", "adapter", "supporting", ["adapter", "legacy"]),
)

COLD_STATIC: tuple[tuple[str, str, str, list[str]], ...] = (
    ("AI_SKILL_LIBRARY/GITHUB_BRAIN_V3.md", "legacy_checkpoint", "compatibility", ["alias", "v3"]),
    ("AI_SKILL_LIBRARY/GITHUB_BRAIN_V2.md", "legacy_checkpoint", "compatibility", ["alias", "v2"]),
    ("AI_SKILL_LIBRARY/GITHUB_BRAIN_V1.md", "legacy_checkpoint", "compatibility", ["alias", "v1"]),
    ("AI_SKILL_LIBRARY/CORE_PROTOCOL.md", "legacy_checkpoint", "compatibility", ["protocol", "v3"]),
    ("AI_SKILL_LIBRARY/bootstrap.yaml", "legacy_control_plane", "compatibility", ["bootstrap", "v3"]),
    ("AI_SKILL_LIBRARY/kernel.yaml", "legacy_control_plane", "compatibility", ["kernel", "v3"]),
    ("AI_SKILL_LIBRARY/router.yaml", "legacy_control_plane", "compatibility", ["router", "v2"]),
    ("AI_SKILL_LIBRARY/runtime.yaml", "legacy_control_plane", "compatibility", ["runtime"]),
    ("AI_SKILL_LIBRARY/context.yaml", "legacy_control_plane", "compatibility", ["context"]),
    ("AI_SKILL_LIBRARY/reliability.yaml", "legacy_control_plane", "compatibility", ["reliability"]),
    ("AI_SKILL_LIBRARY/evidence.yaml", "legacy_control_plane", "compatibility", ["evidence"]),
    ("AI_SKILL_LIBRARY/memory.yaml", "legacy_control_plane", "compatibility", ["memory"]),
    ("AI_SKILL_LIBRARY/observability.yaml", "legacy_control_plane", "compatibility", ["observability"]),
    ("AI_SKILL_LIBRARY/security.yaml", "legacy_control_plane", "compatibility", ["security"]),
    ("AI_SKILL_LIBRARY/migration.yaml", "legacy_control_plane", "compatibility", ["migration", "v3"]),
    ("AI_SKILL_LIBRARY/orchestration.yaml", "legacy_control_plane", "compatibility", ["orchestration"]),
    ("CHECKPOINTS", "out_of_scope_checkpoint_dir", "none", ["kaggriculture", "not_brain", "not_trading"]),
)

TRADING_SKILL_RISK = "project_policy"


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _entry(**kw) -> dict:
    base = {
        "id": "", "domain": "core", "skill_id": None, "project_scope": "ai_brain", "authority_level": "supporting",
        "risk_class": "read_only", "freshness": "current", "source_type": "", "release_version": None, "checkpoint": "GITHUB_BRAIN_V4",
        "provider": None, "tool": None, "tags": [], "aliases": [], "tier": "WARM", "path": "", "preload": "routed",
    }
    base.update(kw)
    base["tags"] = sorted(set(base["tags"]))
    base["aliases"] = sorted(set(base["aliases"]))
    return base


def build_index(root: Path = ROOT) -> dict:
    root = Path(root).resolve()
    lib = root / "AI_SKILL_LIBRARY"
    checkpoint = json.loads((lib / "checkpoint.json").read_text(encoding="utf-8"))
    pointer = json.loads((lib / "v4/releases/current.json").read_text(encoding="utf-8"))
    release = str(pointer["version"])
    catalog = _yaml(lib / "skills/catalog.yaml")
    router = _yaml(lib / "v4/stable/router.yaml")
    projects = _yaml(lib / "projects.yaml")
    sources = _yaml(lib / "sources.yaml")
    history = _yaml(lib / "v4/releases/history.yaml")
    routing_aliases = _yaml(lib / "v4/runtime/routing_aliases.yaml").get("aliases", {})

    entries: list[dict] = []

    def static(rows, tier, preload):
        for rel, source_type, authority, tags in rows:
            scope = "trading" if "trading" in tags else "ai_brain"
            entries.append(_entry(
                id=f"{tier.lower()}:{rel}", domain="core", project_scope=scope, authority_level=authority,
                risk_class="read_only", freshness="current" if tier != "COLD" else "historical", source_type=source_type,
                release_version=release if tier == "HOT" else None, tags=tags, tier=tier, path=rel, preload=preload,
            ))

    static(HOT_STATIC, "HOT", "bootstrap")
    static(WARM_STATIC, "WARM", "routed")
    static(COLD_STATIC, "COLD", "explicit")

    # Current release manifest is HOT; historical manifests are COLD.
    entries.append(_entry(id=f"hot:{pointer['manifest_path']}", authority_level="canonical", source_type="release_manifest",
                          release_version=release, tags=["release", "manifest", "current"], tier="HOT", path=pointer["manifest_path"], preload="bootstrap"))
    for row in history.get("releases", []):
        if row.get("version") == release:
            continue
        entries.append(_entry(id=f"cold:release:{row['version']}", authority_level="historical", freshness="historical",
                              source_type="historical_release", release_version=str(row["version"]), tags=["release", "historical"],
                              tier="COLD", path=row["manifest"], preload="explicit"))

    # Skills: canonical rows are HOT (routing metadata); alias rows resolve to canonical.
    skill_domain: dict[str, str] = {}
    for domain, ids in router.get("domain_routes", {}).items():
        for sid in ids:
            skill_domain[str(sid)] = str(domain)
    rows = {row["id"]: row for row in catalog.get("skills", [])}
    reverse_aliases: dict[str, list[str]] = {}
    for sid, row in rows.items():
        target = row.get("alias_of")
        if target:
            reverse_aliases.setdefault(target, []).append(sid)
    skill_md = {p.stem: p for p in (lib / "skills").glob("*/*.md")}
    for sid in sorted(rows):
        row = rows[sid]
        if row.get("alias_of"):
            continue
        domain = skill_domain.get(sid, "core")
        # Alias ids only: trigger/alias *terms* already live in the HOT routing snapshot.
        aliases = list(reverse_aliases.get(sid, []))
        entries.append(_entry(
            id=f"skill:{sid}", domain=domain, skill_id=sid, project_scope="trading" if domain == "trading" else "ai_brain",
            authority_level="canonical" if sid != "task_router" else "infrastructure",
            risk_class=TRADING_SKILL_RISK if domain == "trading" else "read_only", source_type="canonical_skill",
            release_version=release, tool=",".join(sorted(str(t) for t in row.get("tools", []))) or None,
            tags=[domain, "skill"], aliases=aliases, tier="HOT",
            path="AI_SKILL_LIBRARY/skills/catalog.yaml", preload="bootstrap",
        ))
        md = skill_md.get(sid)
        if md is not None:
            entries.append(_entry(
                id=f"skill_text:{sid}", domain=domain, skill_id=sid, project_scope="trading" if domain == "trading" else "ai_brain",
                authority_level="supporting", risk_class=TRADING_SKILL_RISK if domain == "trading" else "read_only",
                source_type="skill_reasoning_text", tags=[domain, "skill_text"], tier="WARM",
                path=md.relative_to(root).as_posix(), preload="routed",
            ))
    for alias_id in sorted(a for a in rows if rows[a].get("alias_of")):
        md = skill_md.get(alias_id)
        if md is not None:
            target = rows[alias_id]["alias_of"]
            entries.append(_entry(
                id=f"skill_text:{alias_id}", domain=skill_domain.get(target, "core"), skill_id=target, authority_level="supporting",
                source_type="skill_reasoning_text", tags=["skill_text", "legacy_alias"], aliases=[alias_id], tier="WARM",
                path=md.relative_to(root).as_posix(), preload="routed",
            ))

    # Domain packs and mesh domain files.
    for path in sorted((lib / "v4/skills").glob("*/manifest.yaml")):
        domain = path.parent.name
        entries.append(_entry(id=f"domain_pack:{domain}", domain=domain, project_scope="trading" if domain == "trading" else "ai_brain",
                              authority_level="supporting", risk_class=TRADING_SKILL_RISK if domain == "trading" else "read_only",
                              source_type="domain_pack", tags=[domain, "manifest"], tier="WARM", path=path.relative_to(root).as_posix()))
    for path in sorted((lib / "v4/mesh/domains").glob("*.yaml")):
        domain = path.stem
        entries.append(_entry(id=f"mesh_domain:{domain}", domain=domain, project_scope="trading" if domain == "trading" else "ai_brain",
                              authority_level="supporting", source_type="mesh_domain", tags=[domain, "mesh"], tier="WARM",
                              path=path.relative_to(root).as_posix()))

    # Project authorities (loaded only when routed to that project).
    for project in projects.get("projects", []):
        pid = str(project["id"])
        for key in ("authority", "canonical_checkpoint"):
            rel = project.get(key)
            if not rel:
                continue
            entries.append(_entry(
                id=f"project:{pid}:{key}", domain="trading" if pid == "trading" else "core", project_scope=pid,
                authority_level="project", risk_class=TRADING_SKILL_RISK if pid == "trading" else "read_only",
                source_type="project_authority_pointer", checkpoint=project.get("authority_token", "GITHUB_BRAIN_V4"),
                tags=[pid, key, "project_authority"], tier="HOT", path=str(rel), preload="routed",
            ))
    # Historical trading checkpoints are indexed as one COLD directory pointer (not per file) so that routine
    # trading handoffs never make the Brain index stale or block a Brain deploy.
    entries.append(_entry(id="cold:docs/checkpoints", domain="trading", project_scope="trading", authority_level="historical",
                          risk_class=TRADING_SKILL_RISK, freshness="historical", source_type="legacy_checkpoint",
                          checkpoint="retired_unless_pointed_by_projects_yaml", tags=["trading", "historical_checkpoint"],
                          tier="COLD", path="docs/checkpoints", preload="explicit"))

    # Upstream sources are reference material only.
    for row in sources.get("sources", []):
        repo = str(row.get("repo"))
        tier = str(row.get("tier") or sources.get("policy", {}).get("default_tier", "WARM"))
        entries.append(_entry(
            id=f"source:{repo}", domain=str(row.get("category")), authority_level="reference", risk_class="read_only",
            freshness="reference", source_type="upstream_source", provider=repo, tags=[str(row.get("category")), str(row.get("usage_tier"))],
            tier=tier if tier in {"WARM", "COLD"} else "WARM", path="AI_SKILL_LIBRARY/sources.yaml", preload="routed",
        ))

    # Audit / archive records.
    for path in sorted((lib / "v4/audit").glob("*.md")):
        rel = path.relative_to(root).as_posix()
        entries.append(_entry(id=f"cold:{rel}", authority_level="historical", freshness="historical", source_type="audit_record",
                              tags=["audit"], tier="COLD", path=rel, preload="explicit"))
    archive = root / ".github/workflows-archive"
    if archive.is_dir():
        entries.append(_entry(id="cold:.github/workflows-archive", authority_level="none", freshness="historical",
                              source_type="archived_workflow", tags=["ci", "archived", "retired"], tier="COLD",
                              path=".github/workflows-archive", preload="explicit"))

    entries.sort(key=lambda e: (("HOT", "WARM", "COLD").index(e["tier"]), e["id"]))
    hot = sum(1 for e in entries if e["tier"] == "HOT")
    if hot > MAX_HOT:
        raise ValueError(f"HOT tier exceeds {MAX_HOT} entries ({hot})")
    return {
        "version": 1,
        "checkpoint_id": checkpoint.get("checkpoint_id"),
        "release_version": release,
        "policy": {
            "authority": False,
            "exact_before_semantic": True,
            "fast_tiers": ["HOT"],
            "entries_are_pointers_not_content": True,
            "contract": "AI_SKILL_LIBRARY/v4/stable/retrieval.yaml",
            "builder": "AI_SKILL_LIBRARY/v4/tools/build_retrieval_index.py",
        },
        "limits": {"max_hot_entries": MAX_HOT},
        "counts": {"HOT": hot, "WARM": sum(1 for e in entries if e["tier"] == "WARM"), "COLD": sum(1 for e in entries if e["tier"] == "COLD")},
        "entries": entries,
    }


def exact_lookup(index: dict, *, skill_id: str | None = None, path: str | None = None, alias: str | None = None) -> dict | None:
    """O(n) exact match over HOT-first ordered entries; alias ids resolve to their canonical skill entry."""
    entries = index.get("entries", [])
    if skill_id is not None:
        for entry in entries:
            if entry.get("source_type") == "canonical_skill" and entry.get("skill_id") == skill_id:
                return entry
        for entry in entries:
            if entry.get("source_type") == "canonical_skill" and skill_id in entry.get("aliases", []):
                return entry
        return None
    if alias is not None:
        for entry in entries:
            if alias in entry.get("aliases", []):
                return entry
        return None
    if path is not None:
        for entry in entries:
            if entry.get("path") == path:
                return entry
    return None


def dump(index: dict) -> str:
    head = {k: v for k, v in index.items() if k != "entries"}
    lines = [yaml.safe_dump(head, sort_keys=False, allow_unicode=True, width=200).rstrip("\n"), "entries:"]
    for entry in index["entries"]:
        lines.append("  - " + yaml.safe_dump(entry, default_flow_style=True, sort_keys=False, allow_unicode=True, width=10000).strip())
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--write", action="store_true", help="write the index to disk")
    parser.add_argument("--check", action="store_true", help="fail if the committed index is stale")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    index = build_index(root)
    target = root / INDEX_REL
    if args.check:
        on_disk = yaml.safe_load(target.read_text(encoding="utf-8")) if target.is_file() else None
        if on_disk != index:
            print("[ERROR] retrieval index is stale; run: python AI_SKILL_LIBRARY/v4/tools/build_retrieval_index.py --write")
            return 1
        print(f"RETRIEVAL_INDEX=FRESH hot={index['counts']['HOT']} warm={index['counts']['WARM']} cold={index['counts']['COLD']}")
        return 0
    if args.write:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(dump(index), encoding="utf-8")
        print(f"RETRIEVAL_INDEX=WRITTEN {target} hot={index['counts']['HOT']} warm={index['counts']['WARM']} cold={index['counts']['COLD']}")
        return 0
    print(dump(index))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
