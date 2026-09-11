import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


class V4EvergreenWorkflowTests(unittest.TestCase):
    def test_required_workflows_exist_and_are_bounded(self):
        names = [
            ".github/workflows/ai-brain-evergreen-scan.yml",
            ".github/workflows/ai-brain-evergreen-candidate.yml",
            ".github/workflows/ai-brain-v4-release.yml",
        ]
        for rel in names:
            path = ROOT / rel
            self.assertTrue(path.is_file(), rel)
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertIn("jobs", data)
            self.assertNotEqual(data.get("permissions", {}).get("contents"), "write")

    def test_scan_does_not_touch_stable_release_pointer(self):
        text = (ROOT / ".github/workflows/ai-brain-evergreen-scan.yml").read_text(encoding="utf-8")
        self.assertNotIn("current.json", text)
        self.assertIn("quarantine", text)


if __name__ == "__main__":
    unittest.main()
