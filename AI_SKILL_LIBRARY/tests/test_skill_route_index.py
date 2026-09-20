from __future__ import annotations

import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.tools.compile_skill_gateway import compile_snapshot


ROOT = Path(__file__).resolve().parents[2]


class SkillRouteIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = compile_snapshot(
            ROOT,
            source_sha="a" * 40,
            generated_at="2026-09-20T00:00:00Z",
        )

    def test_every_routable_trigger_and_alias_is_reachable_through_index(self):
        index = self.snapshot.get("route_index") or {}
        self.assertEqual(index.get("strategy"), "first_token_bucket_v1")
        buckets = index.get("buckets") or {}
        self.assertGreater(len(buckets), 0)

        for skill_id, meta in self.snapshot["skills"].items():
            if meta.get("primary_selectable") is not True:
                continue
            for term in list(meta.get("triggers") or []) + list(meta.get("aliases") or []):
                import re
                tokens = re.findall(r"\w+", str(term), flags=re.UNICODE)
                key = tokens[0] if tokens else "*"
                self.assertIn(skill_id, buckets.get(key, []), f"{skill_id} missing for {term!r}")

    def test_index_does_not_duplicate_router_authority(self):
        self.assertNotIn("routing_authority", self.snapshot.get("route_index") or {})


if __name__ == "__main__":
    unittest.main()
