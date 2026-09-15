import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.tools.validate_model_mesh import validate_model_mesh


ROOT = Path(__file__).resolve().parents[2]


class AdaptiveFreeModelMeshValidatorTests(unittest.TestCase):
    def test_stable_model_mesh_contracts_are_internally_consistent(self):
        self.assertEqual(validate_model_mesh(ROOT), [])


if __name__ == "__main__":
    unittest.main()
