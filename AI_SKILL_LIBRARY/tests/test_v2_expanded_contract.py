import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "AI_SKILL_LIBRARY"

REQUIRED_SKILLS = {
    "task_router", "core_reasoning", "critical_thinking", "fact_checking", "research",
    "planning", "verification", "coding", "debugging", "tdd", "software_architecture",
    "github", "api", "database", "security", "android", "web_app", "deployment",
    "automation", "trading", "crypto", "forex", "futures", "indices",
    "market_microstructure", "technical_analysis", "risk_management", "backtesting",
    "mt5_mql5", "trading_bot", "live_data_validation", "game_development", "game_design",
    "godot", "unity", "game_ai", "game_2d", "game_3d", "ux_ui", "product_design",
    "graphic_design", "branding", "typography", "layout", "design_2d", "design_3d",
    "modeling", "topology", "uv", "materials", "lighting", "rigging", "animation",
    "rendering", "blender", "photoshop", "illustrator", "premiere_pro", "after_effects",
    "lightroom", "audition", "indesign", "acrobat", "prompt_engineering", "image_prompt",
    "video_prompt", "negative_constraints", "prompt_debugging", "character_consistency",
    "scene_continuity", "camera_direction", "storyboard", "image_video_generation",
    "scriptwriting", "screenwriting", "voice_over", "advertising_copy", "hook_retention",
    "storytelling", "academic_research", "literature_review", "methodology",
    "qualitative_research", "quantitative_analysis", "interdisciplinary_research",
    "citation_review", "data_analysis", "spreadsheet", "chart", "report", "docx", "pdf",
    "slides", "presentation", "business", "marketing", "troubleshooting", "comparison",
    "recommendation", "learning", "summarization", "translation",
}

REQUIRED_METADATA = {
    "id", "domain", "triggers", "excludes", "requires", "conflicts_with", "priority",
    "tools", "sources", "output_contract",
}


class ExpandedV2ContractTests(unittest.TestCase):
    def test_required_structural_files_exist(self):
        for rel in (
            "projects.yaml",
            "skills/catalog.yaml",
            "schemas/skill.schema.json",
            "schemas/router.schema.json",
            "schemas/project.schema.json",
            "validate_router.py",
            "validate_authority.py",
            "GITHUB_BRAIN_V1.md",
        ):
            self.assertTrue((LIB / rel).is_file(), rel)

    def test_skill_catalog_has_required_skills_and_metadata(self):
        catalog = yaml.safe_load((LIB / "skills/catalog.yaml").read_text(encoding="utf-8"))
        skills = catalog["skills"]
        by_id = {row["id"]: row for row in skills}
        self.assertEqual(len(by_id), len(skills), "duplicate skill id")
        self.assertTrue(REQUIRED_SKILLS.issubset(by_id), sorted(REQUIRED_SKILLS - set(by_id)))
        for sid, row in by_id.items():
            self.assertTrue(REQUIRED_METADATA.issubset(row), (sid, sorted(REQUIRED_METADATA - set(row))))
            self.assertIsInstance(row["triggers"], list, sid)
            self.assertIsInstance(row["excludes"], list, sid)
            self.assertIsInstance(row["requires"], list, sid)
            self.assertIsInstance(row["conflicts_with"], list, sid)
            self.assertIsInstance(row["tools"], list, sid)
            self.assertIsInstance(row["sources"], list, sid)

    def test_router_makes_task_router_mandatory_and_limits_supporting_skills(self):
        router = yaml.safe_load((LIB / "router.yaml").read_text(encoding="utf-8"))
        defaults = router["defaults"]
        self.assertIs(defaults["route_every_request"], True)
        self.assertEqual(defaults["mandatory_skill"], "task_router")
        self.assertEqual(defaults["max_supporting_skills"], 2)
        self.assertIs(defaults["preload_all_skills"], False)

    def test_projects_define_single_trading_authority(self):
        projects = yaml.safe_load((LIB / "projects.yaml").read_text(encoding="utf-8"))
        trading = [p for p in projects["projects"] if p["id"] == "trading"]
        self.assertEqual(len(trading), 1)
        project = trading[0]
        self.assertEqual(project["authority"], "docs/checkpoints/CURRENT_HANDOFF.md")
        self.assertEqual(project["canonical_checkpoint"], "docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md")
        self.assertEqual(project["status"], "CURRENT")

    def test_plugin_mapping_contains_required_providers(self):
        plugins = yaml.safe_load((LIB / "plugins.yaml").read_text(encoding="utf-8"))
        providers = {p["provider"] for p in plugins["plugins"]}
        self.assertTrue({"Figma", "Product Design", "Runway", "to3D", "Scite", "Massive", "Binance", "Superpowers"}.issubset(providers))
        self.assertIs(plugins["policy"]["plugins_are_tools_not_skills"], True)

    def test_source_policy_is_explicit_and_training_defaults_false(self):
        sources = yaml.safe_load((LIB / "sources.yaml").read_text(encoding="utf-8"))
        self.assertIs(sources["policy"]["default_training"], False)
        allowed = {"TRAINING_OK", "RAG_ONLY", "REFERENCE_ONLY", "MANUAL_REVIEW"}
        for source in sources["sources"]:
            self.assertIn(source["usage_tier"], allowed, source.get("repo"))
            if source.get("training", False):
                self.assertEqual(source["usage_tier"], "TRAINING_OK", source.get("repo"))

    def test_checkpoint_references_split_validators_and_projects(self):
        checkpoint = json.loads((LIB / "checkpoint.json").read_text(encoding="utf-8"))
        self.assertEqual(checkpoint["checkpoint_id"], "GITHUB_BRAIN_V2")
        self.assertEqual(checkpoint["projects_path"], "AI_SKILL_LIBRARY/projects.yaml")
        self.assertEqual(checkpoint["skill_catalog_path"], "AI_SKILL_LIBRARY/skills/catalog.yaml")
        self.assertEqual(checkpoint["router_validator_path"], "AI_SKILL_LIBRARY/validate_router.py")
        self.assertEqual(checkpoint["authority_validator_path"], "AI_SKILL_LIBRARY/validate_authority.py")
        self.assertIn("GITHUB_BRAIN_V1", checkpoint["activation_aliases"])

    def test_v1_file_is_redirect_only(self):
        text = (LIB / "GITHUB_BRAIN_V1.md").read_text(encoding="utf-8")
        self.assertIn("GITHUB_BRAIN_V2", text)
        self.assertIn("compatibility", text.lower())
        self.assertNotIn("CURRENT_AUTHORITY", text)


if __name__ == "__main__":
    unittest.main()
