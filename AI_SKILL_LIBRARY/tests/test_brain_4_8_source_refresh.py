import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class Brain48SourceRefreshTests(unittest.TestCase):
    """Regression coverage for the production hourly source-refresh contract."""

    def test_hourly_cycle_revalidates_registered_upstreams(self):
        workflow = (ROOT / ".github/workflows/ai-brain-evergreen-scan.yml").read_text(encoding="utf-8")
        self.assertIn("17 * * * *", workflow)
        self.assertNotIn("17 */6 * * *", workflow)
        self.assertIn("validate_registry.py --check-remote", workflow)
        self.assertIn("v4-source-registry-audit", workflow)
        self.assertNotIn("git push origin main", workflow)


if __name__ == "__main__":
    unittest.main()
