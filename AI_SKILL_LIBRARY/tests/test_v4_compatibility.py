import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "AI_SKILL_LIBRARY"


class V4CompatibilityTests(unittest.TestCase):
    def test_v1_v2_v3_files_redirect_to_v4(self):
        for name in ("GITHUB_BRAIN_V1.md", "GITHUB_BRAIN_V2.md", "GITHUB_BRAIN_V3.md"):
            text = (LIB / name).read_text(encoding="utf-8")
            self.assertIn("GITHUB_BRAIN_V4", text, name)
            self.assertLess(len(text), 2500, name)

    def test_one_current_ai_brain_authority_is_v4(self):
        projects = yaml.safe_load((LIB / "projects.yaml").read_text(encoding="utf-8"))
        rows = [r for r in projects["projects"] if r["id"] == "ai_brain" and r["status"] in {"CURRENT", "ACTIVE", "CURRENT_AUTHORITY"}]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["authority"], "AI_SKILL_LIBRARY/GITHUB_BRAIN_V4.md")

    def test_checkpoint_aliases_resolve_to_v4(self):
        cp = json.loads((LIB / "checkpoint.json").read_text(encoding="utf-8"))
        self.assertEqual(cp["activation_key"], "GITHUB_BRAIN_V4")
        self.assertEqual(cp["mode"], "github-first-v4-lts-dual-plane")


if __name__ == "__main__":
    unittest.main()
