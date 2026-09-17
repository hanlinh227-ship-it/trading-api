from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FOCUS_PATH = ROOT / "AI_SKILL_LIBRARY" / "v4" / "memory_continuity" / "focus.json"
BOOTSTRAP_PATH = ROOT / "AI_SKILL_LIBRARY" / "v4" / "tools" / "memory_continuity_bootstrap.py"


def load_bootstrap():
    spec = importlib.util.spec_from_file_location("memory_continuity_bootstrap", BOOTSTRAP_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class MemoryContinuityEndToEndTests(unittest.TestCase):
    def test_real_persisted_focus_resumes_in_fresh_session(self):
        focus = json.loads(FOCUS_PATH.read_text(encoding="utf-8"))
        active = focus.get("active")
        self.assertIsInstance(active, dict, "verified foreground focus must be persisted for E2E resume")
        self.assertEqual(active.get("project_id"), "memory-continuity-fabric")
        self.assertEqual(active.get("domain"), "engineering")
        self.assertTrue(active.get("verified"))
        self.assertTrue(active.get("foreground"))
        self.assertTrue(active.get("resume_eligible"))

        module = load_bootstrap()
        result = module.bootstrap_resume(
            focus,
            {
                "project_id": "memory-continuity-fabric",
                "domain": "engineering",
                "verified": True,
            },
        )

        self.assertTrue(result["resumed"])
        context = result["context"]
        self.assertEqual(context["project_id"], "memory-continuity-fabric")
        self.assertIn("verify_cross_chat_resume", context["next_actions"])
        self.assertFalse(context["authority"])
        self.assertFalse(context["routing_authority"])
        self.assertFalse(context["reasoning_authority"])
        self.assertFalse(context["execution_authority"])
        self.assertFalse(context["stable_mutation"])


if __name__ == "__main__":
    unittest.main()
