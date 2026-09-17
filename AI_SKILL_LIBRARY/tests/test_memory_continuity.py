from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "v4" / "tools" / "memory_continuity.py"


def load_module():
    if not MODULE_PATH.exists():
        raise AssertionError(f"memory continuity implementation missing: {MODULE_PATH}")
    spec = importlib.util.spec_from_file_location("memory_continuity", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def state(project="project-a", domain="engineering", **overrides):
    row = {
        "project_id": project,
        "domain": domain,
        "phase": "implementation",
        "last_completed": "tests",
        "next_actions": ["implement"],
        "canonical_refs": ["AI_SKILL_LIBRARY/checkpoint.json"],
        "source": "verified_handoff",
        "last_verified": "2026-09-17T00:30:00Z",
        "updated_at": "2026-09-17T00:31:00Z",
        "focus": "primary",
        "resume_eligible": True,
        "lifecycle": "active",
        "verified": True,
        "superseded_by": None,
    }
    row.update(overrides)
    return row


class MemoryContinuityTests(unittest.TestCase):
    def test_single_primary_verified_active_state_resumes(self):
        module = load_module()
        result = module.select_continuation([state()])
        self.assertTrue(result["selected"])
        self.assertEqual(result["state"]["project_id"], "project-a")
        self.assertFalse(result["state"]["authority"])
        self.assertFalse(result["state"]["routing_authority"])
        self.assertFalse(result["state"]["reasoning_authority"])

    def test_multiple_primary_states_fail_closed(self):
        module = load_module()
        result = module.select_continuation([state("a"), state("b")])
        self.assertFalse(result["selected"])
        self.assertEqual(result["reason"], "ambiguous_or_missing_focus")

    def test_background_state_does_not_auto_resume(self):
        module = load_module()
        result = module.select_continuation([state(focus="background")])
        self.assertFalse(result["selected"])
        self.assertEqual(result["reason"], "ambiguous_or_missing_focus")

    def test_explicit_project_selection_is_exact_scope(self):
        module = load_module()
        result = module.select_continuation(
            [state("a"), state("b", focus="background")],
            explicit_project="b",
            explicit_domain="engineering",
        )
        self.assertTrue(result["selected"])
        self.assertEqual(result["state"]["project_id"], "b")

    def test_superseded_and_unverified_states_are_rejected(self):
        module = load_module()
        superseded = state(lifecycle="superseded", superseded_by="newer")
        unverified = state(project="b", verified=False)
        result = module.select_continuation([superseded, unverified])
        self.assertFalse(result["selected"])
        self.assertEqual(result["reason"], "ambiguous_or_missing_focus")

    def test_authority_mismatch_drops_memory_context(self):
        module = load_module()
        selected = module.select_continuation([state("project-a")])
        gated = module.gate_against_authority(
            selected,
            {"project_id": "project-b", "domain": "engineering", "verified": True},
        )
        self.assertFalse(gated["allowed"])
        self.assertEqual(gated["reason"], "project_authority_mismatch")
        self.assertIsNone(gated["context"])

    def test_matching_authority_allows_context_without_granting_authority(self):
        module = load_module()
        selected = module.select_continuation([state("project-a")])
        gated = module.gate_against_authority(
            selected,
            {"project_id": "project-a", "domain": "engineering", "verified": True},
        )
        self.assertTrue(gated["allowed"])
        self.assertFalse(gated["context"]["authority"])
        self.assertFalse(gated["context"]["routing_authority"])
        self.assertFalse(gated["context"]["reasoning_authority"])

    def test_sensitive_payload_is_rejected(self):
        module = load_module()
        payload = state()
        payload["metadata"] = {"api_key": "secret-value"}
        result = module.normalize_work_state(payload)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["reason"], "sensitive_data")


if __name__ == "__main__":
    unittest.main()
