import unittest

from AI_SKILL_LIBRARY.v4.local_runtime.resilience import BreakerState, FailureKind
from AI_SKILL_LIBRARY.v4.local_runtime.runtime import (
    ADAPTER_TARGETS,
    InvocationStatus,
    ModelRuntimeAdapter,
    RegistryClaim,
    RuntimeCapability,
    RuntimeMesh,
    TaskContract,
    negotiate,
)


def capability(**kwargs):
    kwargs.setdefault("runtime", "llama.cpp")
    kwargs.setdefault("runtime_version", "b4200")
    kwargs.setdefault("loaded_models", ("qwen3-8b",))
    kwargs.setdefault("available_memory_mb", 24_000)
    kwargs.setdefault("context_limit", 32_768)
    kwargs.setdefault("modalities", frozenset({"text"}))
    kwargs.setdefault("tool_support", True)
    kwargs.setdefault("quantizations", frozenset({"Q4_K_M"}))
    kwargs.setdefault("healthy", True)
    kwargs.setdefault("latency_p50_ms", 120.0)
    return RuntimeCapability(**kwargs)


def claim(**kwargs):
    kwargs.setdefault("model_id", "qwen3-8b")
    kwargs.setdefault("context_limit", 131_072)
    kwargs.setdefault("modalities", frozenset({"text", "vision"}))
    kwargs.setdefault("tool_support", True)
    kwargs.setdefault("zero_cost", True)
    return RegistryClaim(**kwargs)


def contract(**kwargs):
    kwargs.setdefault("task_id", "t-1")
    kwargs.setdefault("model_id", "qwen3-8b")
    kwargs.setdefault("payload", {"prompt": "hello"})
    kwargs.setdefault("context_tokens", 4_000)
    kwargs.setdefault("modality", "text")
    return TaskContract(**kwargs)


class FakeAdapter(ModelRuntimeAdapter):
    def __init__(self, name, cap=None, answer=None, raises=None):
        self._name = name
        self._cap = cap or capability(runtime=name)
        self._answer = answer if answer is not None else {"text": f"from {name}"}
        self._raises = raises
        self.calls = 0

    @property
    def name(self):
        return self._name

    def probe(self):
        return self._cap

    def execute(self, task_contract, capability):
        self.calls += 1
        if self._raises:
            raise self._raises
        return self._answer


class AdapterTargetTests(unittest.TestCase):
    def test_the_declared_adapter_targets_are_present(self):
        for target in ("llama.cpp", "ollama", "vllm", "sglang", "transformers", "mlx"):
            self.assertIn(target, ADAPTER_TARGETS)

    def test_no_adapter_target_is_activated_by_default(self):
        self.assertEqual([name for name, spec in ADAPTER_TARGETS.items() if spec["activated"]], [])

    def test_every_target_declares_its_platforms_and_accelerators(self):
        for name, spec in ADAPTER_TARGETS.items():
            with self.subTest(name=name):
                self.assertTrue(spec["platforms"])
                self.assertTrue(spec["accelerators"])
                self.assertIsInstance(spec["activated"], bool)

    def test_no_adapter_target_claims_routing_authority(self):
        for name, spec in ADAPTER_TARGETS.items():
            with self.subTest(name=name):
                self.assertFalse(spec["routing_authority"])


class NegotiationTests(unittest.TestCase):
    def test_observed_context_limit_overrides_an_optimistic_registry_claim(self):
        result = negotiate(contract(context_tokens=4_000), claim(context_limit=131_072),
                           capability(context_limit=32_768))
        self.assertTrue(result.accepted)
        self.assertEqual(result.effective_context_limit, 32_768)

    def test_a_contract_beyond_the_observed_limit_is_refused_even_if_the_registry_allows_it(self):
        result = negotiate(contract(context_tokens=64_000), claim(context_limit=131_072),
                           capability(context_limit=32_768))
        self.assertFalse(result.accepted)
        self.assertIn("context", result.reason.lower())

    def test_a_modality_the_runtime_does_not_have_is_refused(self):
        result = negotiate(contract(modality="vision"), claim(), capability(modalities=frozenset({"text"})))
        self.assertFalse(result.accepted)
        self.assertIn("modality", result.reason.lower())

    def test_tool_support_claimed_but_not_observed_is_refused(self):
        result = negotiate(contract(requires_tools=True), claim(tool_support=True),
                           capability(tool_support=False))
        self.assertFalse(result.accepted)
        self.assertIn("tool", result.reason.lower())

    def test_an_unhealthy_runtime_is_refused(self):
        result = negotiate(contract(), claim(), capability(healthy=False))
        self.assertFalse(result.accepted)
        self.assertIn("health", result.reason.lower())

    def test_a_paid_model_is_refused_under_free_only(self):
        result = negotiate(contract(free_only=True), claim(zero_cost=False), capability())
        self.assertFalse(result.accepted)
        self.assertIn("zero", result.reason.lower())

    def test_negotiation_records_where_observation_contradicted_the_registry(self):
        result = negotiate(contract(), claim(context_limit=131_072, modalities=frozenset({"text", "vision"})),
                           capability(context_limit=32_768, modalities=frozenset({"text"})))
        self.assertTrue(result.accepted)
        self.assertTrue(result.downgrades)
        self.assertTrue(any("context" in note for note in result.downgrades))

    def test_a_loaded_model_is_reported_as_warm(self):
        self.assertTrue(negotiate(contract(), claim(), capability(loaded_models=("qwen3-8b",))).warm)
        self.assertFalse(negotiate(contract(), claim(), capability(loaded_models=())).warm)


class MeshInvocationTests(unittest.TestCase):
    def test_a_healthy_adapter_serves_the_contract(self):
        mesh = RuntimeMesh([FakeAdapter("llama.cpp")])
        result = mesh.invoke(contract(), claim(), now=0.0)
        self.assertEqual(result.status, InvocationStatus.OK)
        self.assertEqual(result.output, {"text": "from llama.cpp"})
        self.assertEqual(result.runtime, "llama.cpp")

    def test_failover_moves_to_the_next_runtime(self):
        broken = FakeAdapter("vllm", raises=ConnectionResetError("reset"))
        healthy = FakeAdapter("llama.cpp")
        mesh = RuntimeMesh([broken, healthy])
        result = mesh.invoke(contract(), claim(), now=0.0)
        self.assertEqual(result.status, InvocationStatus.OK)
        self.assertEqual(result.runtime, "llama.cpp")
        self.assertIn("vllm", result.attempted)

    def test_a_runtime_crash_does_not_propagate(self):
        mesh = RuntimeMesh([FakeAdapter("vllm", raises=RuntimeError("segfault"))])
        result = mesh.invoke(contract(), claim(), now=0.0)
        self.assertEqual(result.status, InvocationStatus.FAILED)
        self.assertTrue(result.reason)

    def test_an_oom_opens_the_breaker_immediately(self):
        adapter = FakeAdapter("vllm", raises=MemoryError("CUDA out of memory"))
        mesh = RuntimeMesh([adapter])
        mesh.invoke(contract(), claim(), now=0.0)
        self.assertEqual(mesh.breaker("vllm").state, BreakerState.OPEN)
        self.assertEqual(mesh.breaker("vllm").last_failure_kind, FailureKind.OOM)

    def test_an_open_breaker_is_skipped_without_a_call(self):
        adapter = FakeAdapter("vllm", raises=MemoryError("oom"))
        mesh = RuntimeMesh([adapter])
        mesh.invoke(contract(), claim(), now=0.0)
        calls_after_first = adapter.calls
        mesh.invoke(contract(), claim(), now=1.0)
        self.assertEqual(adapter.calls, calls_after_first)

    def test_a_probe_that_raises_is_treated_as_an_unhealthy_runtime(self):
        class ExplodingProbe(FakeAdapter):
            def probe(self):
                raise OSError("runtime socket gone")

        mesh = RuntimeMesh([ExplodingProbe("ollama"), FakeAdapter("llama.cpp")])
        result = mesh.invoke(contract(), claim(), now=0.0)
        self.assertEqual(result.status, InvocationStatus.OK)
        self.assertEqual(result.runtime, "llama.cpp")

    def test_all_runtimes_unavailable_is_a_reported_refusal(self):
        mesh = RuntimeMesh([FakeAdapter("a", raises=ConnectionError("down")),
                            FakeAdapter("b", raises=ConnectionError("down"))])
        result = mesh.invoke(contract(), claim(), now=0.0)
        self.assertEqual(result.status, InvocationStatus.FAILED)
        self.assertEqual(sorted(result.attempted), ["a", "b"])

    def test_an_empty_mesh_refuses_rather_than_raising(self):
        result = RuntimeMesh([]).invoke(contract(), claim(), now=0.0)
        self.assertEqual(result.status, InvocationStatus.NO_RUNTIME)

    def test_no_paid_runtime_is_ever_used_as_a_fallback(self):
        paid = FakeAdapter("paid-api")
        mesh = RuntimeMesh([paid])
        result = mesh.invoke(contract(free_only=True), claim(zero_cost=False), now=0.0)
        self.assertEqual(result.status, InvocationStatus.REFUSED)
        self.assertEqual(paid.calls, 0)

    def test_a_refused_negotiation_does_not_trip_the_breaker(self):
        mesh = RuntimeMesh([FakeAdapter("llama.cpp", cap=capability(context_limit=100))])
        mesh.invoke(contract(context_tokens=50_000), claim(), now=0.0)
        self.assertEqual(mesh.breaker("llama.cpp").state, BreakerState.CLOSED)

    def test_a_warm_runtime_is_tried_before_a_cold_one(self):
        cold = FakeAdapter("vllm", cap=capability(runtime="vllm", loaded_models=()))
        warm = FakeAdapter("llama.cpp", cap=capability(runtime="llama.cpp", loaded_models=("qwen3-8b",)))
        mesh = RuntimeMesh([cold, warm])
        result = mesh.invoke(contract(), claim(), now=0.0)
        self.assertEqual(result.runtime, "llama.cpp")
        self.assertEqual(cold.calls, 0)

    def test_health_report_covers_every_adapter(self):
        mesh = RuntimeMesh([FakeAdapter("a"), FakeAdapter("b")])
        report = mesh.health(now=0.0)
        self.assertEqual(sorted(report), ["a", "b"])
        self.assertIn("breaker", report["a"])
        self.assertIn("capability", report["a"])

    def test_mesh_holds_no_routing_authority(self):
        self.assertFalse(RuntimeMesh([]).routing_authority)
        self.assertFalse(RuntimeMesh([]).model_selection_authority)


if __name__ == "__main__":
    unittest.main()
