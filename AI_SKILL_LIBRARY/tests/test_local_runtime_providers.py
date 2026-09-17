"""The rules that keep a hosted substitute from being read as the real model."""

import unittest

from AI_SKILL_LIBRARY.v4.local_runtime.placement import (
    PlacementState,
    resolve,
)
from AI_SKILL_LIBRARY.v4.local_runtime.providers import (
    CostClass,
    ExecutionType,
    ModelOffering,
    OfferingMatch,
    ProviderError,
    ProviderRecord,
    ProviderRegistry,
    ProviderVerification,
)
from AI_SKILL_LIBRARY.v4.local_runtime.workers import WorkerRegistry

MODEL = {
    "model_id": "openai/gpt-oss-20b",
    "family": "gpt-oss",
    "artifact_identity": {"sha256": "a" * 64, "size_bytes": 12_800 * 1024 * 1024,
                          "format": "gguf", "quantization": "Q4_K_M"},
}


def hosted(offerings, **overrides):
    defaults = dict(
        provider_id="cloudflare_workers_ai",
        execution_type=ExecutionType.SERVERLESS_HOSTED_CATALOG,
        cost_class=CostClass.FREE_HARD_STOP,
        custom_weights=False,
        authentication_required=True,
        credential_available_here=True,
        operator_authorized=True,
        # Selection tests need a path that has actually run. The rule that a
        # provider must not be available on documentation alone has its own
        # test below rather than being smuggled into every other one.
        verification_state=ProviderVerification.VERIFIED_AVAILABLE,
        offerings=tuple(offerings),
    )
    defaults.update(overrides)
    return ProviderRecord(**defaults)


def exact(free=True):
    return ModelOffering(
        requested_model_id="openai/gpt-oss-20b", match=OfferingMatch.EXACT,
        provider_model_id="@cf/openai/gpt-oss-20b", free_tier_eligible=free)


def fallback(free=True):
    return ModelOffering(
        requested_model_id="openai/gpt-oss-20b", match=OfferingMatch.CAPABILITY,
        provider_model_id="@cf/qwen/qwen3-30b-a3b-fp8", free_tier_eligible=free,
        substitution_reason="a different 30B that covers general reasoning")


class OfferingContractTests(unittest.TestCase):
    def test_a_capability_offering_must_say_why_it_is_a_stand_in(self):
        # An unexplained substitution is indistinguishable from a mistake, so
        # it is refused at construction rather than surfacing later as a row
        # nobody can account for.
        with self.assertRaises(ProviderError):
            ModelOffering(requested_model_id="x", match=OfferingMatch.CAPABILITY,
                          provider_model_id="@cf/y")

    def test_an_offering_that_serves_something_must_name_it(self):
        with self.assertRaises(ProviderError):
            ModelOffering(requested_model_id="x", match=OfferingMatch.EXACT)

    def test_only_an_exact_offering_is_the_requested_model(self):
        self.assertTrue(exact().is_the_requested_model)
        self.assertFalse(fallback().is_the_requested_model)


class ProviderAuthorityTests(unittest.TestCase):
    def test_a_provider_cannot_be_constructed_with_authority(self):
        # Same contract as a worker: authority is a class attribute, so passing
        # one is a TypeError rather than a field that silently sticks.
        with self.assertRaises(TypeError):
            ProviderRecord(
                provider_id="p", execution_type=ExecutionType.SERVERLESS_HOSTED_CATALOG,
                cost_class=CostClass.FREE_HARD_STOP, routing_authority=True)

    def test_registry_holds_no_authority(self):
        registry = ProviderRegistry()
        self.assertFalse(registry.routing_authority)
        self.assertFalse(registry.model_selection_authority)
        self.assertFalse(registry.admission_authority)


class ScopeTests(unittest.TestCase):
    def test_a_missing_local_credential_is_not_a_federation_blocker(self):
        # The distinction this whole module exists for: a path the operator has
        # but this container cannot drive is pending, not absent.
        provider = hosted([exact()], credential_available_here=False)
        self.assertEqual(provider.federation_blockers(), ())
        self.assertTrue(provider.local_blockers())

        resolution = ProviderRegistry([provider]).resolve("openai/gpt-oss-20b")
        self.assertFalse(resolution.exact)
        self.assertIn("cloudflare_workers_ai", resolution.pending)
        self.assertNotIn("cloudflare_workers_ai", resolution.rejected)

    def test_an_unauthorized_account_is_a_federation_blocker(self):
        provider = hosted([exact()], operator_authorized=False)
        resolution = ProviderRegistry([provider]).resolve("openai/gpt-oss-20b")
        self.assertIn("cloudflare_workers_ai", resolution.rejected)
        self.assertNotIn("cloudflare_workers_ai", resolution.pending)

    def test_a_soft_quota_on_a_billable_account_is_refused(self):
        provider = hosted([exact()], cost_class=CostClass.FREE_QUOTA_SOFT)
        resolution = ProviderRegistry([provider]).resolve("openai/gpt-oss-20b")
        self.assertIn("cloudflare_workers_ai", resolution.rejected)

    def test_documentation_alone_never_makes_a_provider_available(self):
        # The §34 rule, structural rather than remembered: a provider that has
        # never returned a completion cannot be selected, however complete its
        # catalog entry is.
        provider = hosted([exact()], verification_state=ProviderVerification.DISCOVERED)
        resolution = ProviderRegistry([provider]).resolve("openai/gpt-oss-20b")
        self.assertFalse(resolution.exact)
        self.assertIn("documentation is not execution proof",
                      " ".join(resolution.pending["cloudflare_workers_ai"]))

    def test_a_terms_incompatible_provider_is_refused_on_every_machine(self):
        provider = hosted([exact()],
                          verification_state=ProviderVerification.TERMS_INCOMPATIBLE)
        resolution = ProviderRegistry([provider]).resolve("openai/gpt-oss-20b")
        self.assertIn("cloudflare_workers_ai", resolution.rejected)

    def test_unverified_free_tier_fails_closed(self):
        provider = hosted([exact(free=None)])
        resolution = ProviderRegistry([provider]).resolve("openai/gpt-oss-20b")
        self.assertFalse(resolution.exact)
        self.assertIn("cloudflare_workers_ai", resolution.pending)


class PlacementIntegrationTests(unittest.TestCase):
    """No worker at all, so the provider is the only thing that can answer."""

    def test_an_exact_hosted_model_is_available_serverless(self):
        placement = resolve(MODEL, WorkerRegistry(),
                            providers=ProviderRegistry([hosted([exact()])]))
        self.assertIs(placement.state, PlacementState.AVAILABLE_SERVERLESS)
        self.assertTrue(placement.executable)
        self.assertTrue(placement.runs_the_requested_model)
        self.assertEqual(placement.served_model_id, "@cf/openai/gpt-oss-20b")

    def test_a_capability_fallback_is_answerable_but_not_executable(self):
        # The load-bearing assertion. The request can be served and the model
        # still runs nowhere; a reader who conflates the two would record a
        # measurement of qwen3-30b against gpt-oss-20b.
        placement = resolve(MODEL, WorkerRegistry(),
                            providers=ProviderRegistry([hosted([fallback()])]))
        self.assertIs(placement.state, PlacementState.PROVIDER_CAPABILITY_FALLBACK)
        self.assertFalse(placement.executable)
        self.assertTrue(placement.answerable)
        self.assertFalse(placement.runs_the_requested_model)
        self.assertNotEqual(placement.served_model_id, placement.model_id)
        self.assertTrue(placement.substitution_reason)

    def test_exact_wins_over_a_fallback_offered_alongside_it(self):
        registry = ProviderRegistry([
            hosted([fallback()], provider_id="substitute-only"),
            hosted([exact()], provider_id="serves-the-real-one"),
        ])
        placement = resolve(MODEL, WorkerRegistry(), providers=registry)
        self.assertIs(placement.state, PlacementState.AVAILABLE_SERVERLESS)
        self.assertEqual(placement.provider_id, "serves-the-real-one")

    def test_no_provider_leaves_the_worker_answer_untouched(self):
        # Passing no providers must not change what placement said before they
        # existed, or every prior conclusion would need re-reading.
        bare = resolve(MODEL, WorkerRegistry())
        with_empty = resolve(MODEL, WorkerRegistry(), providers=ProviderRegistry())
        self.assertIs(bare.state, PlacementState.NO_COMPATIBLE_WORKER_ONLINE)
        self.assertIs(with_empty.state, bare.state)

    def test_a_hosted_path_can_answer_a_runtime_incompatible_artifact(self):
        # A provider never sees our artifact, so a format our backend cannot
        # read is not its problem. The state still records that *we* cannot run
        # the bytes.
        placement = resolve(MODEL, WorkerRegistry(), runtime_incompatible=True,
                            providers=ProviderRegistry([hosted([exact()])]))
        self.assertIs(placement.state, PlacementState.AVAILABLE_SERVERLESS)

    def test_an_incompatible_artifact_with_no_provider_stays_incompatible(self):
        placement = resolve(MODEL, WorkerRegistry(), runtime_incompatible=True,
                            providers=ProviderRegistry())
        self.assertIs(placement.state, PlacementState.INCOMPATIBLE_WITH_SUPPORTED_RUNTIMES)


class RecordedPathsTests(unittest.TestCase):
    """The committed file has to survive being loaded and mean what it says."""

    def setUp(self):
        from pathlib import Path

        from AI_SKILL_LIBRARY.v4.tools.wave3_free_execution_paths import load_registry

        root = Path(__file__).resolve().parents[2]
        self.registry, self.document = load_registry(root)

    def test_no_hosted_catalog_claims_to_take_our_weights(self):
        for provider in self.registry.all():
            if provider.execution_type is ExecutionType.SERVERLESS_HOSTED_CATALOG:
                self.assertFalse(
                    provider.custom_weights,
                    f"{provider.provider_id} claims to accept custom weights; a hosted "
                    f"catalog that could would need the evidence to say so")

    def test_every_capability_offering_records_its_reason(self):
        for provider in self.registry.all():
            for offering in provider.offerings:
                if offering.match is OfferingMatch.CAPABILITY:
                    self.assertTrue(offering.substitution_reason)

    def test_no_path_is_recorded_as_paid(self):
        for provider in self.registry.all():
            self.assertIsNot(provider.cost_class, CostClass.PAID)

    def test_unverified_rows_are_carried_but_never_offered(self):
        # An UNVERIFIED catalog check stays in the file so the check is visible,
        # and must not reach the registry as something that could be selected.
        unverified = [row for row in self.document["offerings"]
                      if row["match"] in {"UNVERIFIED", "ABSENT"}]
        self.assertTrue(unverified, "the file should record the checks that came back empty")
        for row in unverified:
            for provider in self.registry.all():
                self.assertIsNone(provider.offering_for(row["requested_model_id"]))


if __name__ == "__main__":
    unittest.main()
