from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.tools.compile_skill_curriculum import compile_curriculum


class CurriculumCompilerTests(unittest.TestCase):
    def _root(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "AI_SKILL_LIBRARY/v4/skills/core").mkdir(parents=True)
        (root / "AI_SKILL_LIBRARY/v4/model_mesh").mkdir(parents=True)
        (root / "AI_SKILL_LIBRARY").mkdir(parents=True, exist_ok=True)
        (root / "AI_SKILL_LIBRARY/evals.yaml").write_text("version: 1\n", encoding="utf-8")
        (root / "AI_SKILL_LIBRARY/v4/model_mesh/role_branches.yaml").write_text(
            yaml.safe_dump({
                "branches": [
                    {"role_id": "REASONING_BRANCH", "required_capabilities": ["text_reasoning"]},
                    {"role_id": "PLANNING_BRANCH", "required_capabilities": ["planning"]},
                ]
            }),
            encoding="utf-8",
        )
        (root / "AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml").write_text(
            yaml.safe_dump({
                "policy": {"hard_capability_weight_threshold": 0.7},
                "domains": {"core": {"capabilities": {"text_reasoning": 0.95, "planning": 0.65}}},
            }),
            encoding="utf-8",
        )
        return root

    def test_compiler_discovers_every_manifest_skill_deterministically(self):
        root = self._root()
        manifest = {
            "id": "core", "domain": "core",
            "skills": ["planning", "core_reasoning"],
            "permissions": ["read_only"],
            "risk_ceiling": "read_only",
            "evals": ["global_verification"],
            "skill_capabilities": {
                "core_reasoning": ["text_reasoning"],
                "planning": ["planning"],
            },
        }
        (root / "AI_SKILL_LIBRARY/v4/skills/core/manifest.yaml").write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )
        one = compile_curriculum(root)
        two = compile_curriculum(root)
        self.assertEqual(one, two)
        self.assertEqual(
            [x["skill_id"] for x in one["curricula"]],
            ["core_reasoning", "planning"],
        )
        self.assertEqual(one["curricula"][0]["roles"], ["REASONING_BRANCH"])
        self.assertEqual(one["curricula"][1]["roles"], ["PLANNING_BRANCH"])

    def test_compiler_never_widens_permissions_or_authority(self):
        root = self._root()
        (root / "AI_SKILL_LIBRARY/v4/skills/core/manifest.yaml").write_text(
            yaml.safe_dump({
                "domain": "core",
                "skills": ["core_reasoning"],
                "permissions": ["read_only"],
                "risk_ceiling": "read_only",
            }, sort_keys=False),
            encoding="utf-8",
        )
        doc = compile_curriculum(root)
        row = doc["curricula"][0]
        self.assertEqual(row["permissions"]["permission_ceiling"], ["read_only"])
        self.assertIs(row["permissions"]["widened_by_learning"], False)
        self.assertTrue(all(value is False for key, value in row["authority"].items() if key.endswith("_authority")))
        self.assertIs(doc["stable_write_allowed"], False)

    def test_unknown_risk_defaults_to_most_conservative_class(self):
        root = self._root()
        (root / "AI_SKILL_LIBRARY/v4/skills/core/manifest.yaml").write_text(
            yaml.safe_dump({"domain": "core", "skills": ["x"]}, sort_keys=False),
            encoding="utf-8",
        )
        row = compile_curriculum(root)["curricula"][0]
        self.assertEqual(row["risk_class"], "D")
        self.assertEqual(row["promotion_class"], "D")


if __name__ == "__main__":
    unittest.main()
