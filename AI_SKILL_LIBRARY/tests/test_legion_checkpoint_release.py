import json
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.tools import release


ROOT = Path(__file__).resolve().parents[2]


class LegionCheckpointReleaseTests(unittest.TestCase):
    def test_checkpoint_resolves_legion_learning_paths(self):
        checkpoint = json.loads((ROOT / "AI_SKILL_LIBRARY/checkpoint.json").read_text(encoding="utf-8"))
        expected = {
            "legion_policy_path": "AI_SKILL_LIBRARY/v4/legion/policy.yaml",
            "legion_agent_registry_path": "AI_SKILL_LIBRARY/v4/legion/agents.yaml",
            "learning_policy_path": "AI_SKILL_LIBRARY/v4/learning/policy.yaml",
            "learning_sources_path": "AI_SKILL_LIBRARY/v4/learning/sources.yaml",
            "skill_factory_policy_path": "AI_SKILL_LIBRARY/v4/learning/skill_factory.yaml",
            "idle_learning_policy_path": "AI_SKILL_LIBRARY/v4/learning/idle.yaml",
            "legion_validator_path": "AI_SKILL_LIBRARY/v4/tools/validate_legion.py",
        }
        for key, rel in expected.items():
            self.assertEqual(checkpoint.get(key), rel)
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_candidate_release_packages_legion_without_mutating_active_pointer(self):
        paths = {rel for rel, _role in release.CANDIDATE_EXTENSION_FILES}
        required = {
            "AI_SKILL_LIBRARY/v4/legion/policy.yaml",
            "AI_SKILL_LIBRARY/v4/legion/agents.yaml",
            "AI_SKILL_LIBRARY/v4/learning/policy.yaml",
            "AI_SKILL_LIBRARY/v4/learning/sources.yaml",
            "AI_SKILL_LIBRARY/v4/learning/skill_factory.yaml",
            "AI_SKILL_LIBRARY/v4/learning/skill_evo.yaml",
            "AI_SKILL_LIBRARY/v4/learning/idle.yaml",
        }
        self.assertTrue(required.issubset(paths))
        before = release.load_release_pointer(ROOT)
        manifest = release.build_candidate_manifest(
            ROOT,
            "4.9.0-candidate",
            source_sha="a" * 40,
            dependencies={"adaptive_free_model_mesh_verified": False},
        )
        after = release.load_release_pointer(ROOT)
        self.assertEqual(before, after)
        self.assertTrue(manifest["promotion"]["blocked"])
        self.assertFalse(manifest["dependencies"]["adaptive_free_model_mesh_verified"])
        manifest_paths = {row["path"] for row in manifest["files"]}
        self.assertTrue(required.issubset(manifest_paths))


if __name__ == "__main__":
    unittest.main()
