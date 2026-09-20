import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ScheduledWorkflowResilienceTests(unittest.TestCase):
    def test_upstream_watch_supports_direct_github_actions_execution(self):
        proc = subprocess.run(
            [
                sys.executable,
                "AI_SKILL_LIBRARY/v4/tools/run_upstream_watch.py",
                "--root",
                ".",
                "--check",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(
            proc.returncode,
            0,
            msg=f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}",
        )
        self.assertIn("UPSTREAM_WATCH=FRESH", proc.stdout)

    def test_g9_validation_installs_brain_validator_dependencies(self):
        workflow = (ROOT / ".github/workflows/g9-continuous-research.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "-r research/cloud_10coin_backtest/requirements.txt -r AI_SKILL_LIBRARY/requirements.txt",
            workflow,
        )

    def test_g9_empty_first_run_is_explicit_and_non_fabricating(self):
        workflow = (ROOT / ".github/workflows/g9-continuous-research.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("NO_PROMOTABLE_EVIDENCE", workflow)
        self.assertIn("route_champions", workflow)
        self.assertIn("if [ -f generated/AI_SKILL_LIBRARY/v4/evergreen/candidate_state/g9_trading_evidence.json ]; then", workflow)
        self.assertNotIn("canonical G9 Champion Pool has no route champions", workflow)


if __name__ == "__main__":
    unittest.main()
