from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
ARCHIVE = ROOT / ".github" / "workflows-archive"
RETIRED = "apply-bybit-objective-v431.yml"


class RetiredWorkflowArchiveImageV2Tests(unittest.TestCase):
    def test_retired_bybit_v431_is_archived_and_active_budget_is_restored(self):
        self.assertFalse((WORKFLOWS / RETIRED).exists())
        self.assertTrue((ARCHIVE / RETIRED).is_file())
        active = list(WORKFLOWS.glob("*.yml"))
        self.assertLess(len(active), 120)


if __name__ == "__main__":
    unittest.main()
