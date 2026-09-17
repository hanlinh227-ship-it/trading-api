"""The invariants the Free Worker Mesh exists to hold.

Each test constructs the condition that would break something and requires the
mesh to refuse, rather than reading the code and agreeing with it.
"""

import unittest

from AI_SKILL_LIBRARY.v4.local_runtime.free_worker_mesh import (
    CAPABILITY_TAGS,
    ExecutionMode,
    FreeWorkerMesh,
    MeshOutcome,
    MeshRequest,
)
from AI_SKILL_LIBRARY.v4.local_runtime.providers import (
    CostClass,
    ExecutionType,
    ModelOffering,
    OfferingMatch,
    ProviderRecord,
    ProviderRegistry,
)
from AI_SKILL_LIBRARY.v4.local_runtime.resilience import FailureKind
from AI_SKILL_LIBRARY.v4.local_runtime.resources import HostFacts, ResourceSnapshot
from AI_SKILL_LIBRARY.v4.local_runtime.scheduler import Privacy
from AI_SKILL_LIBRARY.v4.local_runtime.workers import (
    Attestation,
    WorkerClass,
    WorkerRecord,
    WorkerRegistry,
    WorkerState,
)

NOW = 1_000_000.0
MODEL = "Qwen/Qwen3-Coder-30B-A3B-Instruct"


def snapshot(ram=64_000, disk=500_000):
    return ResourceSnapshot(
        host=HostFacts(system="Darwin", machine="arm64", release="24"),
        cpu_logical=12, cpu_physical=12, ram_total_mb=ram, ram_available_mb=ram,
        disk_total_mb=disk * 2, disk_free_mb=disk, gpus=(),
    )


def join(registry, worker_id, *, worker_class=WorkerClass.OWNED_MAC,
         privacy=Privacy.CONFIDENTIAL, now=NOW, healthy=True, **fields):
    """Register, attest and heartbeat a worker - what enrolling actually is."""
    defaults = dict(
        worker_id=worker_id, endpoint="https://worker.invalid",
        resources=snapshot(), runtimes=frozenset({"llama.cpp"}),
        worker_class=worker_class,
        supported_formats=frozenset({"gguf"}),
        supported_quantizations=frozenset({"Q4_K_M"}),
        supported_model_families=frozenset({"qwen3"}),
        measured_capabilities=frozenset({"coding"}),
    )
    defaults.update(fields)
    registry.register(WorkerRecord(**defaults))
    registry.attest(worker_id, Attestation(zero_cost_only=True, max_privacy=privacy))
    registry.healthcheck(worker_id, healthy=healthy, now=now)
    return registry.get(worker_id)


def request(**fields):
    defaults = dict(model_id=MODEL, capability="coding", ram_mb=8_000,
                    runtime="llama.cpp", artifact_format="gguf",
                    quantization="Q4_K_M", model_family="qwen3")
    defaults.update(fields)
    return MeshRequest(**defaults)


def hosted_provider(match=OfferingMatch.CAPABILITY, free=True):
    offering = ModelOffering(
        requested_model_id=MODEL, match=match,
        provider_model_id="@cf/qwen/qwen2.5-coder-32b-instruct",
        free_tier_eligible=free,
        substitution_reason=("a different code-specialised Qwen"
                             if match is OfferingMatch.CAPABILITY else None),
    )
    return ProviderRecord(
        provider_id="cloudflare_workers_ai",
        execution_type=ExecutionType.SERVERLESS_HOSTED_CATALOG,
        cost_class=CostClass.FREE_HARD_STOP,
        custom_weights=False, authentication_required=True,
        credential_available_here=True, operator_authorized=True,
        offerings=(offering,),
    )


class AuthorityTests(unittest.TestCase):
    def test_the_mesh_holds_no_authority(self):
        mesh = FreeWorkerMesh(WorkerRegistry())
        for flag in ("routing_authority", "reasoning_authority", "memory_authority",
                     "model_selection_authority", "admission_authority",
                     "evidence_authority"):
            self.assertFalse(getattr(mesh, flag), flag)

    def test_a_worker_cannot_claim_routing_authority(self):
        with self.assertRaises(TypeError):
            WorkerRecord(worker_id="w", endpoint="https://x.invalid",
                         resources=snapshot(), runtimes=frozenset(),
                         routing_authority=True)

    def test_a_worker_cannot_claim_model_selection_authority(self):
        with self.assertRaises(TypeError):
            WorkerRecord(worker_id="w", endpoint="https://x.invalid",
                         resources=snapshot(), runtimes=frozenset(),
                         model_selection_authority=True)

    def test_every_placement_restates_that_it_decided_nothing(self):
        registry = WorkerRegistry()
        join(registry, "mac")
        row = FreeWorkerMesh(registry).place(request(), now=NOW).to_dict()
        self.assertFalse(row["routing_authority"])
        self.assertFalse(row["model_selection_authority"])
        self.assertFalse(row["admission_authority"])


class SelectionTests(unittest.TestCase):
    def test_a_healthy_owned_worker_runs_the_exact_model(self):
        registry = WorkerRegistry()
        join(registry, "mac")
        placement = FreeWorkerMesh(registry).place(request(), now=NOW)
        self.assertIs(placement.outcome, MeshOutcome.EXACT_MODEL_WORKER)
        self.assertIs(placement.execution_mode, ExecutionMode.EXACT_MODEL)
        self.assertTrue(placement.ran_the_requested_model)
        self.assertEqual(placement.executed_model_id, MODEL)

    def test_a_stale_heartbeat_prevents_selection(self):
        # The machine may already be gone. Handing it a job is the failure this
        # exists to prevent, so it is excluded and the reason names the lease.
        registry = WorkerRegistry()
        join(registry, "mac", lease_seconds=60.0)
        placement = FreeWorkerMesh(registry).place(request(), now=NOW + 3600)
        self.assertIs(placement.outcome, MeshOutcome.CAPABILITY_TEMPORARILY_UNAVAILABLE)
        self.assertIn("lease", " ".join(placement.refusals["mac"]))

    def test_insufficient_ram_prevents_placement(self):
        registry = WorkerRegistry()
        join(registry, "mac", resources=snapshot(ram=4_000))
        placement = FreeWorkerMesh(registry).place(request(ram_mb=37_200), now=NOW)
        self.assertIs(placement.outcome, MeshOutcome.CAPABILITY_TEMPORARILY_UNAVAILABLE)
        self.assertIn("37200", " ".join(placement.refusals["mac"]))

    def test_insufficient_disk_prevents_acquisition(self):
        registry = WorkerRegistry()
        join(registry, "mac", resources=snapshot(disk=500))
        placement = FreeWorkerMesh(registry).place(request(disk_mb=20_000), now=NOW)
        self.assertIs(placement.outcome, MeshOutcome.CAPABILITY_TEMPORARILY_UNAVAILABLE)
        self.assertIn("disk", " ".join(placement.refusals["mac"]))

    def test_an_incompatible_backend_prevents_placement(self):
        registry = WorkerRegistry()
        join(registry, "mac", runtimes=frozenset({"mlx"}))
        placement = FreeWorkerMesh(registry).place(request(), now=NOW)
        self.assertIs(placement.outcome, MeshOutcome.CAPABILITY_TEMPORARILY_UNAVAILABLE)
        self.assertIn("llama.cpp", " ".join(placement.refusals["mac"]))

    def test_a_declared_capability_does_not_qualify_a_worker(self):
        # The line between a taxonomy and a claim. The worker advertises the
        # capability and has never been measured for it, so it is not eligible
        # and the refusal says exactly that.
        registry = WorkerRegistry()
        join(registry, "mac", measured_capabilities=frozenset(),
             declared_capabilities=frozenset({"coding"}))
        placement = FreeWorkerMesh(registry).place(request(), now=NOW)
        self.assertIs(placement.outcome, MeshOutcome.CAPABILITY_TEMPORARILY_UNAVAILABLE)
        self.assertIn("advertises but does not qualify", " ".join(placement.refusals["mac"]))

    def test_owned_hardware_is_preferred_over_a_free_third_party_runner(self):
        registry = WorkerRegistry()
        join(registry, "ci", worker_class=WorkerClass.CI_EPHEMERAL, privacy=Privacy.PUBLIC)
        join(registry, "mac", worker_class=WorkerClass.OWNED_MAC)
        placement = FreeWorkerMesh(registry).place(request(privacy=Privacy.PUBLIC), now=NOW)
        self.assertEqual(placement.worker_id, "mac")


class QuotaTests(unittest.TestCase):
    def test_quota_exhaustion_excludes_a_worker_without_retrying_it(self):
        registry = WorkerRegistry()
        join(registry, "free-tier", quota_remaining=0, quota_reset_at=NOW + 3600)
        placement = FreeWorkerMesh(registry).place(request(), now=NOW)
        self.assertIs(placement.outcome, MeshOutcome.CAPABILITY_TEMPORARILY_UNAVAILABLE)
        self.assertIn("clears on reset, not on retry",
                      " ".join(placement.refusals["free-tier"]))

    def test_quota_exhaustion_falls_over_to_another_worker(self):
        registry = WorkerRegistry()
        join(registry, "free-tier", quota_remaining=0, quota_reset_at=NOW + 3600)
        join(registry, "mac")
        placement = FreeWorkerMesh(registry).place(request(), now=NOW)
        self.assertEqual(placement.worker_id, "mac")

    def test_a_reset_window_restores_the_worker(self):
        registry = WorkerRegistry()
        join(registry, "free-tier", quota_remaining=0, quota_reset_at=NOW + 3600,
             lease_seconds=1e9)
        mesh = FreeWorkerMesh(registry)
        self.assertIs(mesh.place(request(), now=NOW).outcome,
                      MeshOutcome.CAPABILITY_TEMPORARILY_UNAVAILABLE)
        # Past the reset the count is merely stale, not a limit.
        self.assertIs(mesh.place(request(), now=NOW + 7200).outcome,
                      MeshOutcome.EXACT_MODEL_WORKER)

    def test_unmetered_is_not_read_as_exhausted(self):
        registry = WorkerRegistry()
        join(registry, "mac", quota_remaining=None)
        self.assertIs(FreeWorkerMesh(registry).place(request(), now=NOW).outcome,
                      MeshOutcome.EXACT_MODEL_WORKER)


class FailoverTests(unittest.TestCase):
    def test_repeated_failures_open_the_circuit_and_the_next_worker_is_used(self):
        registry = WorkerRegistry()
        join(registry, "flaky")
        join(registry, "steady")
        mesh = FreeWorkerMesh(registry, failure_threshold=2)

        first = mesh.place(request(), now=NOW)
        for _ in range(2):
            mesh.record_failure(first.worker_id, FailureKind.TIMEOUT, now=NOW)

        second = mesh.place(request(), now=NOW)
        self.assertNotEqual(second.worker_id, first.worker_id)
        self.assertIs(second.outcome, MeshOutcome.EXACT_MODEL_WORKER)
        self.assertIn("circuit is OPEN", " ".join(second.refusals[first.worker_id]))

    def test_a_breaker_is_never_a_permanent_removal(self):
        registry = WorkerRegistry()
        join(registry, "flaky", lease_seconds=1e9)
        mesh = FreeWorkerMesh(registry, failure_threshold=1, cooldown_seconds=30.0)
        mesh.record_failure("flaky", FailureKind.TIMEOUT, now=NOW)
        self.assertIs(mesh.place(request(), now=NOW).outcome,
                      MeshOutcome.CAPABILITY_TEMPORARILY_UNAVAILABLE)
        # After the cooldown a probe is allowed through, which is how it recovers.
        self.assertIs(mesh.place(request(), now=NOW + 120).outcome,
                      MeshOutcome.EXACT_MODEL_WORKER)

    def test_nothing_available_is_a_truthful_state_not_an_exception(self):
        placement = FreeWorkerMesh(WorkerRegistry()).place(request(), now=NOW)
        self.assertIs(placement.outcome, MeshOutcome.CAPABILITY_TEMPORARILY_UNAVAILABLE)
        self.assertIsNone(placement.executed_model_id)
        self.assertFalse(placement.ran_the_requested_model)
        self.assertTrue(placement.fallback_reason)


class ExactVersusCapabilityTests(unittest.TestCase):
    def test_a_capability_fallback_is_never_reported_as_the_requested_model(self):
        mesh = FreeWorkerMesh(WorkerRegistry(), ProviderRegistry([hosted_provider()]))
        placement = mesh.place(request(allow_capability_fallback=True,
                                       privacy=Privacy.PUBLIC), now=NOW)
        self.assertIs(placement.outcome, MeshOutcome.CAPABILITY_PROVIDER)
        self.assertIs(placement.execution_mode, ExecutionMode.CAPABILITY_PROVIDER)
        self.assertFalse(placement.ran_the_requested_model)
        self.assertNotEqual(placement.executed_model_id, placement.request_model_id)
        self.assertTrue(placement.fallback_reason)

    def test_a_fallback_is_not_taken_unless_the_caller_permitted_one(self):
        mesh = FreeWorkerMesh(WorkerRegistry(), ProviderRegistry([hosted_provider()]))
        placement = mesh.place(request(privacy=Privacy.PUBLIC), now=NOW)
        self.assertIs(placement.outcome, MeshOutcome.CAPABILITY_TEMPORARILY_UNAVAILABLE)
        self.assertIn("did not permit", placement.fallback_reason)

    def test_a_provider_serving_the_same_model_is_still_exact_execution(self):
        mesh = FreeWorkerMesh(
            WorkerRegistry(), ProviderRegistry([hosted_provider(OfferingMatch.EXACT)]))
        placement = mesh.place(request(privacy=Privacy.PUBLIC), now=NOW)
        self.assertIs(placement.execution_mode, ExecutionMode.EXACT_MODEL)
        self.assertTrue(placement.ran_the_requested_model)

    def test_an_exact_worker_beats_a_provider_that_also_serves_it(self):
        registry = WorkerRegistry()
        join(registry, "mac")
        mesh = FreeWorkerMesh(
            registry, ProviderRegistry([hosted_provider(OfferingMatch.EXACT)]))
        placement = mesh.place(request(privacy=Privacy.PUBLIC), now=NOW)
        self.assertEqual(placement.worker_id, "mac")
        self.assertIsNone(placement.provider_id)


class PrivacyTests(unittest.TestCase):
    def test_a_confidential_payload_never_reaches_a_third_party_provider(self):
        # Privacy overrides the cost saving, and the refusal says so rather
        # than reporting the provider as merely unavailable.
        mesh = FreeWorkerMesh(
            WorkerRegistry(), ProviderRegistry([hosted_provider(OfferingMatch.EXACT)]))
        placement = mesh.place(request(privacy=Privacy.CONFIDENTIAL), now=NOW)
        self.assertIs(placement.outcome, MeshOutcome.CAPABILITY_TEMPORARILY_UNAVAILABLE)
        self.assertIn("may not leave hardware the operator controls",
                      " ".join(placement.provider_refusals["cloudflare_workers_ai"]))

    def test_a_third_party_worker_cannot_attest_above_internal(self):
        registry = WorkerRegistry()
        registry.register(WorkerRecord(
            worker_id="serverless", endpoint="https://api.invalid",
            resources=snapshot(), runtimes=frozenset({"api"}),
            worker_class=WorkerClass.SERVERLESS_INFERENCE))
        result = registry.attest(
            "serverless", Attestation(zero_cost_only=True, max_privacy=Privacy.CONFIDENTIAL))
        self.assertFalse(result.accepted)

    def test_an_owned_worker_may_hold_confidential_work(self):
        registry = WorkerRegistry()
        join(registry, "mac", privacy=Privacy.CONFIDENTIAL)
        self.assertIs(FreeWorkerMesh(registry).place(
            request(privacy=Privacy.CONFIDENTIAL), now=NOW).outcome,
            MeshOutcome.EXACT_MODEL_WORKER)


class PaidPathTests(unittest.TestCase):
    def test_a_paid_provider_is_never_selected(self):
        paid = ProviderRecord(
            provider_id="paid-gpu", execution_type=ExecutionType.SERVERLESS_HOSTED_CATALOG,
            cost_class=CostClass.PAID, authentication_required=False,
            operator_authorized=True,
            offerings=(ModelOffering(requested_model_id=MODEL, match=OfferingMatch.EXACT,
                                     provider_model_id="paid/whatever",
                                     free_tier_eligible=True),))
        mesh = FreeWorkerMesh(WorkerRegistry(), ProviderRegistry([paid]))
        placement = mesh.place(request(allow_capability_fallback=True,
                                       privacy=Privacy.PUBLIC), now=NOW)
        self.assertIs(placement.outcome, MeshOutcome.CAPABILITY_TEMPORARILY_UNAVAILABLE)
        self.assertIn("paid", " ".join(placement.provider_refusals["paid-gpu"]).lower())

    def test_a_worker_that_is_not_zero_cost_cannot_attest(self):
        registry = WorkerRegistry()
        registry.register(WorkerRecord(
            worker_id="rented", endpoint="https://gpu.invalid",
            resources=snapshot(), runtimes=frozenset({"llama.cpp"}),
            worker_class=WorkerClass.REMOTE_GPU))
        result = registry.attest(
            "rented", Attestation(zero_cost_only=False, max_privacy=Privacy.PUBLIC))
        self.assertFalse(result.accepted)


class DynamicMembershipTests(unittest.TestCase):
    """An owned device coming and going must cost the caller only capacity."""

    def test_a_device_joins_and_becomes_eligible_with_no_code_change(self):
        registry = WorkerRegistry()
        mesh = FreeWorkerMesh(registry)
        self.assertIs(mesh.place(request(), now=NOW).outcome,
                      MeshOutcome.CAPABILITY_TEMPORARILY_UNAVAILABLE)
        join(registry, "macbook", worker_class=WorkerClass.OWNED_MAC)
        placement = mesh.place(request(), now=NOW)
        self.assertIs(placement.outcome, MeshOutcome.EXACT_MODEL_WORKER)
        self.assertEqual(placement.worker_id, "macbook")

    def test_a_device_leaving_falls_over_rather_than_failing(self):
        registry = WorkerRegistry()
        join(registry, "macbook", lease_seconds=60.0)
        join(registry, "linux-box", worker_class=WorkerClass.OWNED_LINUX,
             lease_seconds=1e9)
        mesh = FreeWorkerMesh(registry)
        self.assertEqual(mesh.place(request(), now=NOW).worker_id, "macbook")
        # The laptop closes. Its lease lapses; nothing else has to happen.
        later = mesh.place(request(), now=NOW + 600)
        self.assertEqual(later.worker_id, "linux-box")

    def test_an_offline_worker_is_not_selected(self):
        registry = WorkerRegistry()
        join(registry, "macbook")
        registry.expire_stale(now=NOW + 1e6, timeout_seconds=60)
        self.assertIs(registry.get("macbook").state, WorkerState.OFFLINE)
        self.assertIs(FreeWorkerMesh(registry).place(request(), now=NOW).outcome,
                      MeshOutcome.CAPABILITY_TEMPORARILY_UNAVAILABLE)


class FutureWaveReadinessTests(unittest.TestCase):
    """Architectural readiness only - nothing here operationalises a later wave."""

    def test_a_future_capability_needs_no_new_scheduler_or_router(self):
        # A Wave 4 requirement is a different string. If this passes, adding
        # vision or OCR later is a measurement, not an architecture change.
        for capability in ("vision", "ocr", "audio_understanding", "long_context"):
            with self.subTest(capability=capability):
                registry = WorkerRegistry()
                join(registry, "gpu-box", worker_class=WorkerClass.REMOTE_GPU,
                     privacy=Privacy.INTERNAL,
                     measured_capabilities=frozenset({capability}))
                placement = FreeWorkerMesh(registry).place(
                    request(capability=capability, privacy=Privacy.INTERNAL), now=NOW)
                self.assertIs(placement.outcome, MeshOutcome.EXACT_MODEL_WORKER)

    def test_an_unmeasured_future_capability_does_not_become_eligible(self):
        registry = WorkerRegistry()
        join(registry, "gpu-box", measured_capabilities=frozenset({"coding"}),
             declared_capabilities=frozenset({"vision"}))
        self.assertIs(FreeWorkerMesh(registry).place(
            request(capability="vision"), now=NOW).outcome,
            MeshOutcome.CAPABILITY_TEMPORARILY_UNAVAILABLE)

    def test_an_unknown_worker_class_needs_no_change_to_anything(self):
        # FUTURE_PROVIDER stands for a worker type nobody has thought of. It is
        # matched on its declared resources and measured capabilities like any
        # other, which is what makes the fabric wave-independent.
        registry = WorkerRegistry()
        join(registry, "something-new", worker_class=WorkerClass.FUTURE_PROVIDER,
             privacy=Privacy.PUBLIC)
        placement = FreeWorkerMesh(registry).place(request(privacy=Privacy.PUBLIC), now=NOW)
        self.assertIs(placement.outcome, MeshOutcome.EXACT_MODEL_WORKER)
        self.assertEqual(placement.worker_class, "FUTURE_PROVIDER")

    def test_the_capability_vocabulary_covers_the_later_waves(self):
        for capability in ("vision", "ocr", "audio_understanding", "speech_to_text",
                           "embedding", "image_generation", "future_multimodal"):
            self.assertIn(capability, CAPABILITY_TAGS)


class SchedulerIntegrationTests(unittest.TestCase):
    """serve() must not run work the mesh placed somewhere else."""

    def _serve(self, **kwargs):
        from AI_SKILL_LIBRARY.v4.local_runtime.federation import serve
        from AI_SKILL_LIBRARY.v4.local_runtime.runtime import RuntimeMesh
        from AI_SKILL_LIBRARY.v4.local_runtime.scheduler import TaskRequest

        return serve(
            TaskRequest(task_id="t1"),
            slots=(), snapshot=snapshot(), mesh=RuntimeMesh(adapters=()), claims={},
            now=NOW, **kwargs)

    def test_a_job_placed_on_another_worker_is_refused_not_localised(self):
        # The failure this guard prevents: a result attributed to a machine
        # that never touched it.
        registry = WorkerRegistry()
        join(registry, "gpu-box", worker_class=WorkerClass.OWNED_LINUX)
        outcome = self._serve(
            worker_mesh=FreeWorkerMesh(registry),
            mesh_request=request(), local_worker_id="ephemeral-local-0")
        self.assertFalse(outcome.admitted)
        self.assertIn("gpu-box", outcome.reason)
        self.assertIn("remote transport is not implemented", outcome.reason)
        self.assertEqual(outcome.worker_placement["worker_id"], "gpu-box")

    def test_a_job_placed_on_a_provider_is_refused_by_the_local_plane(self):
        mesh = FreeWorkerMesh(
            WorkerRegistry(), ProviderRegistry([hosted_provider(OfferingMatch.EXACT)]))
        outcome = self._serve(worker_mesh=mesh,
                              mesh_request=request(privacy=Privacy.PUBLIC),
                              local_worker_id="ephemeral-local-0")
        self.assertFalse(outcome.admitted)
        self.assertIn("provider cloudflare_workers_ai", outcome.reason)

    def test_nothing_available_refuses_before_any_slot_is_considered(self):
        outcome = self._serve(worker_mesh=FreeWorkerMesh(WorkerRegistry()),
                              mesh_request=request(),
                              local_worker_id="ephemeral-local-0")
        self.assertFalse(outcome.admitted)
        self.assertIn("no executor is available", outcome.reason)

    def test_no_mesh_leaves_serve_behaving_exactly_as_before(self):
        # Every prior conclusion drawn from serve() must still hold, or they
        # would all need re-reading.
        without = self._serve()
        self.assertIsNone(without.worker_placement)
        self.assertFalse(without.admitted)  # no slots were offered
        self.assertNotIn("mesh", without.reason.lower())


if __name__ == "__main__":
    unittest.main()
