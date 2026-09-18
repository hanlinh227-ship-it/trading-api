"""AI CORE continuity: the checkpoint has to be one a new session can use.

Continuity asserted inside one process proves a variable survived a function
call. These tests check the two things that make it real: the checkpoint is
written through Memory Continuity's own contract, so its own selector can pick
it back up, and the committed evidence shows a different process doing so.
"""

import json
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.control_plane.federation import load_specialists
from AI_SKILL_LIBRARY.v4.local_runtime.golden_e2e import make_legion, make_memory
from AI_SKILL_LIBRARY.v4.tools.memory_continuity import normalize_work_state, select_continuation

ROOT = Path(__file__).resolve().parents[2]
E2E = ROOT / "CHECKPOINTS/evidence/AI_CORE_E2E_EVIDENCE.json"
RESUME = ROOT / "CHECKPOINTS/evidence/AI_CORE_RESUME_EVIDENCE.json"


class LegionAssignmentTests(unittest.TestCase):
    def test_the_role_comes_from_the_canonical_specialist_registry(self):
        legion = make_legion(ROOT)
        assignment = legion({"primary_skill": "core_reasoning"}, {})
        self.assertIn(assignment["specialist_group"], load_specialists(ROOT))

    def test_it_never_claims_authority_over_routing_or_selection(self):
        assignment = make_legion(ROOT)({"primary_skill": "core_reasoning"}, {})
        self.assertFalse(assignment["orchestration_authority"])
        self.assertEqual(assignment["routed_by"], "task_router")
        self.assertEqual(assignment["model_selection_authority"], "model_mesh")

    def test_an_unknown_skill_falls_back_rather_than_inventing_a_group(self):
        assignment = make_legion(ROOT)({"primary_skill": "underwater_basket_weaving"}, {})
        self.assertIn(assignment["specialist_group"], load_specialists(ROOT))
        self.assertFalse(assignment["matched_exactly"])

    def test_the_assignment_carries_the_groups_evidence_requirements(self):
        assignment = make_legion(ROOT)({"primary_skill": "core_reasoning"}, {})
        self.assertTrue(assignment["evidence_requirements"])


class CheckpointContractTests(unittest.TestCase):
    def write(self, tmp, verified=True):
        memory = make_memory(ROOT, checkpoint_dir=tmp)
        return memory({"request_id": "t-1"}, {"answer": "Tokyo"},
                      {"passed": verified, "evidence_refs": ["e"]})

    def test_a_verified_run_writes_a_resumable_checkpoint(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            record = self.write(Path(tmp))
            self.assertTrue(record["resumable"])
            self.assertFalse(record["memory_authority"])

    def test_the_checkpoint_is_accepted_by_memory_continuity(self):
        """Written through its contract, not merely shaped like state."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            record = self.write(Path(tmp))
            self.assertTrue(normalize_work_state(record["work_state"])["accepted"])

    def test_memory_continuity_can_select_it_back(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            record = self.write(Path(tmp))
            self.assertTrue(select_continuation([record["work_state"]])["selected"])

    def test_an_unverified_run_writes_a_checkpoint_that_refuses_to_resume(self):
        """Not resuming a wrong answer is the point; the record still exists."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            record = self.write(Path(tmp), verified=False)
            self.assertFalse(record["resumable"])
            self.assertFalse(select_continuation([record["work_state"]])["selected"])

    def test_the_checkpoint_lands_on_disk(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            record = self.write(Path(tmp))
            self.assertTrue(Path(record["path"]).is_file())

    def test_authority_is_declared_even_when_the_state_is_rejected(self):
        """A refusal that omits it reads as one claiming authority."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            memory = make_memory(ROOT, checkpoint_dir=Path(tmp))
            # A request_id of the wrong shape still produces a declared record.
            record = memory({"request_id": "t-2"}, {"answer": "x"}, {"passed": True})
            self.assertIn("memory_authority", record)
            self.assertFalse(record["memory_authority"])


class CommittedContinuityEvidenceTests(unittest.TestCase):
    def setUp(self):
        if not (E2E.is_file() and RESUME.is_file()):
            self.skipTest("no AI CORE evidence committed")
        # Resolved through the gate's own rule rather than a fixed filename.
        # Two documents record "the AI CORE golden run" and only one of them is
        # refreshed by the production worker, so reading the fixed name meant
        # comparing a resume from THIS run against a run from four days ago and
        # calling the mismatch a continuity failure. The run was continuous;
        # the two files were not the same run.
        from AI_SKILL_LIBRARY.v4.tools.ai_core_release_gate import (
            golden_evidence_source)
        golden = ROOT / "CHECKPOINTS/evidence" / golden_evidence_source(ROOT)
        self.run = json.loads(golden.read_text(encoding="utf-8"))
        self.resume = json.loads(RESUME.read_text(encoding="utf-8"))

    def test_the_chain_includes_legion_and_continuity_stages(self):
        for stage in ("ai_legion", "memory_update", "checkpoint"):
            self.assertIn(stage, self.run["trace"])

    def test_legion_runs_before_model_selection(self):
        """A role chosen after the model is a label on a decision already made."""
        trace = self.run["trace"]
        self.assertLess(trace.index("ai_legion"), trace.index("model_mesh"))

    def test_the_resume_happened_in_a_different_process(self):
        """The whole point: a new session, not a variable that survived."""
        self.assertNotEqual(self.run["process_id"], self.resume["process_id"])

    def test_the_resumed_checkpoint_is_the_one_the_run_wrote(self):
        self.assertEqual(self.resume["checkpoint_id"], self.run["checkpoint"]["checkpoint_id"])

    def test_the_resume_used_memory_continuitys_own_selector(self):
        self.assertEqual(self.resume["selected_by"], "memory_continuity.select_continuation")
        self.assertEqual(self.resume["resume_status"], "RESUMED")

    def test_resuming_grants_no_authority(self):
        self.assertFalse(self.resume["memory_authority"])
        self.assertFalse(self.resume["routing_authority"])

    def test_the_run_passed_every_gate_it_claims(self):
        self.assertEqual(self.run["ai_core_e2e"], "PASS")
        self.assertEqual(self.run["failures"], [])
        for gate in ("B2_pass", "B3_pass", "B4_pass", "continuity_pass"):
            self.assertTrue(self.run[gate], gate)


if __name__ == "__main__":
    unittest.main()
