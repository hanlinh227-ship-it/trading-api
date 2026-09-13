import json
import unittest
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.tools.build_retrieval_index import build_index
from AI_SKILL_LIBRARY.v4.tools.compile_skill_gateway import compile_snapshot
from AI_SKILL_LIBRARY.v4.tools.release import RELEASE_FILES

ROOT = Path(__file__).resolve().parents[2]
SHA = "c" * 40


class PlainLanguagePresentationTests(unittest.TestCase):
    def test_checkpoint_declares_presentation_paths(self):
        checkpoint = json.loads((ROOT / "AI_SKILL_LIBRARY/checkpoint.json").read_text(encoding="utf-8"))
        self.assertEqual(checkpoint["stable_presentation_path"], "AI_SKILL_LIBRARY/v4/stable/presentation.yaml")
        self.assertEqual(checkpoint["stable_display_names_path"], "AI_SKILL_LIBRARY/v4/stable/display_names.yaml")

    def test_every_compiled_skill_has_easy_display_name(self):
        snapshot = compile_snapshot(ROOT, SHA, generated_at="2026-09-13T00:00:00Z")
        self.assertEqual(snapshot["presentation"]["locale"], "vi")
        self.assertEqual(snapshot["presentation"]["mode"], "plain")
        for skill_id, meta in snapshot["skills"].items():
            with self.subTest(skill_id=skill_id):
                name = meta["display_name"]
                self.assertIsInstance(name, str)
                self.assertTrue(name.strip())
                self.assertNotIn("_", name)

    def test_key_skill_names_are_simple_vietnamese(self):
        snapshot = compile_snapshot(ROOT, SHA, generated_at="2026-09-13T00:00:00Z")
        expected = {
            "skill_engineering": "Tạo kỹ năng",
            "eval_engineering": "Kiểm tra kỹ năng",
            "quant_validation": "Kiểm tra chiến lược",
            "asset_validation_3d": "Kiểm tra mô hình 3D",
            "risk_management": "Quản lý rủi ro",
            "live_data_validation": "Kiểm tra dữ liệu trực tiếp",
            "task_router": "Bộ chọn cách xử lý",
        }
        for skill_id, display_name in expected.items():
            self.assertEqual(snapshot["skills"][skill_id]["display_name"], display_name)

    def test_presentation_policy_cannot_grant_permissions(self):
        policy_path = ROOT / "AI_SKILL_LIBRARY/v4/stable/presentation.yaml"
        names_path = ROOT / "AI_SKILL_LIBRARY/v4/stable/display_names.yaml"
        policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
        names = yaml.safe_load(names_path.read_text(encoding="utf-8"))
        forbidden = {"permissions", "tools", "routing_authority", "execution_authority", "risk_ceiling"}
        self.assertTrue(forbidden.isdisjoint(policy.keys()))
        self.assertTrue(forbidden.isdisjoint(names.keys()))

    def test_presentation_files_are_part_of_immutable_release(self):
        release_paths = {path for path, _role in RELEASE_FILES}
        self.assertIn("AI_SKILL_LIBRARY/v4/stable/presentation.yaml", release_paths)
        self.assertIn("AI_SKILL_LIBRARY/v4/stable/display_names.yaml", release_paths)

    def test_presentation_files_are_hot_retrieval_entries(self):
        index = build_index(ROOT)
        by_path = {row.get("path"): row for row in index["entries"]}
        for path in (
            "AI_SKILL_LIBRARY/v4/stable/presentation.yaml",
            "AI_SKILL_LIBRARY/v4/stable/display_names.yaml",
        ):
            self.assertIn(path, by_path)
            self.assertEqual(by_path[path]["tier"], "HOT")
            self.assertEqual(by_path[path]["authority_level"], "canonical")

    def test_trading_authority_stays_read_only(self):
        trading = yaml.safe_load((ROOT / "AI_SKILL_LIBRARY/v4/skills/trading/manifest.yaml").read_text(encoding="utf-8"))
        self.assertEqual(trading["permissions"], ["read_only"])
        self.assertTrue(trading["project_authority_required"])
        self.assertFalse(trading["research_may_grant_execution"])


if __name__ == "__main__":
    unittest.main()
