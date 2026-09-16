from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.tools.run_upstream_watch import build_ledger


class RunUpstreamWatchTests(unittest.TestCase):
    def test_runner_classifies_sources_without_authority(self) -> None:
        source_doc = {
            "sources": [
                {
                    "source_id": "good",
                    "source_type": "github",
                    "location": "example/good",
                    "pinned_revision": "a" * 40,
                    "license": "MIT",
                    "maintenance_status": "active",
                    "approved": True,
                    "domain": "core",
                    "risk_class": "A",
                    "capabilities": ["novel_capability"],
                },
                {
                    "source_id": "blocked-license",
                    "source_type": "github",
                    "location": "example/blocked",
                    "pinned_revision": "b" * 40,
                    "license": "UNKNOWN",
                    "maintenance_status": "active",
                    "approved": False,
                    "domain": "core",
                    "risk_class": "A",
                    "capabilities": ["other_capability"],
                },
                {
                    "source_id": "blocked-security",
                    "source_type": "github",
                    "location": "example/security",
                    "pinned_revision": "c" * 40,
                    "license": "Apache-2.0",
                    "maintenance_status": "active",
                    "approved": False,
                    "critical_security_risk": True,
                    "domain": "core",
                    "risk_class": "A",
                    "capabilities": ["unsafe_capability"],
                },
            ]
        }
        ledger = build_ledger(Path(__file__).resolve().parents[2], source_doc)
        states = {row["source_id"]: row["state"] for row in ledger["sources"]}
        self.assertEqual(states["good"], "active")
        self.assertEqual(states["blocked-license"], "blocked")
        self.assertEqual(states["blocked-security"], "blocked")
        self.assertFalse(ledger["routing_authority"])
        self.assertFalse(ledger["reasoning_authority"])
        self.assertFalse(ledger["stable_direct_write"])
        for source in ledger["sources"]:
            for result in source["capability_results"]:
                self.assertFalse(result["routing_authority"])
                self.assertFalse(result["reasoning_authority"])

    def test_distinct_capability_becomes_candidate_action(self) -> None:
        source_doc = {
            "sources": [{
                "source_id": "distinct",
                "source_type": "github",
                "location": "example/distinct",
                "pinned_revision": "d" * 40,
                "license": "MIT",
                "maintenance_status": "active",
                "approved": True,
                "domain": "core",
                "risk_class": "A",
                "capabilities": ["capability_that_does_not_match_a_skill_id"],
            }]
        }
        ledger = build_ledger(Path(__file__).resolve().parents[2], source_doc)
        self.assertEqual(len(ledger["candidate_actions"]), 1)
        action = ledger["candidate_actions"][0]
        self.assertEqual(action["status"], "distinct_candidate")
        self.assertEqual(action["action"], "create")
        self.assertEqual(action["promotion_class"], "A")
        self.assertFalse(action["stable_write"])


if __name__ == "__main__":
    unittest.main()
