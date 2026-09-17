from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECKPOINT = ROOT / "AI_SKILL_LIBRARY" / "checkpoint.json"
FOCUS = ROOT / "AI_SKILL_LIBRARY" / "v4" / "memory_continuity" / "focus.json"


class MemoryContinuityBootstrapTests(unittest.TestCase):
    def test_checkpoint_exposes_continuity_bootstrap_paths(self):
        data = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        self.assertEqual(
            data.get("memory_continuity_policy_path"),
            "AI_SKILL_LIBRARY/v4/memory_continuity/policy.yaml",
        )
        self.assertEqual(
            data.get("memory_continuity_resolver_path"),
            "AI_SKILL_LIBRARY/v4/tools/memory_continuity.py",
        )
        self.assertEqual(
            data.get("memory_continuity_focus_path"),
            "AI_SKILL_LIBRARY/v4/memory_continuity/focus.json",
        )

    def test_focus_file_is_authority_free_and_fail_closed_by_default(self):
        self.assertTrue(FOCUS.exists(), "continuity focus file is missing")
        data = json.loads(FOCUS.read_text(encoding="utf-8"))
        self.assertFalse(data["authority"])
        self.assertFalse(data["routing_authority"])
        self.assertFalse(data["reasoning_authority"])
        self.assertIsNone(data["active"])
        self.assertEqual(data["on_missing_focus"], "no_resume")
        self.assertEqual(data["on_ambiguous_focus"], "no_resume")


if __name__ == "__main__":
    unittest.main()
