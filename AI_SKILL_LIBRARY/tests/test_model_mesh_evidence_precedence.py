"""A documentation URL must not outrank a benchmark.

The Open Model Universe requires a non-zero capability score to be backed by a
digest-bound measurement. The Model Mesh's active index accepted a provider's
own documentation link as justification for the same number. Two standards for
one field, and the weaker one was winning: `capability_fit` is the dominant term
of the candidate score, and it read the declared number directly, so a
self-reported 0.85 beat a locally measured 0.75.

The rule tested here resolves that without banning unmeasured candidates: an
unverified score is capped at the mesh's own capability floor. A declaration is
enough to clear the bar and never enough to win on quality.
"""

import unittest

from AI_SKILL_LIBRARY.v4.tools import model_mesh as mesh

REQUIREMENTS = {"text_reasoning": 0.95}


def candidate(score, state=None, supported=True):
    row = {"supported": supported, "score": score}
    if state is not None:
        row["evidence_state"] = state
    return {"capabilities": {"text_reasoning": row}}


class UnverifiedCeilingTests(unittest.TestCase):
    def test_the_ceiling_is_the_meshs_own_floor_not_a_new_number(self):
        config = mesh._load_domain_capabilities()
        floor = config["policy"]["hard_capability_min_score"]
        self.assertEqual(mesh._unverified_ceiling(), floor)

    def test_a_measured_score_beats_a_higher_declared_one(self):
        """The inversion this exists to fix."""
        declared = mesh._capability_fit(candidate(0.85, "PROVISIONAL"), REQUIREMENTS)
        measured = mesh._capability_fit(candidate(0.75, "VERIFIED"), REQUIREMENTS)
        self.assertGreater(measured, declared)

    def test_a_declared_score_is_capped_not_zeroed(self):
        """Unmeasured candidates stay selectable when nothing better exists."""
        fit = mesh._capability_fit(candidate(0.85, "PROVISIONAL"), REQUIREMENTS)
        self.assertGreater(fit, 0.0)

    def test_a_declared_score_below_the_ceiling_is_left_alone(self):
        low = mesh._capability_fit(candidate(0.20, "PROVISIONAL"), REQUIREMENTS)
        self.assertAlmostEqual(low, mesh._capability_fit(candidate(0.20, "VERIFIED"), REQUIREMENTS))

    def test_measured_scores_still_rank_against_each_other(self):
        weaker = mesh._capability_fit(candidate(0.75, "VERIFIED"), REQUIREMENTS)
        stronger = mesh._capability_fit(candidate(0.92, "VERIFIED"), REQUIREMENTS)
        self.assertGreater(stronger, weaker)

    def test_an_unstated_evidence_state_is_read_as_provisional(self):
        """Absent must be the conservative reading, not the generous one.

        Every candidate written before this field existed omits it. If absence
        meant VERIFIED, adding the field would have silently promoted all of
        them.
        """
        unstated = mesh._capability_fit(candidate(0.85), REQUIREMENTS)
        provisional = mesh._capability_fit(candidate(0.85, "PROVISIONAL"), REQUIREMENTS)
        self.assertAlmostEqual(unstated, provisional)

    def test_a_stale_measurement_does_not_count_as_verified(self):
        stale = mesh._capability_fit(candidate(0.85, "STALE"), REQUIREMENTS)
        self.assertAlmostEqual(stale, mesh._capability_fit(candidate(0.85, "PROVISIONAL"), REQUIREMENTS))

    def test_an_unsupported_capability_contributes_nothing_whatever_its_state(self):
        fit = mesh._capability_fit(candidate(0.99, "VERIFIED", supported=False), REQUIREMENTS)
        self.assertEqual(fit, 0.0)


class NormalizationTests(unittest.TestCase):
    def raw(self, **capability):
        return {
            "model_id": "m", "model_family": "f", "provider_class": "F1",
            "endpoint_family": "openai_compatible", "free_status": "recurring",
            "free_verified_at": "2026-09-17T00:00:00Z",
            "zero_cost": {"eligible": True, "basis": "verified_recurring_free",
                          "price_verified_at": "2026-09-17T00:00:00Z"},
            "quota_scope": "account", "quota_dimensions": ["requests"],
            "reset_semantics": "rolling", "privacy_class": "confidential_safe",
            "usage_terms": "evaluation", "health": "healthy", "context_window": 4096,
            "capabilities": {"text_reasoning": capability},
            "data_training_allowed_by_provider": False,
            "source_evidence": ["https://example.invalid/docs"],
        }

    def normalize(self, **capability):
        normalized = mesh.normalize_candidate("p", self.raw(**capability),
                                              observed_at="2026-09-17T00:00:00Z")
        return normalized["capabilities"]["text_reasoning"]

    def test_a_declared_state_is_carried_through(self):
        self.assertEqual(self.normalize(supported=True, score=0.8,
                                        evidence_state="VERIFIED")["evidence_state"], "VERIFIED")

    def test_an_absent_state_normalises_to_provisional(self):
        self.assertEqual(self.normalize(supported=True, score=0.8)["evidence_state"], "PROVISIONAL")

    def test_an_unrecognised_state_is_not_trusted(self):
        """A candidate cannot invent a state that outranks the vocabulary."""
        self.assertEqual(self.normalize(supported=True, score=0.8,
                                        evidence_state="TOTALLY_VERIFIED")["evidence_state"],
                         "PROVISIONAL")

    def test_case_is_normalised(self):
        self.assertEqual(self.normalize(supported=True, score=0.8,
                                        evidence_state="verified")["evidence_state"], "VERIFIED")


class LocalCandidateTests(unittest.TestCase):
    """The local lane must mark its measurements, or the cap applies to them too."""

    def test_a_digest_bound_measurement_is_marked_verified(self):
        import datetime
        from pathlib import Path

        from AI_SKILL_LIBRARY.v4.local_runtime.canonical_route import as_mesh_candidate
        from AI_SKILL_LIBRARY.v4.local_runtime.projection import load_registry, project_record

        root = Path(__file__).resolve().parents[2]
        now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        for record in load_registry(root)["models"]:
            projected = project_record(record, available_runtimes=["llama.cpp"])
            if projected.profile is None:
                continue
            row = as_mesh_candidate(projected.profile, record, observed_at=now)
            capability = row["capabilities"].get("text_reasoning") or {}
            evidence = (record.get("capability_evidence") or {}).get("text_reasoning") or {}
            expected = "VERIFIED" if evidence.get("artifact_sha256") == \
                record["artifact_identity"]["sha256"] else "PROVISIONAL"
            with self.subTest(model_id=record["model_id"]):
                self.assertEqual(capability["evidence_state"], expected)


if __name__ == "__main__":
    unittest.main()
