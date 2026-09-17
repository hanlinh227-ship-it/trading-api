from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "v4" / "tools" / "memory_continuity_writeback.py"


def load_module():
    if not MODULE_PATH.exists():
        raise AssertionError(f"continuity writeback implementation missing: {MODULE_PATH}")
    spec = importlib.util.spec_from_file_location("memory_continuity_writeback", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def handoff(**overrides):
    row = {
        "project_id": "project-a",
        "domain": "engineering",
        "phase": "implementation",
        "last_completed": "validator_pass",
        "next_actions": ["continue implementation"],
        "canonical_refs": ["AI_SKILL_LIBRARY/checkpoint.json"],
        "source": "verified_project_handoff",
        "last_verified": "2026-09-17T00:40:00Z",
        "updated_at": "2026-09-17T00:40:00Z",
        "verified": True,
        "foreground": True,
        "resume_eligible": True,
    }
    row.update(overrides)
    return row


class MemoryContinuityWritebackTests(unittest.TestCase):
    def test_verified_foreground_handoff_builds_active_focus(self):
        module = load_module()
        result = module.build_focus_update(handoff())
        self.assertTrue(result["accepted"])
        active = result["focus"]["active"]
        self.assertEqual(active["project_id"], "project-a")
        self.assertFalse(result["focus"]["authority"])
        self.assertFalse(result["focus"]["routing_authority"])
        self.assertFalse(result["focus"]["reasoning_authority"])

    def test_unverified_handoff_cannot_change_focus(self):
        module = load_module()
        result = module.build_focus_update(handoff(verified=False))
        self.assertFalse(result["accepted"])
        self.assertEqual(result["reason"], "handoff_unverified")

    def test_background_work_cannot_steal_foreground_focus(self):
        module = load_module()
        existing = {"project_id": "project-running", "domain": "prompt_media"}
        result = module.build_focus_update(handoff(foreground=False), current_active=existing)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["reason"], "background_work_cannot_take_focus")
        self.assertEqual(result["focus"]["active"], existing)

    def test_protected_running_project_is_not_replaced_without_same_scope(self):
        module = load_module()
        existing = {"project_id": "image-render", "domain": "prompt_media", "protected_running": True}
        result = module.build_focus_update(handoff(project_id="memory-project"), current_active=existing)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["reason"], "protected_running_project")
        self.assertEqual(result["focus"]["active"], existing)

    def test_same_protected_project_can_refresh_its_own_focus(self):
        module = load_module()
        existing = {"project_id": "project-a", "domain": "engineering", "protected_running": True}
        result = module.build_focus_update(handoff(), current_active=existing)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["focus"]["active"]["project_id"], "project-a")

    def test_sensitive_handoff_is_rejected(self):
        module = load_module()
        payload = handoff(metadata={"private_key": "do-not-store"})
        result = module.build_focus_update(payload)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["reason"], "sensitive_data")


if __name__ == "__main__":
    unittest.main()
