import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


class V4EvergreenWorkflowTests(unittest.TestCase):
    def _load(self, rel):
        path = ROOT / rel
        self.assertTrue(path.is_file(), rel)
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertIn("jobs", data)
        return path, data

    def test_scan_is_read_only_and_quarantine_only(self):
        path, data = self._load(".github/workflows/ai-brain-evergreen-scan.yml")
        self.assertEqual(data.get("permissions", {}).get("contents"), "read")
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("current.json", text)
        self.assertIn("quarantine", text)

    def test_candidate_write_path_is_gated(self):
        path, data = self._load(".github/workflows/ai-brain-evergreen-candidate.yml")
        self.assertEqual(data.get("permissions", {}).get("contents"), "write")
        text = path.read_text(encoding="utf-8")
        self.assertIn("validate_v4.py", text)
        self.assertIn("candidate", text.lower())
        self.assertNotIn("git push origin main", text)

    def test_release_workflow_requires_v4_validation_and_class_gate(self):
        path, data = self._load(".github/workflows/ai-brain-v4-release.yml")
        self.assertEqual(data.get("permissions", {}).get("contents"), "write")
        text = path.read_text(encoding="utf-8")
        self.assertIn("validate_v4.py", text)
        self.assertIn("promotion", text.lower())
        self.assertIn("Class D", text)

    def test_release_workflow_never_merges_its_own_candidate(self):
        """promotion.yaml: pointer swap only after every gate, canary observed, and
        Class A/B unattended promotion only when ALL gates pass. The release
        workflow validated a bot-authored candidate PR and then merged it itself
        with `gh pr merge`, so a scanned skill.yaml could reach main and move
        current.json with no human ever looking at it. Merging is a human act."""
        path, data = self._load(".github/workflows/ai-brain-v4-release.yml")
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("pr merge", text)
        self.assertNotIn("merge_pull_request", text)
        self.assertNotEqual(data.get("permissions", {}).get("pull-requests"), "write")
        self.assertIn("human", text.lower())

    def test_release_reaudit_uses_canonical_catalog_as_existing_skills(self):
        path, _ = self._load(".github/workflows/ai-brain-v4-release.yml")
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("existing_skills=[]", text)
        self.assertIn("canonical_skill_rows", text)


if __name__ == "__main__":
    unittest.main()
