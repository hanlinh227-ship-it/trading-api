from __future__ import annotations

import unittest

from AI_SKILL_LIBRARY.v4.tools.memory_lifecycle import evaluate_candidate, transition


BASE = {
    "candidate_id": "m1",
    "domain": "engineering",
    "scope": "project:ai_brain",
    "content": "Universal Entry uses one canonical Brain authority.",
    "source": "verified_test",
    "confidence": 0.9,
    "created_at": "2026-09-16T03:00:00Z",
    "evidence_refs": ["spec:universal-brain-fabric"],
    "reusable": True,
    "verified": True,
    "non_sensitive": True,
}


class MemoryLifecycleTests(unittest.TestCase):
    def test_candidate_never_promotes_directly(self) -> None:
        out = evaluate_candidate(dict(BASE), [])
        self.assertTrue(out["eligible_for_review"])
        self.assertEqual(out["state"], "candidate")
        self.assertFalse(out["active"])

    def test_missing_evidence_holds_candidate(self) -> None:
        row = dict(BASE, evidence_refs=[])
        out = evaluate_candidate(row, [])
        self.assertFalse(out["eligible_for_review"])
        self.assertIn("missing_evidence", out["reasons"])

    def test_conflict_blocks_review(self) -> None:
        active = [{
            "memory_id": "old",
            "domain": "engineering",
            "scope": "project:ai_brain",
            "content": "Universal Entry uses a parallel Brain authority.",
            "state": "active",
            "verified": True,
            "created_at": "2026-09-15T03:00:00Z",
        }]
        row = dict(BASE, conflicts_with=["old"])
        out = evaluate_candidate(row, active)
        self.assertFalse(out["eligible_for_review"])
        self.assertIn("unresolved_conflict", out["reasons"])

    def test_secret_and_raw_chat_are_rejected(self) -> None:
        row = dict(BASE, content="api_key=SECRET123")
        out = evaluate_candidate(row, [])
        self.assertFalse(out["eligible_for_review"])
        self.assertIn("sensitive_content", out["reasons"])
        raw = dict(BASE)
        raw["raw_private_chat"] = "private transcript"
        out = evaluate_candidate(raw, [])
        self.assertFalse(out["eligible_for_review"])
        self.assertIn("forbidden_field", out["reasons"])

    def test_active_transition_requires_verified_gate(self) -> None:
        candidate = dict(BASE, state="candidate")
        with self.assertRaises(ValueError):
            transition(candidate, "active", {"verified": False})
        active = transition(candidate, "active", {
            "verified": True,
            "scoped": True,
            "reusable": True,
            "non_sensitive": True,
            "conflict_free": True,
            "verified_at": "2026-09-16T04:00:00Z",
        })
        self.assertEqual(active["state"], "active")
        self.assertEqual(active["last_verified"], "2026-09-16T04:00:00Z")

    def test_verified_newer_can_supersede(self) -> None:
        active = transition(dict(BASE, state="candidate"), "active", {
            "verified": True,
            "scoped": True,
            "reusable": True,
            "non_sensitive": True,
            "conflict_free": True,
            "verified_at": "2026-09-16T04:00:00Z",
        })
        superseded = transition(active, "superseded", {
            "verified": True,
            "superseded_by": "m2",
            "verified_at": "2026-09-16T05:00:00Z",
        })
        self.assertEqual(superseded["state"], "superseded")
        self.assertEqual(superseded["superseded_by"], "m2")


if __name__ == "__main__":
    unittest.main()
