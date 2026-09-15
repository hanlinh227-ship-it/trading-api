import unittest

from AI_SKILL_LIBRARY.v4.tools.model_mesh import (
    dedupe_model_families,
    eligible_free_candidate,
    model_family_key,
    normalize_candidate,
)


class AdaptiveFreeModelMeshRegistryTests(unittest.TestCase):
    def _raw(self, **overrides):
        raw = {
            "model_id": "gpt-oss-120b",
            "model_family": "gpt-oss-120b",
            "model_variant": "hosted",
            "provider_class": "F1",
            "endpoint_family": "openai_compatible",
            "free_status": "recurring",
            "free_verified_at": "2026-09-15T04:00:00Z",
            "quota_scope": "account",
            "quota_dimensions": ["rpm", "tpm"],
            "reset_semantics": "minute",
            "capabilities": {
                "text_reasoning": {"supported": True, "score": 0.8, "evidence": ["bench:reasoning"], "verified_at": "2026-09-15T04:00:00Z"},
                "coding": {"supported": True, "score": 0.7, "evidence": ["bench:code"], "verified_at": "2026-09-15T04:00:00Z"},
            },
            "context_window": 131072,
            "privacy_class": "public_safe",
            "data_training_allowed_by_provider": False,
            "retention_policy": "provider documented",
            "usage_terms": "production_allowed",
            "health": "healthy",
            "latency_ema_ms": 120.0,
            "success_rate_ema": 0.99,
            "quality_scores": {"engineering": 0.78},
            "last_benchmark_at": "2026-09-15T04:00:00Z",
            "source_evidence": ["https://example.test/provider-docs"],
        }
        raw.update(overrides)
        return raw

    def test_normalize_candidate_produces_required_contract(self):
        candidate = normalize_candidate("groq", self._raw(), observed_at="2026-09-15T04:05:00Z")
        self.assertEqual(candidate["provider_id"], "groq")
        self.assertEqual(candidate["model_id"], "gpt-oss-120b")
        self.assertEqual(candidate["model_family"], "gpt-oss-120b")
        self.assertEqual(candidate["observed_at"], "2026-09-15T04:05:00Z")
        for key in (
            "provider_class", "model_variant", "endpoint_family", "free_status", "free_verified_at",
            "quota_scope", "quota_dimensions", "reset_semantics", "capabilities", "context_window",
            "privacy_class", "data_training_allowed_by_provider", "retention_policy", "usage_terms",
            "health", "latency_ema_ms", "success_rate_ema", "quality_scores", "last_benchmark_at",
            "source_evidence",
        ):
            self.assertIn(key, candidate)

    def test_free_only_excludes_unknown_paid_and_secret(self):
        base = normalize_candidate("groq", self._raw(), observed_at="2026-09-15T04:05:00Z")
        self.assertTrue(eligible_free_candidate(base, data_class="PUBLIC"))
        self.assertFalse(eligible_free_candidate(dict(base, free_status="unknown"), data_class="PUBLIC"))
        self.assertFalse(eligible_free_candidate(dict(base, free_status="paid"), data_class="PUBLIC"))
        self.assertFalse(eligible_free_candidate(base, data_class="SECRET"))

    def test_internal_requires_compatible_privacy(self):
        public_only = normalize_candidate("zen", self._raw(privacy_class="public_safe"), observed_at="2026-09-15T04:05:00Z")
        internal_ok = normalize_candidate("groq", self._raw(privacy_class="confidential_safe"), observed_at="2026-09-15T04:05:00Z")
        self.assertFalse(eligible_free_candidate(public_only, data_class="INTERNAL"))
        self.assertTrue(eligible_free_candidate(internal_ok, data_class="INTERNAL"))
        self.assertTrue(eligible_free_candidate(internal_ok, data_class="CONFIDENTIAL"))

    def test_model_family_dedupe_keeps_provider_paths_grouped(self):
        groq = normalize_candidate("groq", self._raw(), observed_at="2026-09-15T04:05:00Z")
        cerebras = normalize_candidate("cerebras", self._raw(model_variant="fast-host"), observed_at="2026-09-15T04:05:00Z")
        groups = dedupe_model_families([groq, cerebras])
        self.assertEqual(len(groups), 1)
        self.assertEqual(model_family_key(groq), "gpt-oss-120b")
        self.assertEqual({row["provider_id"] for row in groups["gpt-oss-120b"]}, {"groq", "cerebras"})

    def test_family_key_does_not_merge_unrelated_names_by_substring(self):
        a = normalize_candidate("p1", self._raw(model_id="alpha-7b", model_family="alpha-7b"), observed_at="2026-09-15T04:05:00Z")
        b = normalize_candidate("p2", self._raw(model_id="alpha-70b", model_family="alpha-70b"), observed_at="2026-09-15T04:05:00Z")
        self.assertNotEqual(model_family_key(a), model_family_key(b))
        self.assertEqual(len(dedupe_model_families([a, b])), 2)


if __name__ == "__main__":
    unittest.main()
