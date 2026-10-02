import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = {
    "superpowers": ("obra/superpowers", "MIT", "approved_reference"),
    "addy_agent_skills": ("addyosmani/agent-skills", "MIT", "approved_reference"),
    "ponytail": ("DietrichGebert/ponytail", "MIT", "approved_reference"),
    "caveman": ("JuliusBrussee/caveman", "Apache-2.0", "approved_reference"),
    "ui_ux_pro_max": ("nextlevelbuilder/ui-ux-pro-max-skill", "MIT", "approved_reference"),
    "impeccable": ("pbakaus/impeccable", "Apache-2.0", "approved_reference"),
    "graphify": ("Graphify-Labs/graphify", "Apache-2.0", "approved_reference"),
    "understand_anything": ("Egonex-AI/Understand-Anything", "MIT", "manual_review_reference"),
    "awesome_claude_skills": ("ComposioHQ/awesome-claude-skills", "NOASSERTION", "manual_review_reference"),
    "archify": ("tt-a1i/archify", "MIT", "approved_reference"),
}


class CuratedUpstreamReposTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / "AI_SKILL_LIBRARY/v4/integrations/upstream_knowledge_fusion.yaml"
        cls.registry = yaml.safe_load(path.read_text(encoding="utf-8"))
        cls.entries = {row["id"]: row for row in cls.registry["entries"]}

    def test_every_reviewed_repo_is_pinned_and_bounded(self):
        for entry_id, (repo, license_name, status) in EXPECTED.items():
            with self.subTest(entry_id=entry_id):
                row = self.entries[entry_id]
                self.assertEqual(row["repo"], repo)
                self.assertEqual(row["source_url"], f"https://github.com/{repo}")
                self.assertRegex(row["source_commit"], re.compile(r"^[0-9a-f]{40}$"))
                self.assertTrue(row["source_ref"])
                self.assertEqual(row["observed_at"], "2026-10-02")
                self.assertEqual(row["license"], license_name)
                self.assertEqual(row["status"], status)
                self.assertFalse(row["routing_authority"])
                self.assertFalse(row["reasoning_authority"])
                self.assertFalse(row["code_reuse"])
                self.assertFalse(row["executable_dependency_added"])
                self.assertFalse(row["auto_activate"])

    def test_duplicate_graph_and_unlicensed_index_stay_deferred(self):
        self.assertIn("Deferred duplicate", self.entries["understand_anything"]["review_note"])
        self.assertEqual(self.entries["awesome_claude_skills"]["license_status"], "manual_review")
        self.assertIn("No standard LICENSE", self.entries["awesome_claude_skills"]["review_note"])
        self.assertEqual(self.entries["graphify"]["status"], "approved_reference")
        self.assertFalse(self.registry["safety"]["permission_expansion"])


if __name__ == "__main__":
    unittest.main()
