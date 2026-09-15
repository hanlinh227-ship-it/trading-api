import unittest

from AI_SKILL_LIBRARY.v4.tools.intelligence_bus import (
    link_contradictions,
    normalize_claim,
    resolve_claim_set,
    score_claim_evidence,
)


NOW = "2026-09-15T06:40:00Z"


class IntelligenceBusTests(unittest.TestCase):
    def _claim(self, claim_id, layer, statement, **overrides):
        raw = {
            "claim_id": claim_id,
            "learning_layer": layer,
            "source_id": f"source-{claim_id}",
            "source_revision": "rev-1",
            "authority_type": "public_source",
            "observed_at": "2026-09-15T06:00:00Z",
            "freshness_deadline": "2026-09-16T06:00:00Z",
            "domain": "engineering",
            "statement": statement,
            "conflict_key": "api-contract",
            "reproducibility": "unknown",
            "benchmark_refs": [],
            "confidence": 0.5,
            "contradiction_ids": [],
            "verification_state": "unverified",
            "source_integrity": 0.7,
        }
        raw.update(overrides)
        return normalize_claim(raw)

    def test_normalization_preserves_provenance_and_hashes_statement(self):
        claim = self._claim("c1", "experience", "parameter is y")
        self.assertEqual(claim["learning_layer"], "experience")
        self.assertEqual(len(claim["statement_hash"]), 64)
        self.assertEqual(claim["source_revision"], "rev-1")

    def test_learning_layer_never_changes_evidence_score(self):
        scores = []
        for layer in ("experience", "curated", "exploration"):
            claim = self._claim("x-" + layer, layer, "same claim")
            scores.append(score_claim_evidence(claim, now=NOW))
        self.assertEqual(scores[0], scores[1])
        self.assertEqual(scores[1], scores[2])

    def test_link_contradictions_is_content_based(self):
        claims = [
            self._claim("a", "experience", "use x"),
            self._claim("b", "curated", "use x"),
            self._claim("c", "exploration", "use y"),
        ]
        linked = {c["claim_id"]: c for c in link_contradictions(claims)}
        self.assertIn("c", linked["a"]["contradiction_ids"])
        self.assertIn("a", linked["c"]["contradiction_ids"])
        self.assertNotIn("b", linked["a"]["contradiction_ids"])

    def test_single_verified_exploration_claim_can_beat_two_unsupported_claims(self):
        claims = link_contradictions([
            self._claim("a", "experience", "use x", confidence=0.8),
            self._claim("b", "curated", "use x", confidence=0.8),
            self._claim(
                "c",
                "exploration",
                "use y",
                authority_type="official_spec",
                reproducibility="reproduced",
                benchmark_refs=["bench:api-contract"],
                verification_state="verified",
                source_integrity=1.0,
                confidence=0.7,
            ),
        ])
        result = resolve_claim_set(claims, {"c": "verified", "a": "unverified", "b": "unverified"})
        self.assertEqual(result["accepted_claim_ids"], ["c"])
        self.assertFalse(result["majority_vote_used"])
        self.assertFalse(result["promotion_blocked"])

    def test_unresolved_material_conflict_blocks_promotion(self):
        claims = link_contradictions([
            self._claim("a", "experience", "use x"),
            self._claim("b", "curated", "use y"),
        ])
        result = resolve_claim_set(claims, {})
        self.assertTrue(result["promotion_blocked"])
        self.assertEqual(set(result["unresolved_claim_ids"]), {"a", "b"})
        self.assertFalse(result["majority_vote_used"])


if __name__ == "__main__":
    unittest.main()
