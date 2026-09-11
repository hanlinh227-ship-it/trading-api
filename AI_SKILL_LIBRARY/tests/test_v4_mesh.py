import unittest
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.tools.mesh import resolve_context_nodes

ROOT = Path(__file__).resolve().parents[2]
V4 = ROOT / "AI_SKILL_LIBRARY" / "v4"


class V4MeshTests(unittest.TestCase):
    def test_fast_route_loads_only_primary_domain(self):
        nodes = resolve_context_nodes(V4, "engineering", [], profile="FAST")
        self.assertEqual(nodes, ["engineering"])

    def test_bridge_route_is_explicit_and_bounded(self):
        nodes = resolve_context_nodes(V4, "academic", ["data_docs"], profile="STANDARD")
        self.assertEqual(nodes, ["academic", "data_docs"])

    def test_illegal_bridge_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve_context_nodes(V4, "business", ["trading"], profile="STANDARD")

    def test_bridge_budget_is_bounded(self):
        data = yaml.safe_load((V4 / "mesh/bridges.yaml").read_text(encoding="utf-8"))
        self.assertTrue(all(0 < row["max_context_tokens"] <= 2500 for row in data["bridges"]))


if __name__ == "__main__":
    unittest.main()
