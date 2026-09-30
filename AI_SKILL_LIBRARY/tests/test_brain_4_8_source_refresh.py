import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class Brain48SourceRefreshTests(unittest.TestCase):
    """Keep public source discovery off unattended GitHub-hosted schedules."""

    def test_manual_cycle_revalidates_registered_upstreams(self):
        workflow = (ROOT / ".github/workflows/ai-brain-evergreen-scan.yml").read_text(encoding="utf-8")
        self.assertNotIn("17 * * * *", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("23 3 * * 0", workflow)
        self.assertIn("validate_registry.py --check-remote", workflow)
        self.assertIn("v4-source-registry-audit", workflow)
        self.assertNotIn("git push origin main", workflow)


if __name__ == "__main__":
    unittest.main()
