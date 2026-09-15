import unittest

from AI_SKILL_LIBRARY.v4.tools.model_mesh import (
    normalize_candidate,
    required_capabilities,
    score_candidate,
    select_workers,
)


OBSERVED = "2026-09-15T05:10:00Z"


def candidate(provider: str, model: str, family: str, *, capability_score: float, quality: float, latency_ms: float = 100.0):
    caps = {}
    for name in (
        "text_reasoning", "coding", "math_quant", "long_context", "multilingual",
        "vision", "structured_output", "tool_calling", "planning", "creative_writing",
        "prompt_media", "research_synthesis", "data_analysis", "low_latency",
    ):
        caps[name] = {
            "supported": True,
            "score": capability_score,
            "evidence": [f"bench:{provider}:{model}:{name}"],
            "verified_at": OBSERVED,
        }
    raw = {
        "provider_class": "F1",
        "model_id": model,
        "model_family": family,
        "model_variant": "hosted",
        "endpoint_family": "openai_compatible",
        "free_status": "recurring",
        "free_verified_at": OBSERVED,
        "quota_scope": "account",
        "quota_dimensions": ["rpm", "tpm"],
        "reset_semantics": "minute",
        "capabilities": caps,
        "context_window": 131072,
        "privacy_class": "confidential_safe",
        "data_training_allowed_by_provider": False,
        "retention_policy": "verified",
        "usage_terms": "production_allowed",
        "health": "healthy",
        "latency_ema_ms": latency_ms,
        "success_rate_ema": quality,
        "quality_scores": {"general": quality, "engineering": quality, "trading": quality},
        "last_benchmark_at": OBSERVED,
        "source_evidence": [f"evidence:{provider}:{model}"],
    }
    return normalize_candidate(provider, raw, observed_at=OBSERVED)


def task(profile="DEEP", domain="engineering", role="specialist", candidates=()):
    ids = [f"{row['provider_id']}:{row['model_id']}" for row in candidates]
    return {
        "profile": profile,
        "domain": domain,
        "primary_skill": "debugging" if domain == "engineering" else "trading_router",
        "data_class": "PUBLIC",
        "has_image": False,
        "context_tokens": 8000,
        "role": role,
        "permission_allowed": {key: True for key in ids},
        "quota_headroom": {key: 0.75 for key in ids},
        "reputation": {key: 0.70 for key in ids},
    }


class AdaptiveFreeModelMeshSelectionTests(unittest.TestCase):
    def test_fast_returns_zero_workers(self):
        rows = [candidate("p1", "m1", "family-a", capability_score=0.9, quality=0.9)]
        self.assertEqual(select_workers(task(profile="FAST", candidates=rows), rows, max_workers=4), [])

    def test_profile_parallel_limits_are_hard_capped(self):
        rows = [candidate(f"p{i}", f"m{i}", f"family-{i}", capability_score=0.9, quality=0.9) for i in range(6)]
        self.assertLessEqual(len(select_workers(task(profile="STANDARD", candidates=rows), rows, max_workers=10)), 2)
        self.assertLessEqual(len(select_workers(task(profile="DEEP", candidates=rows), rows, max_workers=10)), 4)

    def test_same_family_alternate_host_becomes_fallback_not_diversity_vote(self):
        primary = candidate("groq", "gpt-oss-120b", "gpt-oss-120b", capability_score=0.95, quality=0.94)
        alternate = candidate("cerebras", "gpt-oss-120b", "gpt-oss-120b", capability_score=0.92, quality=0.90)
        other = candidate("other-provider", "strong-b", "strong-b-family", capability_score=0.90, quality=0.89)
        rows = [primary, alternate, other]
        selected = select_workers(task(candidates=rows), rows, max_workers=2)
        self.assertEqual(len(selected), 2)
        self.assertEqual({row["model_family"] for row in selected}, {"gpt-oss-120b", "strong-b-family"})
        gpt = next(row for row in selected if row["model_family"] == "gpt-oss-120b")
        self.assertEqual(gpt["provider_id"], "groq")
        self.assertIn(
            {"provider_id": "cerebras", "model_id": "gpt-oss-120b"},
            gpt["fallback_provider_paths"],
        )

    def test_weak_model_does_not_win_only_because_quota_is_high(self):
        strong = candidate("p1", "strong", "strong-family", capability_score=0.95, quality=0.95)
        weak = candidate("p2", "weak", "weak-family", capability_score=0.45, quality=0.40)
        requirements = required_capabilities("engineering", "debugging")
        strong_score = score_candidate(strong, requirements, quota_headroom=0.10, reputation=0.85)
        weak_score = score_candidate(weak, requirements, quota_headroom=1.00, reputation=0.85)
        self.assertGreater(strong_score, weak_score)

    def test_filter_gates_run_before_scoring(self):
        good = candidate("p1", "good", "good-family", capability_score=0.9, quality=0.9)
        bad_privacy = dict(candidate("p2", "privacy", "privacy-family", capability_score=0.99, quality=0.99), privacy_class="public_safe")
        unknown_free = dict(candidate("p3", "unknown", "unknown-family", capability_score=0.99, quality=0.99), free_status="unknown", free_verified_at=None)
        rows = [good, bad_privacy, unknown_free]
        t = task(candidates=rows)
        t["data_class"] = "CONFIDENTIAL"
        selected = select_workers(t, rows, max_workers=4)
        self.assertEqual([(row["provider_id"], row["model_id"]) for row in selected], [("p1", "good")])

    def test_permission_quota_and_context_gates_fail_closed(self):
        allowed = candidate("p1", "allowed", "allowed-family", capability_score=0.9, quality=0.9)
        blocked_permission = candidate("p2", "blocked", "blocked-family", capability_score=0.99, quality=0.99)
        no_quota = candidate("p3", "quota", "quota-family", capability_score=0.99, quality=0.99)
        short_context = dict(candidate("p4", "context", "context-family", capability_score=0.99, quality=0.99), context_window=4096)
        rows = [allowed, blocked_permission, no_quota, short_context]
        t = task(candidates=rows)
        t["permission_allowed"]["p2:blocked"] = False
        t["quota_headroom"]["p3:quota"] = 0.0
        selected = select_workers(t, rows, max_workers=4)
        self.assertEqual([(row["provider_id"], row["model_id"]) for row in selected], [("p1", "allowed")])

    def test_trading_workers_are_explicitly_research_only(self):
        rows = [candidate("p1", "trader", "trader-family", capability_score=0.9, quality=0.9)]
        selected = select_workers(task(profile="DEEP", domain="trading", candidates=rows), rows, max_workers=1)
        self.assertEqual(len(selected), 1)
        self.assertTrue(selected[0]["research_only"])
        self.assertEqual(selected[0]["worker_role"], "specialist")


if __name__ == "__main__":
    unittest.main()
