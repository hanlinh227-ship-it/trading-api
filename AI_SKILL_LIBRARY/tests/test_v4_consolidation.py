"""Regression tests for the 2026-09-12 GITHUB_BRAIN_V4 consolidation.

Each test locks one conflict/bottleneck fix documented in
AI_SKILL_LIBRARY/v4/audit/BRAIN_CONSOLIDATION_2026-09-12.md.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unicodedata
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "AI_SKILL_LIBRARY"
V4 = LIB / "v4"
WORKFLOWS = ROOT / ".github" / "workflows"
SHA = "a" * 40


def _yaml(rel: str) -> dict:
    return yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))


def _json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _compile():
    from AI_SKILL_LIBRARY.v4.tools.compile_skill_gateway import compile_snapshot

    return compile_snapshot(ROOT, SHA, generated_at="2026-01-01T00:00:00Z")


LEGACY_CONTROL_PLANE = [
    "AI_SKILL_LIBRARY/bootstrap.yaml",
    "AI_SKILL_LIBRARY/kernel.yaml",
    "AI_SKILL_LIBRARY/router.yaml",
    "AI_SKILL_LIBRARY/runtime.yaml",
    "AI_SKILL_LIBRARY/context.yaml",
    "AI_SKILL_LIBRARY/reliability.yaml",
    "AI_SKILL_LIBRARY/evidence.yaml",
    "AI_SKILL_LIBRARY/memory.yaml",
    "AI_SKILL_LIBRARY/observability.yaml",
    "AI_SKILL_LIBRARY/security.yaml",
    "AI_SKILL_LIBRARY/migration.yaml",
    "AI_SKILL_LIBRARY/orchestration.yaml",
]


class AuthorityChainTests(unittest.TestCase):
    def test_legacy_control_plane_files_declare_v4_supersession(self):
        for rel in LEGACY_CONTROL_PLANE:
            data = _yaml(rel)
            self.assertEqual(data.get("superseded_by"), "GITHUB_BRAIN_V4", rel)
            self.assertEqual(data.get("authority_role"), "compatibility_alias", rel)
        protocol = (LIB / "CORE_PROTOCOL.md").read_text(encoding="utf-8")
        self.assertIn("GITHUB_BRAIN_V4", protocol.splitlines()[0])

    def test_no_document_claims_pre_v4_authority(self):
        readme = (LIB / "README.md").read_text(encoding="utf-8")
        self.assertIn("GITHUB_BRAIN_V4", readme.splitlines()[0])
        self.assertNotIn("activation key is `GITHUB_BRAIN_V2`", readme)
        self.assertFalse((LIB / "LEGACY_CLEANUP.md").exists(), "stale V2 cleanup doc must be archived")

    def test_exactly_one_router_has_routing_authority(self):
        legacy = _yaml("AI_SKILL_LIBRARY/router.yaml")
        stable = _yaml("AI_SKILL_LIBRARY/v4/stable/router.yaml")
        self.assertIs(legacy.get("routing_authority"), False)
        self.assertEqual(legacy.get("canonical_router"), "AI_SKILL_LIBRARY/v4/stable/router.yaml")
        self.assertIs(stable["policy"].get("routing_authority"), True)
        self.assertIs(stable["policy"].get("parallel_router_allowed"), False)

    def test_single_authority_precedence_chain(self):
        evidence = _yaml("AI_SKILL_LIBRARY/v4/stable/evidence.yaml")
        chain = evidence["source_precedence"]
        self.assertIsInstance(chain, list)
        for rel in ("AI_SKILL_LIBRARY/v4/stable/harmonization.yaml", "AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml"):
            data = _yaml(rel)
            self.assertEqual(data["authority"]["precedence_source"], "AI_SKILL_LIBRARY/v4/stable/evidence.yaml", rel)

    def test_checkpoint_declares_consolidation_paths(self):
        checkpoint = _json("AI_SKILL_LIBRARY/checkpoint.json")
        for key, rel in {
            "stable_budgets_path": "AI_SKILL_LIBRARY/v4/stable/budgets.yaml",
            "stable_retrieval_path": "AI_SKILL_LIBRARY/v4/stable/retrieval.yaml",
            "retrieval_index_path": "AI_SKILL_LIBRARY/v4/index/retrieval_index.yaml",
            "workspace_map_path": "AI_SKILL_LIBRARY/v4/index/workspace_map.yaml",
            "ci_validate_path": "AI_SKILL_LIBRARY/v4/tools/ci_validate.py",
            "release_tool_path": "AI_SKILL_LIBRARY/v4/tools/release.py",
            "retrieval_index_builder_path": "AI_SKILL_LIBRARY/v4/tools/build_retrieval_index.py",
        }.items():
            self.assertEqual(checkpoint.get(key), rel, key)
            self.assertTrue((ROOT / rel).is_file(), rel)


class SkillLibraryTests(unittest.TestCase):
    def setUp(self):
        self.catalog = _yaml("AI_SKILL_LIBRARY/skills/catalog.yaml")
        self.rows = {row["id"]: row for row in self.catalog["skills"]}
        self.aliases = {sid: row["alias_of"] for sid, row in self.rows.items() if row.get("alias_of")}

    def test_expected_duplicates_are_aliased(self):
        expected = {
            "software_engineering": "coding", "debugging_tdd": "debugging", "platform_engineering": "deployment",
            "game_dev": "game_development", "design_2d_ux": "ux_ui", "design_3d_blender": "blender",
            "adobe_media": "photoshop", "image_video_generation": "image_prompt", "generative_media": "video_prompt",
            "data_documents": "report", "marketing_business": "marketing", "trading": "trading_router",
            "backtesting": "quant_backtesting", "presentation": "slides",
        }
        self.assertEqual(self.aliases, expected)
        for alias, target in self.aliases.items():
            self.assertIn(target, self.rows, alias)
            self.assertNotIn("alias_of", self.rows[target], f"{alias} -> {target} must be canonical")

    def test_alias_rows_never_primary_and_fold_into_canonical(self):
        snapshot = _compile()
        self.assertEqual(snapshot["skill_aliases"], self.aliases)
        for alias, target in self.aliases.items():
            self.assertNotIn(alias, snapshot["skills"], alias)
            self.assertNotIn(alias, snapshot["capsules"], alias)
            folded = set(snapshot["skills"][target]["aliases"])
            trigger_owner = {t: sid for sid, m in snapshot["skills"].items() if m["primary_selectable"] for t in m["triggers"]}
            for term in self.rows[alias]["triggers"]:
                norm = unicodedata.normalize("NFKC", term).casefold()
                # Folded into the canonical skill, unless another canonical skill already owns it as a trigger
                # (the trigger owner wins so no term has two owners).
                self.assertTrue(norm in folded or norm in trigger_owner, (alias, term))
        for domain, ids in _yaml("AI_SKILL_LIBRARY/v4/stable/router.yaml")["domain_routes"].items():
            self.assertFalse(set(ids) & set(self.aliases), f"router domain {domain} routes an alias id")
        for path in sorted((V4 / "skills").glob("*/manifest.yaml")):
            manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertFalse(set(manifest.get("skills", [])) & set(self.aliases), path.name)
            for alias in manifest.get("legacy_aliases", []):
                self.assertIn(alias, self.aliases, (path.name, alias))

    def test_no_two_active_skills_share_a_trigger_term(self):
        snapshot = _compile()
        owner: dict[str, str] = {}
        for sid, meta in snapshot["skills"].items():
            if not meta["primary_selectable"]:
                continue
            for term in meta["triggers"]:
                self.assertNotIn(term, owner, f"trigger {term!r} owned by both {owner.get(term)} and {sid}")
                owner[term] = sid

    def test_routing_terms_are_lowercase_stable(self):
        snapshot = _compile()
        for sid, meta in snapshot["skills"].items():
            for term in meta["triggers"] + meta["aliases"] + meta["excludes"]:
                # Must survive the Worker's toLocaleLowerCase('und') identically to Python casefold().
                self.assertEqual(term, " ".join(unicodedata.normalize("NFKC", term).lower().split()), (sid, term))
                self.assertEqual(term, unicodedata.normalize("NFKC", term).casefold(), (sid, term))

    def test_alias_terms_never_collide_with_another_skill_trigger(self):
        snapshot = _compile()
        trigger_owner = {t: sid for sid, m in snapshot["skills"].items() if m["primary_selectable"] for t in m["triggers"]}
        alias_owner: dict[str, str] = {}
        for sid, meta in snapshot["skills"].items():
            for term in meta["aliases"]:
                self.assertEqual(trigger_owner.get(term, sid), sid, (sid, term, trigger_owner.get(term)))
                self.assertEqual(alias_owner.setdefault(term, sid), sid, (sid, term))

    def test_no_provider_or_plugin_has_routing_authority(self):
        index = _yaml("AI_SKILL_LIBRARY/skills/registry/index.yaml")
        for registry in index["registries"]:
            if registry["id"] != "canonical_skills":
                self.assertIs(registry["routing_authority"], False, registry["id"])
        self.assertIs(index["policy"]["provider_registry_is_reasoning_authority"], False)
        plugins = _yaml("AI_SKILL_LIBRARY/plugins.yaml")
        self.assertIs(plugins["policy"]["plugins_are_tools_not_skills"], True)
        self.assertIs(plugins["policy"].get("routing_authority"), False)
        trading = _yaml("AI_SKILL_LIBRARY/v4/mesh/domains/trading.yaml")
        self.assertIs(trading["provider_registry_reasoning_authority"], False)


class CreativeFusionTests(unittest.TestCase):
    def test_creative_bindings_are_canonical_and_shared_logic_has_single_owner(self):
        fusion = _yaml("AI_SKILL_LIBRARY/v4/stable/creative_visual_fusion.yaml")
        catalog = _yaml("AI_SKILL_LIBRARY/skills/catalog.yaml")
        aliases = {row["id"] for row in catalog["skills"] if row.get("alias_of")}
        for group, ids in fusion["canonical_skill_bindings"].items():
            self.assertFalse(set(ids) & aliases, f"{group} binds alias ids")
        owners = fusion["shared_logic_owner"]
        for logic in ("identity_preservation", "scene_continuity", "object_counts", "camera_variation", "reference_preservation",
                      "mask_first_editing", "target_grounding", "render_constraints", "negative_constraints"):
            self.assertIn(logic, owners, logic)
            self.assertIsInstance(owners[logic], str)
            self.assertNotIn(owners[logic], aliases)
        self.assertEqual(len(set(owners.values())) <= len(owners), True)
        self.assertIs(fusion["policy"]["routing_authority"], False)
        self.assertIs(fusion["policy"]["no_parallel_creative_brain"], True)


class MemoryTests(unittest.TestCase):
    def test_memory_is_context_not_authority(self):
        memory = _yaml("AI_SKILL_LIBRARY/v4/stable/memory.yaml")
        self.assertIs(memory["authority"], False)
        for layer in ("working", "project", "durable_preferences"):
            self.assertIn(layer, memory["layers"], layer)
        self.assertEqual(memory["conflict"]["action"], "reverify_or_supersede")
        self.assertIs(memory["conflict"]["majority_vote"], False)
        self.assertIs(memory["conflict"]["current_project_authority_wins"], True)
        for item in ("credentials", "api_keys", "private_keys", "secrets", "hidden_reasoning"):
            self.assertIn(item, memory["never_store"], item)
        self.assertEqual(memory["retrieval"]["FAST"]["max_items"], 0)
        legacy = _yaml("AI_SKILL_LIBRARY/memory.yaml")
        self.assertEqual(legacy["superseded_by"], "GITHUB_BRAIN_V4")


class BudgetAndFastPathTests(unittest.TestCase):
    REQUIRED = (
        "max_skill_loads", "max_supporting_skills", "max_source_candidates", "max_index_hits", "max_retrieval_stages",
        "max_graph_nodes", "max_parallel_nodes", "max_revisions", "max_durable_memory_items", "max_context_tokens",
        "max_file_reads", "max_tool_calls", "index_tiers",
    )

    def test_budgets_single_source_and_consistent(self):
        budgets = _yaml("AI_SKILL_LIBRARY/v4/stable/budgets.yaml")["profiles"]
        runtime = _yaml("AI_SKILL_LIBRARY/v4/stable/runtime.yaml")["profiles"]
        fusion = _yaml("AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml")["execution_graph"]
        harmonization = _yaml("AI_SKILL_LIBRARY/v4/stable/harmonization.yaml")["cognitive_execution"]
        orchestration = _yaml("AI_SKILL_LIBRARY/orchestration.yaml")
        for profile in ("FAST", "STANDARD", "DEEP"):
            row = budgets[profile]
            for key in self.REQUIRED:
                self.assertIn(key, row, (profile, key))
            self.assertEqual(runtime[profile]["max_supporting_skills"], row["max_supporting_skills"], profile)
            self.assertEqual(runtime[profile]["durable_memory_items"], row["max_durable_memory_items"], profile)
            self.assertEqual(runtime[profile]["context_tokens"], row["max_context_tokens"], profile)
            self.assertEqual(runtime[profile]["max_parallel_tasks"], row["max_parallel_nodes"], profile)
            self.assertLessEqual(orchestration["profiles"][profile]["max_parallel_tasks"], row["max_parallel_nodes"], profile)
        self.assertEqual(fusion["max_nodes_standard"], budgets["STANDARD"]["max_graph_nodes"])
        self.assertEqual(fusion["max_nodes_deep"], budgets["DEEP"]["max_graph_nodes"])
        self.assertEqual(fusion["max_revisions_standard"], budgets["STANDARD"]["max_revisions"])
        self.assertEqual(fusion["max_revisions_deep"], budgets["DEEP"]["max_revisions"])
        self.assertEqual(harmonization["STANDARD"]["max_revisions"], budgets["STANDARD"]["max_revisions"])
        self.assertEqual(harmonization["DEEP"]["max_revisions"], budgets["DEEP"]["max_revisions"])
        self.assertLessEqual(orchestration["task_graph"]["max_nodes"], budgets["DEEP"]["max_graph_nodes"])
        self.assertLessEqual(orchestration["budgets"]["max_tool_calls_per_request"], budgets["DEEP"]["max_tool_calls"])

    def test_fast_path_is_exact_only_and_lightweight(self):
        budgets = _yaml("AI_SKILL_LIBRARY/v4/stable/budgets.yaml")["profiles"]["FAST"]
        for key in ("max_supporting_skills", "max_source_candidates", "max_revisions", "max_durable_memory_items", "max_tool_calls", "max_parallel_nodes"):
            self.assertLessEqual(budgets[key], 1 if key == "max_parallel_nodes" else 0, key)
        self.assertEqual(budgets["max_skill_loads"], 1)
        self.assertEqual(budgets["max_retrieval_stages"], 1)
        self.assertEqual(budgets["index_tiers"], ["HOT"])
        retrieval = _yaml("AI_SKILL_LIBRARY/v4/stable/retrieval.yaml")
        fast = retrieval["profiles"]["FAST"]
        self.assertEqual(fast["tiers"], ["HOT"])
        self.assertIs(fast["semantic_retrieval"], False)
        self.assertIs(fast["semantic_cache"], False)
        self.assertEqual(fast["stages"], ["exact_lookup"])
        self.assertIs(retrieval["policy"]["exact_before_semantic"], True)
        self.assertIs(retrieval["policy"]["fast_preloads_warm_or_cold"], False)
        fusion = _yaml("AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml")
        self.assertIs(fusion["fast_knowledge_plane"]["fast_exact_only"], True)
        self.assertEqual(fusion["fast_knowledge_plane"]["semantic_cache_profiles"], ["STANDARD", "DEEP"])
        context = _yaml("AI_SKILL_LIBRARY/v4/stable/context.yaml")
        self.assertEqual(context["cache"]["semantic_enabled_profiles"], ["STANDARD", "DEEP"])
        runtime = _yaml("AI_SKILL_LIBRARY/v4/stable/runtime.yaml")["profiles"]["FAST"]
        for forbidden in ("planner", "retrieval_plane", "memory", "critic", "sources", "tools"):
            self.assertNotIn(forbidden, runtime["stages"], forbidden)
        self.assertEqual(runtime["retrieval_index_tiers"], ["HOT"])


class RetrievalIndexTests(unittest.TestCase):
    REQUIRED_META = ("id", "domain", "skill_id", "project_scope", "authority_level", "risk_class", "freshness", "source_type",
                     "release_version", "checkpoint", "provider", "tool", "tags", "aliases", "tier", "path")

    def test_retrieval_index_is_fresh_and_complete(self):
        from AI_SKILL_LIBRARY.v4.tools.build_retrieval_index import build_index

        built = build_index(ROOT)
        on_disk = _yaml("AI_SKILL_LIBRARY/v4/index/retrieval_index.yaml")
        self.assertEqual(built, on_disk, "retrieval index is stale: run build_retrieval_index.py --write")
        self.assertEqual(on_disk["release_version"], _json("AI_SKILL_LIBRARY/v4/releases/current.json")["version"])
        tiers = {"HOT", "WARM", "COLD"}
        ids = set()
        for entry in on_disk["entries"]:
            for key in self.REQUIRED_META:
                self.assertIn(key, entry, (entry.get("id"), key))
            self.assertIn(entry["tier"], tiers)
            self.assertNotIn(entry["id"], ids, "duplicate index id")
            ids.add(entry["id"])
        hot = [e for e in on_disk["entries"] if e["tier"] == "HOT"]
        hot_paths = {e["path"] for e in hot}
        for rel in ("AI_SKILL_LIBRARY/checkpoint.json", "AI_SKILL_LIBRARY/v4/stable/router.yaml", "AI_SKILL_LIBRARY/v4/releases/current.json"):
            self.assertIn(rel, hot_paths, rel)
        for entry in on_disk["entries"]:
            if entry["source_type"] == "legacy_checkpoint" or entry["source_type"] == "historical_release":
                self.assertEqual(entry["tier"], "COLD", entry["id"])
            if entry["source_type"] == "upstream_source":
                self.assertIn(entry["tier"], {"WARM", "COLD"}, entry["id"])
        self.assertLessEqual(len(hot), on_disk["limits"]["max_hot_entries"])

    def test_exact_lookup_resolves_skill_without_full_scan(self):
        from AI_SKILL_LIBRARY.v4.tools.build_retrieval_index import exact_lookup

        index = _yaml("AI_SKILL_LIBRARY/v4/index/retrieval_index.yaml")
        hit = exact_lookup(index, skill_id="debugging")
        self.assertEqual(hit["domain"], "engineering")
        self.assertEqual(hit["tier"], "HOT")
        alias_hit = exact_lookup(index, skill_id="software_engineering")
        self.assertEqual(alias_hit["skill_id"], "coding")
        self.assertIsNone(exact_lookup(index, skill_id="does_not_exist"))


class ReleaseTests(unittest.TestCase):
    def test_release_history_contains_current_release_and_is_rollbackable(self):
        pointer = _json("AI_SKILL_LIBRARY/v4/releases/current.json")
        history = _yaml("AI_SKILL_LIBRARY/v4/releases/history.yaml")
        versions = [row["version"] for row in history["releases"]]
        self.assertIn(pointer["version"], versions)
        self.assertEqual(versions[-1], pointer["version"])
        for row in history["releases"]:
            self.assertTrue((ROOT / row["manifest"]).is_file(), row["version"])
        from AI_SKILL_LIBRARY.v4.tools.release import rollback_release, verify_active_pointer

        errors, _ = verify_active_pointer(ROOT)
        self.assertEqual(errors, [])
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "repo"
            shutil.copytree(LIB, copy / "AI_SKILL_LIBRARY", ignore=shutil.ignore_patterns("__pycache__", "tests"))
            (copy / "docs").mkdir()
            target = rollback_release(copy)
            self.assertEqual(target, versions[-2])

    def test_release_manifest_is_reproducible_from_builder(self):
        from AI_SKILL_LIBRARY.v4.tools.release import build_manifest

        pointer = _json("AI_SKILL_LIBRARY/v4/releases/current.json")
        on_disk = yaml.safe_load((ROOT / pointer["manifest_path"]).read_text(encoding="utf-8"))
        rebuilt = build_manifest(ROOT, pointer["version"], promotion=on_disk["promotion"])
        on_disk_rows = {row["path"]: row["sha256"] for row in on_disk["files"]}
        for row in rebuilt["files"]:
            self.assertEqual(on_disk_rows.get(row["path"]), row["sha256"], f"manifest hash stale for {row['path']}: run release.py build")
        roles = {row["role"] for row in on_disk["files"]}
        for role in ("budgets", "retrieval", "router", "runtime", "memory", "harmonization", "capability_fusion", "creative_visual_fusion"):
            self.assertIn(role, roles, role)


class TradingAuthorityTests(unittest.TestCase):
    def test_trading_bridges_require_authority_and_mesh_enforces_it(self):
        from AI_SKILL_LIBRARY.v4.tools.mesh import resolve_context_nodes

        bridges = _yaml("AI_SKILL_LIBRARY/v4/mesh/bridges.yaml")["bridges"]
        for row in bridges:
            if "trading" in (row["from"], row["to"]):
                self.assertIs(row["authority_required"], True, row["id"])
        with self.assertRaises(PermissionError):
            resolve_context_nodes(V4, "engineering", ["trading"], profile="STANDARD")
        with self.assertRaises(PermissionError):
            resolve_context_nodes(V4, "trading", ["engineering"], profile="DEEP")
        self.assertEqual(resolve_context_nodes(V4, "trading", ["engineering"], profile="DEEP", authority_loaded=True), ["trading", "engineering"])
        self.assertEqual(resolve_context_nodes(V4, "academic", ["data_docs"], profile="STANDARD"), ["academic", "data_docs"])

    def test_trading_skills_cannot_expand_execution_authority(self):
        manifest = yaml.safe_load((V4 / "skills/trading/manifest.yaml").read_text(encoding="utf-8"))
        self.assertEqual(manifest["permissions"], ["read_only"])
        self.assertEqual(manifest["execution_authority"], "external_project_only")
        self.assertIs(manifest["research_may_grant_execution"], False)
        for sid in ("multi_market_analysis", "market_analysis", "technical_analysis", "live_data_validation"):
            self.assertIn(sid, manifest["analysis_only_skills"], sid)
        snapshot = _compile()
        for sid, capsule in snapshot["capsules"].items():
            if capsule["domain"] == "trading":
                self.assertEqual(capsule["permissions"], ["read_only"], sid)
                self.assertEqual(capsule["risk_ceiling"], "project_policy", sid)
        projects = _yaml("AI_SKILL_LIBRARY/projects.yaml")
        trading = next(p for p in projects["projects"] if p["id"] == "trading")
        self.assertEqual(trading["authority"], "docs/checkpoints/CURRENT_HANDOFF.md")
        for forbidden in ("github_research", "provider_consensus", "legacy_memory", "legacy_checkpoint", "crypto_agent", "multi_market_research"):
            self.assertIn(forbidden, trading["execution_authority_never_from"], forbidden)


class SourceRegistryTests(unittest.TestCase):
    def test_sources_have_tier_and_bounded_growth(self):
        sources = _yaml("AI_SKILL_LIBRARY/sources.yaml")
        policy = sources["policy"]
        self.assertEqual(policy["tiers"], ["WARM", "COLD"])
        self.assertIs(policy["sources_are_authority"], False)
        self.assertEqual(policy["precedence_source"], "AI_SKILL_LIBRARY/v4/stable/evidence.yaml")
        cap = policy["max_sources_per_category"]
        counts: dict[str, int] = {}
        for row in sources["sources"]:
            self.assertIn(row.get("tier"), {"WARM", "COLD"}, row.get("repo"))
            counts[row["category"]] = counts.get(row["category"], 0) + 1
        for category, count in counts.items():
            self.assertLessEqual(count, cap, category)


class CiAndDeploymentTests(unittest.TestCase):
    CANONICAL_BRAIN_CI = (
        "ai-skill-library-ci.yml",
        "skill-mandatory-fast-gateway-ci.yml",
        "crypto-skill-registry-validate.yml",
        "zero-local-cloud-runtime.yml",
        "deploy-skill-mandatory-fast-gateway.yml",
        "cloudflare-research-runtime-ci.yml",
    )

    def test_ci_workflows_use_single_validation_entrypoint(self):
        for name in self.CANONICAL_BRAIN_CI:
            text = (WORKFLOWS / name).read_text(encoding="utf-8")
            self.assertIn("AI_SKILL_LIBRARY/v4/tools/ci_validate.py", text, name)
            self.assertNotIn("python AI_SKILL_LIBRARY/validate_router.py", text, name)
            self.assertNotIn("python AI_SKILL_LIBRARY/validate_authority.py", text, name)

    def test_production_deploy_workflows_do_not_cancel_each_other(self):
        for name in ("deploy-skill-mandatory-fast-gateway.yml", "deploy-cloudflare-worker.yml"):
            data = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
            self.assertEqual(data["concurrency"]["group"], "cloudflare-zero-local-runtime-production", name)
            self.assertIs(data["concurrency"]["cancel-in-progress"], False, name)

    def test_retired_one_shot_workflows_are_archived(self):
        active = [p.name for p in WORKFLOWS.glob("*.yml")]
        self.assertFalse([n for n in active if n.startswith("meme-alpha-") or n.startswith("run-signalhub-")])
        archive = ROOT / ".github" / "workflows-archive"
        self.assertTrue((archive / "README.md").is_file())
        self.assertGreater(len(list(archive.glob("*.yml"))), 300)
        self.assertLess(len(active), 120)

    def test_ci_validate_entrypoint_runs_clean(self):
        from AI_SKILL_LIBRARY.v4.tools.ci_validate import run_validators

        with tempfile.TemporaryDirectory() as tmp:
            failures = run_validators(ROOT, source_sha=SHA, include_tests=False, snapshot_output=str(Path(tmp) / "snapshot.json"))
        self.assertEqual(failures, [])


class WorkspaceMapTests(unittest.TestCase):
    def test_workspace_map_declares_tiers_and_out_of_scope_areas(self):
        wmap = _yaml("AI_SKILL_LIBRARY/v4/index/workspace_map.yaml")
        self.assertEqual(wmap["single_brain"], "GITHUB_BRAIN_V4")
        self.assertEqual(wmap["single_router"], "AI_SKILL_LIBRARY/v4/stable/router.yaml")
        for tier in ("HOT", "WARM", "COLD"):
            self.assertIn(tier, wmap["tiers"])
            self.assertTrue(wmap["tiers"][tier]["paths"])
        for rel in wmap["tiers"]["HOT"]["paths"]:
            self.assertTrue((ROOT / rel).exists(), rel)
        out = wmap["out_of_brain_scope"]
        self.assertIn("CHECKPOINTS/", [row["path"] for row in out])
        self.assertIn("docs/checkpoints/CURRENT_HANDOFF.md", wmap["external_authorities"]["trading"])


if __name__ == "__main__":
    unittest.main()
