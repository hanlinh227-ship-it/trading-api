from __future__ import annotations

import unittest

from AI_SKILL_LIBRARY.v4.tools.upstream_watch import capability_diff, normalize_source


class UpstreamWatchTests(unittest.TestCase):
    def test_whitelist_source_normalizes_active(self) -> None:
        row = normalize_source({
            "source_id": "superpowers",
            "source_type": "github",
            "location": "obra/superpowers",
            "pinned_revision": "a" * 40,
            "license": "MIT",
            "maintenance_status": "active",
            "approved": True,
            "capabilities": ["tdd", "debugging"],
        })
        self.assertEqual(row["state"], "active")
        self.assertFalse(row["routing_authority"])

    def test_new_source_stays_candidate(self) -> None:
        row = normalize_source({
            "source_id": "candidate",
            "source_type": "github",
            "location": "example/candidate",
            "pinned_revision": "b" * 40,
            "license": "Apache-2.0",
            "maintenance_status": "active",
            "approved": False,
            "capabilities": ["novel_eval"],
        })
        self.assertEqual(row["state"], "candidate")
        self.assertFalse(row["routing_authority"])

    def test_unresolved_license_is_blocked(self) -> None:
        row = normalize_source({
            "source_id": "bad",
            "source_type": "github",
            "location": "example/bad",
            "pinned_revision": "c" * 40,
            "license": "UNKNOWN",
            "maintenance_status": "active",
            "approved": False,
            "capabilities": ["x"],
        })
        self.assertEqual(row["state"], "blocked")
        self.assertIn("license", row["block_reasons"])

    def test_strengthen_existing_preferred(self) -> None:
        active = {"capabilities": {"tdd": {"skill_id": "tdd"}}}
        upstream = {"capabilities": ["tdd", "new_eval"]}
        diff = capability_diff(active, upstream)
        self.assertEqual(diff["tdd"], "strengthen_existing")
        self.assertEqual(diff["new_eval"], "distinct_candidate")

    def test_conflict_and_security_blocks(self) -> None:
        active = {"capabilities": {"security": {"skill_id": "security"}}}
        upstream = {
            "capabilities": ["security", "unsafe_tool"],
            "conflicts": ["security"],
            "security_blocked": ["unsafe_tool"],
        }
        diff = capability_diff(active, upstream)
        self.assertEqual(diff["security"], "conflict")
        self.assertEqual(diff["unsafe_tool"], "blocked_security")


if __name__ == "__main__":
    unittest.main()
