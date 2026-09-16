import json
import tempfile
import unittest
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.tools.release import (
    load_release_pointer,
    rollback_release,
    verify_release,
)


class V4ReleaseTests(unittest.TestCase):
    def test_missing_release_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            errors, _ = verify_release(Path(tmp), "4.0.404")
            self.assertTrue(any("missing" in e.lower() for e in errors))

    def test_active_release_verifies(self):
        root = Path(__file__).resolve().parents[2]
        pointer = load_release_pointer(root)
        errors, _ = verify_release(root, pointer["version"])
        self.assertEqual(errors, [])

    def test_pointer_is_repository_relative(self):
        root = Path(__file__).resolve().parents[2]
        pointer = load_release_pointer(root)
        self.assertFalse(Path(pointer["manifest_path"]).is_absolute())
        self.assertNotIn("..", Path(pointer["manifest_path"]).parts)

    def test_current_release_is_known_good_after_production_closure(self):
        root = Path(__file__).resolve().parents[2]
        pointer = load_release_pointer(root)
        version = pointer["version"]
        history = yaml.safe_load((root / "AI_SKILL_LIBRARY/v4/releases/history.yaml").read_text(encoding="utf-8"))
        row = next(item for item in history["releases"] if item["version"] == version)
        manifest = yaml.safe_load((root / pointer["manifest_path"]).read_text(encoding="utf-8"))
        self.assertTrue(row["known_good"], f"active release {version} must be known_good after production closure")
        self.assertTrue(manifest["promotion"]["validated"], f"active release {version} manifest must be validated after production closure")

    def test_rollback_requires_known_good_previous_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AI_SKILL_LIBRARY/v4/releases").mkdir(parents=True)
            (root / "AI_SKILL_LIBRARY/v4/releases/current.json").write_text(json.dumps({"version": "4.0.0"}), encoding="utf-8")
            (root / "AI_SKILL_LIBRARY/v4/releases/history.yaml").write_text("releases: []\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                rollback_release(root)


if __name__ == "__main__":
    unittest.main()
