from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECKPOINT = ROOT / "AI_SKILL_LIBRARY" / "checkpoint.json"
FOCUS = ROOT / "AI_SKILL_LIBRARY" / "v4" / "memory_continuity" / "focus.json"
MODULE_PATH = ROOT / "AI_SKILL_LIBRARY" / "v4" / "tools" / "memory_continuity_bootstrap.py"


def load_module():
    if not MODULE_PATH.exists():
        raise AssertionError(f"memory continuity bootstrap implementation missing: {MODULE_PATH}")
    spec = importlib.util.spec_from_file_location("memory_continuity_bootstrap", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def focus(active=None):
    return {
        "version": 1,
        "authority": False,
        "routing_authority": False,
        "reasoning_authority": False,
        "execution_authority": False,
        "stable_mutation": False,
        "active": active,
        "on_missing_focus": "no_resume",
        "on_ambiguous_focus": "no_resume",
        "write_mode": "candidate_only",
        "cross_project_read": False,
        "cross_project_write": False,
        "requires_verified_project_handoff": True,
        "current_project_authority_wins": True,
    }


def active(project="memory-continuity-fabric", domain="engineering", **overrides):
    row = {
        "project_id": project,
        "domain": domain,
        "phase": "e2e_validation",
        "last_completed": "writeback_merged",
        "next_actions": ["validate_new_chat_resume"],
        "canonical_refs": ["AI_SKILL_LIBRARY/checkpoint.json"],
        "source": "verified_project_handoff",
        "last_verified": "2026-09-17T01:00:40Z",
        "updated_at": "2026-09-17T01:00:40Z",
        "verified": True,
        "foreground": True,
        "resume_eligible": True,
        "authority": False,
        "routing_authority": False,
        "reasoning_authority": False,
        "execution_authority": False,
    }
    row.update(overrides)
    return row


class MemoryContinuityBootstrapTests(unittest.TestCase):
    def test_checkpoint_exposes_bootstrap_tool(self):
        data = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        self.assertEqual(
            data.get("memory_continuity_bootstrap_path"),
            "AI_SKILL_LIBRARY/v4/tools/memory_continuity_bootstrap.py",
        )

    def test_verified_matching_focus_resumes_context_only(self):
        module = load_module()
        result = module.bootstrap_resume(
            focus(active()),
            {"project_id": "memory-continuity-fabric", "domain": "engineering", "verified": True},
        )
        self.assertTrue(result["resumed"])
        self.assertEqual(result["context"]["project_id"], "memory-continuity-fabric")
        self.assertFalse(result["context"]["authority"])
        self.assertFalse(result["context"]["routing_authority"])
        self.assertFalse(result["context"]["reasoning_authority"])
        self.assertFalse(result["context"]["execution_authority"])

    def test_missing_focus_fails_closed(self):
        module = load_module()
        result = module.bootstrap_resume(
            focus(None),
            {"project_id": "memory-continuity-fabric", "domain": "engineering", "verified": True},
        )
        self.assertFalse(result["resumed"])
        self.assertEqual(result["reason"], "missing_active_focus")

    def test_unverified_focus_fails_closed(self):
        module = load_module()
        result = module.bootstrap_resume(
            focus(active(verified=False)),
            {"project_id": "memory-continuity-fabric", "domain": "engineering", "verified": True},
        )
        self.assertFalse(result["resumed"])
        self.assertEqual(result["reason"], "focus_unverified")

    def test_unverified_authority_fails_closed(self):
        module = load_module()
        result = module.bootstrap_resume(
            focus(active()),
            {"project_id": "memory-continuity-fabric", "domain": "engineering", "verified": False},
        )
        self.assertFalse(result["resumed"])
        self.assertEqual(result["reason"], "authority_unverified")

    def test_project_mismatch_fails_closed(self):
        module = load_module()
        result = module.bootstrap_resume(
            focus(active()),
            {"project_id": "other-project", "domain": "engineering", "verified": True},
        )
        self.assertFalse(result["resumed"])
        self.assertEqual(result["reason"], "project_authority_mismatch")

    def test_domain_mismatch_fails_closed(self):
        module = load_module()
        result = module.bootstrap_resume(
            focus(active()),
            {"project_id": "memory-continuity-fabric", "domain": "prompt_media", "verified": True},
        )
        self.assertFalse(result["resumed"])
        self.assertEqual(result["reason"], "domain_authority_mismatch")


if __name__ == "__main__":
    unittest.main()
