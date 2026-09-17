import unittest

from AI_SKILL_LIBRARY.v4.local_runtime.cache import (
    ArtifactKind,
    CacheEntry,
    CachePolicy,
    eviction_score,
    plan_eviction,
    reclaimable_bytes,
)
from AI_SKILL_LIBRARY.v4.local_runtime.lifecycle import ModelState
from AI_SKILL_LIBRARY.v4.local_runtime.resources import HostFacts, ResourceSnapshot

HOST = HostFacts(system="Linux", machine="x86_64", release="6.8.0")

MB = 1024 * 1024


def snapshot(disk_free_mb=500_000, disk_total_mb=1_000_000):
    return ResourceSnapshot(
        host=HOST,
        cpu_logical=16,
        cpu_physical=8,
        ram_total_mb=64_000,
        ram_available_mb=32_000,
        disk_total_mb=disk_total_mb,
        disk_free_mb=disk_free_mb,
        gpus=(),
    )


def entry(model_id, **kwargs):
    kwargs.setdefault("revision", "rev1")
    kwargs.setdefault("kind", ArtifactKind.WEIGHTS)
    kwargs.setdefault("size_bytes", 8_000 * MB)
    kwargs.setdefault("idle_seconds", 86_400.0)
    kwargs.setdefault("use_count", 1)
    kwargs.setdefault("quality", 0.7)
    kwargs.setdefault("state", ModelState.CACHED)
    return CacheEntry(model_id=model_id, **kwargs)


class EvictionScoreTests(unittest.TestCase):
    def test_a_long_idle_artifact_outscores_a_recent_one(self):
        cold = entry("cold", idle_seconds=30 * 86_400.0)
        hot = entry("hot", idle_seconds=60.0)
        self.assertGreater(eviction_score(cold), eviction_score(hot))

    def test_a_frequently_used_artifact_is_protected(self):
        rare = entry("rare", use_count=1)
        popular = entry("popular", use_count=500)
        self.assertGreater(eviction_score(rare), eviction_score(popular))

    def test_a_larger_artifact_is_preferred_when_reclaiming(self):
        small = entry("small", size_bytes=1_000 * MB)
        large = entry("large", size_bytes=40_000 * MB)
        self.assertGreater(eviction_score(large), eviction_score(small))

    def test_higher_quality_is_protected(self):
        weak = entry("weak", quality=0.2)
        strong = entry("strong", quality=0.95)
        self.assertGreater(eviction_score(weak), eviction_score(strong))

    def test_a_specialist_with_no_replacement_is_protected(self):
        generic = entry("generic", replacement_available=True)
        sole = entry("sole", specialization_score=1.0, replacement_available=False)
        self.assertGreater(eviction_score(generic), eviction_score(sole))

    def test_a_superseded_artifact_is_the_first_to_go(self):
        superseded = entry("old", state=ModelState.SUPERSEDED, idle_seconds=60.0, use_count=500, quality=0.99)
        healthy = entry("current", idle_seconds=30 * 86_400.0, use_count=1, quality=0.1)
        self.assertGreater(eviction_score(superseded), eviction_score(healthy))


class ProtectionTests(unittest.TestCase):
    def test_a_loaded_artifact_is_never_evicted(self):
        for state in (ModelState.RUNNING, ModelState.WARM, ModelState.DEGRADED):
            with self.subTest(state=state):
                actions = plan_eviction([entry("busy", state=state)], need_bytes=10**15, snapshot=snapshot())
                self.assertEqual(actions, ())

    def test_an_artifact_with_work_in_flight_is_never_evicted(self):
        actions = plan_eviction(
            [entry("pinned", in_flight=1), entry("free")], need_bytes=10**15, snapshot=snapshot()
        )
        self.assertEqual([action.model_id for action in actions], ["free"])

    def test_a_pinned_artifact_is_never_evicted(self):
        actions = plan_eviction([entry("keep", pinned=True)], need_bytes=10**15, snapshot=snapshot())
        self.assertEqual(actions, ())

    def test_only_weight_class_artifacts_are_evicted(self):
        entries = [entry("registry-history", kind=ArtifactKind.REGISTRY_HISTORY), entry("weights")]
        actions = plan_eviction(entries, need_bytes=10**15, snapshot=snapshot())
        self.assertEqual([action.model_id for action in actions], ["weights"])

    def test_every_evictable_kind_is_reachable(self):
        for kind in (ArtifactKind.WEIGHTS, ArtifactKind.QUANTIZATION,
                     ArtifactKind.ADAPTER, ArtifactKind.EMBEDDING):
            with self.subTest(kind=kind):
                actions = plan_eviction([entry("x", kind=kind)], need_bytes=10**15, snapshot=snapshot())
                self.assertEqual(len(actions), 1)

    def test_eviction_targets_are_legal_lifecycle_transitions(self):
        from AI_SKILL_LIBRARY.v4.local_runtime.lifecycle import ModelLifecycle
        entries = [entry("a"), entry("b", state=ModelState.SLEEPING), entry("c", state=ModelState.SUPERSEDED)]
        for action in plan_eviction(entries, need_bytes=10**15, snapshot=snapshot()):
            lifecycle = ModelLifecycle(action.model_id, state=action.source)
            lifecycle.transition(ModelState.EVICTED, reason=action.reason)


class ReclaimTests(unittest.TestCase):
    def test_eviction_stops_once_the_need_is_met(self):
        entries = [entry(f"m{i}", size_bytes=1_000 * MB, idle_seconds=(i + 1) * 86_400.0) for i in range(6)]
        actions = plan_eviction(entries, need_bytes=2_500 * MB, snapshot=snapshot())
        self.assertEqual(len(actions), 3)
        self.assertGreaterEqual(sum(action.freed_bytes for action in actions), 2_500 * MB)

    def test_nothing_is_evicted_when_nothing_is_needed(self):
        self.assertEqual(plan_eviction([entry("a")], need_bytes=0, snapshot=snapshot()), ())

    def test_the_coldest_artifact_goes_first(self):
        entries = [
            entry("warm-ish", idle_seconds=3_600.0),
            entry("ancient", idle_seconds=90 * 86_400.0),
        ]
        actions = plan_eviction(entries, need_bytes=1 * MB, snapshot=snapshot())
        self.assertEqual(actions[0].model_id, "ancient")

    def test_reclaimable_bytes_counts_only_evictable_entries(self):
        entries = [
            entry("free", size_bytes=1_000 * MB),
            entry("loaded", size_bytes=9_000 * MB, state=ModelState.RUNNING),
            entry("history", size_bytes=9_000 * MB, kind=ArtifactKind.REGISTRY_HISTORY),
        ]
        self.assertEqual(reclaimable_bytes(entries), 1_000 * MB)

    def test_a_shortfall_is_reported_not_hidden(self):
        entries = [entry("only", size_bytes=100 * MB)]
        actions = plan_eviction(entries, need_bytes=10_000 * MB, snapshot=snapshot())
        self.assertEqual(len(actions), 1)
        self.assertLess(sum(action.freed_bytes for action in actions), 10_000 * MB)


class DiskPressureTests(unittest.TestCase):
    def test_disk_pressure_reclaims_down_to_the_target_free_ratio(self):
        # 2% free against a 20% target: the shortfall is what must be reclaimed.
        tight = snapshot(disk_free_mb=20_000, disk_total_mb=1_000_000)
        policy = CachePolicy(target_free_ratio=0.20)
        entries = [entry(f"m{i}", size_bytes=50_000 * MB, idle_seconds=(i + 1) * 86_400.0) for i in range(8)]
        actions = plan_eviction(entries, need_bytes=0, snapshot=tight, policy=policy)
        freed_mb = sum(action.freed_bytes for action in actions) // MB
        self.assertGreaterEqual(freed_mb, 180_000)

    def test_healthy_disk_triggers_no_eviction(self):
        entries = [entry("a"), entry("b")]
        self.assertEqual(plan_eviction(entries, need_bytes=0, snapshot=snapshot()), ())

    def test_unknown_disk_state_does_not_trigger_speculative_eviction(self):
        blind = ResourceSnapshot(
            host=HOST, cpu_logical=8, cpu_physical=4, ram_total_mb=16_000,
            ram_available_mb=8_000, disk_total_mb=None, disk_free_mb=None, gpus=(),
        )
        self.assertEqual(plan_eviction([entry("a")], need_bytes=0, snapshot=blind), ())

    def test_an_explicit_need_is_honoured_even_on_a_healthy_disk(self):
        actions = plan_eviction([entry("a")], need_bytes=1 * MB, snapshot=snapshot())
        self.assertEqual(len(actions), 1)


if __name__ == "__main__":
    unittest.main()
