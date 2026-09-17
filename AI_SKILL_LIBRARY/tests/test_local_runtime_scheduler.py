import unittest

from AI_SKILL_LIBRARY.v4.local_runtime.lifecycle import ModelState
from AI_SKILL_LIBRARY.v4.local_runtime.resources import (
    GpuDevice,
    GpuVendor,
    HostFacts,
    ResourceSnapshot,
    Watermark,
)
from AI_SKILL_LIBRARY.v4.local_runtime.scheduler import (
    PlacementAction,
    Priority,
    Privacy,
    QualityTier,
    ModelProfile,
    RuntimeSlot,
    SchedulerPolicy,
    TaskRequest,
    plan_placement,
    plan_sleep,
)

HOST = HostFacts(system="Linux", machine="x86_64", release="6.8.0")


def snapshot(ram_available_mb=32000, ram_total_mb=64000, disk_free_mb=500_000,
             disk_total_mb=1_000_000, gpus=("nvidia",), vram_available_mb=20000,
             vram_total_mb=24000, **kwargs):
    devices = ()
    if gpus:
        devices = (
            GpuDevice(
                index=0,
                vendor=GpuVendor.NVIDIA,
                name="RTX 4090",
                vram_total_mb=vram_total_mb,
                vram_available_mb=vram_available_mb,
            ),
        )
    return ResourceSnapshot(
        host=HOST,
        cpu_logical=16,
        cpu_physical=8,
        ram_total_mb=ram_total_mb,
        ram_available_mb=ram_available_mb,
        disk_total_mb=disk_total_mb,
        disk_free_mb=disk_free_mb,
        gpus=devices,
        **kwargs,
    )


def profile(model_id, ram_mb=8000, vram_mb=8000, quality=0.7, **kwargs):
    kwargs.setdefault("capabilities", frozenset({"text"}))
    # Fixtures stand for models that already cleared projection.
    kwargs.setdefault("acquisition_eligible", True)
    return ModelProfile(
        model_id=model_id,
        ram_mb=ram_mb,
        vram_mb=vram_mb,
        disk_mb=16000,
        runtime="llama.cpp",
        context_limit=32768,
        quality=quality,
        **kwargs,
    )


def slot(model_id, state=ModelState.CACHED, **kwargs):
    return RuntimeSlot(model=profile(model_id, **kwargs), state=state)


def request(**kwargs):
    kwargs.setdefault("task_id", "t-1")
    kwargs.setdefault("required_capabilities", frozenset({"text"}))
    return TaskRequest(**kwargs)


class WarmPreferenceTests(unittest.TestCase):
    def test_running_model_is_preferred_over_cold_one(self):
        decision = plan_placement(
            request(quality_tier=QualityTier.FAST),
            [slot("hot", state=ModelState.RUNNING), slot("cold", state=ModelState.CACHED, quality=0.9)],
            snapshot(),
        )
        self.assertTrue(decision.admitted)
        self.assertEqual(decision.placements[0].model_id, "hot")
        self.assertEqual(decision.placements[0].action, PlacementAction.SERVE_RUNNING)

    def test_fast_tier_takes_a_warm_model_over_a_better_cold_one(self):
        decision = plan_placement(
            request(quality_tier=QualityTier.FAST),
            [slot("warm-ok", state=ModelState.WARM, quality=0.6),
             slot("cold-great", state=ModelState.CACHED, quality=0.99)],
            snapshot(),
        )
        self.assertEqual(decision.placements[0].model_id, "warm-ok")
        self.assertEqual(decision.placements[0].action, PlacementAction.USE_WARM)

    def test_standard_tier_wakes_a_specialist_when_the_gap_justifies_it(self):
        decision = plan_placement(
            request(quality_tier=QualityTier.STANDARD, required_capabilities=frozenset({"code"})),
            [
                RuntimeSlot(model=profile("generalist", quality=0.5,
                                          capabilities=frozenset({"text", "code"})),
                            state=ModelState.WARM),
                RuntimeSlot(model=profile("code-specialist", quality=0.95,
                                          capabilities=frozenset({"code"}),
                                          specializations=frozenset({"code"})),
                            state=ModelState.SLEEPING),
            ],
            snapshot(),
        )
        self.assertEqual(decision.placements[0].model_id, "code-specialist")
        self.assertEqual(decision.placements[0].action, PlacementAction.WAKE)

    def test_standard_tier_keeps_the_warm_model_when_the_gap_is_marginal(self):
        decision = plan_placement(
            request(quality_tier=QualityTier.STANDARD),
            [slot("warm", state=ModelState.WARM, quality=0.80),
             slot("asleep", state=ModelState.SLEEPING, quality=0.83)],
            snapshot(),
        )
        self.assertEqual(decision.placements[0].model_id, "warm")

    def test_deep_tier_may_fan_out_to_several_specialists(self):
        decision = plan_placement(
            request(quality_tier=QualityTier.DEEP),
            [slot(f"m{i}", state=ModelState.WARM, ram_mb=4000, vram_mb=4000) for i in range(6)],
            snapshot(),
        )
        self.assertGreater(len(decision.placements), 1)
        self.assertLessEqual(len(decision.placements), SchedulerPolicy().max_parallel[QualityTier.DEEP])

    def test_fast_tier_never_fans_out(self):
        decision = plan_placement(
            request(quality_tier=QualityTier.FAST),
            [slot(f"m{i}", state=ModelState.WARM) for i in range(4)],
            snapshot(),
        )
        self.assertEqual(len(decision.placements), 1)

    def test_cold_start_estimate_grows_with_distance_from_running(self):
        estimates = {}
        for name, state in (("run", ModelState.RUNNING), ("warm", ModelState.WARM),
                            ("sleep", ModelState.SLEEPING), ("cache", ModelState.CACHED)):
            decision = plan_placement(request(), [slot(name, state=state)], snapshot())
            estimates[name] = decision.placements[0].estimated_start_s
        self.assertLess(estimates["run"], estimates["warm"])
        self.assertLess(estimates["warm"], estimates["sleep"])
        self.assertLess(estimates["sleep"], estimates["cache"])


class OvercommitTests(unittest.TestCase):
    def test_ram_overcommit_is_refused(self):
        decision = plan_placement(
            request(), [slot("huge", state=ModelState.CACHED, ram_mb=60000, vram_mb=None)],
            snapshot(ram_available_mb=8000),
        )
        self.assertFalse(decision.admitted)
        self.assertIn("ram", decision.rejected["huge"].lower())

    def test_reserve_headroom_is_not_spendable(self):
        policy = SchedulerPolicy(ram_reserve_ratio=0.25)
        # 20000 MB free, but a quarter of 64000 total is reserved -> 4000 usable.
        decision = plan_placement(
            request(), [slot("mid", state=ModelState.CACHED, ram_mb=6000, vram_mb=None)],
            snapshot(ram_available_mb=20000, ram_total_mb=64000), policy=policy,
        )
        self.assertFalse(decision.admitted)

    def test_vram_overcommit_is_refused(self):
        decision = plan_placement(
            request(), [slot("big", state=ModelState.CACHED, vram_mb=40000)],
            snapshot(vram_available_mb=8000),
        )
        self.assertFalse(decision.admitted)
        self.assertIn("vram", decision.rejected["big"].lower())

    def test_a_model_needing_a_gpu_is_refused_on_a_cpu_only_host(self):
        decision = plan_placement(
            request(), [slot("gpu-only", state=ModelState.CACHED, vram_mb=8000)],
            snapshot(gpus=()),
        )
        self.assertFalse(decision.admitted)

    def test_cpu_only_model_runs_on_a_gpu_less_host(self):
        decision = plan_placement(
            request(), [slot("cpu", state=ModelState.CACHED, vram_mb=None)], snapshot(gpus=()),
        )
        self.assertTrue(decision.admitted)
        self.assertIsNone(decision.placements[0].device)

    def test_unknown_ram_blocks_a_new_load_but_not_a_running_model(self):
        blind = snapshot(ram_available_mb=None, ram_total_mb=None)
        cold = plan_placement(request(), [slot("cold", state=ModelState.CACHED)], blind)
        self.assertFalse(cold.admitted)
        self.assertIn("unknown", cold.rejected["cold"].lower())

        hot = plan_placement(request(), [slot("hot", state=ModelState.RUNNING)], blind)
        self.assertTrue(hot.admitted)

    def test_disk_pressure_blocks_acquisition_only(self):
        tight = snapshot(disk_free_mb=1000, disk_total_mb=1_000_000)
        acquire = plan_placement(request(), [slot("new", state=ModelState.AVAILABLE)], tight)
        self.assertFalse(acquire.admitted)
        self.assertIn("disk", acquire.rejected["new"].lower())

        cached = plan_placement(request(), [slot("already", state=ModelState.WARM)], tight)
        self.assertTrue(cached.admitted)


class EligibilityTests(unittest.TestCase):
    def test_models_in_non_selectable_states_are_excluded(self):
        for state in (ModelState.DISCOVERED, ModelState.BROKEN, ModelState.QUARANTINED,
                      ModelState.BLOCKED, ModelState.RETIRED):
            with self.subTest(state=state):
                decision = plan_placement(request(), [slot("x", state=state)], snapshot())
                self.assertFalse(decision.admitted)
                self.assertIn("state", decision.rejected["x"].lower())

    def test_missing_capability_is_excluded(self):
        decision = plan_placement(
            request(required_capabilities=frozenset({"vision"})),
            [slot("text-only", state=ModelState.WARM)], snapshot(),
        )
        self.assertFalse(decision.admitted)
        self.assertIn("capabilit", decision.rejected["text-only"].lower())

    def test_context_that_does_not_fit_is_excluded(self):
        decision = plan_placement(
            request(required_context=200_000), [slot("small-ctx", state=ModelState.WARM)], snapshot(),
        )
        self.assertFalse(decision.admitted)
        self.assertIn("context", decision.rejected["small-ctx"].lower())

    def test_paid_model_is_excluded_under_free_only(self):
        paid = RuntimeSlot(model=profile("paid", zero_cost=False), state=ModelState.WARM)
        decision = plan_placement(request(free_only=True), [paid], snapshot())
        self.assertFalse(decision.admitted)
        self.assertIn("zero", decision.rejected["paid"].lower())

    def test_no_paid_fallback_even_when_nothing_else_is_eligible(self):
        paid = RuntimeSlot(model=profile("paid", zero_cost=False, quality=0.99), state=ModelState.RUNNING)
        decision = plan_placement(request(free_only=True), [paid], snapshot())
        self.assertEqual(decision.placements, ())

    def test_secret_work_never_leaves_a_local_runtime(self):
        remote = RuntimeSlot(
            model=profile("hosted", local=False, max_privacy=Privacy.PUBLIC), state=ModelState.RUNNING
        )
        decision = plan_placement(request(privacy=Privacy.SECRET), [remote], snapshot())
        self.assertFalse(decision.admitted)
        self.assertIn("privacy", decision.rejected["hosted"].lower())

    def test_unhealthy_runtime_is_skipped(self):
        broken = RuntimeSlot(model=profile("m"), state=ModelState.RUNNING, runtime_healthy=False)
        decision = plan_placement(request(), [broken], snapshot())
        self.assertFalse(decision.admitted)
        self.assertIn("health", decision.rejected["m"].lower())

    def test_empty_candidate_set_fails_closed_with_a_reason(self):
        decision = plan_placement(request(), [], snapshot())
        self.assertFalse(decision.admitted)
        self.assertTrue(decision.reason)
        self.assertEqual(decision.placements, ())


class WatermarkAdmissionTests(unittest.TestCase):
    def test_pressure_refuses_to_wake_for_background_work(self):
        pressured = snapshot(ram_available_mb=6000, ram_total_mb=64000)
        decision = plan_placement(
            request(priority=Priority.P4_TRAINING),
            [slot("sleepy", state=ModelState.SLEEPING, ram_mb=1000, vram_mb=1000)],
            pressured,
        )
        self.assertEqual(pressured.watermark, Watermark.PRESSURE)
        self.assertFalse(decision.admitted)
        self.assertIn("pressure", decision.reason.lower())

    def test_pressure_still_serves_an_interactive_task_on_a_warm_model(self):
        pressured = snapshot(ram_available_mb=6000, ram_total_mb=64000)
        decision = plan_placement(
            request(priority=Priority.P1_INTERACTIVE),
            [slot("warm", state=ModelState.WARM)], pressured,
        )
        self.assertTrue(decision.admitted)

    def test_critical_admits_only_interactive_work(self):
        critical = snapshot(ram_available_mb=1000, ram_total_mb=64000)
        self.assertEqual(critical.watermark, Watermark.CRITICAL)
        for priority in (Priority.P2_STANDARD, Priority.P3_BACKGROUND_EVAL,
                         Priority.P4_TRAINING, Priority.P5_MAINTENANCE):
            with self.subTest(priority=priority):
                decision = plan_placement(
                    request(priority=priority), [slot("warm", state=ModelState.WARM)], critical
                )
                self.assertFalse(decision.admitted)
                self.assertIn("critical", decision.reason.lower())

    def test_critical_preserves_the_active_user_task(self):
        critical = snapshot(ram_available_mb=1000, ram_total_mb=64000)
        decision = plan_placement(
            request(priority=Priority.P0_INTERACTIVE_CRITICAL),
            [slot("warm", state=ModelState.RUNNING)], critical,
        )
        self.assertTrue(decision.admitted)

    def test_critical_never_raises_it_returns_a_refusal(self):
        critical = snapshot(ram_available_mb=0, ram_total_mb=64000, disk_free_mb=0)
        decision = plan_placement(request(priority=Priority.P5_MAINTENANCE), [], critical)
        self.assertFalse(decision.admitted)
        self.assertIsInstance(decision.reason, str)


class SleepPolicyTests(unittest.TestCase):
    def test_idle_warm_model_is_put_to_sleep(self):
        slots = [RuntimeSlot(model=profile("idle"), state=ModelState.WARM, idle_seconds=3600.0)]
        actions = plan_sleep(slots, snapshot())
        self.assertEqual([action.model_id for action in actions], ["idle"])
        self.assertEqual(actions[0].target, ModelState.SLEEPING)

    def test_recently_used_model_stays_warm(self):
        slots = [RuntimeSlot(model=profile("recent"), state=ModelState.WARM, idle_seconds=5.0)]
        self.assertEqual(plan_sleep(slots, snapshot()), ())

    def test_a_running_model_is_never_slept_from_under_a_task(self):
        slots = [RuntimeSlot(model=profile("busy"), state=ModelState.RUNNING,
                             idle_seconds=99999.0, in_flight=1)]
        self.assertEqual(plan_sleep(slots, snapshot()), ())

    def test_pressure_shortens_the_idle_grace_period(self):
        slots = [RuntimeSlot(model=profile("idle"), state=ModelState.WARM, idle_seconds=90.0)]
        self.assertEqual(plan_sleep(slots, snapshot()), ())
        pressured = snapshot(ram_available_mb=6000, ram_total_mb=64000)
        self.assertEqual([action.model_id for action in plan_sleep(slots, pressured)], ["idle"])

    def test_critical_sheds_every_idle_model_at_once(self):
        slots = [
            RuntimeSlot(model=profile("a"), state=ModelState.WARM, idle_seconds=1.0),
            RuntimeSlot(model=profile("b"), state=ModelState.SLEEPING, idle_seconds=1.0),
            RuntimeSlot(model=profile("c"), state=ModelState.RUNNING, idle_seconds=1.0, in_flight=1),
        ]
        actions = plan_sleep(slots, snapshot(ram_available_mb=500, ram_total_mb=64000))
        by_model = {action.model_id: action.target for action in actions}
        self.assertEqual(by_model["a"], ModelState.SLEEPING)
        self.assertEqual(by_model["b"], ModelState.CACHED)
        self.assertNotIn("c", by_model)

    def test_every_sleep_action_is_a_legal_lifecycle_transition(self):
        from AI_SKILL_LIBRARY.v4.local_runtime.lifecycle import ModelLifecycle
        slots = [
            RuntimeSlot(model=profile("a"), state=ModelState.WARM, idle_seconds=1.0),
            RuntimeSlot(model=profile("b"), state=ModelState.SLEEPING, idle_seconds=1.0),
        ]
        for action in plan_sleep(slots, snapshot(ram_available_mb=500, ram_total_mb=64000)):
            lifecycle = ModelLifecycle(action.model_id, state=action.source)
            lifecycle.transition(action.target, reason=action.reason)


class PriorityQueueTests(unittest.TestCase):
    def test_priority_order_is_p0_first(self):
        self.assertEqual(
            sorted(Priority, key=lambda p: p.rank)[0], Priority.P0_INTERACTIVE_CRITICAL
        )
        self.assertEqual(sorted(Priority, key=lambda p: p.rank)[-1], Priority.P5_MAINTENANCE)

    def test_interactive_priorities_are_not_preemptible(self):
        for priority in (Priority.P0_INTERACTIVE_CRITICAL, Priority.P1_INTERACTIVE,
                         Priority.P2_STANDARD):
            self.assertFalse(priority.preemptible, priority)

    def test_background_work_is_preemptible(self):
        for priority in (Priority.P3_BACKGROUND_EVAL, Priority.P4_TRAINING,
                         Priority.P5_MAINTENANCE):
            self.assertTrue(priority.preemptible, priority)


if __name__ == "__main__":
    unittest.main()
