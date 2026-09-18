"""Task 9a - automated repair of a replica set, and the one number that lies.

Spec S19 says what happens when a provider is lost: mark it OFFLINE, stop new
writes to it, serve reads from a *verified* replica, enqueue repair, restore the
required replica count on another eligible free provider, and update the
manifest only after hash verification. Spec S8 says how many copies are owed.
Spec S18 says destructive lifecycle stays blocked while the index is uncertain.

The single most important thing asserted in this file is a negative:
``replica_backends`` is a claim, not a copy. The index names the backends the
mesh registered at some point; a provider that has since gone offline, expired
the object, or never really took it still appears in that list. Task 5 counted
those claims and had to be fixed. So every test that talks about a replica count
here asks for a *confirmed* copy - bytes read back from that backend and hashed
to the object's own address - and the offline provider in the sample is in the
record, is scanned, fails, and never appears in ``verified_copies_after``.

Three further themes:

**Independence, not arity.** Two aliases pointing at one physical provider are
one copy. The mapping key must equal the store's own ``backend_id``, a provider
named twice is refused, and all local backends collapse into one independence
domain, because two paths on one host survive that host exactly as well as one.

**Nothing is deleted here.** ``repair.py`` contains no call to ``delete`` at
all; it reports ``destructive_cleanup_enabled`` and leaves the act to
``replication.rebalance_object``, which already carries the Spec S15 ordering.
A repair module that could delete is a repair module that can delete the last
verified copy on the strength of a claim.

**Bounded and quiet.** Provider scans are bounded by the configured provider
list and by ``MAX_PROVIDERS_SCANNED``; writes by ``MAX_REPAIR_WRITES``; each
destination is attempted at most once, so there is no retry loop to run away.
Refusals name fields and never echo values - the credential needle is fed
through every input including mapping *keys*, and must appear in no ``str``, no
``repr`` and no ``traceback.format_exc()``.

Nothing here opens a connection, writes a file or touches a provider account.
"""

from __future__ import annotations

import re
import traceback
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.storage import manifest as manifest_module
from AI_SKILL_LIBRARY.v4.storage import metadata as metadata_module
from AI_SKILL_LIBRARY.v4.storage import repair
from AI_SKILL_LIBRARY.v4.storage.adapters import s3_object

from AI_SKILL_LIBRARY.tests.test_storage_metadata import (
    AUTHORITY_FLAGS,
    FakeMetadataStore,
    MANIFEST_SCHEMA,
    SMUGGLED_CREDENTIAL,
    TIME,
)
from AI_SKILL_LIBRARY.tests.test_storage_s3_adapter import FakeS3Transport
from AI_SKILL_LIBRARY.tests.test_storage_replication import object_store

PAYLOAD = b"federated-free-storage-mesh-repair-object"
DIGEST = s3_object.content_digest(PAYLOAD)
OBJECT_ID = "obj_" + DIGEST

#: The provider that has been lost. It is named by the record, it is scanned,
#: and it answers nothing.
OFFLINE = "backblaze_b2"
#: The provider that really holds a copy: the only legitimate read source.
ONLINE = "cloudflare_r2"
#: The eligible free destination the repair is expected to reach.
SPARE = "oracle_object_storage"

EVERY_OPERATION = ("put", "get", "head", "delete")


def record(criticality="CRITICAL", **overrides):
    """A record claiming two holders, one of which is about to be a lie."""
    kwargs = dict(
        privacy_class="PUBLIC",
        criticality=criticality,
        storage_tier="WARM",
        object_class="benchmark-bundle",
        mime_type="application/octet-stream",
        retention_class="short-window",
        primary_backend=OFFLINE,
        replica_backends=(ONLINE,),
        created_at=TIME,
        lifecycle_state="RAW",
        reproducible=True,
    )
    kwargs.update(overrides)
    return manifest_module.StorageObject.from_bytes(
        PAYLOAD, **kwargs).to_manifest()


def holding_store(backend_id, *, holds=True, **kwargs):
    transport = FakeS3Transport(**kwargs)
    if holds:
        transport.objects[OBJECT_ID] = (PAYLOAD, {})
    return object_store(backend_id, transport)


def offline_store(backend_id=OFFLINE):
    """A provider that is registered, named by the record, and unreachable."""
    return object_store(backend_id, FakeS3Transport(raise_on=EVERY_OPERATION))


def providers(*, spare=True, online=True, offline=True):
    """The configured provider list: the bound on every scan in this module."""
    configured = {}
    if offline:
        configured[OFFLINE] = offline_store()
    if online:
        configured[ONLINE] = holding_store(ONLINE)
    if spare:
        configured[SPARE] = holding_store(SPARE, holds=False)
    return configured


def index(records=None, healthy=True):
    return FakeMetadataStore(
        records=records if records is not None else [record()], healthy=healthy)


def puts(store):
    """How many writes a store's transport actually received."""
    transport = store._transport  # noqa: SLF001 - the fake's own call log
    return [call for call in transport.calls if call["operation"] == "put"]


HOSTILE = (SMUGGLED_CREDENTIAL, "A" * 300, "", None, -1, 10 ** 30, True,
           False, 1.5, 2, [], {}, (), b"bytes", bytearray(b"bytes"),
           memoryview(b"bytes"), object(), "unexpected", set())


class AuthorityTests(unittest.TestCase):
    """Repair decides nothing about placement, routing or approval."""

    def test_no_authority_of_any_kind(self):
        self.assertIs(repair.AUTHORITY, False)
        self.assertEqual(set(repair.AUTHORITY_FLAGS), set(AUTHORITY_FLAGS))
        for flag in AUTHORITY_FLAGS:
            self.assertIs(repair.AUTHORITY_FLAGS[flag], False, flag)

    def test_github_remains_canonical(self):
        self.assertEqual(repair.CANONICAL_AUTHORITY, "GITHUB_BRAIN_V4")
        self.assertEqual(repair.ROUTED_BY, "task_router")

    def test_no_cryptography_is_invented_here(self):
        self.assertIs(repair.ENCRYPTION_IMPLEMENTED_HERE, False)
        for name in ("encrypt", "decrypt", "derive_key", "wrap_key"):
            self.assertFalse(hasattr(repair, name), name)
        source = Path(repair.__file__).read_text(encoding="utf-8")
        self.assertNotIn("import hmac", source)

    def test_the_module_creates_nothing_external(self):
        self.assertIs(repair.CREATES_EXTERNAL_RESOURCES, False)
        self.assertIs(repair.PROVISIONING_AUTHORIZED, False)
        source = Path(repair.__file__).read_text(encoding="utf-8")
        for forbidden in ("import requests", "import socket", "import urllib",
                          "boto3"):
            self.assertNotIn(forbidden, source, forbidden)

    def test_anchored_patterns_use_backslash_Z(self):
        source = Path(repair.__file__).read_text(encoding="utf-8")
        for line in source.splitlines():
            if "re.compile" in line:
                self.assertNotIn('$"', line, line)
                self.assertNotIn("$'", line, line)


class NoDeletionHereTests(unittest.TestCase):
    """The structural half of "never delete the final verified copy"."""

    def test_the_module_declares_and_contains_no_deletion(self):
        self.assertIs(repair.PERFORMS_DELETION, False)
        source = Path(repair.__file__).read_text(encoding="utf-8")
        self.assertNotIn(".delete(", source)

    def test_destructive_cleanup_is_disabled_until_obligations_are_met(self):
        # Degraded: one confirmed copy where two are owed.
        result = repair.repair_replica_set(
            record(), providers(spare=False), index())
        self.assertIs(result.degraded, True)
        self.assertIs(result.destructive_cleanup_enabled, False)

    def test_destructive_cleanup_is_disabled_while_the_index_is_uncertain(self):
        result = repair.repair_replica_set(
            record(), providers(), index(healthy=False))
        self.assertEqual(result.status, "BLOCKED_METADATA_UNCERTAIN")
        self.assertIs(result.destructive_cleanup_enabled, False)

    def test_cleanup_is_enabled_only_when_healthy_and_satisfied(self):
        store = index()
        result = repair.repair_replica_set(record(), providers(), store)
        self.assertEqual(result.status, "REPAIRED")
        self.assertIs(result.degraded, False)
        self.assertIs(result.destructive_cleanup_enabled, True)


class ProviderLossTests(unittest.TestCase):
    """The plan's first sample, and the rule underneath it."""

    def test_provider_loss_reads_replica_and_repairs_count(self):
        configured = providers()
        result = repair.repair_replica_set(record(), configured, index())
        self.assertNotEqual(result.read_source, OFFLINE)
        self.assertEqual(result.read_source, ONLINE)
        self.assertEqual(result.target_replica_count, 2)
        self.assertEqual(result.status, "REPAIRED")
        self.assertEqual(result.repaired_to, (SPARE,))
        self.assertEqual(result.verified_copies_after,
                         tuple(sorted((ONLINE, SPARE))))

    def test_the_offline_provider_is_never_counted_and_never_written_to(self):
        configured = providers()
        result = repair.repair_replica_set(record(), configured, index())
        self.assertNotIn(OFFLINE, result.verified_copies_before)
        self.assertNotIn(OFFLINE, result.verified_copies_after)
        self.assertIn(OFFLINE, result.unconfirmed)
        # Spec S19: a provider that could not be probed is marked OFFLINE and
        # receives no new writes. It is not a repair destination.
        self.assertEqual(puts(configured[OFFLINE]), [])

    def test_the_index_claim_alone_is_never_a_copy(self):
        """The whole defect from Task 5, stated as one assertion.

        The record names both backends. Only one of them answers. A count taken
        from ``replica_backends`` would be 2 and the object would look healthy
        while one real copy existed.
        """
        claimed = record()
        self.assertEqual(
            {claimed["primary_backend"], *claimed["replica_backends"]},
            {OFFLINE, ONLINE})
        result = repair.repair_replica_set(
            claimed, providers(spare=False), index())
        self.assertEqual(result.verified_copies_before, (ONLINE,))
        self.assertEqual(result.verified_copies_after, (ONLINE,))
        self.assertIs(result.degraded, True)
        self.assertEqual(result.status, "DEGRADED_INSUFFICIENT_DESTINATIONS")

    def test_the_repaired_copy_is_registered_in_the_index(self):
        store = index()
        repair.repair_replica_set(record(), providers(), store)
        stored = store.get_manifest(OBJECT_ID)
        holders = {stored["primary_backend"], *stored["replica_backends"]}
        self.assertIn(SPARE, holders)
        # The failed holder is not struck from the record: a failed probe is a
        # repair job, not a licence to edit the index downwards (Spec S19).
        self.assertIn(OFFLINE, holders)

    def test_a_corrupt_copy_is_not_a_copy_and_is_not_a_destination(self):
        configured = providers(online=False)
        configured[ONLINE] = holding_store(ONLINE, corrupt_get=True)
        result = repair.repair_replica_set(record(), configured, index())
        self.assertNotIn(ONLINE, result.verified_copies_before)
        self.assertEqual(result.status, "DEGRADED_NO_VERIFIED_COPY")
        self.assertIsNone(result.read_source)
        self.assertEqual(puts(configured[SPARE]), [])

    def test_no_verified_copy_anywhere_fabricates_nothing(self):
        configured = {OFFLINE: offline_store(),
                      SPARE: holding_store(SPARE, holds=False)}
        result = repair.repair_replica_set(record(), configured, index())
        self.assertEqual(result.status, "DEGRADED_NO_VERIFIED_COPY")
        self.assertIsNone(result.read_source)
        self.assertEqual(result.repaired_to, ())
        self.assertEqual(result.verified_copies_after, ())
        self.assertIs(result.degraded, True)
        self.assertEqual(puts(configured[SPARE]), [])

    def test_an_already_satisfied_object_is_left_alone(self):
        configured = {ONLINE: holding_store(ONLINE),
                      SPARE: holding_store(SPARE)}
        result = repair.repair_replica_set(
            record(primary_backend=ONLINE, replica_backends=(SPARE,)),
            configured, index(records=[record(primary_backend=ONLINE,
                                              replica_backends=(SPARE,))]))
        self.assertEqual(result.status, "ALREADY_SATISFIED")
        self.assertEqual(result.repaired_to, ())
        self.assertEqual(puts(configured[SPARE]), [])
        self.assertIs(result.degraded, False)

    def test_an_ephemeral_object_is_owed_nothing_and_nothing_is_written(self):
        configured = providers()
        result = repair.repair_replica_set(
            record(criticality="EPHEMERAL"), configured,
            index(records=[record(criticality="EPHEMERAL")]))
        self.assertEqual(result.target_replica_count, 0)
        self.assertEqual(result.status, "ALREADY_SATISFIED")
        self.assertEqual(puts(configured[SPARE]), [])


class IndependenceTests(unittest.TestCase):
    """A copy is independent or it is not a second copy (Spec S8)."""

    def test_all_local_backends_share_one_independence_domain(self):
        self.assertEqual(repair.independence_domain("local_owned_store"),
                         repair.LOCAL_INDEPENDENCE_DOMAIN)
        self.assertNotEqual(repair.independence_domain(ONLINE),
                            repair.LOCAL_INDEPENDENCE_DOMAIN)

    def test_each_external_provider_is_its_own_domain(self):
        self.assertNotEqual(repair.independence_domain(ONLINE),
                            repair.independence_domain(SPARE))
        self.assertEqual(repair.independence_domain(ONLINE), ONLINE)

    def test_an_alias_key_that_is_not_the_backends_own_id_is_refused(self):
        configured = dict(providers())
        configured["not_the_backend_id"] = holding_store(ONLINE)
        result = repair.repair_replica_set(record(), configured, index())
        self.assertEqual(result.status, "REFUSED_INVALID_REQUEST")

    def test_the_same_provider_listed_twice_is_refused(self):
        listed = [holding_store(ONLINE), holding_store(ONLINE)]
        result = repair.repair_replica_set(record(), listed, index())
        self.assertEqual(result.status, "REFUSED_INVALID_REQUEST")

    def test_a_sequence_of_stores_is_keyed_by_the_backends_own_id(self):
        listed = [offline_store(), holding_store(ONLINE),
                  holding_store(SPARE, holds=False)]
        result = repair.repair_replica_set(record(), listed, index())
        self.assertEqual(result.status, "REPAIRED")
        self.assertEqual(result.read_source, ONLINE)


class DestinationEligibilityTests(unittest.TestCase):
    """Privacy outranks capacity, and repair is not a placement engine."""

    def test_a_local_only_object_is_never_repaired_to_an_external_backend(self):
        local = record(privacy_class="LOCAL_ONLY",
                       primary_backend="local_owned_store",
                       replica_backends=())
        for backend in (ONLINE, SPARE, OFFLINE):
            with self.subTest(backend=backend):
                self.assertIs(
                    repair.destination_is_eligible(local, backend), False)
        self.assertIs(
            repair.destination_is_eligible(local, "local_owned_store"), True)

    def test_a_public_object_may_reach_an_admitted_external_backend(self):
        self.assertIs(repair.destination_is_eligible(record(), SPARE), True)

    def test_a_backend_outside_the_registry_is_never_eligible(self):
        self.assertIs(
            repair.destination_is_eligible(record(), "not_a_provider"), False)
        self.assertIs(
            repair.destination_is_eligible(record(), SMUGGLED_CREDENTIAL), False)


class BoundsTests(unittest.TestCase):
    """Every cap is stated, and every cap is enforced."""

    def test_the_caps_are_declared(self):
        self.assertEqual(repair.MAX_PROVIDERS_SCANNED, 16)
        self.assertEqual(repair.MAX_REPAIR_WRITES, 4)
        self.assertEqual(repair.MAX_TARGET_COPIES,
                         manifest_module._MAX_REPLICAS)
        self.assertLessEqual(repair.MAX_REPAIR_WRITES,
                             repair.MAX_PROVIDERS_SCANNED)

    def test_a_provider_list_over_the_cap_is_refused(self):
        configured = {f"filler_{n}": None
                      for n in range(repair.MAX_PROVIDERS_SCANNED + 1)}
        result = repair.repair_replica_set(record(), configured, index())
        self.assertEqual(result.status, "REFUSED_INVALID_REQUEST")

    def test_each_destination_is_attempted_at_most_once(self):
        """There is no retry loop: a destination that refuses is not revisited."""
        configured = providers()
        configured[SPARE] = object_store(
            SPARE, FakeS3Transport(raise_on=("put",)))
        result = repair.repair_replica_set(record(), configured, index())
        self.assertEqual(len(puts(configured[SPARE])), 1)
        self.assertIs(result.degraded, True)
        self.assertEqual(result.repaired_to, ())

    def test_the_write_budget_is_never_exceeded(self):
        self.assertLessEqual(repair.MAX_REPAIR_WRITES, repair.MAX_TARGET_COPIES)
        configured = providers()
        result = repair.repair_replica_set(record(), configured, index())
        self.assertLessEqual(len(result.repaired_to), repair.MAX_REPAIR_WRITES)


class FailClosedTests(unittest.TestCase):
    """Spec S14: degrade, refuse, never crash."""

    def test_an_uncertain_index_blocks_the_repair_entirely(self):
        configured = providers()
        result = repair.repair_replica_set(
            record(), configured, index(healthy=False))
        self.assertEqual(result.status, "BLOCKED_METADATA_UNCERTAIN")
        self.assertEqual(puts(configured[SPARE]), [])

    def test_a_duck_typed_metadata_store_is_not_a_metadata_store(self):
        class Plausible:
            def healthy(self):
                return True

            def get_manifest(self, object_id):
                return None

            def put_manifest(self, manifest):
                return None

        result = repair.repair_replica_set(record(), providers(), Plausible())
        self.assertEqual(result.status, "BLOCKED_METADATA_UNCERTAIN")

    def test_a_copy_that_cannot_be_registered_is_reported_not_claimed(self):
        class RefusingIndex(FakeMetadataStore):
            def _put_record(self, object_id, record_):
                raise RuntimeError("the index refused the write")

        result = repair.repair_replica_set(
            record(), providers(), RefusingIndex(records=[record()]))
        self.assertEqual(result.status, "DEGRADED_COPY_UNREGISTERED")
        self.assertIs(result.degraded, True)
        self.assertIs(result.destructive_cleanup_enabled, False)
        self.assertEqual(result.repaired_to, ())

    def test_hostile_arguments_never_raise_and_never_succeed(self):
        for value in HOSTILE:
            with self.subTest(value=repr(value)[:24]):
                result = repair.repair_replica_set(value, providers(), index())
                self.assertIn(result.status, repair.REPAIR_STATUSES)
                self.assertIs(result.destructive_cleanup_enabled, False)
                result = repair.repair_replica_set(record(), value, index())
                self.assertIn(result.status, repair.REPAIR_STATUSES)
                result = repair.repair_replica_set(record(), providers(), value)
                self.assertIn(result.status, repair.REPAIR_STATUSES)

    def test_bytes_is_a_sequence_and_is_not_a_provider_list(self):
        for value in (b"cloudflare_r2", bytearray(b"cloudflare_r2"),
                      "cloudflare_r2"):
            with self.subTest(value=repr(value)[:24]):
                result = repair.repair_replica_set(record(), value, index())
                self.assertEqual(result.status, "REFUSED_INVALID_REQUEST")

    def test_a_non_object_store_in_the_provider_list_is_refused(self):
        class Plausible:
            backend_id = ONLINE

            def get(self, object_id):
                return PAYLOAD

            def head(self, object_id):
                return None

        result = repair.repair_replica_set(
            record(), {ONLINE: Plausible()}, index())
        self.assertEqual(result.status, "REFUSED_INVALID_REQUEST")

    def test_an_object_the_index_does_not_know_is_refused(self):
        result = repair.repair_replica_set(
            record(), providers(), FakeMetadataStore(records=[]))
        self.assertEqual(result.status, "REFUSED_UNKNOWN_OBJECT")

    def test_every_status_emitted_is_in_the_closed_vocabulary(self):
        self.assertEqual(len(set(repair.REPAIR_STATUSES)),
                         len(repair.REPAIR_STATUSES))
        for status in repair.REPAIR_STATUSES:
            self.assertRegex(status, r"\A[A-Z][A-Z_]{0,63}\Z")


class StructuralGuardTests(unittest.TestCase):
    """The field tuple comes from the checker table; the table from the schema."""

    def test_the_manifest_partition_is_driven_from_the_schema_on_disk(self):
        read = set(repair.MANIFEST_FIELDS_READ)
        not_read = set(repair.MANIFEST_FIELDS_NOT_READ)
        self.assertEqual(read | not_read, set(MANIFEST_SCHEMA["properties"]))
        self.assertEqual(read & not_read, set())

    def test_every_read_field_binds_the_identical_metadata_checker(self):
        """No seventh copy: the same callable object, asserted with ``is``."""
        for field, checker in repair.MANIFEST_FIELDS_READ.items():
            with self.subTest(field=field):
                self.assertIs(
                    checker, metadata_module._RECORD_FIELD_CHECKS[field])

    def test_every_field_not_read_states_a_reason(self):
        for field, reason in repair.MANIFEST_FIELDS_NOT_READ.items():
            with self.subTest(field=field):
                self.assertIsInstance(reason, str)
                self.assertGreater(len(reason), 20)

    def test_the_result_field_tuple_is_derived_from_its_check_table(self):
        self.assertEqual(repair.RESULT_FIELDS, tuple(repair.RESULT_VALUE_CHECKS))
        self.assertEqual(
            set(repair.RESULT_FIELDS),
            {f.name for f in repair.RepairResult.__dataclass_fields__.values()})

    def test_every_string_result_field_is_bounded_by_pattern_and_length(self):
        for field, pattern in repair.RESULT_FIELD_PATTERNS.items():
            with self.subTest(field=field):
                self.assertIn(field, repair.RESULT_VALUE_CHECKS)
                self.assertIn(field, repair.RESULT_FIELD_MAX_LENGTHS)
                self.assertIsInstance(pattern, re.Pattern)
                self.assertTrue(pattern.pattern.endswith("\\Z"), field)
                self.assertGreater(repair.RESULT_FIELD_MAX_LENGTHS[field], 0)

    def test_every_emitted_result_is_clean(self):
        for maker in (lambda: repair.repair_replica_set(record(), providers(),
                                                        index()),
                      lambda: repair.repair_replica_set(record(),
                                                        providers(spare=False),
                                                        index()),
                      lambda: repair.repair_replica_set(record(), providers(),
                                                        index(healthy=False)),
                      lambda: repair.repair_replica_set(None, None, None)):
            result = maker()
            self.assertIs(repair.assert_result_is_clean(result), result)

    def test_a_result_field_with_no_checker_cannot_exist(self):
        self.assertEqual(set(repair.RESULT_VALUE_CHECKS),
                         set(repair.RESULT_FIELDS))
        doctored = repair.repair_replica_set(record(), providers(), index())
        payload = doctored.as_dict()
        payload["extra_field"] = "anything"
        with self.assertRaises(repair.RepairResultRejected):
            repair.assert_result_is_clean(payload)

    def test_an_unbounded_detail_is_refused(self):
        payload = repair.repair_replica_set(
            record(), providers(), index()).as_dict()
        payload["detail"] = "a" * (repair.MAX_DETAIL + 1)
        with self.assertRaises(repair.RepairResultRejected):
            repair.assert_result_is_clean(payload)


class NoLeakTests(unittest.TestCase):
    """The needle goes through every input, including mapping keys."""

    def _assert_clean(self, *values):
        for value in values:
            self.assertNotIn(SMUGGLED_CREDENTIAL, value)
            self.assertNotIn("sk-A7bQ", value)

    def test_the_needle_never_reaches_a_result_or_a_traceback(self):
        needled_record = dict(record())
        needled_record[SMUGGLED_CREDENTIAL] = SMUGGLED_CREDENTIAL
        cases = (
            (needled_record, providers(), index()),
            (dict(record(), object_class=SMUGGLED_CREDENTIAL), providers(),
             index()),
            (record(), {SMUGGLED_CREDENTIAL: holding_store(ONLINE)}, index()),
            (record(), {ONLINE: SMUGGLED_CREDENTIAL}, index()),
            (record(), [SMUGGLED_CREDENTIAL], index()),
            (record(), providers(), SMUGGLED_CREDENTIAL),
            (SMUGGLED_CREDENTIAL, SMUGGLED_CREDENTIAL, SMUGGLED_CREDENTIAL),
        )
        for manifest_arg, provider_arg, store_arg in cases:
            with self.subTest(case=repr(provider_arg)[:24]):
                try:
                    result = repair.repair_replica_set(
                        manifest_arg, provider_arg, store_arg)
                except Exception:  # noqa: BLE001 - it must not, and is checked
                    self._assert_clean(traceback.format_exc())
                    raise
                self._assert_clean(str(result), repr(result),
                                   str(result.as_dict()))

    def test_a_refusal_of_a_needled_result_leaks_nothing_through_context(self):
        payload = repair.repair_replica_set(
            record(), providers(), index()).as_dict()
        payload["detail"] = SMUGGLED_CREDENTIAL
        try:
            repair.assert_result_is_clean(payload)
        except repair.RepairResultRejected:
            self._assert_clean(traceback.format_exc())
        else:
            self.fail("a needled detail must be refused")

    def test_a_needled_object_id_leaks_nothing_through_context(self):
        payload = repair.repair_replica_set(
            record(), providers(), index()).as_dict()
        payload["object_id"] = SMUGGLED_CREDENTIAL
        try:
            repair.assert_result_is_clean(payload)
        except repair.RepairResultRejected:
            self._assert_clean(traceback.format_exc())
        else:
            self.fail("a needled object_id must be refused")


if __name__ == "__main__":
    unittest.main()
