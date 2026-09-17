import unittest

from AI_SKILL_LIBRARY.v4.local_runtime.resources import (
    GpuDevice,
    GpuVendor,
    HostFacts,
    ResourceSnapshot,
)
from AI_SKILL_LIBRARY.v4.local_runtime.scheduler import Privacy
from AI_SKILL_LIBRARY.v4.local_runtime.workers import (
    Attestation,
    WorkerError,
    WorkerRecord,
    WorkerRegistry,
    WorkerRequirement,
    WorkerState,
    valid_worker_targets,
)


def resources(system="Linux", machine="x86_64", gpus=True, ram_available_mb=32_000):
    devices = ()
    if gpus:
        devices = (GpuDevice(index=0, vendor=GpuVendor.NVIDIA, name="RTX 4090",
                             vram_total_mb=24_000, vram_available_mb=20_000),)
    return ResourceSnapshot(
        host=HostFacts(system=system, machine=machine, release="1"),
        cpu_logical=16, cpu_physical=8, ram_total_mb=64_000,
        ram_available_mb=ram_available_mb, disk_total_mb=1_000_000,
        disk_free_mb=500_000, gpus=devices,
    )


def record(worker_id="w-1", **kwargs):
    kwargs.setdefault("endpoint", "https://gpu-box.lan:8443")
    kwargs.setdefault("resources", resources())
    kwargs.setdefault("runtimes", frozenset({"llama.cpp"}))
    kwargs.setdefault("state", WorkerState.REGISTERED)
    return WorkerRecord(worker_id=worker_id, **kwargs)


def attestation(**kwargs):
    kwargs.setdefault("zero_cost_only", True)
    kwargs.setdefault("max_privacy", Privacy.INTERNAL)
    kwargs.setdefault("shell_execution", False)
    kwargs.setdefault("financial_execution", False)
    kwargs.setdefault("credential_storage", False)
    return Attestation(**kwargs)


class AuthorityInvariantTests(unittest.TestCase):
    def test_a_worker_never_holds_routing_authority(self):
        self.assertFalse(record().routing_authority)
        self.assertFalse(record().reasoning_authority)
        self.assertFalse(record().memory_authority)

    def test_authority_cannot_be_set_on_a_worker(self):
        with self.assertRaises(TypeError):
            WorkerRecord(worker_id="w", endpoint="https://x", resources=resources(),
                         runtimes=frozenset(), routing_authority=True)

    def test_the_registry_itself_holds_no_authority(self):
        registry = WorkerRegistry()
        self.assertFalse(registry.routing_authority)
        self.assertFalse(registry.model_selection_authority)


class AttestationTests(unittest.TestCase):
    def test_a_compliant_attestation_passes(self):
        self.assertEqual(attestation().refusals(), ())

    def test_shell_execution_is_refused_by_default(self):
        refusals = attestation(shell_execution=True).refusals()
        self.assertTrue(any("shell" in r for r in refusals), refusals)

    def test_financial_execution_is_always_refused(self):
        refusals = attestation(financial_execution=True).refusals()
        self.assertTrue(any("financial" in r for r in refusals), refusals)

    def test_credential_storage_is_refused(self):
        refusals = attestation(credential_storage=True).refusals()
        self.assertTrue(any("credential" in r for r in refusals), refusals)

    def test_a_worker_that_is_not_zero_cost_only_is_refused(self):
        refusals = attestation(zero_cost_only=False).refusals()
        self.assertTrue(any("zero" in r for r in refusals), refusals)

    def test_a_worker_may_not_widen_its_own_privacy_ceiling(self):
        worker = attestation(max_privacy=Privacy.SECRET)
        self.assertTrue(any("privacy" in r for r in worker.refusals(ceiling=Privacy.INTERNAL)))


class WorkerLifecycleTests(unittest.TestCase):
    def test_the_registration_path(self):
        registry = WorkerRegistry()
        worker = registry.register(record())
        self.assertEqual(worker.state, WorkerState.REGISTERED)
        registry.attest("w-1", attestation())
        self.assertEqual(registry.get("w-1").state, WorkerState.ATTESTED)
        registry.healthcheck("w-1", healthy=True, now=0.0)
        self.assertEqual(registry.get("w-1").state, WorkerState.ELIGIBLE)
        registry.activate("w-1")
        self.assertEqual(registry.get("w-1").state, WorkerState.ACTIVE)

    def test_a_failed_attestation_leaves_the_worker_unusable(self):
        registry = WorkerRegistry()
        registry.register(record())
        result = registry.attest("w-1", attestation(financial_execution=True))
        self.assertFalse(result.accepted)
        self.assertEqual(registry.get("w-1").state, WorkerState.REGISTERED)
        self.assertEqual(registry.eligible(WorkerRequirement()), ())

    def test_a_worker_cannot_skip_attestation(self):
        registry = WorkerRegistry()
        registry.register(record())
        with self.assertRaises(WorkerError):
            registry.activate("w-1")

    def test_a_failed_healthcheck_degrades_an_active_worker(self):
        registry = WorkerRegistry()
        registry.register(record())
        registry.attest("w-1", attestation())
        registry.healthcheck("w-1", healthy=True, now=0.0)
        registry.activate("w-1")
        registry.healthcheck("w-1", healthy=False, now=1.0)
        self.assertEqual(registry.get("w-1").state, WorkerState.DEGRADED)

    def test_a_worker_that_disappears_goes_offline(self):
        registry = WorkerRegistry()
        registry.register(record())
        registry.attest("w-1", attestation())
        registry.healthcheck("w-1", healthy=True, now=0.0)
        registry.activate("w-1")
        registry.expire_stale(now=10_000.0, timeout_seconds=60.0)
        self.assertEqual(registry.get("w-1").state, WorkerState.OFFLINE)

    def test_an_offline_worker_can_rejoin_through_healthcheck(self):
        registry = WorkerRegistry()
        registry.register(record())
        registry.attest("w-1", attestation())
        registry.healthcheck("w-1", healthy=True, now=0.0)
        registry.activate("w-1")
        registry.expire_stale(now=10_000.0, timeout_seconds=60.0)
        registry.healthcheck("w-1", healthy=True, now=10_001.0)
        self.assertEqual(registry.get("w-1").state, WorkerState.ELIGIBLE)

    def test_illegal_worker_transitions_are_rejected(self):
        self.assertNotIn(WorkerState.ACTIVE, valid_worker_targets(WorkerState.REGISTERED))
        self.assertNotIn(WorkerState.ELIGIBLE, valid_worker_targets(WorkerState.REGISTERED))

    def test_losing_a_worker_never_raises_into_the_caller(self):
        registry = WorkerRegistry()
        registry.expire_stale(now=1.0, timeout_seconds=1.0)
        self.assertEqual(registry.eligible(WorkerRequirement()), ())


class EligibilityTests(unittest.TestCase):
    def _active(self, registry, worker):
        registry.register(worker)
        registry.attest(worker.worker_id, attestation())
        registry.healthcheck(worker.worker_id, healthy=True, now=0.0)
        registry.activate(worker.worker_id)
        return registry

    def test_only_active_and_eligible_workers_are_offered(self):
        registry = WorkerRegistry()
        self._active(registry, record("live"))
        registry.register(record("fresh"))
        self.assertEqual([w.worker_id for w in registry.eligible(WorkerRequirement())], ["live"])

    def test_a_worker_without_the_runtime_is_not_offered(self):
        registry = WorkerRegistry()
        self._active(registry, record("cpu-box", runtimes=frozenset({"llama.cpp"})))
        self.assertEqual(registry.eligible(WorkerRequirement(runtime="vllm")), ())

    def test_a_worker_without_the_vram_is_not_offered(self):
        registry = WorkerRegistry()
        self._active(registry, record("small", resources=resources(gpus=False)))
        self.assertEqual(registry.eligible(WorkerRequirement(vram_mb=8_000)), ())

    def test_a_worker_without_the_ram_is_not_offered(self):
        registry = WorkerRegistry()
        self._active(registry, record("tight", resources=resources(ram_available_mb=2_000)))
        self.assertEqual(registry.eligible(WorkerRequirement(ram_mb=32_000)), ())

    def test_confidential_work_is_not_offered_to_a_worker_below_the_ceiling(self):
        registry = WorkerRegistry()
        self._active(registry, record("public-box"))
        self.assertEqual(registry.eligible(WorkerRequirement(privacy=Privacy.SECRET)), ())

    def test_no_eligible_free_only_worker_is_an_empty_result_not_a_paid_one(self):
        registry = WorkerRegistry()
        registry.register(record("paid-box"))
        registry.attest("paid-box", attestation(zero_cost_only=False))
        self.assertEqual(registry.eligible(WorkerRequirement()), ())

    def test_all_workers_unavailable_is_an_empty_result(self):
        registry = WorkerRegistry()
        self._active(registry, record("a"))
        self._active(registry, record("b"))
        registry.expire_stale(now=10_000.0, timeout_seconds=60.0)
        self.assertEqual(registry.eligible(WorkerRequirement()), ())


class CrossMachineTests(unittest.TestCase):
    def test_workers_are_addressed_by_endpoint_not_by_localhost(self):
        registry = WorkerRegistry()
        for worker_id, endpoint, system, machine in (
            ("win-gpu", "https://win-gpu.lan:8443", "Windows", "AMD64"),
            ("mac-studio", "https://mac.lan:8443", "Darwin", "arm64"),
            ("linux-gpu", "https://gpu01.internal:8443", "Linux", "x86_64"),
            ("cloud-free", "https://worker.example.invalid", "Linux", "x86_64"),
        ):
            registry.register(record(worker_id, endpoint=endpoint,
                                     resources=resources(system=system, machine=machine)))
        self.assertEqual(len(registry.all()), 4)
        self.assertTrue(all("localhost" not in w.endpoint for w in registry.all()))

    def test_an_endpoint_is_required(self):
        with self.assertRaises(WorkerError):
            WorkerRegistry().register(record("nowhere", endpoint=""))

    def test_a_plaintext_remote_endpoint_is_refused(self):
        with self.assertRaises(WorkerError):
            WorkerRegistry().register(record("insecure", endpoint="http://gpu-box.lan:8000"))

    def test_loopback_http_is_allowed_for_a_same_machine_worker(self):
        registry = WorkerRegistry()
        registry.register(record("local", endpoint="http://127.0.0.1:11434"))
        self.assertEqual(registry.get("local").worker_id, "local")

    def test_each_worker_reports_its_own_platform_and_resources(self):
        registry = WorkerRegistry()
        registry.register(record("mac", resources=resources(system="Darwin", machine="arm64", gpus=False)))
        worker = registry.get("mac")
        self.assertEqual(worker.resources.host.system, "Darwin")
        self.assertTrue(worker.resources.is_apple_silicon)

    def test_registry_report_is_json_safe(self):
        import json
        registry = WorkerRegistry()
        registry.register(record())
        payload = registry.to_dict(now=0.0)
        self.assertEqual(json.loads(json.dumps(payload))["w-1"]["state"], "REGISTERED")
        self.assertFalse(payload["w-1"]["routing_authority"])


if __name__ == "__main__":
    unittest.main()
