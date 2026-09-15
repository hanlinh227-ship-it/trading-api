import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ModelMeshRuntimeActivationTests(unittest.TestCase):
    def test_checkpoint_and_release_include_runtime_activation_contracts(self):
        checkpoint = json.loads((ROOT / "AI_SKILL_LIBRARY/checkpoint.json").read_text(encoding="utf-8"))
        self.assertEqual(checkpoint.get("model_mesh_active_registry_path"), "AI_SKILL_LIBRARY/v4/model_mesh/active.json")
        self.assertEqual(checkpoint.get("model_mesh_runtime_bindings_path"), "AI_SKILL_LIBRARY/v4/model_mesh/runtime_bindings.json")
        self.assertTrue((ROOT / checkpoint["model_mesh_active_registry_path"]).is_file())
        self.assertTrue((ROOT / checkpoint["model_mesh_runtime_bindings_path"]).is_file())

        release_text = (ROOT / "AI_SKILL_LIBRARY/v4/tools/release.py").read_text(encoding="utf-8")
        self.assertIn("AI_SKILL_LIBRARY/v4/model_mesh/active.json", release_text)
        self.assertIn("AI_SKILL_LIBRARY/v4/model_mesh/runtime_bindings.json", release_text)

    def test_ci_defaults_to_canonical_active_registry_instead_of_empty_pool(self):
        ci_text = (ROOT / "AI_SKILL_LIBRARY/v4/tools/ci_validate.py").read_text(encoding="utf-8")
        self.assertIn("AI_SKILL_LIBRARY/v4/model_mesh/active.json", ci_text)
        self.assertIn("--active-registry", ci_text)

    def test_active_registry_is_free_only_and_contains_no_credentials(self):
        active = json.loads((ROOT / "AI_SKILL_LIBRARY/v4/model_mesh/active.json").read_text(encoding="utf-8"))
        self.assertEqual(active.get("version"), 1)
        self.assertEqual(active.get("mode"), "FREE_ONLY")
        self.assertFalse(active.get("routing_authority"))
        self.assertFalse(active.get("reasoning_authority"))
        self.assertIsInstance(active.get("models"), list)
        self.assertGreater(len(active["models"]), 0)
        serialized = json.dumps(active).lower()
        for forbidden in ("api_key", "authorization", "bearer ", "secret_value"):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
