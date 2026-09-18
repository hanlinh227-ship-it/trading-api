"""Task 3b - the placement engine, and the one rule it may never trade away.

``placement_candidates`` turns an object and a set of provider rows into the
ordered list of backends that may legitimately receive it, and
``select_primary`` takes the first. Everything interesting about this module is
in what it *refuses*, so that is what these tests are mostly about.

The decision order is fixed by Spec S5 and restated verbatim in the plan's
Global Constraints:

    privacy -> integrity/criticality -> free-only eligibility -> provider
    health -> quota headroom -> object size -> access frequency -> retention
    class -> latency -> backend choice

with three sentences underneath it that are not tie-breaks but absolutes:
capacity never overrides privacy, free capacity never overrides integrity,
latency never overrides the zero-cost policy. The order is therefore tested as
an *order*: a provider that loses on privacy is not merely ranked lower than
one that wins on capacity, it is not in the list at all, and no amount of free
terabytes moves it back in.

Four themes:

1. **Privacy first and privacy absolute.** The headline test puts a provider
   with 99% free headroom and perfect health against one with almost none, and
   the small one wins because it is the only one admitted for the object's
   class. LOCAL_ONLY gets its own class of tests, because "never leaves owned
   storage" has to hold through the default path, the omitted field and the
   provider nobody has ever heard of - not only through the row that helpfully
   declares itself external.

2. **Fail closed on every gap.** Each required provider field is removed in
   turn and the provider must disappear from the candidate list. An unknown
   enum value, an undeclared field, a duplicated provider id and a
   non-mapping all do the same. There is no input shape for which a missing
   answer produces a placement.

3. **Determinism.** Same inputs, same order out - under key reordering, input
   permutation and repetition. Placement that depends on set iteration or dict
   hashing is placement that cannot be reviewed, reproduced or trusted.

4. **Nothing unbounded comes back out.** Exclusion reasons are a closed
   vocabulary of codes. No caller-supplied string is ever echoed into an
   explanation, because an explanation gets logged and a log is exactly where
   an unbounded string turns into a leaked credential.

No placement is performed against a live provider, nothing is written, no
provider account is touched, and the shipped registry still yields no primary -
which the last test asserts, because the honest state of the mesh today is that
nothing has been probed.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from AI_SKILL_LIBRARY.v4.storage import capacity, mesh_validator, placement
from AI_SKILL_LIBRARY.v4.storage.manifest import StorageObject

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "AI_SKILL_LIBRARY/v4/storage/policy.yaml"
MANIFEST_SCHEMA_PATH = ROOT / "AI_SKILL_LIBRARY/v4/schemas/storage_object_manifest.schema.json"
PROVIDER_SCHEMA_PATH = ROOT / "AI_SKILL_LIBRARY/v4/schemas/storage_provider.schema.json"

POLICY = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
MANIFEST_SCHEMA = json.loads(MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
PROVIDER_SCHEMA = json.loads(PROVIDER_SCHEMA_PATH.read_text(encoding="utf-8"))
PROVIDER_VALIDATOR = Draft202012Validator(PROVIDER_SCHEMA)

AUTHORITY_FLAGS = (
    "storage_authority", "routing_authority", "reasoning_authority",
    "model_selection_authority", "admission_authority", "scheduling_authority",
    "merge_authority", "trading_authority",
)

ABSENT = object()
NOW = "2026-09-18T00:00:00Z"
PAST = "2020-01-01T00:00:00Z"

DIGEST = "a" * 64


def provider(provider_id="cloudflare_r2", **overrides):
    """An external row that is admitted for everything the fixture allows."""
    row = {
        "provider_id": provider_id,
        "adapter_type": "s3_compatible",
        "external": True,
        "free_status": "VERIFIED_RECURRING_FREE",
        "free_status_evidence": {
            "evidence_class": "runtime_account_evidence",
            "verified_at": NOW,
            "evidence_ref": "evidence/storage/probe.json",
        },
        "free_expiry_at": None,
        "quota_total": 1000,
        "quota_used": 0,
        "quota_reserved": 0,
        "hard_stop_verified": True,
        "paid_spillover_possible": False,
        "privacy_classes_allowed": ["PUBLIC", "INTERNAL"],
        "encryption_required_classes": ["CONFIDENTIAL"],
        "health": "HEALTHY",
        "autonomous_write_allowed": True,
        "read_enabled": True,
        "write_enabled": True,
        "bulk_object_backend_allowed": True,
        "tiers_allowed": ["HOT", "WARM", "COLD"],
        "preferred_tiers": ["WARM"],
        "acceptable_use_class": "object-storage",
        "last_probe_at": NOW,
        "authority": False,
        "authority_flags": {flag: False for flag in AUTHORITY_FLAGS},
    }
    row.update(overrides)
    return {key: value for key, value in row.items() if value is not ABSENT}


def owned(provider_id="local_owned_store", **overrides):
    """Owned storage: the only place a LOCAL_ONLY object may ever live."""
    row = {
        "provider_id": provider_id,
        "adapter_type": "local_filesystem",
        "external": False,
        "free_status": "NOT_APPLICABLE",
        "free_status_evidence": {"evidence_class": "not_applicable"},
        # storage_provider.schema.json forbids an owned local row from
        # declaring any quota: there is no provider-granted allowance to read,
        # so the honest value is null and the broker treats it as unknowable.
        "quota_total": None,
        "quota_used": None,
        "quota_reserved": None,
        "hard_stop_verified": True,
        "paid_spillover_possible": False,
        "privacy_classes_allowed": ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "LOCAL_ONLY"],
        "encryption_required_classes": [],
        "health": "HEALTHY",
        "autonomous_write_allowed": True,
        "read_enabled": True,
        "write_enabled": True,
        "bulk_object_backend_allowed": True,
        "tiers_allowed": ["HOT", "WARM", "COLD"],
        "preferred_tiers": ["HOT"],
        "acceptable_use_class": "owned-storage",
        "last_probe_at": NOW,
        "authority": False,
        "authority_flags": {flag: False for flag in AUTHORITY_FLAGS},
    }
    row.update(overrides)
    return {key: value for key, value in row.items() if value is not ABSENT}


def obj(**overrides):
    """The plainest legitimate object: small, public, reproducible, warm."""
    record = {
        "privacy_class": "PUBLIC",
        "criticality": "REPRODUCIBLE",
        "size_bytes": 10,
        "storage_tier": "WARM",
        "encryption_state": "NONE",
        "object_class": "benchmark-bundle",
        "retention_class": "bounded",
        "lifecycle_state": "RAW",
        "reproducible": True,
    }
    record.update(overrides)
    return {key: value for key, value in record.items() if value is not ABSENT}


def ids(rows):
    return [row["provider_id"] for row in rows]


def chosen(object_record, rows):
    primary = placement.select_primary(object_record, rows, now=NOW)
    return None if primary is None else primary["provider_id"]


class FixtureIntegrityTests(unittest.TestCase):
    def test_both_provider_fixtures_validate_against_the_shipped_schema(self):
        for row in (provider(), owned()):
            with self.subTest(provider=row["provider_id"]):
                errors = [f"{list(e.absolute_path)}: {e.message}"
                          for e in PROVIDER_VALIDATOR.iter_errors(row)]
                self.assertEqual(errors, [])


class PrivacyBeatsCapacityTests(unittest.TestCase):
    """Spec S5: 'Capacity never overrides privacy.' The single load-bearing rule."""

    def test_privacy_beats_capacity(self):
        # The plan's own example, made harder: the provider that cannot hold
        # the class is also the one with more headroom, better health and a
        # lexicographically earlier id, so every other signal in the ranking
        # points at it and privacy still decides.
        record = obj(privacy_class="INTERNAL", criticality="IMPORTANT")
        cheap = provider("a_huge_public_only", privacy_classes_allowed=["PUBLIC"],
                         quota_total=10 ** 12, quota_used=0, health="FREE")
        verified = provider("z_small_verified",
                            privacy_classes_allowed=["PUBLIC", "INTERNAL"],
                            quota_total=100, quota_used=70, health="HEALTHY")
        self.assertEqual(chosen(record, [cheap, verified]), "z_small_verified")
        self.assertEqual(chosen(record, [verified, cheap]), "z_small_verified")

    def test_a_provider_that_does_not_admit_the_class_is_excluded_at_any_scale(self):
        record = obj(privacy_class="INTERNAL")
        cheap = provider("a_huge_public_only", privacy_classes_allowed=["PUBLIC"],
                         quota_total=10 ** 15, health="FREE")
        self.assertEqual(ids(placement.placement_candidates(record, [cheap], now=NOW)), [])
        self.assertIsNone(chosen(record, [cheap]))

    def test_an_empty_privacy_allowance_admits_nothing(self):
        record = obj()
        self.assertEqual(
            ids(placement.placement_candidates(
                record, [provider(privacy_classes_allowed=[])], now=NOW)),
            [])

    def test_an_absent_privacy_allowance_admits_nothing(self):
        self.assertEqual(
            ids(placement.placement_candidates(
                obj(), [provider(privacy_classes_allowed=ABSENT)], now=NOW)),
            [])

    def test_an_object_with_no_privacy_class_is_placed_nowhere(self):
        self.assertEqual(
            ids(placement.placement_candidates(
                obj(privacy_class=ABSENT), [provider(), owned()], now=NOW)),
            [])

    def test_an_object_with_an_unknown_privacy_class_is_placed_nowhere(self):
        for value in ("public", "SECRET", "", None, 1, ["PUBLIC"]):
            with self.subTest(value=repr(value)):
                self.assertEqual(
                    ids(placement.placement_candidates(
                        obj(privacy_class=value), [provider(), owned()], now=NOW)),
                    [])


class LocalOnlyTests(unittest.TestCase):
    """Spec S4: LOCAL_ONLY must never be uploaded to third-party cloud storage."""

    def setUp(self):
        self.record = obj(privacy_class="LOCAL_ONLY", storage_tier="HOT")

    def test_local_only_lives_on_owned_storage(self):
        self.assertEqual(chosen(self.record, [owned()]), "local_owned_store")

    def test_local_only_never_reaches_an_external_backend(self):
        external = provider(privacy_classes_allowed=[
            "PUBLIC", "INTERNAL", "CONFIDENTIAL", "LOCAL_ONLY"])
        self.assertEqual(
            ids(placement.placement_candidates(self.record, [external], now=NOW)), [])

    def test_local_only_is_unreachable_even_from_a_provider_named_local(self):
        # The reserved namespace is a control only if externality still governs.
        impostor = provider("local_r2", external=True, privacy_classes_allowed=[
            "PUBLIC", "INTERNAL", "CONFIDENTIAL", "LOCAL_ONLY"])
        self.assertEqual(
            ids(placement.placement_candidates(self.record, [impostor], now=NOW)), [])

    def test_local_only_is_unreachable_from_owned_storage_outside_the_namespace(self):
        # And the converse: external=false is not enough on its own, because a
        # row can claim anything. The id must be in the reserved local_ space.
        mislabelled = owned("cloudflare_r2", adapter_type="s3_compatible")
        self.assertEqual(
            ids(placement.placement_candidates(self.record, [mislabelled], now=NOW)), [])

    def test_local_only_is_unreachable_when_externality_is_not_declared(self):
        self.assertEqual(
            ids(placement.placement_candidates(
                self.record, [owned(external=ABSENT)], now=NOW)), [])

    def test_local_only_is_unreachable_when_externality_is_not_a_boolean(self):
        for value in (None, "false", 0, "no"):
            with self.subTest(value=repr(value)):
                self.assertEqual(
                    ids(placement.placement_candidates(
                        self.record, [owned(external=value)], now=NOW)), [])

    def test_local_only_is_unreachable_from_a_provider_nobody_described(self):
        for row in ({}, {"provider_id": "mystery"}, None, "cloudflare_r2", []):
            with self.subTest(row=repr(row)):
                self.assertEqual(
                    ids(placement.placement_candidates(
                        self.record, [row], now=NOW)), [])

    def test_local_only_is_unreachable_from_every_row_in_the_shipped_registry(self):
        rows = mesh_validator.load_providers()
        self.assertEqual(
            ids(placement.placement_candidates(self.record, rows, now=NOW)), [])

    def test_no_external_provider_survives_a_local_only_object_in_any_mixture(self):
        rows = [provider(), owned(), provider("backblaze_b2"), {}, None]
        candidates = placement.placement_candidates(self.record, rows, now=NOW)
        self.assertEqual(ids(candidates), ["local_owned_store"])
        for row in candidates:
            self.assertIs(row["external"], False)


class ConfidentialTests(unittest.TestCase):
    """Spec S4/S21/S22: CONFIDENTIAL leaves owned storage only as ciphertext."""

    def confidential(self, **overrides):
        return obj(privacy_class="CONFIDENTIAL", **overrides)

    def encrypted(self, **overrides):
        record = self.confidential(
            encryption_state="CLIENT_SIDE_ENCRYPTED",
            encryption_scheme_version=1,
            encryption={
                "algorithm": "aes-256-gcm",
                "scheme_version": 1,
                "key_ref": "secretstore://mesh/dek-1",
            },
        )
        record.update(overrides)
        return record

    def cloud(self, **overrides):
        return provider(privacy_classes_allowed=["PUBLIC", "INTERNAL", "CONFIDENTIAL"],
                        encryption_required_classes=["CONFIDENTIAL"], **overrides)

    def test_plaintext_confidential_never_reaches_an_external_backend(self):
        self.assertEqual(
            ids(placement.placement_candidates(
                self.confidential(), [self.cloud()], now=NOW)), [])

    def test_ciphertext_confidential_reaches_a_provider_that_requires_encryption(self):
        self.assertEqual(chosen(self.encrypted(), [self.cloud()]), "cloudflare_r2")

    def test_a_provider_that_does_not_require_encryption_is_not_admitted(self):
        # Registry incoherence: admitting the class without requiring the
        # ciphertext is a contradiction, and the contradiction fails closed.
        row = provider(privacy_classes_allowed=["PUBLIC", "CONFIDENTIAL"],
                       encryption_required_classes=[])
        self.assertEqual(
            ids(placement.placement_candidates(self.encrypted(), [row], now=NOW)), [])

    def test_an_encryption_claim_with_no_metadata_behind_it_is_refused(self):
        record = self.confidential(encryption_state="CLIENT_SIDE_ENCRYPTED")
        self.assertEqual(
            ids(placement.placement_candidates(record, [self.cloud()], now=NOW)), [])

    def test_a_key_reference_outside_the_permitted_locations_is_refused(self):
        for key_ref in ("s3://bucket/dek-1", "https://example.invalid/k",
                        "dek-1", "", None, "a" * 4096):
            with self.subTest(key_ref=repr(key_ref)[:40]):
                record = self.encrypted()
                record["encryption"] = dict(record["encryption"], key_ref=key_ref)
                self.assertEqual(
                    ids(placement.placement_candidates(
                        record, [self.cloud()], now=NOW)), [])

    def test_an_unknown_algorithm_is_refused(self):
        record = self.encrypted()
        record["encryption"] = dict(record["encryption"], algorithm="rot13")
        self.assertEqual(
            ids(placement.placement_candidates(record, [self.cloud()], now=NOW)), [])

    def test_confidential_may_stay_on_owned_storage_without_encryption(self):
        # Spec S4 conditions apply to *leaving* owned storage. Requiring
        # ciphertext on the local disk too would be a rule the spec does not
        # make, and would leave plaintext CONFIDENTIAL data with no home.
        self.assertEqual(chosen(self.confidential(), [owned()]), "local_owned_store")

    def test_encryption_metadata_carrying_a_field_nobody_declared_is_refused(self):
        record = self.encrypted()
        record["encryption"] = dict(record["encryption"], plaintext_key="hunter2")
        self.assertEqual(
            ids(placement.placement_candidates(record, [self.cloud()], now=NOW)), [])


class ZeroCostTests(unittest.TestCase):
    """Spec S11. No path through this module can create paid usage."""

    def test_an_unverified_free_tier_is_never_a_candidate(self):
        for status in ("UNVERIFIED", "DOCUMENTED_ONLY", "PAID_ONLY",
                       "FREE_EXPIRED", "NOT_APPLICABLE", ABSENT, None, "FREE"):
            with self.subTest(status=repr(status)):
                self.assertEqual(
                    ids(placement.placement_candidates(
                        obj(), [provider(free_status=status)], now=NOW)), [])

    def test_an_expired_free_tier_is_never_a_candidate(self):
        self.assertEqual(
            ids(placement.placement_candidates(
                obj(), [provider(free_status="VERIFIED_FREE",
                                 free_expiry_at=PAST)], now=NOW)), [])

    def test_possible_or_unknown_paid_spillover_is_never_a_candidate(self):
        for value in (True, "unknown", ABSENT, None):
            with self.subTest(value=repr(value)):
                self.assertEqual(
                    ids(placement.placement_candidates(
                        obj(), [provider(paid_spillover_possible=value)], now=NOW)),
                    [])

    def test_an_unverified_hard_stop_is_never_a_candidate(self):
        self.assertEqual(
            ids(placement.placement_candidates(
                obj(), [provider(hard_stop_verified=False)], now=NOW)), [])

    def test_a_provider_that_has_not_been_granted_autonomous_writes_is_excluded(self):
        for value in (False, ABSENT, None, "true", 1):
            with self.subTest(value=repr(value)):
                self.assertEqual(
                    ids(placement.placement_candidates(
                        obj(), [provider(autonomous_write_allowed=value)], now=NOW)),
                    [])

    def test_the_module_never_declares_paid_storage_allowed(self):
        self.assertIs(placement.PAID_STORAGE_ALLOWED, False)
        self.assertIs(placement.OVERAGE_ALLOWED, False)
        self.assertEqual(placement.UNKNOWN_COST_STATE, "QUARANTINE")

    def test_the_shipped_registry_yields_no_primary_for_anything_external(self):
        rows = mesh_validator.load_providers()
        for privacy_class in ("PUBLIC", "INTERNAL", "CONFIDENTIAL"):
            with self.subTest(privacy_class=privacy_class):
                record = obj(privacy_class=privacy_class)
                for row in placement.placement_candidates(record, rows, now=NOW):
                    self.assertIs(row["external"], False)


class FailClosedOmissionTests(unittest.TestCase):
    """Every required provider field, removed one at a time."""

    def test_removing_any_required_field_removes_the_provider(self):
        for field in PROVIDER_SCHEMA["required"]:
            with self.subTest(field=field):
                row = provider(**{field: ABSENT})
                self.assertEqual(
                    ids(placement.placement_candidates(obj(), [row], now=NOW)), [],
                    f"{field} omitted and the provider was still admitted")

    def test_removing_any_write_relevant_optional_field_removes_the_provider(self):
        for field in ("write_enabled", "read_enabled", "bulk_object_backend_allowed",
                      "tiers_allowed", "acceptable_use_class", "last_probe_at",
                      "free_expiry_at"):
            with self.subTest(field=field):
                row = provider(**{field: ABSENT})
                self.assertEqual(
                    ids(placement.placement_candidates(obj(), [row], now=NOW)), [],
                    f"{field} omitted and the provider was still admitted")

    def test_a_provider_carrying_an_undeclared_field_is_excluded(self):
        for extra in ("api_key", "token", "private_key", "seed_phrase",
                      "authorization", "notes"):
            with self.subTest(extra=extra):
                self.assertEqual(
                    ids(placement.placement_candidates(
                        obj(), [provider(**{extra: "x" * 2048})], now=NOW)), [])

    def test_an_object_carrying_an_undeclared_field_is_placed_nowhere(self):
        for extra in ("api_key", "plaintext_key", "raw_prompt", "reasoning"):
            with self.subTest(extra=extra):
                self.assertEqual(
                    ids(placement.placement_candidates(
                        obj(**{extra: "x" * 2048}), [provider(), owned()], now=NOW)),
                    [])

    def test_an_object_whose_nested_record_carries_an_undeclared_field_is_placed_nowhere(self):
        for field, value in (
                ("source_provenance", {"origin_class": "x", "api_key": "k" * 900}),
                ("verification", {"hash_verified": True, "token": "t" * 900}),
                ("authority_flags", {"storage_authority": False, "secret": "s"})):
            with self.subTest(field=field):
                self.assertEqual(
                    ids(placement.placement_candidates(
                        obj(**{field: value}), [provider(), owned()], now=NOW)),
                    [])

    def test_a_provider_whose_nested_record_carries_an_undeclared_field_is_excluded(self):
        self.assertEqual(
            ids(placement.placement_candidates(
                obj(), [provider(object_size_limits={
                    "max_object_bytes": 10 ** 6, "api_key": "k" * 900})], now=NOW)),
            [])

    def test_an_unbounded_classifier_on_the_object_is_placed_nowhere(self):
        for field in ("object_class", "retention_class"):
            for value in ("x" * 900, "", 7, "a" * 64, "Benchmark"):
                with self.subTest(field=field, value=repr(value)[:24]):
                    self.assertEqual(
                        ids(placement.placement_candidates(
                            obj(**{field: value}), [provider(), owned()], now=NOW)),
                        [])

    def test_an_object_missing_a_required_placement_input_is_placed_nowhere(self):
        for field in ("criticality", "size_bytes", "storage_tier",
                      "encryption_state"):
            with self.subTest(field=field):
                self.assertEqual(
                    ids(placement.placement_candidates(
                        obj(**{field: ABSENT}), [provider(), owned()], now=NOW)),
                    [])

    def test_an_object_with_an_unknown_enum_value_is_placed_nowhere(self):
        for field, value in (("criticality", "URGENT"), ("criticality", None),
                             ("storage_tier", "LUKEWARM"), ("storage_tier", 3),
                             ("encryption_state", "SERVER_SIDE"),
                             ("lifecycle_state", "PENDING")):
            with self.subTest(field=field, value=repr(value)):
                self.assertEqual(
                    ids(placement.placement_candidates(
                        obj(**{field: value}), [provider(), owned()], now=NOW)),
                    [])

    def test_an_object_whose_size_is_not_a_byte_count_is_placed_nowhere(self):
        for value in (None, "10", -1, 1.5, True):
            with self.subTest(value=repr(value)):
                self.assertEqual(
                    ids(placement.placement_candidates(
                        obj(size_bytes=value), [provider(), owned()], now=NOW)),
                    [])

    def test_a_non_mapping_provider_is_ignored_rather_than_admitted(self):
        rows = [None, "cloudflare_r2", 7, [], ["provider_id"], provider()]
        self.assertEqual(
            ids(placement.placement_candidates(obj(), rows, now=NOW)),
            ["cloudflare_r2"])

    def test_a_missing_or_unusable_provider_list_yields_nothing(self):
        for rows in (None, [], "cloudflare_r2", 7, {}):
            with self.subTest(rows=repr(rows)):
                self.assertEqual(
                    ids(placement.placement_candidates(obj(), rows, now=NOW)), [])
                self.assertIsNone(placement.select_primary(obj(), rows, now=NOW))

    def test_duplicate_provider_ids_are_excluded_rather_than_guessed_between(self):
        first = provider("cloudflare_r2", quota_total=1000)
        second = provider("cloudflare_r2", quota_total=2000)
        self.assertEqual(
            ids(placement.placement_candidates(
                obj(), [first, second, owned()], now=NOW)),
            ["local_owned_store"])

    def test_a_provider_with_a_malformed_identifier_is_excluded(self):
        for value in ("", "A_R2", "r2!", "x", 7, None, "a" * 200, ABSENT):
            with self.subTest(value=repr(value)[:30]):
                self.assertEqual(
                    ids(placement.placement_candidates(
                        obj(), [provider(provider_id=value)], now=NOW)), [])


class IntegrityAndRoleTests(unittest.TestCase):
    """Spec S5: free capacity never overrides integrity. Spec S6/S17: roles."""

    def test_the_metadata_index_never_holds_an_object(self):
        row = provider("supabase", adapter_type="supabase_metadata",
                       acceptable_use_class="metadata-index-only",
                       bulk_object_backend_allowed=False,
                       tiers_allowed=["METADATA"], preferred_tiers=["METADATA"])
        for tier in ("HOT", "WARM", "COLD", "METADATA"):
            with self.subTest(tier=tier):
                self.assertEqual(
                    ids(placement.placement_candidates(
                        obj(storage_tier=tier), [row], now=NOW)), [])

    def test_a_human_backup_surface_serves_only_the_human_backup_tier(self):
        row = provider("google_drive", adapter_type="google_drive_api",
                       acceptable_use_class="human-backup-only",
                       tiers_allowed=["HUMAN_BACKUP"],
                       preferred_tiers=["HUMAN_BACKUP"])
        self.assertEqual(
            ids(placement.placement_candidates(obj(storage_tier="WARM"), [row], now=NOW)),
            [])
        self.assertEqual(
            chosen(obj(storage_tier="HUMAN_BACKUP"), [row]), "google_drive")

    def test_an_ai_artifact_surface_refuses_an_object_that_is_not_one(self):
        row = provider("huggingface_hub", adapter_type="huggingface_hub",
                       acceptable_use_class="ai-artifacts-only",
                       tiers_allowed=["COLD"], preferred_tiers=["COLD"])
        cold = obj(storage_tier="COLD")
        self.assertEqual(
            ids(placement.placement_candidates(
                cold | {"object_class": "telemetry-log"}, [row], now=NOW)), [])
        self.assertEqual(
            ids(placement.placement_candidates(
                cold | {"object_class": ABSENT}, [row], now=NOW)), [])
        self.assertEqual(
            chosen(cold | {"object_class": "dataset"}, [row]), "huggingface_hub")

    def test_an_unknown_acceptable_use_class_is_excluded(self):
        for value in ("bulk-dump", "", None, ABSENT, 7):
            with self.subTest(value=repr(value)):
                self.assertEqual(
                    ids(placement.placement_candidates(
                        obj(), [provider(acceptable_use_class=value)], now=NOW)), [])

    def test_a_tier_the_provider_does_not_serve_is_excluded(self):
        self.assertEqual(
            ids(placement.placement_candidates(
                obj(storage_tier="HUMAN_BACKUP"), [provider()], now=NOW)), [])

    def test_the_canonical_tier_is_githubs_and_not_a_backends(self):
        # Spec S6: CANONICAL lives on GitHub and carries no bulk object data.
        # No registry row serves it, so no placement can put an object there.
        self.assertEqual(
            ids(placement.placement_candidates(
                obj(storage_tier="CANONICAL"),
                [provider(tiers_allowed=["CANONICAL", "WARM"]), owned()], now=NOW)),
            [])

    def test_critical_evidence_requires_a_bulk_object_backend(self):
        row = provider(bulk_object_backend_allowed=False)
        self.assertEqual(
            ids(placement.placement_candidates(
                obj(criticality="CRITICAL"), [row], now=NOW)), [])

    def test_an_object_larger_than_the_providers_declared_limit_is_excluded(self):
        row = provider(object_size_limits={"max_object_bytes": 9})
        self.assertEqual(
            ids(placement.placement_candidates(obj(size_bytes=10), [row], now=NOW)), [])
        self.assertEqual(chosen(obj(size_bytes=9), [row]), "cloudflare_r2")

    def test_an_object_smaller_than_the_providers_declared_floor_is_excluded(self):
        row = provider(object_size_limits={"min_object_bytes": 11})
        self.assertEqual(
            ids(placement.placement_candidates(obj(size_bytes=10), [row], now=NOW)), [])

    def test_bulk_object_data_never_lands_on_a_non_bulk_backend(self):
        threshold = POLICY["bulk_object_threshold_bytes"]
        row = provider(bulk_object_backend_allowed=False)
        self.assertEqual(
            ids(placement.placement_candidates(
                obj(size_bytes=threshold + 1), [row], now=NOW)), [])


class CapacityGateTests(unittest.TestCase):
    """Spec S10/S14: the limits bound writes and 5% is held for CRITICAL."""

    def test_a_near_full_provider_receives_nothing(self):
        self.assertEqual(
            ids(placement.placement_candidates(
                obj(), [provider(quota_used=920)], now=NOW)), [])

    def test_a_read_only_or_offline_provider_receives_nothing(self):
        for health in ("READ_ONLY", "OFFLINE", "QUARANTINED", "NEAR_FULL"):
            with self.subTest(health=health):
                self.assertEqual(
                    ids(placement.placement_candidates(
                        obj(), [provider(health=health)], now=NOW)), [])

    def test_a_pressured_provider_still_accepts_writes(self):
        self.assertEqual(chosen(obj(), [provider(quota_used=850)]), "cloudflare_r2")

    def test_a_write_that_would_cross_the_ceiling_is_excluded(self):
        # 1000 total: ceiling 920, reserve 50, so an ordinary object sees 870.
        row = provider(quota_used=800)
        self.assertEqual(chosen(obj(size_bytes=70), [row]), "cloudflare_r2")
        self.assertEqual(
            ids(placement.placement_candidates(obj(size_bytes=71), [row], now=NOW)), [])

    def test_the_emergency_reserve_is_withheld_from_ordinary_objects(self):
        row = provider(quota_used=870)
        self.assertEqual(
            ids(placement.placement_candidates(obj(size_bytes=10), [row], now=NOW)), [])

    def test_critical_evidence_may_draw_on_the_emergency_reserve(self):
        row = provider(quota_used=870)
        self.assertEqual(
            chosen(obj(size_bytes=10, criticality="CRITICAL"), [row]), "cloudflare_r2")

    def test_the_reserve_is_not_a_door_past_the_hard_limit(self):
        row = provider(quota_used=915)
        self.assertEqual(
            ids(placement.placement_candidates(
                obj(size_bytes=10, criticality="CRITICAL"), [row], now=NOW)), [])


class RankingTests(unittest.TestCase):
    """The Global Constraints order, asserted as an order rather than a vibe."""

    def test_health_outranks_headroom(self):
        # Spec S5 puts provider health before quota headroom. The pressured
        # provider has more than ten times the free space and still loses.
        healthy = provider("z_healthy", quota_total=1000, quota_used=700)
        pressured = provider("a_pressured", quota_total=100000, quota_used=85000)
        self.assertEqual(
            ids(placement.placement_candidates(obj(), [pressured, healthy], now=NOW)),
            ["z_healthy", "a_pressured"])

    def test_headroom_outranks_tier_preference(self):
        roomy = provider("z_roomy", quota_total=10000, quota_used=0,
                         preferred_tiers=["COLD"])
        tight = provider("a_tight", quota_total=1000, quota_used=0,
                         preferred_tiers=["WARM"])
        self.assertEqual(
            ids(placement.placement_candidates(obj(), [tight, roomy], now=NOW)),
            ["z_roomy", "a_tight"])

    def test_criticality_fit_outranks_everything_below_it(self):
        # Spec S8: EPHEMERAL data is cache/local where possible. The external
        # provider is FREE with a thousand times the headroom and still loses.
        record = obj(criticality="EPHEMERAL", storage_tier="HOT")
        external = provider("a_external", health="FREE", quota_total=10 ** 6)
        self.assertEqual(
            ids(placement.placement_candidates(record, [external, owned()], now=NOW)),
            ["local_owned_store", "a_external"])

    def test_tier_preference_breaks_a_tie_before_the_identifier_does(self):
        preferred = provider("z_preferred", preferred_tiers=["WARM"])
        merely_allowed = provider("a_allowed", preferred_tiers=["COLD"])
        self.assertEqual(
            ids(placement.placement_candidates(
                obj(storage_tier="WARM"), [merely_allowed, preferred], now=NOW)),
            ["z_preferred", "a_allowed"])

    def test_the_identifier_is_the_final_tie_break(self):
        rows = [provider("c_one"), provider("a_one"), provider("b_one")]
        self.assertEqual(
            ids(placement.placement_candidates(obj(), rows, now=NOW)),
            ["a_one", "b_one", "c_one"])

    def test_select_primary_is_the_head_of_the_candidate_list(self):
        rows = [provider("c_one"), provider("a_one"), owned()]
        candidates = placement.placement_candidates(obj(), rows, now=NOW)
        self.assertEqual(placement.select_primary(obj(), rows, now=NOW),
                         candidates[0])

    def test_select_primary_returns_none_when_nothing_is_admissible(self):
        self.assertIsNone(placement.select_primary(
            obj(), [provider(free_status="UNVERIFIED")], now=NOW))


class DeterminismTests(unittest.TestCase):
    """Same inputs, same order out. No set iteration, no dict hashing, no clock."""

    def rows(self):
        return [
            provider("a_one", quota_total=1000, quota_used=100),
            provider("b_two", quota_total=1000, quota_used=100),
            provider("c_three", quota_total=1000, quota_used=100),
            owned(),
            provider("d_four", quota_total=5000, quota_used=100),
        ]

    def test_repeated_calls_return_the_same_order(self):
        rows = self.rows()
        first = ids(placement.placement_candidates(obj(), rows, now=NOW))
        for _ in range(25):
            self.assertEqual(
                ids(placement.placement_candidates(obj(), rows, now=NOW)), first)

    def test_input_permutation_does_not_change_the_order(self):
        rows = self.rows()
        expected = ids(placement.placement_candidates(obj(), rows, now=NOW))
        for offset in range(len(rows)):
            rotated = rows[offset:] + rows[:offset]
            with self.subTest(offset=offset):
                self.assertEqual(
                    ids(placement.placement_candidates(obj(), rotated, now=NOW)),
                    expected)
        self.assertEqual(
            ids(placement.placement_candidates(obj(), list(reversed(rows)), now=NOW)),
            expected)

    def test_key_insertion_order_does_not_change_the_order(self):
        rows = self.rows()
        expected = ids(placement.placement_candidates(obj(), rows, now=NOW))
        shuffled = [dict(reversed(list(row.items()))) for row in rows]
        self.assertEqual(
            ids(placement.placement_candidates(obj(), shuffled, now=NOW)), expected)

    def test_placement_does_not_mutate_its_inputs(self):
        rows = self.rows()
        record = obj()
        before_rows = json.dumps(rows, sort_keys=True)
        before_obj = json.dumps(record, sort_keys=True)
        placement.placement_candidates(record, rows, now=NOW)
        placement.select_primary(record, rows, now=NOW)
        placement.placement_report(record, rows, now=NOW)
        self.assertEqual(json.dumps(rows, sort_keys=True), before_rows)
        self.assertEqual(json.dumps(record, sort_keys=True), before_obj)

    def test_the_only_clock_input_is_injectable_and_can_only_narrow(self):
        row = provider(free_status="VERIFIED_FREE", free_expiry_at="2027-01-01T00:00:00Z")
        self.assertEqual(chosen(obj(), [row]), "cloudflare_r2")
        self.assertIsNone(
            placement.select_primary(obj(), [row], now="2028-01-01T00:00:00Z"))


class ReportTests(unittest.TestCase):
    """An explanation is only useful if it cannot itself carry a secret."""

    def test_every_provider_is_accounted_for_in_the_report(self):
        rows = [provider(), owned(), provider("b2", free_status="UNVERIFIED")]
        report = placement.placement_report(obj(), rows, now=NOW)
        self.assertEqual([entry["provider_id"] for entry in report],
                         ["b2", "cloudflare_r2", "local_owned_store"])

    def test_reasons_are_drawn_from_a_closed_vocabulary(self):
        rows = [provider(free_status="UNVERIFIED"),
                provider("b2", privacy_classes_allowed=[]),
                provider("c3", health="OFFLINE"),
                provider("d4", acceptable_use_class="bulk-dump"),
                {"provider_id": "e5"}, None]
        for entry in placement.placement_report(obj(), rows, now=NOW):
            with self.subTest(provider=entry["provider_id"]):
                self.assertTrue(entry["reasons"])
                for reason in entry["reasons"]:
                    self.assertIn(reason, placement.EXCLUSION_REASONS)

    def test_an_eligible_provider_has_no_reasons(self):
        [entry] = placement.placement_report(obj(), [provider()], now=NOW)
        self.assertTrue(entry["eligible"])
        self.assertEqual(entry["reasons"], ())

    def test_no_caller_supplied_string_is_ever_echoed_back(self):
        needle = "AKIAIOSFODNN7EXAMPLE" + "Z" * 512
        rows = [provider(provider_id=needle, acceptable_use_class=needle),
                provider("b2", free_status=needle)]
        record = obj(privacy_class=needle, object_class=needle,
                     retention_class=needle)
        blob = json.dumps([
            placement.placement_report(obj(), rows, now=NOW),
            placement.placement_report(record, rows, now=NOW),
            placement.placement_candidates(record, rows, now=NOW),
        ])
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", blob)
        self.assertNotIn("ZZZZZZZZ", blob)

    def test_every_reason_code_is_a_bounded_token(self):
        for reason in placement.EXCLUSION_REASONS:
            with self.subTest(reason=reason):
                self.assertRegex(reason, r"^[A-Z][A-Z0-9_]{2,47}$")

    def test_the_report_identifier_is_omitted_when_it_is_not_a_bounded_token(self):
        [entry] = placement.placement_report(
            obj(), [provider(provider_id="A" * 300)], now=NOW)
        self.assertEqual(entry["provider_id"], placement.UNNAMED_PROVIDER)
        self.assertFalse(entry["eligible"])


class AuthorityAndPurityTests(unittest.TestCase):
    """Spec S2/S30: the placement engine holds no authority and writes nothing."""

    def test_the_module_declares_no_authority(self):
        self.assertIs(placement.AUTHORITY, False)
        for flag in AUTHORITY_FLAGS:
            with self.subTest(flag=flag):
                self.assertIs(placement.AUTHORITY_FLAGS[flag], False)

    def test_github_remains_canonical_and_the_router_remains_the_router(self):
        self.assertEqual(placement.CANONICAL_AUTHORITY, "GITHUB_BRAIN_V4")
        self.assertEqual(placement.ROUTED_BY, "task_router")

    def test_the_module_writes_nothing_and_calls_nothing_out(self):
        source = (ROOT / "AI_SKILL_LIBRARY/v4/storage/placement.py").read_text(
            encoding="utf-8")
        code = "\n".join(line for line in source.splitlines()
                         if not line.lstrip().startswith("#"))
        # Matched as code fragments rather than bare words: "requests" alone
        # also matches the schema's own ``requests_per_minute`` field name, and
        # a purity test that fires on a field name is a test nobody keeps.
        for forbidden in ("open(", "import requests", "requests.", "urllib",
                          "httpx", "import socket", "socket.", "subprocess",
                          "boto3", "write_text", "read_text", "os.environ",
                          "getenv(", "eval(", "exec("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code)

    def test_the_placement_order_is_the_one_the_spec_fixes(self):
        self.assertEqual(list(placement.PLACEMENT_ORDER),
                         list(POLICY["placement_order"]))

    def test_the_precedence_absolutes_are_declared_and_false(self):
        for key in ("capacity_overrides_privacy", "free_capacity_overrides_integrity",
                    "latency_overrides_zero_cost"):
            with self.subTest(key=key):
                self.assertIs(placement.PLACEMENT_PRECEDENCE[key], False)
                self.assertIs(POLICY["placement_precedence"][key], False)

    def test_the_known_object_fields_match_the_manifest_schema(self):
        self.assertEqual(set(placement.MANIFEST_FIELDS),
                         set(MANIFEST_SCHEMA["properties"]))

    def test_candidates_are_the_rows_they_were_given(self):
        row = provider()
        [candidate] = placement.placement_candidates(obj(), [row], now=NOW)
        self.assertIs(candidate, row)


class TypedManifestIntegrationTests(unittest.TestCase):
    """The Task 2 producer and the Task 3 engine have to meet somewhere."""

    def manifest(self, **overrides):
        return StorageObject.from_bytes(
            b"abc",
            mime_type="application/octet-stream",
            privacy_class=overrides.pop("privacy_class", "PUBLIC"),
            criticality=overrides.pop("criticality", "REPRODUCIBLE"),
            retention_class="bounded",
            storage_tier=overrides.pop("storage_tier", "COLD"),
            object_class="benchmark-bundle",
            source_provenance={"origin_class": "benchmark-bundle"},
            **overrides,
        ).to_manifest()

    def test_a_manifest_from_the_typed_producer_is_accepted_as_input(self):
        record = self.manifest()
        self.assertEqual(chosen(record, [provider()]), "cloudflare_r2")

    def test_a_local_only_manifest_stays_on_owned_storage(self):
        record = self.manifest(privacy_class="LOCAL_ONLY", storage_tier="HOT")
        self.assertEqual(
            ids(placement.placement_candidates(
                record, [provider(privacy_classes_allowed=[
                    "PUBLIC", "INTERNAL", "CONFIDENTIAL", "LOCAL_ONLY"]),
                    owned()], now=NOW)),
            ["local_owned_store"])

    def test_the_manifests_own_authority_flags_survive_placement(self):
        record = self.manifest()
        self.assertIs(record["authority"], False)
        placement.placement_candidates(record, [provider()], now=NOW)
        self.assertIs(record["authority"], False)


if __name__ == "__main__":
    unittest.main()
