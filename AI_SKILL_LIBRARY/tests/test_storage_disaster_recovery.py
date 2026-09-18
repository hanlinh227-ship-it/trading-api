"""Task 9b - disaster reconstruction, and the word that must never be borrowed.

Spec S18 keeps a bounded pointer set on GitHub so the metadata service is not a
single point of failure. Spec S23 says a rebuild must be possible from that plus
provider-side object metadata and content hashes, and step 9 of it says the
unrecoverable objects are marked *explicitly*. Spec S19 says an object with no
replica is either regenerated, if it is reproducible, or surfaced as a degraded
state with the evidence of its loss preserved - and that success is never
fabricated.

``reconstruct_mesh`` therefore answers with three disjoint sets, and the tests
below spend most of their effort on the boundary between two of them:

``recovered``
    the object's bytes were read back from enough *independent* providers,
    hashed here, matched against the snapshot pointer, and its rebuilt record
    was written into the destination index.
``degraded``
    at least one verified copy exists, but fewer than its criticality class is
    owed. The record is restored; the shortfall is stated.
``unrecoverable``
    nobody could produce the bytes. It is named, it is never in ``recovered``,
    and no record is written that says otherwise.

The plan's second sample is the whole point: an object nothing holds must appear
in ``unrecoverable`` and must not appear in ``recovered``. Metadata surviving is
not an object surviving, and a provider's own ``head`` asserting a digest is a
claim by the thing being checked - so the observations handed to the production
rebuild are built only from bytes this process hashed, never from a head.

The drill reuses production code on purpose: ``recovery.assert_snapshot_is_clean``
and ``recovery.restore_into_store``. A second, looser reconstruction path beside
the real one is the path an edit would get to use.

Nothing here contacts a network, a provider account or a metadata service.
"""

from __future__ import annotations

import re
import traceback
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.storage import manifest as manifest_module
from AI_SKILL_LIBRARY.v4.storage import recovery as recovery_module
from AI_SKILL_LIBRARY.v4.storage.adapters import s3_object
from AI_SKILL_LIBRARY.v4.tools import storage_mesh_recovery_drill as drill

from AI_SKILL_LIBRARY.tests.test_storage_metadata import (
    AUTHORITY_FLAGS,
    FakeMetadataStore,
    MANIFEST_SCHEMA,
    SMUGGLED_CREDENTIAL,
    TIME,
)
from AI_SKILL_LIBRARY.tests.test_storage_s3_adapter import FakeS3Transport
from AI_SKILL_LIBRARY.tests.test_storage_replication import object_store

KEPT_PAYLOAD = b"federated-free-storage-mesh-surviving-object"
LOST_PAYLOAD = b"federated-free-storage-mesh-irreplaceable-object"

KEPT_ID = "obj_" + s3_object.content_digest(KEPT_PAYLOAD)
LOST_ID = "obj_" + s3_object.content_digest(LOST_PAYLOAD)

ONLINE = "cloudflare_r2"
SPARE = "oracle_object_storage"
OFFLINE = "backblaze_b2"

EVERY_OPERATION = ("put", "get", "head", "delete")


def record(payload, *, criticality="CRITICAL", **overrides):
    kwargs = dict(
        privacy_class="PUBLIC",
        criticality=criticality,
        storage_tier="WARM",
        object_class="benchmark-bundle",
        mime_type="application/octet-stream",
        retention_class="short-window",
        primary_backend=ONLINE,
        replica_backends=(SPARE,),
        created_at=TIME,
        lifecycle_state="RAW",
        reproducible=False,
    )
    kwargs.update(overrides)
    return manifest_module.StorageObject.from_bytes(
        payload, **kwargs).to_manifest()


def snapshot_of(records):
    return recovery_module.export_recovery_snapshot(
        FakeMetadataStore(records=records), generated_at=TIME)


def snapshot_with_missing_irreplaceable():
    """One object that survives and one that nothing holds any more."""
    return snapshot_of([record(KEPT_PAYLOAD), record(LOST_PAYLOAD)])


def store_holding(backend_id, *payloads, **kwargs):
    transport = FakeS3Transport(**kwargs)
    for payload in payloads:
        transport.objects["obj_" + s3_object.content_digest(payload)] = (
            payload, {})
    return object_store(backend_id, transport)


def both_copies():
    """Two independent providers, each really holding the surviving object."""
    return {ONLINE: store_holding(ONLINE, KEPT_PAYLOAD),
            SPARE: store_holding(SPARE, KEPT_PAYLOAD)}


HOSTILE = (SMUGGLED_CREDENTIAL, "A" * 300, "", None, -1, 10 ** 30, True,
           False, 1.5, 2, [], {}, (), b"bytes", bytearray(b"bytes"),
           memoryview(b"bytes"), object(), "unexpected", set())

#: The same sweep minus the three empty containers: an empty provider list is
#: not hostile, it is the plan's own sample of a mesh with nothing left.
HOSTILE_PROVIDERS = (SMUGGLED_CREDENTIAL, "A" * 300, "", None, -1, 10 ** 30,
                     True, False, 1.5, 2, b"bytes", bytearray(b"bytes"),
                     memoryview(b"bytes"), object(), "unexpected", set())


class AuthorityTests(unittest.TestCase):

    def test_no_authority_of_any_kind(self):
        self.assertIs(drill.AUTHORITY, False)
        self.assertEqual(set(drill.AUTHORITY_FLAGS), set(AUTHORITY_FLAGS))
        for flag in AUTHORITY_FLAGS:
            self.assertIs(drill.AUTHORITY_FLAGS[flag], False, flag)

    def test_github_remains_canonical(self):
        self.assertEqual(drill.CANONICAL_AUTHORITY, "GITHUB_BRAIN_V4")
        self.assertEqual(drill.ROUTED_BY, "task_router")

    def test_content_identity_is_a_hashlib_digest_and_nothing_invented(self):
        self.assertIs(drill.ENCRYPTION_IMPLEMENTED_HERE, False)
        for name in ("encrypt", "decrypt", "derive_key"):
            self.assertFalse(hasattr(drill, name), name)
        source = Path(drill.__file__).read_text(encoding="utf-8")
        self.assertIn("hashlib.sha256", source)

    def test_the_drill_reaches_no_network(self):
        self.assertIs(drill.CREATES_EXTERNAL_RESOURCES, False)
        self.assertIs(drill.PROVISIONING_AUTHORIZED, False)
        source = Path(drill.__file__).read_text(encoding="utf-8")
        for forbidden in ("import requests", "import socket", "import urllib",
                          "boto3"):
            self.assertNotIn(forbidden, source, forbidden)

    def test_the_drill_deletes_nothing(self):
        self.assertIs(drill.PERFORMS_DELETION, False)
        source = Path(drill.__file__).read_text(encoding="utf-8")
        self.assertNotIn(".delete(", source)

    def test_anchored_patterns_use_backslash_Z(self):
        source = Path(drill.__file__).read_text(encoding="utf-8")
        for line in source.splitlines():
            if "re.compile" in line:
                self.assertNotIn('$"', line, line)
                self.assertNotIn("$'", line, line)


class UnrecoverableIsExplicitTests(unittest.TestCase):
    """The plan's second sample, and the rule it stands for."""

    def test_unrecoverable_is_explicit_not_fabricated(self):
        report = drill.reconstruct_mesh(
            snapshot_with_missing_irreplaceable(), [], FakeMetadataStore())
        self.assertIn(LOST_ID, report.unrecoverable)
        self.assertNotIn(LOST_ID, report.recovered)

    def test_with_no_provider_at_all_nothing_is_recovered(self):
        report = drill.reconstruct_mesh(
            snapshot_with_missing_irreplaceable(), [], FakeMetadataStore())
        self.assertEqual(report.recovered, frozenset())
        self.assertEqual(report.unrecoverable, frozenset({KEPT_ID, LOST_ID}))
        self.assertEqual(report.restored, ())

    def test_surviving_metadata_is_not_a_surviving_object(self):
        """The snapshot knows everything about the lost object and it is
        still lost: a record is not a byte."""
        snapshot = snapshot_with_missing_irreplaceable()
        self.assertIn(LOST_ID, [e["object_id"] for e in snapshot["entries"]])
        report = drill.reconstruct_mesh(snapshot, both_copies(),
                                        FakeMetadataStore())
        self.assertIn(LOST_ID, report.unrecoverable)
        self.assertNotIn(LOST_ID, report.recovered)
        self.assertNotIn(LOST_ID, report.restored)

    def test_the_three_sets_are_disjoint_and_explicit(self):
        report = drill.reconstruct_mesh(
            snapshot_with_missing_irreplaceable(), both_copies(),
            FakeMetadataStore())
        self.assertEqual(report.recovered & report.unrecoverable, frozenset())
        self.assertEqual(report.recovered & report.degraded, frozenset())
        self.assertEqual(report.degraded & report.unrecoverable, frozenset())
        for value in (report.recovered, report.degraded, report.unrecoverable):
            self.assertIsInstance(value, frozenset)

    def test_every_snapshot_object_is_accounted_for_exactly_once(self):
        snapshot = snapshot_with_missing_irreplaceable()
        report = drill.reconstruct_mesh(snapshot, both_copies(),
                                        FakeMetadataStore())
        named = report.recovered | report.degraded | report.unrecoverable
        self.assertEqual(named,
                         frozenset(e["object_id"] for e in snapshot["entries"]))

    def test_a_provider_head_that_lies_recovers_nothing(self):
        """A head is a claim by the thing being checked (Spec S15).

        The store asserts the right digest and the right length and does not
        hold the bytes. An implementation that trusted the claim would report a
        recovery; this one reads, hashes and finds nothing.
        """
        lying = object_store(ONLINE, FakeS3Transport(
            head_override={"size_bytes": len(KEPT_PAYLOAD),
                           "content_sha256": KEPT_ID[len("obj_"):]}))
        report = drill.reconstruct_mesh(
            snapshot_of([record(KEPT_PAYLOAD)]), {ONLINE: lying},
            FakeMetadataStore())
        self.assertIn(KEPT_ID, report.unrecoverable)
        self.assertEqual(report.recovered, frozenset())

    def test_corrupt_bytes_are_unverified_and_never_recovered(self):
        corrupt = store_holding(ONLINE, KEPT_PAYLOAD, corrupt_get=True)
        report = drill.reconstruct_mesh(
            snapshot_of([record(KEPT_PAYLOAD)]), {ONLINE: corrupt},
            FakeMetadataStore())
        self.assertIn(KEPT_ID, report.unverified)
        self.assertIn(KEPT_ID, report.unrecoverable)
        self.assertNotIn(KEPT_ID, report.recovered)
        self.assertLessEqual(report.unverified, report.unrecoverable)


class RecoveredMeansVerifiedTests(unittest.TestCase):
    """Recovered is a count of confirmed independent copies, never of claims."""

    def test_two_independent_verified_copies_recover_a_critical_object(self):
        destination = FakeMetadataStore()
        report = drill.reconstruct_mesh(
            snapshot_of([record(KEPT_PAYLOAD)]), both_copies(), destination)
        self.assertIn(KEPT_ID, report.recovered)
        self.assertEqual(report.degraded, frozenset())
        self.assertEqual(report.restored, (KEPT_ID,))
        self.assertIsNotNone(destination.get_manifest(KEPT_ID))

    def test_one_verified_copy_of_a_critical_object_is_degraded_not_recovered(self):
        report = drill.reconstruct_mesh(
            snapshot_of([record(KEPT_PAYLOAD)]),
            {ONLINE: store_holding(ONLINE, KEPT_PAYLOAD)}, FakeMetadataStore())
        self.assertIn(KEPT_ID, report.degraded)
        self.assertNotIn(KEPT_ID, report.recovered)
        self.assertNotIn(KEPT_ID, report.unrecoverable)
        # Spec S19: the record is preserved and the shortfall surfaced.
        self.assertIn(KEPT_ID, report.restored)

    def test_the_snapshot_replica_list_is_never_counted_as_a_copy(self):
        snapshot = snapshot_of([record(KEPT_PAYLOAD)])
        entry = snapshot["entries"][0]
        self.assertEqual({entry["primary_backend"], *entry["replica_backends"]},
                         {ONLINE, SPARE})
        report = drill.reconstruct_mesh(
            snapshot, {ONLINE: store_holding(ONLINE, KEPT_PAYLOAD),
                       SPARE: object_store(
                           SPARE, FakeS3Transport(raise_on=EVERY_OPERATION))},
            FakeMetadataStore())
        self.assertIn(KEPT_ID, report.degraded)
        self.assertNotIn(KEPT_ID, report.recovered)
        self.assertIn(SPARE, report.unreachable_backends)

    def test_a_reproducible_object_needs_one_copy_and_is_recovered(self):
        reproducible = record(KEPT_PAYLOAD, criticality="REPRODUCIBLE",
                              reproducible=True)
        report = drill.reconstruct_mesh(
            snapshot_of([reproducible]),
            {ONLINE: store_holding(ONLINE, KEPT_PAYLOAD)}, FakeMetadataStore())
        self.assertIn(KEPT_ID, report.recovered)
        self.assertEqual(report.degraded, frozenset())

    def test_recovered_is_always_a_subset_of_restored(self):
        report = drill.reconstruct_mesh(
            snapshot_with_missing_irreplaceable(), both_copies(),
            FakeMetadataStore())
        self.assertLessEqual(report.recovered, frozenset(report.restored))
        self.assertEqual(report.unrecoverable & frozenset(report.restored),
                         frozenset())


class DestructiveCleanupTests(unittest.TestCase):
    """Spec S18: fail closed on uncertain evidence."""

    def test_cleanup_is_disabled_while_anything_is_unrecoverable(self):
        report = drill.reconstruct_mesh(
            snapshot_with_missing_irreplaceable(), both_copies(),
            FakeMetadataStore())
        self.assertIs(report.destructive_cleanup_enabled, False)

    def test_cleanup_is_disabled_while_anything_is_degraded(self):
        report = drill.reconstruct_mesh(
            snapshot_of([record(KEPT_PAYLOAD)]),
            {ONLINE: store_holding(ONLINE, KEPT_PAYLOAD)}, FakeMetadataStore())
        self.assertIs(report.destructive_cleanup_enabled, False)

    def test_cleanup_is_enabled_only_on_a_complete_verified_reconstruction(self):
        report = drill.reconstruct_mesh(
            snapshot_of([record(KEPT_PAYLOAD)]), both_copies(),
            FakeMetadataStore())
        self.assertIs(report.destructive_cleanup_enabled, True)

    def test_an_unhealthy_destination_index_blocks_the_reconstruction(self):
        report = drill.reconstruct_mesh(
            snapshot_of([record(KEPT_PAYLOAD)]), both_copies(),
            FakeMetadataStore(healthy=False))
        self.assertEqual(report.status, "BLOCKED_METADATA_UNCERTAIN")
        self.assertEqual(report.recovered, frozenset())
        self.assertEqual(report.restored, ())
        self.assertIs(report.destructive_cleanup_enabled, False)

    def test_a_duck_typed_destination_is_not_a_metadata_store(self):
        class Plausible:
            def healthy(self):
                return True

            def put_manifest(self, manifest):
                return None

        report = drill.reconstruct_mesh(
            snapshot_of([record(KEPT_PAYLOAD)]), both_copies(), Plausible())
        self.assertEqual(report.status, "BLOCKED_METADATA_UNCERTAIN")
        self.assertEqual(report.recovered, frozenset())


class ProductionChecksActuallyRunTests(unittest.TestCase):
    """No second, looser reconstruction path beside the real one."""

    def test_a_tampered_snapshot_is_refused_by_the_production_gate(self):
        snapshot = dict(snapshot_of([record(KEPT_PAYLOAD)]))
        snapshot["entry_count"] = 99
        with self.assertRaises(drill.RecoveryRefused):
            drill.reconstruct_mesh(snapshot, both_copies(), FakeMetadataStore())

    def test_an_object_the_snapshot_never_heard_of_is_never_adopted(self):
        """The snapshot is the authority for what the mesh was managing.

        ``unknown`` is carried through from ``recovery.rebuild_report`` and is
        empty in practice, because ``ObjectStore`` has no listing operation and
        this drill therefore cannot enumerate a provider: it asks each provider
        only about the ids the snapshot names. The honest assertion is
        consequently the one that matters - an object the snapshot never heard
        of is never recovered, never restored and never written down.
        """
        destination = FakeMetadataStore()
        report = drill.reconstruct_mesh(
            snapshot_of([record(KEPT_PAYLOAD)]),
            {ONLINE: store_holding(ONLINE, KEPT_PAYLOAD, LOST_PAYLOAD)},
            destination)
        self.assertNotIn(LOST_ID, report.recovered)
        self.assertNotIn(LOST_ID, report.degraded)
        self.assertNotIn(LOST_ID, report.restored)
        self.assertIsNone(destination.get_manifest(LOST_ID))

    def test_the_observation_shape_is_the_production_one(self):
        self.assertEqual(drill.OBSERVATION_FIELDS,
                         recovery_module.PROVIDER_RECORD_FIELDS)
        for field, checker in drill.OBSERVATION_VALUE_CHECKS.items():
            with self.subTest(field=field):
                self.assertIs(
                    checker, recovery_module.PROVIDER_RECORD_VALUE_CHECKS[field])

    def test_the_snapshot_entry_projection_lives_in_the_manifest_schema(self):
        self.assertLessEqual(set(recovery_module.ENTRY_FIELDS),
                             set(MANIFEST_SCHEMA["properties"]))


class BoundsTests(unittest.TestCase):

    def test_the_caps_are_declared_and_consistent(self):
        self.assertEqual(drill.MAX_PROVIDERS_SCANNED, 16)
        self.assertEqual(drill.MAX_OBJECTS_RECONSTRUCTED,
                         recovery_module.MAX_SNAPSHOT_ENTRIES)
        self.assertEqual(drill.MAX_READS,
                         drill.MAX_PROVIDERS_SCANNED
                         * drill.MAX_OBJECTS_RECONSTRUCTED)

    def test_a_provider_list_over_the_cap_is_refused(self):
        configured = {f"filler_{n}": None
                      for n in range(drill.MAX_PROVIDERS_SCANNED + 1)}
        with self.assertRaises(drill.RecoveryRefused):
            drill.reconstruct_mesh(snapshot_of([record(KEPT_PAYLOAD)]),
                                   configured, FakeMetadataStore())

    def test_bytes_is_a_sequence_and_is_not_a_provider_list(self):
        for value in (b"cloudflare_r2", bytearray(b"cloudflare_r2"),
                      "cloudflare_r2"):
            with self.subTest(value=repr(value)[:24]):
                with self.assertRaises(drill.RecoveryRefused):
                    drill.reconstruct_mesh(
                        snapshot_of([record(KEPT_PAYLOAD)]), value,
                        FakeMetadataStore())

    def test_the_same_provider_listed_twice_is_refused(self):
        with self.assertRaises(drill.RecoveryRefused):
            drill.reconstruct_mesh(
                snapshot_of([record(KEPT_PAYLOAD)]),
                [store_holding(ONLINE, KEPT_PAYLOAD),
                 store_holding(ONLINE, KEPT_PAYLOAD)],
                FakeMetadataStore())

    def test_an_alias_key_that_is_not_the_backends_own_id_is_refused(self):
        with self.assertRaises(drill.RecoveryRefused):
            drill.reconstruct_mesh(
                snapshot_of([record(KEPT_PAYLOAD)]),
                {"not_the_backend_id": store_holding(ONLINE, KEPT_PAYLOAD)},
                FakeMetadataStore())

    def test_hostile_arguments_are_refused_rather_than_crashing(self):
        snapshot = snapshot_of([record(KEPT_PAYLOAD)])
        for value in HOSTILE:
            with self.subTest(snapshot=repr(value)[:24]):
                with self.assertRaises(drill.RecoveryRefused):
                    drill.reconstruct_mesh(value, both_copies(),
                                           FakeMetadataStore())
        for value in HOSTILE_PROVIDERS:
            with self.subTest(providers=repr(value)[:24]):
                with self.assertRaises(drill.RecoveryRefused):
                    drill.reconstruct_mesh(snapshot, value, FakeMetadataStore())


class StructuralGuardTests(unittest.TestCase):
    """The field tuple is derived from the checker table, not written twice."""

    def test_the_report_field_tuple_is_derived_from_its_check_table(self):
        self.assertEqual(drill.REPORT_FIELDS, tuple(drill.REPORT_VALUE_CHECKS))
        self.assertEqual(
            set(drill.REPORT_FIELDS),
            {f.name for f in drill.RecoveryReport.__dataclass_fields__.values()})

    def test_every_string_report_field_is_bounded_by_pattern_and_length(self):
        for field, pattern in drill.REPORT_FIELD_PATTERNS.items():
            with self.subTest(field=field):
                self.assertIn(field, drill.REPORT_VALUE_CHECKS)
                self.assertIn(field, drill.REPORT_FIELD_MAX_LENGTHS)
                self.assertIsInstance(pattern, re.Pattern)
                self.assertTrue(pattern.pattern.endswith("\\Z"), field)
                self.assertGreater(drill.REPORT_FIELD_MAX_LENGTHS[field], 0)

    def test_every_object_id_field_is_checked_by_the_production_checker(self):
        self.assertIs(drill.OBJECT_ID_CHECK,
                      recovery_module._metadata._check_object_id)

    def test_every_emitted_report_is_clean(self):
        for providers in ([], both_copies(),
                          {ONLINE: store_holding(ONLINE, KEPT_PAYLOAD)}):
            report = drill.reconstruct_mesh(
                snapshot_with_missing_irreplaceable(), providers,
                FakeMetadataStore())
            self.assertIs(drill.assert_report_is_clean(report), report)

    def test_a_report_field_with_no_checker_cannot_exist(self):
        payload = drill.reconstruct_mesh(
            snapshot_of([record(KEPT_PAYLOAD)]), both_copies(),
            FakeMetadataStore()).as_dict()
        payload["extra_field"] = "anything"
        with self.assertRaises(drill.RecoveryReportRejected):
            drill.assert_report_is_clean(payload)

    def test_an_unbounded_detail_is_refused(self):
        payload = drill.reconstruct_mesh(
            snapshot_of([record(KEPT_PAYLOAD)]), both_copies(),
            FakeMetadataStore()).as_dict()
        payload["detail"] = "a" * (drill.MAX_DETAIL + 1)
        with self.assertRaises(drill.RecoveryReportRejected):
            drill.assert_report_is_clean(payload)

    def test_a_report_claiming_a_recovered_object_it_also_calls_lost_is_refused(self):
        payload = drill.reconstruct_mesh(
            snapshot_with_missing_irreplaceable(), both_copies(),
            FakeMetadataStore()).as_dict()
        payload["recovered"] = frozenset(payload["recovered"] | {LOST_ID})
        with self.assertRaises(drill.RecoveryReportRejected):
            drill.assert_report_is_clean(payload)


class NoLeakTests(unittest.TestCase):
    """The needle goes through every input, including mapping keys."""

    def _assert_clean(self, *values):
        for value in values:
            self.assertNotIn(SMUGGLED_CREDENTIAL, value)
            self.assertNotIn("sk-A7bQ", value)

    def test_the_needle_never_reaches_a_report_a_refusal_or_a_traceback(self):
        snapshot = snapshot_of([record(KEPT_PAYLOAD)])
        needled_snapshot = dict(snapshot)
        needled_snapshot[SMUGGLED_CREDENTIAL] = SMUGGLED_CREDENTIAL
        cases = (
            (needled_snapshot, both_copies(), FakeMetadataStore()),
            (snapshot, {SMUGGLED_CREDENTIAL: store_holding(ONLINE, KEPT_PAYLOAD)},
             FakeMetadataStore()),
            (snapshot, {ONLINE: SMUGGLED_CREDENTIAL}, FakeMetadataStore()),
            (snapshot, [SMUGGLED_CREDENTIAL], FakeMetadataStore()),
            (snapshot, both_copies(), SMUGGLED_CREDENTIAL),
            (SMUGGLED_CREDENTIAL, SMUGGLED_CREDENTIAL, SMUGGLED_CREDENTIAL),
        )
        for snapshot_arg, provider_arg, store_arg in cases:
            with self.subTest(case=repr(provider_arg)[:24]):
                try:
                    report = drill.reconstruct_mesh(
                        snapshot_arg, provider_arg, store_arg)
                except drill.RecoveryRefused as exc:
                    self._assert_clean(str(exc), repr(exc),
                                       traceback.format_exc())
                else:
                    self._assert_clean(str(report), repr(report),
                                       str(report.as_dict()))

    def test_a_needled_report_refusal_leaks_nothing_through_context(self):
        payload = drill.reconstruct_mesh(
            snapshot_of([record(KEPT_PAYLOAD)]), both_copies(),
            FakeMetadataStore()).as_dict()
        payload["detail"] = SMUGGLED_CREDENTIAL
        try:
            drill.assert_report_is_clean(payload)
        except drill.RecoveryReportRejected:
            self._assert_clean(traceback.format_exc())
        else:
            self.fail("a needled detail must be refused")

    def test_a_needled_object_id_leaks_nothing_through_context(self):
        payload = drill.reconstruct_mesh(
            snapshot_of([record(KEPT_PAYLOAD)]), both_copies(),
            FakeMetadataStore()).as_dict()
        payload["unrecoverable"] = frozenset({SMUGGLED_CREDENTIAL})
        try:
            drill.assert_report_is_clean(payload)
        except drill.RecoveryReportRejected:
            self._assert_clean(traceback.format_exc())
        else:
            self.fail("a needled object id must be refused")


if __name__ == "__main__":
    unittest.main()
