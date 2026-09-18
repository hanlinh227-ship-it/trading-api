"""The rules the 24/7 operating view exists to enforce.

Each of these is a way the federation could be made to look better than it is.
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from AI_SKILL_LIBRARY.v4.local_runtime.federation_ops import (  # noqa: E402
    DemandLedger,
    FederationHealth,
    FederationOps,
    OperationalResidency,
    RoleHealth,
    RoleObservation,
    ServiceProfile,
    hotness,
)
from AI_SKILL_LIBRARY.v4.local_runtime.free_worker_mesh import FreeWorkerMesh  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.providers import ProviderRegistry  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.resources import detect_resources  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.scheduler import Privacy  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.workers import (  # noqa: E402
    Attestation,
    WorkerClass,
    WorkerRecord,
    WorkerRegistry,
    WorkerState,
)
from AI_SKILL_LIBRARY.v4.tools import role_capability_matrix  # noqa: E402


def _fleet(now: float, *, capabilities: set[str]) -> WorkerRegistry:
    registry = WorkerRegistry()
    registry.register(WorkerRecord(
        worker_id="host-0", endpoint="http://127.0.0.1",
        resources=detect_resources(), runtimes=frozenset({"llama.cpp"}),
        worker_class=WorkerClass.PERSISTENT_LOCAL,
        supported_formats=frozenset({"gguf"}),
        measured_capabilities=frozenset(capabilities)))
    registry.attest("host-0", Attestation(zero_cost_only=True,
                                          max_privacy=Privacy.CONFIDENTIAL))
    registry.healthcheck("host-0", healthy=True, now=now)
    return registry


class AuthorityCannotBeAcquired(unittest.TestCase):
    def test_the_operating_view_has_no_authority_argument(self) -> None:
        for flag in ("routing_authority", "model_selection_authority",
                     "admission_authority", "scheduling_authority",
                     "evidence_authority"):
            with self.subTest(flag=flag):
                with self.assertRaises(TypeError):
                    FederationOps(None, {}, **{flag: True})

    def test_the_flags_are_false(self) -> None:
        ops = FederationOps(FreeWorkerMesh(WorkerRegistry(), ProviderRegistry()), {})
        for flag in ("routing_authority", "model_selection_authority",
                     "admission_authority", "scheduling_authority"):
            self.assertFalse(getattr(ops, flag))


class HotIsEarned(unittest.TestCase):
    def test_a_large_idle_model_is_not_hot(self) -> None:
        score = hotness("big/rare", requests=0, role_criticality="NORMAL",
                        peak_ram_mb=22000.0, cold_load_ms=40000.0, window_requests=50)
        self.assertIsNot(score.recommended, OperationalResidency.HOT)

    def test_a_cheap_busy_critical_model_is_hot(self) -> None:
        score = hotness("small/busy", requests=45, role_criticality="CRITICAL",
                        peak_ram_mb=1500.0, cold_load_ms=9000.0, window_requests=50)
        self.assertIs(score.recommended, OperationalResidency.HOT)

    def test_no_demand_is_stated_rather_than_assumed_away(self) -> None:
        score = hotness("quiet/model", requests=0, role_criticality="HIGH",
                        peak_ram_mb=2000.0, cold_load_ms=5000.0, window_requests=0)
        self.assertTrue(any("no observed demand" in r for r in score.reasons))


class DemandIsObservedNotInvented(unittest.TestCase):
    def test_a_thin_window_says_it_is_thin(self) -> None:
        ledger = DemandLedger()
        now = time.time()
        ledger.record(RoleObservation(
            role_id="REASONING_BRANCH", model_id="m", executor_id="host-0",
            execution_mode="EXACT_MODEL", started_at=now, latency_ms=10.0,
            succeeded=True))
        self.assertEqual(ledger.demand(now=now)["mode"], "OBSERVED_ONLY")

    def test_an_empty_ledger_reports_nothing_rather_than_zero_traffic(self) -> None:
        demand = DemandLedger().demand(now=time.time())
        self.assertEqual(demand["observations"], 0)
        self.assertEqual(demand["per_role"], {})


class HealthIsCoverage(unittest.TestCase):
    def setUp(self) -> None:
        self.now = time.time()
        self.matrix = role_capability_matrix.build(ROOT)

    def test_no_worker_is_not_healthy(self) -> None:
        registry = _fleet(self.now, capabilities={"deep_reasoning", "text_reasoning"})
        registry.healthcheck("host-0", healthy=False, now=self.now)
        registry._move(registry.get("host-0"), WorkerState.OFFLINE)
        ops = FederationOps(FreeWorkerMesh(registry, ProviderRegistry()), self.matrix)
        health = ops.federation_health(now=self.now)
        self.assertNotEqual(health["FEDERATION_STATE"], FederationHealth.HEALTHY.value)

    def test_a_local_only_role_is_blocked_without_a_worker(self) -> None:
        registry = WorkerRegistry()  # nothing joined at all
        ops = FederationOps(FreeWorkerMesh(registry, ProviderRegistry()), self.matrix)
        health = {r["role_id"]: r["health"] for r in ops.role_health(now=self.now)}
        local = [r["role_id"] for r in self.matrix["ROLE_CAPABILITY_MATRIX"]
                 if (r.get("primary") or {}).get("placement") == "LOCAL"]
        self.assertTrue(local, "no local-only role, so this test proves nothing")
        for role in local:
            self.assertNotEqual(health[role], RoleHealth.AVAILABLE_PRIMARY.value)

    def test_minimum_profile_stops_claiming_when_its_paths_go(self) -> None:
        registry = WorkerRegistry()
        ops = FederationOps(FreeWorkerMesh(registry, ProviderRegistry()), self.matrix)
        minimum = ops.service_profiles(now=self.now)[ServiceProfile.MINIMUM.value]
        self.assertFalse(minimum["met"])
        self.assertTrue(minimum["unmet_roles"])


class TheHostIsNotASecondMachine(unittest.TestCase):
    """A LOCAL_PROCESS path recorded in the paths file is this host again."""

    def test_a_local_path_does_not_count_as_independent_capacity(self) -> None:
        from AI_SKILL_LIBRARY.v4.tools.wave3_free_execution_paths import load_registry
        now = time.time()
        providers, _ = load_registry(ROOT)
        registry = _fleet(now, capabilities={"deep_reasoning"})
        ops = FederationOps(FreeWorkerMesh(registry, providers),
                            role_capability_matrix.build(ROOT))
        rows = ops.worker_role_matrix(now=now)
        local_echo = [r for r in rows if r["kind"] == "PROVIDER"
                      and r.get("is_this_host_under_another_name")]
        self.assertTrue(local_echo, "the paths file records no local process path")
        for row in local_echo:
            self.assertFalse(row["offers_independent_capacity"])
        snapshot = ops.snapshot(now=now)
        for row in local_echo:
            self.assertNotIn(row["executor_id"], snapshot["VERIFIED_PROVIDERS"])


class DerivedResidencyKeepsFactsApart(unittest.TestCase):
    def test_sleeping_and_broken_do_not_read_the_same(self) -> None:
        from AI_SKILL_LIBRARY.v4.local_runtime.federation_ops import _PHYSICAL_READING
        from AI_SKILL_LIBRARY.v4.local_runtime.residency import ResidencyState
        self.assertNotEqual(_PHYSICAL_READING[ResidencyState.SLEEPING],
                            _PHYSICAL_READING[ResidencyState.BROKEN])

    def test_jit_is_not_immediately_callable(self) -> None:
        from AI_SKILL_LIBRARY.v4.local_runtime.federation_ops import IMMEDIATE_RESIDENCY
        self.assertNotIn(OperationalResidency.JIT, IMMEDIATE_RESIDENCY)
        self.assertNotIn(OperationalResidency.COLD, IMMEDIATE_RESIDENCY)
        self.assertIn(OperationalResidency.SERVERLESS, IMMEDIATE_RESIDENCY)


class MatrixIsDerivedFromEvidence(unittest.TestCase):
    def setUp(self) -> None:
        self.matrix = role_capability_matrix.build(ROOT)

    def test_every_named_primary_carries_evidence(self) -> None:
        for row in self.matrix["ROLE_CAPABILITY_MATRIX"]:
            primary = row.get("primary")
            if not primary:
                continue
            with self.subTest(role=row["role_id"]):
                self.assertTrue(primary.get("evidence_refs"))

    def test_a_provider_substitute_is_never_called_an_exact_model(self) -> None:
        for row in self.matrix["ROLE_CAPABILITY_MATRIX"]:
            primary = row.get("primary") or {}
            model = str(primary.get("model_id") or "")
            if model.startswith("@"):
                with self.subTest(role=row["role_id"]):
                    self.assertNotEqual(primary.get("execution_mode"), "EXACT_MODEL")

    def test_redundancy_counts_placements_not_models(self) -> None:
        """Six models on one host is one path, and must report as one."""
        for row in self.matrix["ROLE_CAPABILITY_MATRIX"]:
            if row.get("independent_paths") == 1 and row.get("candidate_count", 0) > 1:
                with self.subTest(role=row["role_id"]):
                    self.assertFalse(row["redundant"])
                    self.assertTrue(row["single_path_risk"])

    def test_a_degraded_role_names_what_is_missing(self) -> None:
        for row in self.matrix["ROLE_CAPABILITY_MATRIX"]:
            if row["status"] == "DEGRADED":
                with self.subTest(role=row["role_id"]):
                    self.assertTrue(row["capabilities_uncovered"])
                    self.assertTrue(row["capabilities_covered"])

    def test_no_role_grants_trading_authority(self) -> None:
        for row in self.matrix["ROLE_CAPABILITY_MATRIX"]:
            self.assertFalse(row["trading_authority"])


if __name__ == "__main__":
    unittest.main()
