import json
import tempfile
import unittest
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.tools.release import (
    atomic_write_text,
    load_history,
    load_release_pointer,
    rollback_release,
    verify_history_chain,
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

    def test_current_release_history_and_manifest_validation_are_consistent(self):
        root = Path(__file__).resolve().parents[2]
        pointer = load_release_pointer(root)
        version = pointer["version"]
        history = yaml.safe_load((root / "AI_SKILL_LIBRARY/v4/releases/history.yaml").read_text(encoding="utf-8"))
        row = next(item for item in history["releases"] if item["version"] == version)
        manifest = yaml.safe_load((root / pointer["manifest_path"]).read_text(encoding="utf-8"))
        known_good = row.get("known_good") is True
        validated = manifest.get("promotion", {}).get("validated") is True
        self.assertEqual(
            known_good,
            validated,
            f"active release {version} closure drift: history.known_good={known_good} manifest.promotion.validated={validated}",
        )

    def test_history_chain_is_structurally_valid(self):
        root = Path(__file__).resolve().parents[2]
        self.assertEqual(verify_history_chain(load_history(root)), [])

    def test_history_chain_rejects_hand_edit_drift(self):
        history = {
            "releases": [
                {"version": "4.0.0", "known_good": True, "architecture": "GITHUB_BRAIN_V4", "manifest": "AI_SKILL_LIBRARY/v4/releases/4.0.0/manifest.yaml", "previous": None},
                {"version": "4.0.1", "known_good": True, "architecture": "GITHUB_BRAIN_V4", "manifest": "AI_SKILL_LIBRARY/v4/releases/4.0.0/manifest.yaml", "previous": "4.0.0"},
                {"version": "4.0.2", "known_good": "yes", "architecture": "GITHUB_BRAIN_V4", "manifest": "AI_SKILL_LIBRARY/v4/releases/4.0.2/manifest.yaml", "previous": "4.0.0"},
            ]
        }
        errors = verify_history_chain(history)
        self.assertTrue(any("4.0.1 manifest" in e for e in errors), errors)
        self.assertTrue(any("4.0.2 known_good" in e for e in errors), errors)
        self.assertTrue(any("4.0.2 previous" in e for e in errors), errors)

    def test_atomic_write_leaves_no_temp_file_and_replaces_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "releases" / "history.yaml"
            atomic_write_text(target, "a: 1\n")
            atomic_write_text(target, "a: 2\n")
            self.assertEqual(target.read_text(encoding="utf-8"), "a: 2\n")
            self.assertEqual([p.name for p in target.parent.iterdir()], ["history.yaml"])

    def test_release_temp_files_are_gitignored(self):
        root = Path(__file__).resolve().parents[2]
        ignore = (root / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("AI_SKILL_LIBRARY/v4/releases/**/*.tmp", ignore)
        self.assertIn("AI_SKILL_LIBRARY/v4/releases/*.tmp", ignore)

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
