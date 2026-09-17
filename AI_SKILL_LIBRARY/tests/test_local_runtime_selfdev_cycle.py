"""The self-development cycle runner, and the recorded run it produced.

`test_local_runtime_selfdev.py` covers the contract. These cover the thing that
drives it, because a runner is where the guarantees are most easily lost: a gate
that reports its own verdict instead of a command's, a rejection the tool
decided rather than a gate finding, a rollback asserted rather than compared.
"""

import json
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.local_runtime.selfdev import REQUIRED_GATES
from AI_SKILL_LIBRARY.v4.tools.local_runtime_selfdev_cycle import (
    GATE_COMMANDS,
    break_a_gate_for_real,
    improve_autorun_no_record,
    run_gate,
)

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "CHECKPOINTS/evidence/SELFDEV_CYCLE_EVIDENCE.json"


class GateCommandTests(unittest.TestCase):
    def test_every_required_gate_has_a_real_command(self):
        """A gate with no command would have to be passed by assertion."""
        self.assertEqual(set(GATE_COMMANDS), set(REQUIRED_GATES))

    def test_a_gates_verdict_is_the_commands_exit_code(self):
        """Not the runner's opinion of the command."""
        passing = run_gate(ROOT, "benchmark")
        self.assertIs(passing.passed, True)
        self.assertIn("|exit:0|", passing.evidence_ref)

    def test_a_gate_that_could_not_finish_did_not_pass(self):
        """A timeout is a failure, not an absence of news."""
        result = run_gate(ROOT, "tests", timeout=0)
        self.assertIs(result.passed, False)
        self.assertIn("timed out", result.detail)


class ChangesAreRealTests(unittest.TestCase):
    """Both patches must alter what they claim to, and refuse when they cannot.

    The accepted change has since landed, so it is exercised against a fixture
    holding the pre-change form rather than against the live file. Asserting
    "the live file changed" would only have held until the change was merged,
    and would then have failed for the one reason that means the cycle worked.
    """

    PRE_CHANGE = '''    if record is None:
        print(json.dumps({"status": "NO_RECORD"}, indent=2))
        return 2
'''

    def _tree(self, tmp: Path, tool_body: str) -> Path:
        tool = tmp / "AI_SKILL_LIBRARY/v4/tools/local_runtime_autorun.py"
        tool.parent.mkdir(parents=True, exist_ok=True)
        tool.write_text(tool_body, encoding="utf-8")
        suite = tmp / "AI_SKILL_LIBRARY/tests/test_local_runtime_autorun.py"
        suite.parent.mkdir(parents=True, exist_ok=True)
        suite.write_text("import unittest\n", encoding="utf-8")
        return tool

    def test_the_accepted_change_edits_the_tool_and_adds_a_test(self):
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            tool = self._tree(tmp, self.PRE_CHANGE)
            improve_autorun_no_record(tmp)
            after = tool.read_text(encoding="utf-8")
            self.assertIn("available_model_ids", after)
            self.assertIn("--model-id is required", after)
            suite = (tmp / "AI_SKILL_LIBRARY/tests/test_local_runtime_autorun.py").read_text()
            self.assertIn("NoRecordIsActionableTests", suite)

    def test_the_landed_change_produced_the_behaviour_it_claimed(self):
        """The live tool, not a fixture: this is what the cycle delivered."""
        live = (ROOT / "AI_SKILL_LIBRARY/v4/tools/local_runtime_autorun.py").read_text()
        self.assertIn("available_model_ids", live)
        self.assertIn("matched no registry record", live)

    def test_a_change_that_no_longer_applies_raises_rather_than_no_ops(self):
        """A patch that silently matched nothing would run the cycle over an
        empty diff and report READY_TO_MERGE for having changed nothing."""
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            self._tree(tmp, "nothing to patch here\n")
            with self.assertRaises(RuntimeError):
                improve_autorun_no_record(tmp)

    def test_the_rejection_change_really_disables_the_guard(self):
        """The rejected run must be rejected by a gate finding a real defect."""
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            module = tmp / "AI_SKILL_LIBRARY/v4/local_runtime/selfdev.py"
            module.parent.mkdir(parents=True, exist_ok=True)
            module.write_text(
                (ROOT / "AI_SKILL_LIBRARY/v4/local_runtime/selfdev.py").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            break_a_gate_for_real(tmp)
            self.assertIn("if False and name.lower() in AUTOMATION_ACTORS:",
                          module.read_text(encoding="utf-8"))


class RecordedCycleTests(unittest.TestCase):
    """What the committed evidence must say to be worth committing."""

    @classmethod
    def setUpClass(cls):
        cls.evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))

    def test_the_run_reached_merge_readiness_without_approving_itself(self):
        accepted = self.evidence["accepted_run"]
        self.assertEqual(accepted["final_state"], "AUTO_DEV_READY_TO_MERGE")
        self.assertIs(accepted["self_approval_refused"], True)
        self.assertIs(accepted["can_merge_without_approval"], False)
        self.assertIsNone(accepted["run"]["approved_by"])

    def test_every_gate_passed_on_a_real_exit_code(self):
        gates = self.evidence["accepted_run"]["run"]["gates"]
        self.assertEqual(set(gates), set(REQUIRED_GATES))
        for name, result in gates.items():
            with self.subTest(gate=name):
                self.assertIs(result["passed"], True)
                self.assertIn("|exit:0|", result["evidence_ref"])
                self.assertIn("command:", result["evidence_ref"])

    def test_the_run_never_worked_on_the_checked_out_branch(self):
        self.assertIs(
            self.evidence["accepted_run"]["worktree_is_not_the_checked_out_branch"], True
        )

    def test_the_rejection_came_from_a_gate_and_stayed_final(self):
        rejected = self.evidence["rejected_run"]
        self.assertTrue(rejected["failed_gates"])
        self.assertIs(rejected["rejected_run_can_still_propose"], False)
        self.assertIs(rejected["failed_gate_overwrite_refused"], True)
        self.assertEqual(rejected["final_state"], "AUTO_DEV_ROLLED_BACK")

    def test_the_rollback_is_a_comparison_not_a_claim(self):
        rejected = self.evidence["rejected_run"]
        self.assertIs(rejected["worktree_restored_to_base"], True)
        self.assertEqual(rejected["residual_worktree_changes"], [])

    def test_the_runner_claims_no_merge_or_approval_authority(self):
        self.assertIs(self.evidence["merge_authority"], False)
        self.assertIs(self.evidence["approval_authority"], False)

    def test_the_verdict_is_earned_by_every_property(self):
        self.assertEqual(self.evidence["selfdev_cycle"], "PROVEN")
        self.assertEqual(
            self.evidence["properties_held"], self.evidence["properties_checked"]
        )


if __name__ == "__main__":
    unittest.main()
