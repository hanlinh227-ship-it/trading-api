import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ControlPlaneWiringTests(unittest.TestCase):
    def test_checkpoint_resolves_every_control_plane_contract(self):
        checkpoint = json.loads((ROOT / "AI_SKILL_LIBRARY/checkpoint.json").read_text(encoding="utf-8"))
        keys = (
            "personal_ai_control_plane_path", "personal_ai_ingress_path", "personal_ai_verifier_path",
            "personal_ai_e2e_path", "personal_ai_wave0_path", "personal_ai_benchmark_path",
            "personal_ai_federation_path", "personal_ai_specialists_path", "personal_ai_self_development_path",
            "personal_ai_convergence_handoff_path",
        )
        for key in keys:
            self.assertIn(key, checkpoint)
            self.assertTrue((ROOT / checkpoint[key]).is_file(), key)

    def test_ci_discovers_control_plane_tests_and_authority_is_false(self):
        ci = (ROOT / "AI_SKILL_LIBRARY/v4/tools/ci_validate.py").read_text(encoding="utf-8")
        self.assertIn('"test_*.py"', ci)
        package = (ROOT / "AI_SKILL_LIBRARY/v4/control_plane/__init__.py").read_text(encoding="utf-8")
        self.assertIn("ROUTING_AUTHORITY = False", package)
        self.assertIn("RUNTIME_AUTHORITY = False", package)

    def test_handoff_has_required_status_fields(self):
        text = (ROOT / "CHECKPOINTS/PERSONAL_AI_FULL_CONVERGENCE_WORK_HANDOFF_LATEST.md").read_text(encoding="utf-8")
        for field in ("CURRENT_MAIN", "WORK_HEAD", "PR", "B2_READY", "B3_READY", "B4_READY", "WAVE0_READY", "BASELINE_READY", "MULTI_MODEL", "SELF_DEVELOPMENT", "CI", "BLOCKER", "CLAUDE_DEPENDENCY", "NEXT_WORK_ACTION"):
            self.assertIn(field + ":", text)


if __name__ == "__main__": unittest.main()
