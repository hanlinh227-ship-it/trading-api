"""Consolidation invariants for GITHUB_BRAIN_V4: one brain, one router, one authority chain.

Pure functions returning error lists so they can run from ci_validate.py and from tests.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

LEGACY_CONTROL_PLANE = (
    "bootstrap.yaml", "kernel.yaml", "router.yaml", "runtime.yaml", "context.yaml", "reliability.yaml", "evidence.yaml",
    "memory.yaml", "observability.yaml", "security.yaml", "migration.yaml", "orchestration.yaml",
)
RETIRED_WORKFLOW_PREFIXES = ("meme-alpha-", "run-signalhub-")
PRODUCTION_DEPLOY_WORKFLOWS = ("deploy-skill-mandatory-fast-gateway.yml", "deploy-cloudflare-worker.yml")


class _NoDuplicateLoader(yaml.SafeLoader):
    pass


def _construct_mapping(loader, node, deep=False):
    seen = set()
    for key_node, _ in node.value:
        if key_node.tag == "tag:yaml.org,2002:merge":
            continue
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise ValueError(f"duplicate YAML key {key!r} at line {key_node.start_mark.line + 1}")
        seen.add(key)
    loader.flatten_mapping(node)
    return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)


_NoDuplicateLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def check_duplicate_yaml_keys(root: Path) -> list[str]:
    errors = []
    lib = root / "AI_SKILL_LIBRARY"
    for path in sorted(list(lib.glob("*.yaml")) + list((lib / "v4").rglob("*.yaml")) + list((lib / "skills").rglob("*.yaml"))):
        try:
            yaml.load(path.read_text(encoding="utf-8"), Loader=_NoDuplicateLoader)
        except ValueError as exc:
            errors.append(f"{path.relative_to(root)}: {exc}")
        except yaml.YAMLError as exc:  # pragma: no cover - other validators report syntax
            errors.append(f"{path.relative_to(root)}: invalid yaml: {exc}")
    return errors


def check_single_router(root: Path) -> list[str]:
    errors = []
    lib = root / "AI_SKILL_LIBRARY"
    legacy = _yaml(lib / "router.yaml")
    stable = _yaml(lib / "v4/stable/router.yaml")
    if legacy.get("routing_authority") is not False:
        errors.append("legacy AI_SKILL_LIBRARY/router.yaml must declare routing_authority: false")
    if legacy.get("canonical_router") != "AI_SKILL_LIBRARY/v4/stable/router.yaml":
        errors.append("legacy router must point canonical_router at v4/stable/router.yaml")
    policy = stable.get("policy", {})
    if policy.get("routing_authority") is not True or policy.get("parallel_router_allowed") is not False:
        errors.append("v4/stable/router.yaml must be the only router (routing_authority true, parallel_router_allowed false)")
    return errors


def check_legacy_supersession(root: Path) -> list[str]:
    errors = []
    lib = root / "AI_SKILL_LIBRARY"
    for name in LEGACY_CONTROL_PLANE:
        data = _yaml(lib / name)
        if data.get("superseded_by") != "GITHUB_BRAIN_V4" or data.get("authority_role") != "compatibility_alias":
            errors.append(f"AI_SKILL_LIBRARY/{name} must declare superseded_by: GITHUB_BRAIN_V4 and authority_role: compatibility_alias")
    for name in ("README.md", "CORE_PROTOCOL.md"):
        first = (lib / name).read_text(encoding="utf-8").splitlines()[0]
        if "GITHUB_BRAIN_V4" not in first:
            errors.append(f"AI_SKILL_LIBRARY/{name} first line must name GITHUB_BRAIN_V4")
    if (lib / "LEGACY_CLEANUP.md").exists():
        errors.append("AI_SKILL_LIBRARY/LEGACY_CLEANUP.md is a stale V2 authority document; keep it archived under v4/audit")
    return errors


def check_skill_aliases(root: Path) -> list[str]:
    errors = []
    lib = root / "AI_SKILL_LIBRARY"
    catalog = _yaml(lib / "skills/catalog.yaml")
    rows = {row["id"]: row for row in catalog.get("skills", [])}
    aliases = {sid: row["alias_of"] for sid, row in rows.items() if row.get("alias_of")}
    for alias, target in aliases.items():
        if target not in rows:
            errors.append(f"alias {alias} -> unknown skill {target}")
        elif rows[target].get("alias_of"):
            errors.append(f"alias {alias} -> {target} which is itself an alias")
    router = _yaml(lib / "v4/stable/router.yaml")
    routed = set()
    for domain, ids in router.get("domain_routes", {}).items():
        for sid in ids:
            if sid in aliases:
                errors.append(f"router domain {domain} routes alias id {sid}")
            routed.add(sid)
    declared_aliases = set()
    for path in sorted((lib / "v4/skills").glob("*/manifest.yaml")):
        manifest = _yaml(path)
        for sid in manifest.get("skills", []):
            if sid in aliases:
                errors.append(f"{path.relative_to(root)} lists alias id {sid} as a skill")
        for sid in manifest.get("legacy_aliases", []):
            if sid not in aliases:
                errors.append(f"{path.relative_to(root)} declares legacy alias {sid} that is not an alias row")
            declared_aliases.add(sid)
    for alias in aliases:
        if alias not in declared_aliases:
            errors.append(f"alias {alias} is not declared in any domain manifest legacy_aliases")
    # Unused / orphaned skills: catalog rows that are neither routed nor aliases.
    for sid in rows:
        if sid == "task_router" or sid in aliases:
            continue
        if sid not in routed:
            errors.append(f"skill {sid} exists in the catalog but is neither routed nor aliased (unused skill)")
    return errors


def check_budgets(root: Path) -> list[str]:
    errors = []
    lib = root / "AI_SKILL_LIBRARY"
    budgets = _yaml(lib / "v4/stable/budgets.yaml").get("profiles", {})
    runtime = _yaml(lib / "v4/stable/runtime.yaml").get("profiles", {})
    fusion = _yaml(lib / "v4/stable/capability_fusion.yaml")
    harmonization = _yaml(lib / "v4/stable/harmonization.yaml").get("cognitive_execution", {})
    orchestration = _yaml(lib / "orchestration.yaml")
    retrieval = _yaml(lib / "v4/stable/retrieval.yaml").get("profiles", {})
    creative = _yaml(lib / "v4/stable/creative_visual_fusion.yaml").get("profiles", {})
    for profile in ("FAST", "STANDARD", "DEEP"):
        b = budgets.get(profile, {})
        r = runtime.get(profile, {})
        if r.get("max_supporting_skills") != b.get("max_supporting_skills"):
            errors.append(f"{profile}: runtime max_supporting_skills != budgets")
        if r.get("durable_memory_items") != b.get("max_durable_memory_items"):
            errors.append(f"{profile}: runtime durable_memory_items != budgets")
        if r.get("context_tokens") != b.get("max_context_tokens"):
            errors.append(f"{profile}: runtime context_tokens != budgets")
        if r.get("max_parallel_tasks") != b.get("max_parallel_nodes"):
            errors.append(f"{profile}: runtime max_parallel_tasks != budgets max_parallel_nodes")
        if r.get("retrieval_index_tiers") != b.get("index_tiers"):
            errors.append(f"{profile}: runtime retrieval_index_tiers != budgets index_tiers")
        if retrieval.get(profile, {}).get("tiers") != b.get("index_tiers"):
            errors.append(f"{profile}: retrieval tiers != budgets index_tiers")
        if retrieval.get(profile, {}).get("max_index_hits") != b.get("max_index_hits"):
            errors.append(f"{profile}: retrieval max_index_hits != budgets")
        if retrieval.get(profile, {}).get("max_source_candidates") != b.get("max_source_candidates"):
            errors.append(f"{profile}: retrieval max_source_candidates != budgets")
        if len(retrieval.get(profile, {}).get("stages", [])) > b.get("max_retrieval_stages", 0):
            errors.append(f"{profile}: retrieval stages exceed budgets max_retrieval_stages")
        if orchestration.get("profiles", {}).get(profile, {}).get("max_parallel_tasks", 0) > b.get("max_parallel_nodes", 0):
            errors.append(f"{profile}: orchestration max_parallel_tasks exceeds budgets")
        if profile != "FAST" and harmonization.get(profile, {}).get("max_revisions") != b.get("max_revisions"):
            errors.append(f"{profile}: harmonization max_revisions != budgets")
        if creative.get(profile, {}).get("external_framework_required") is not False:
            errors.append(f"{profile}: creative fusion must not require an external framework")
    graph = fusion.get("execution_graph", {})
    if graph.get("max_nodes_standard") != budgets.get("STANDARD", {}).get("max_graph_nodes"):
        errors.append("capability_fusion max_nodes_standard != budgets")
    if graph.get("max_nodes_deep") != budgets.get("DEEP", {}).get("max_graph_nodes"):
        errors.append("capability_fusion max_nodes_deep != budgets")
    if graph.get("max_revisions_standard") != budgets.get("STANDARD", {}).get("max_revisions") or graph.get("max_revisions_deep") != budgets.get("DEEP", {}).get("max_revisions"):
        errors.append("capability_fusion max_revisions != budgets")
    if orchestration.get("task_graph", {}).get("max_nodes", 0) > budgets.get("DEEP", {}).get("max_graph_nodes", 0):
        errors.append("orchestration task_graph.max_nodes exceeds budgets DEEP max_graph_nodes")
    if orchestration.get("budgets", {}).get("max_tool_calls_per_request", 0) > budgets.get("DEEP", {}).get("max_tool_calls", 0):
        errors.append("orchestration max_tool_calls_per_request exceeds budgets DEEP max_tool_calls")
    fast = budgets.get("FAST", {})
    for key in ("max_supporting_skills", "max_source_candidates", "max_revisions", "max_durable_memory_items", "max_tool_calls", "max_external_routing_calls"):
        if fast.get(key) != 0:
            errors.append(f"FAST budget {key} must be 0")
    if fast.get("index_tiers") != ["HOT"] or fast.get("vector_retrieval") is not False:
        errors.append("FAST must use HOT tier only and no vector retrieval")
    fkp = fusion.get("fast_knowledge_plane", {})
    if fkp.get("fast_exact_only") is not True or fkp.get("semantic_cache_profiles") != ["STANDARD", "DEEP"]:
        errors.append("capability_fusion fast_knowledge_plane must be exact-only for FAST")
    return errors


def check_trading_guards(root: Path) -> list[str]:
    errors = []
    lib = root / "AI_SKILL_LIBRARY"
    bridges = _yaml(lib / "v4/mesh/bridges.yaml").get("bridges", [])
    for row in bridges:
        if "trading" in (row.get("from"), row.get("to")) and row.get("authority_required") is not True:
            errors.append(f"bridge {row.get('id')} touches trading but authority_required is not true")
    manifest = _yaml(lib / "v4/skills/trading/manifest.yaml")
    if manifest.get("permissions") != ["read_only"]:
        errors.append("trading domain pack permissions must be exactly [read_only]")
    if manifest.get("execution_authority") != "external_project_only" or manifest.get("research_may_grant_execution") is not False:
        errors.append("trading domain pack must declare execution_authority: external_project_only and research_may_grant_execution: false")
    for sid in ("multi_market_analysis", "market_analysis", "live_data_validation"):
        if sid not in manifest.get("analysis_only_skills", []):
            errors.append(f"trading analysis skill {sid} must be listed in analysis_only_skills")
    projects = _yaml(lib / "projects.yaml")
    trading = next((p for p in projects.get("projects", []) if p.get("id") == "trading"), {})
    if trading.get("authority") != "docs/checkpoints/CURRENT_HANDOFF.md":
        errors.append("trading authority must remain docs/checkpoints/CURRENT_HANDOFF.md")
    never = set(trading.get("execution_authority_never_from", []))
    for item in ("github_research", "provider_consensus", "legacy_memory", "legacy_checkpoint", "crypto_agent", "multi_market_research"):
        if item not in never:
            errors.append(f"projects.yaml trading.execution_authority_never_from missing {item}")
    return errors


def check_memory_and_sources(root: Path) -> list[str]:
    errors = []
    lib = root / "AI_SKILL_LIBRARY"
    memory = _yaml(lib / "v4/stable/memory.yaml")
    if memory.get("authority") is not False:
        errors.append("v4/stable/memory.yaml must declare authority: false")
    conflict = memory.get("conflict", {})
    if conflict.get("action") != "reverify_or_supersede" or conflict.get("majority_vote") is not False:
        errors.append("memory conflict policy must be reverify_or_supersede without majority vote")
    for layer in ("working", "project", "durable_preferences"):
        if layer not in memory.get("layers", {}):
            errors.append(f"memory layer {layer} missing")
    for item in ("credentials", "api_keys", "private_keys", "secrets", "hidden_reasoning"):
        if item not in memory.get("never_store", []):
            errors.append(f"memory never_store missing {item}")
    sources = _yaml(lib / "sources.yaml")
    policy = sources.get("policy", {})
    cap = int(policy.get("max_sources_per_category", 0))
    total_cap = int(policy.get("max_total_sources", 0))
    if policy.get("sources_are_authority") is not False or cap <= 0 or total_cap <= 0:
        errors.append("sources.yaml policy must declare sources_are_authority: false and positive growth caps")
    counts: dict[str, int] = {}
    rows = sources.get("sources", [])
    for row in rows:
        if row.get("tier") not in {"WARM", "COLD"}:
            errors.append(f"source {row.get('repo')} missing tier WARM/COLD")
        counts[row.get("category")] = counts.get(row.get("category"), 0) + 1
    for category, count in counts.items():
        if count > cap:
            errors.append(f"source category {category} has {count} entries > cap {cap}")
    if len(rows) > total_cap:
        errors.append(f"source registry has {len(rows)} entries > max_total_sources {total_cap}")
    return errors


def check_creative(root: Path) -> list[str]:
    errors = []
    lib = root / "AI_SKILL_LIBRARY"
    fusion = _yaml(lib / "v4/stable/creative_visual_fusion.yaml")
    catalog = _yaml(lib / "skills/catalog.yaml")
    aliases = {row["id"] for row in catalog.get("skills", []) if row.get("alias_of")}
    ids = {row["id"] for row in catalog.get("skills", [])}
    for group, skills in fusion.get("canonical_skill_bindings", {}).items():
        for sid in skills:
            if sid in aliases:
                errors.append(f"creative binding {group} references alias id {sid}")
            if sid not in ids:
                errors.append(f"creative binding {group} references unknown skill {sid}")
    owners = fusion.get("shared_logic_owner", {})
    if not owners:
        errors.append("creative_visual_fusion must declare shared_logic_owner")
    for logic, owner in owners.items():
        if owner in aliases or owner not in ids:
            errors.append(f"creative shared logic {logic} owner {owner} is not a canonical skill")
    if fusion.get("policy", {}).get("routing_authority") is not False or fusion.get("policy", {}).get("no_parallel_creative_brain") is not True:
        errors.append("creative fusion must stay subordinate (routing_authority false, no_parallel_creative_brain true)")
    return errors


def check_workflows(root: Path) -> list[str]:
    errors = []
    workflows = root / ".github/workflows"
    if not workflows.is_dir():
        return ["missing .github/workflows"]
    for path in workflows.glob("*.yml"):
        if path.name.startswith(RETIRED_WORKFLOW_PREFIXES):
            errors.append(f"retired one-shot workflow still active: {path.name}")
    for name in PRODUCTION_DEPLOY_WORKFLOWS:
        path = workflows / name
        if not path.is_file():
            errors.append(f"missing production deploy workflow {name}")
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        concurrency = data.get("concurrency", {})
        if concurrency.get("cancel-in-progress") is not False:
            errors.append(f"{name}: production deploys must queue (cancel-in-progress: false) to avoid mutual cancellation")
    archive = root / ".github/workflows-archive"
    if not (archive / "README.md").is_file():
        errors.append(".github/workflows-archive/README.md missing")
    return errors


def check_release_and_index(root: Path) -> list[str]:
    errors = []
    from AI_SKILL_LIBRARY.v4.tools import release as release_tool
    from AI_SKILL_LIBRARY.v4.tools.build_retrieval_index import INDEX_REL, build_index

    pointer = release_tool.load_release_pointer(root)
    history = release_tool.load_history(root)
    versions = [row.get("version") for row in history.get("releases", [])]
    if pointer.get("version") not in versions:
        errors.append(f"release history does not contain current release {pointer.get('version')}")
    elif versions[-1] != pointer.get("version"):
        errors.append("current release must be the last entry in history.yaml")
    on_disk = release_tool.load_release_manifest(root, pointer["version"])
    stale = release_tool.manifest_is_fresh(root, on_disk)
    if stale:
        errors.append(f"release manifest hashes are stale ({stale}); run: python AI_SKILL_LIBRARY/v4/tools/release.py build")
    index_path = root / INDEX_REL
    on_disk_index = yaml.safe_load(index_path.read_text(encoding="utf-8")) if index_path.is_file() else None
    if on_disk_index != build_index(root):
        errors.append("retrieval index is stale; run: python AI_SKILL_LIBRARY/v4/tools/build_retrieval_index.py --write")
    return errors


def check_checkpoint_paths(root: Path) -> list[str]:
    errors = []
    checkpoint = json.loads((root / "AI_SKILL_LIBRARY/checkpoint.json").read_text(encoding="utf-8"))
    for key, value in checkpoint.items():
        if key.endswith("_path") and isinstance(value, str) and not value.startswith("/"):
            if not (root / value).exists():
                errors.append(f"checkpoint {key} points at missing path {value}")
    for key in ("stable_budgets_path", "stable_retrieval_path", "retrieval_index_path", "workspace_map_path", "ci_validate_path", "release_tool_path"):
        if key not in checkpoint:
            errors.append(f"checkpoint missing {key}")
    if checkpoint.get("fast_profile_tiers") != ["HOT"]:
        errors.append("checkpoint fast_profile_tiers must be [HOT]")
    return errors


CHECKS = (
    ("duplicate_yaml_keys", check_duplicate_yaml_keys),
    ("single_router", check_single_router),
    ("legacy_supersession", check_legacy_supersession),
    ("skill_aliases", check_skill_aliases),
    ("budgets", check_budgets),
    ("trading_guards", check_trading_guards),
    ("memory_and_sources", check_memory_and_sources),
    ("creative", check_creative),
    ("workflows", check_workflows),
    ("checkpoint_paths", check_checkpoint_paths),
    ("release_and_index", check_release_and_index),
)


def run_all(root: Path) -> list[str]:
    errors: list[str] = []
    for name, check in CHECKS:
        try:
            errors.extend(f"[{name}] {item}" for item in check(root))
        except Exception as exc:  # noqa: BLE001 - report, never crash CI silently
            errors.append(f"[{name}] crashed: {exc}")
    return errors


def main() -> int:
    import sys

    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    errors = run_all(root)
    for item in errors:
        print(f"[ERROR] {item}")
    print(f"Consolidation validation summary: {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
