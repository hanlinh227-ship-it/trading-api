import unittest

from AI_SKILL_LIBRARY.v4.local_runtime.federation import ServeOutcome, serve, wake_transitions
from AI_SKILL_LIBRARY.v4.local_runtime.lifecycle import ModelLifecycle, ModelState
from AI_SKILL_LIBRARY.v4.local_runtime.resources import GpuDevice, GpuVendor, HostFacts, ResourceSnapshot
from AI_SKILL_LIBRARY.v4.local_runtime.runtime import (
    InvocationStatus,
    ModelRuntimeAdapter,
    RegistryClaim,
    RuntimeCapability,
    RuntimeMesh,
)
from AI_SKILL_LIBRARY.v4.local_runtime.scheduler import (
    ModelProfile,
    PlacementAction,
    Priority,
    QualityTier,
    RuntimeSlot,
    TaskRequest,
)

HOST = HostFacts(system="Linux", machine="x86_64", release="6.8.0")


def snapshot(ram_available_mb=32_000, **kwargs):
    kwargs.setdefault("disk_free_mb", 500_000)
    return ResourceSnapshot(
        host=HOST, cpu_logical=16, cpu_physical=8, ram_total_mb=64_000,
        ram_available_mb=ram_available_mb, disk_total_mb=1_000_000,
        gpus=(GpuDevice(index=0, vendor=GpuVendor.NVIDIA, name="RTX 4090",
                        vram_total_mb=24_000, vram_available_mb=20_000),),
        **kwargs,
    )


def slot(model_id, state=ModelState.WARM, **kwargs):
    profile = ModelProfile(
        model_id=model_id, ram_mb=8_000, vram_mb=8_000, disk_mb=16_000,
        runtime="llama.cpp", context_limit=32_768, quality=0.8,
        capabilities=frozenset({"text"}),
    )
    return RuntimeSlot(model=profile, state=state, **kwargs)


def claims(*model_ids):
    return {
        model_id: RegistryClaim(model_id=model_id, context_limit=32_768,
                                modalities=frozenset({"text"}), tool_support=True)
        for model_id in model_ids
    }


class Adapter(ModelRuntimeAdapter):
    def __init__(self, name="llama.cpp", loaded=("m1",), raises=None):
        self._name, self._loaded, self._raises = name, tuple(loaded), raises

    @property
    def name(self):
        return self._name

    def probe(self):
        return RuntimeCapability(
            runtime=self._name, runtime_version="b4200", loaded_models=self._loaded,
            available_memory_mb=20_000, context_limit=32_768, modalities=frozenset({"text"}),
            tool_support=True, quantizations=frozenset({"Q4_K_M"}), healthy=True,
            latency_p50_ms=100.0,
        )

    def execute(self, task_contract, capability):
        if self._raises:
            raise self._raises
        return {"text": f"answer for {task_contract.task_id}"}


class EndToEndTests(unittest.TestCase):
    def test_a_task_is_placed_invoked_and_answered(self):
        outcome = serve(
            TaskRequest(task_id="t-1", required_capabilities=frozenset({"text"})),
            [slot("m1")], snapshot(), RuntimeMesh([Adapter()]), claims("m1"), now=0.0,
        )
        self.assertTrue(outcome.ok)
        self.assertEqual(outcome.model_id, "m1")
        self.assertEqual(outcome.runtime, "llama.cpp")
        self.assertEqual(outcome.output, {"text": "answer for t-1"})

    def test_a_sleeping_model_is_woken_for_the_task(self):
        outcome = serve(
            TaskRequest(task_id="t-2", required_capabilities=frozenset({"text"})),
            [slot("m1", state=ModelState.SLEEPING)], snapshot(),
            RuntimeMesh([Adapter(loaded=())]), claims("m1"), now=0.0,
        )
        self.assertTrue(outcome.ok)
        self.assertEqual(outcome.action, PlacementAction.WAKE)

    def test_the_wake_path_is_a_legal_lifecycle_walk(self):
        outcome = serve(
            TaskRequest(task_id="t-3", required_capabilities=frozenset({"text"})),
            [slot("m1", state=ModelState.CACHED)], snapshot(),
            RuntimeMesh([Adapter(loaded=())]), claims("m1"), now=0.0,
        )
        lifecycle = ModelLifecycle("m1", state=ModelState.CACHED)
        for _source, target in wake_transitions(
            type("P", (), {"action": outcome.action})()
        ):
            lifecycle.transition(target, reason="wake path")
        self.assertIs(lifecycle.state, ModelState.RUNNING)

    def test_every_placement_action_maps_to_a_legal_lifecycle_walk(self):
        starts = {
            PlacementAction.SERVE_RUNNING: ModelState.RUNNING,
            PlacementAction.USE_WARM: ModelState.WARM,
            PlacementAction.WAKE: ModelState.SLEEPING,
            PlacementAction.LOAD_FROM_CACHE: ModelState.CACHED,
            PlacementAction.ACQUIRE: ModelState.AVAILABLE,
        }
        for action, start in starts.items():
            with self.subTest(action=action):
                lifecycle = ModelLifecycle("m", state=start)
                for _source, target in wake_transitions(type("P", (), {"action": action})()):
                    lifecycle.transition(target, reason="walk")

    def test_housekeeping_is_reported_alongside_the_answer(self):
        outcome = serve(
            TaskRequest(task_id="t-4", required_capabilities=frozenset({"text"})),
            [slot("m1"), slot("idle", state=ModelState.WARM, idle_seconds=99_999.0)],
            snapshot(), RuntimeMesh([Adapter()]), claims("m1", "idle"), now=0.0,
        )
        self.assertTrue(outcome.ok)
        self.assertIn("idle", [action.model_id for action in outcome.sleep_actions])

    def test_a_model_without_a_registry_claim_is_refused_not_invented(self):
        outcome = serve(
            TaskRequest(task_id="t-5", required_capabilities=frozenset({"text"})),
            [slot("m1")], snapshot(), RuntimeMesh([Adapter()]), {}, now=0.0,
        )
        self.assertFalse(outcome.admitted)
        self.assertIn("claim", outcome.reason)


class BackgroundYieldTests(unittest.TestCase):
    def test_background_work_stands_down_under_pressure(self):
        pressured = snapshot(ram_available_mb=6_000)
        outcome = serve(
            TaskRequest(task_id="train", priority=Priority.P4_TRAINING,
                        required_capabilities=frozenset({"text"})),
            [slot("m1")], pressured, RuntimeMesh([Adapter()]), claims("m1"), now=0.0,
        )
        self.assertFalse(outcome.admitted)
        self.assertIn("stands down", outcome.reason)

    def test_the_interactive_task_still_runs_at_the_same_pressure(self):
        pressured = snapshot(ram_available_mb=6_000)
        outcome = serve(
            TaskRequest(task_id="chat", priority=Priority.P1_INTERACTIVE,
                        required_capabilities=frozenset({"text"})),
            [slot("m1")], pressured, RuntimeMesh([Adapter()]), claims("m1"), now=0.0,
        )
        self.assertTrue(outcome.ok)

    def test_at_critical_only_the_user_task_survives(self):
        critical = snapshot(ram_available_mb=800)
        interactive = serve(
            TaskRequest(task_id="chat", priority=Priority.P0_INTERACTIVE_CRITICAL,
                        required_capabilities=frozenset({"text"})),
            [slot("m1", state=ModelState.RUNNING)], critical,
            RuntimeMesh([Adapter()]), claims("m1"), now=0.0,
        )
        self.assertTrue(interactive.ok)
        for priority in (Priority.P3_BACKGROUND_EVAL, Priority.P4_TRAINING, Priority.P5_MAINTENANCE):
            with self.subTest(priority=priority):
                outcome = serve(
                    TaskRequest(task_id="bg", priority=priority,
                                required_capabilities=frozenset({"text"})),
                    [slot("m1", state=ModelState.RUNNING)], critical,
                    RuntimeMesh([Adapter()]), claims("m1"), now=0.0,
                )
                self.assertFalse(outcome.admitted)


class ContainmentTests(unittest.TestCase):
    def test_a_runtime_crash_is_an_outcome_not_an_exception(self):
        outcome = serve(
            TaskRequest(task_id="t", required_capabilities=frozenset({"text"})),
            [slot("m1")], snapshot(),
            RuntimeMesh([Adapter(raises=RuntimeError("segfault"))]), claims("m1"), now=0.0,
        )
        self.assertEqual(outcome.status, InvocationStatus.FAILED)
        self.assertFalse(outcome.degraded)

    def test_a_subsystem_that_throws_degrades_this_task_and_nothing_else(self):
        class ExplodingMesh(RuntimeMesh):
            def invoke(self, *args, **kwargs):
                raise AssertionError("runtime plane bug")

        outcome = serve(
            TaskRequest(task_id="t", required_capabilities=frozenset({"text"})),
            [slot("m1")], snapshot(), ExplodingMesh([Adapter()]), claims("m1"), now=0.0,
        )
        self.assertTrue(outcome.degraded)
        self.assertFalse(outcome.admitted)
        self.assertIn("degraded", outcome.reason)

    def test_a_malformed_snapshot_does_not_escape_the_plane(self):
        outcome = serve(
            TaskRequest(task_id="t", required_capabilities=frozenset({"text"})),
            [slot("m1")], object(), RuntimeMesh([Adapter()]), claims("m1"), now=0.0,
        )
        self.assertTrue(outcome.degraded)
        self.assertIsInstance(outcome, ServeOutcome)

    def test_no_internet_and_no_worker_is_a_refusal_with_a_reason(self):
        outcome = serve(
            TaskRequest(task_id="t", required_capabilities=frozenset({"text"})),
            [slot("m1")], snapshot(), RuntimeMesh([]), claims("m1"), now=0.0,
        )
        self.assertEqual(outcome.status, InvocationStatus.NO_RUNTIME)
        self.assertTrue(outcome.reason)

    def test_no_eligible_free_only_candidate_never_falls_back_to_paid(self):
        paid = RuntimeSlot(
            model=ModelProfile(
                model_id="paid", ram_mb=1_000, vram_mb=None, disk_mb=1_000, runtime="hosted",
                context_limit=32_768, quality=0.99, capabilities=frozenset({"text"}),
                zero_cost=False,
            ),
            state=ModelState.RUNNING,
        )
        outcome = serve(
            TaskRequest(task_id="t", free_only=True, required_capabilities=frozenset({"text"})),
            [paid], snapshot(), RuntimeMesh([Adapter()]), claims("paid"), now=0.0,
        )
        self.assertFalse(outcome.admitted)
        self.assertIsNone(outcome.output)


class AuthorityInvariantTests(unittest.TestCase):
    """Section 16: nothing in this plane may become a second router or brain."""

    def test_no_module_exports_a_parallel_router_or_brain(self):
        import pkgutil

        import AI_SKILL_LIBRARY.v4.local_runtime as package

        forbidden = ("parallel_router", "ParallelRouter", "parallel_brain", "ParallelBrain",
                     "TaskRouter", "route_task")
        for info in pkgutil.iter_modules(package.__path__):
            module = __import__(f"{package.__name__}.{info.name}", fromlist=["*"])
            for name in forbidden:
                with self.subTest(module=info.name, symbol=name):
                    self.assertFalse(hasattr(module, name))

    def test_every_authority_bearing_class_declares_false(self):
        from AI_SKILL_LIBRARY.v4.local_runtime.workers import WorkerRecord, WorkerRegistry

        for klass in (RuntimeMesh, WorkerRegistry, WorkerRecord):
            for claim in ("routing_authority", "reasoning_authority", "memory_authority"):
                with self.subTest(klass=klass.__name__, claim=claim):
                    self.assertFalse(getattr(klass, claim))

    def test_the_plane_declares_no_model_selection_authority(self):
        from AI_SKILL_LIBRARY.v4.local_runtime.workers import WorkerRegistry

        self.assertFalse(RuntimeMesh.model_selection_authority)
        self.assertFalse(WorkerRegistry.model_selection_authority)

    def test_the_stable_brain_does_not_depend_on_this_plane(self):
        import json
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        checkpoint = json.loads(
            (root / "AI_SKILL_LIBRARY/checkpoint.json").read_text(encoding="utf-8")
        )
        self.assertFalse(
            [key for key, value in checkpoint.items() if isinstance(value, str) and "local_runtime" in value],
            "the canonical checkpoint must not require the local runtime plane",
        )


if __name__ == "__main__":
    unittest.main()
