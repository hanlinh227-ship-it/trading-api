from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
ARCHIVE = ROOT / ".github" / "workflows-archive"
RETIRED = "apply-bybit-objective-v431.yml"

def _workflow_budget():
    """The one place the active-workflow budget is written down."""
    import importlib.util
    path = Path(__file__).resolve().parent / "_workflow_budget.py"
    spec = importlib.util.spec_from_file_location("_workflow_budget", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ACTIVE_WORKFLOW_BUDGET



class RetiredWorkflowArchiveImageV2Tests(unittest.TestCase):
    def test_retired_bybit_v431_is_history_only_and_active_budget_is_restored(self):
        self.assertFalse((WORKFLOWS / RETIRED).exists())
        self.assertFalse((ARCHIVE / RETIRED).exists())
        self.assertTrue((ARCHIVE / "README.md").is_file())
        self.assertEqual(list(ARCHIVE.glob("*.yml")), [])
        active = list(WORKFLOWS.glob("*.yml"))
        self.assertLess(len(active), _workflow_budget())


if __name__ == "__main__":
    unittest.main()
