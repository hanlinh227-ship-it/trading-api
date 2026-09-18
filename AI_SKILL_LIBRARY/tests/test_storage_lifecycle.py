"""Task 7b - the pressure response, and the deletions it must never propose.

Spec S14 lists eight responses to storage pressure and then says, in case the
list read as advice, that the system must degrade instead of crashing. Three of
those eight steps can destroy data, which makes this the module in the lane with
the most ways to be quietly wrong, so the tests are built around four
properties rather than around the happy path.

**It proposes; it does not act.** ``lifecycle_actions`` returns ``Action``
values. Returning an ``Action`` is not executing one, and the tests assert the
distinction directly: no file is written, no connection is opened, no store is
called, and the module declares ``PERFORMS_DELETION_HERE = False``.

**A CRITICAL object is never capacity-deleted.** Not at NEAR_FULL, not in
degraded mode, not when every provider is full. The sweep below runs every
provider state in ``PROVIDER_STATES``, every power set of them, with the
metadata store healthy and confirmed copies supplied - every condition that
could possibly unlock a deletion - and requires that no ``DELETE`` ever names
it. ``policy.yaml`` says ``auto_delete_for_capacity: false`` for CRITICAL and
for IMPORTANT, and the module reads that from the document rather than
mirroring it, so both are covered.

**No last verified copy is ever proposed for deletion.** Task 5 was found
counting index claims - the record's own ``replica_backends`` - instead of
confirmed copies. The tests here supply a record claiming three replicas with
one confirmed copy and require silence, because a claim is not a copy.

**Uncertain evidence fails closed.** Absent metadata store, unhealthy store,
malformed record, unknown provider state, unparseable ``last_verified_at``:
each one on its own is enough to stop every destructive proposal. An absent
fact is never permission.
"""

from __future__ import annotations

import io
import itertools
import json
import pathlib
import traceback
import unittest
from unittest import mock

from AI_SKILL_LIBRARY.v4.storage import capacity, lifecycle, mesh_validator
from AI_SKILL_LIBRARY.v4.storage import manifest as manifest_module
from AI_SKILL_LIBRARY.v4.storage import metadata as metadata_module

from AI_SKILL_LIBRARY.tests.test_storage_metadata import (
    FakeMetadataStore,
    SMUGGLED_CREDENTIAL,
    TIME,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MANIFEST_SCHEMA_PATH = (
    REPO_ROOT / "AI_SKILL_LIBRARY/v4/schemas/storage_object_manifest.schema.json")

AUTHORITY_FLAGS = (
    "storage_authority", "routing_authority", "reasoning_authority",
    "model_selection_authority", "admission_authority", "scheduling_authority",
    "merge_authority", "trading_authority",
)

NOW = "2026-09-20T00:00:00Z"
OLD = "2026-09-01T00:00:00Z"

PRIMARY = "cloudflare_r2"
REPLICA = "backblaze_b2"
THIRD = "oracle_object_storage"


def schema_properties():
    return set(json.loads(MANIFEST_SCHEMA_PATH.read_text())["properties"])


def obj(content=b"storage-mesh-object", **overrides):
    """A manifest record, built by the typed producer rather than by hand."""
    kwargs = dict(
        privacy_class="PUBLIC",
        criticality="REPRODUCIBLE",
        storage_tier="WARM",
        object_class="benchmark-bundle",
        mime_type="application/octet-stream",
        retention_class="short-window",
        primary_backend=PRIMARY,
        replica_backends=(REPLICA,),
        created_at=OLD,
        last_accessed_at=OLD,
        last_verified_at=OLD,
        lifecycle_state="RAW",
        reproducible=True,
        verification={"hash_verified": True, "verified_replica_count": 2,
                      "last_probe_at": OLD},
    )
    kwargs.update(overrides)
    return manifest_module.StorageObject.from_bytes(content, **kwargs).to_manifest()


def critical_object(content=b"release-evidence"):
    return obj(content, criticality="CRITICAL", reproducible=False,
               replica_backends=(REPLICA, THIRD))


def ephemeral_object(content=b"transient-evidence"):
    return obj(content, criticality="EPHEMERAL", storage_tier="HOT")


def healthy_store():
    return FakeMetadataStore()


def all_confirmed(record):
    """Every backend the record names, as if each had been head-verified."""
    return {record["object_id"]:
            {record["primary_backend"], *record["replica_backends"]}}


def deletes(actions):
    return [action for action in actions if action.kind == "DELETE"]


class AuthorityTests(unittest.TestCase):
    """Spec S2. A subordinate subsystem that proposes and never decides."""

    def test_module_holds_no_authority(self):
        self.assertIs(lifecycle.AUTHORITY, False)
        self.assertEqual(set(lifecycle.AUTHORITY_FLAGS), set(AUTHORITY_FLAGS))
        for flag, held in lifecycle.AUTHORITY_FLAGS.items():
            self.assertIs(held, False, flag)

    def test_module_declares_that_it_performs_nothing(self):
        self.assertIs(lifecycle.PROPOSAL_ONLY, True)
        self.assertIs(lifecycle.PERFORMS_DELETION_HERE, False)
        self.assertIs(lifecycle.PERFORMS_NETWORK_IO_HERE, False)
        self.assertIs(lifecycle.ENCRYPTION_IMPLEMENTED_HERE, False)

    def test_an_action_is_a_proposal_and_says_so(self):
        actions = lifecycle.lifecycle_actions([obj()], {PRIMARY: "NEAR_FULL"})
        self.assertTrue(actions)
        for action in actions:
            self.assertIs(action.proposal_only, True)
            self.assertIn(action.kind, lifecycle.ACTION_KINDS)
            self.assertIn(action.step, range(1, 9))

    def test_the_module_never_touches_the_store_it_is_asked_about(self):
        """``can_perform_destructive_lifecycle`` asks a question; nothing here
        reads, writes or lists through the index."""
        store = healthy_store()
        with mock.patch.object(FakeMetadataStore, "_get_record",
                               side_effect=AssertionError("read attempted")), \
             mock.patch.object(FakeMetadataStore, "_put_record",
                               side_effect=AssertionError("write attempted")), \
             mock.patch.object(FakeMetadataStore, "_all_records",
                               side_effect=AssertionError("list attempted")):
            lifecycle.lifecycle_actions(
                [obj(), critical_object()], {PRIMARY: "NEAR_FULL"},
                now=NOW, metadata_store=store,
                confirmed_copies=all_confirmed(obj()))

    def test_no_file_is_opened_while_deciding(self):
        real_open = io.open
        opened = []

        def watched(*args, **kwargs):
            opened.append(args[:1])
            return real_open(*args, **kwargs)

        lifecycle.lifecycle_actions([obj()], {PRIMARY: "HEALTHY"})  # warm caches
        with mock.patch("io.open", watched), mock.patch("builtins.open", watched):
            lifecycle.lifecycle_actions([obj(), critical_object()],
                                        {PRIMARY: "NEAR_FULL"}, now=NOW)
        self.assertEqual(opened, [])


class StructuralGuardTests(unittest.TestCase):
    """Every manifest property is read for a reason or ignored for one.

    Driven from the schema on disk, so a property added to the contract later is
    in neither table and fails this test the day it is added, rather than
    arriving as a field a deletion gate silently does not consult.
    """

    def test_partition_covers_the_manifest_schema_exactly(self):
        partition = (set(lifecycle.DECISION_FIELDS)
                     | set(lifecycle.IGNORED_MANIFEST_FIELDS))
        self.assertEqual(partition, schema_properties())

    def test_the_two_halves_are_disjoint(self):
        self.assertEqual(
            set(lifecycle.DECISION_FIELDS) & set(lifecycle.IGNORED_MANIFEST_FIELDS),
            set())

    def test_the_partition_matches_the_metadata_field_table(self):
        self.assertEqual(set(lifecycle.DECISION_FIELDS)
                         | set(lifecycle.IGNORED_MANIFEST_FIELDS),
                         set(metadata_module.RECORD_FIELDS))

    def test_every_ignored_field_carries_a_written_reason(self):
        for field, reason in lifecycle.IGNORED_MANIFEST_FIELDS.items():
            self.assertIsInstance(reason, str, field)
            self.assertGreater(len(reason), 40, field)

    def test_decision_fields_are_derived_from_the_checker_table(self):
        self.assertEqual(lifecycle.DECISION_FIELDS,
                         tuple(lifecycle.DECISION_VALUE_CHECKS))

    def test_checkers_are_the_metadata_tables_own_callables(self):
        """Bound by identity, not re-implemented. A sixth copy of a bounded
        checker is a copy that will drift, and the looser one gets used."""
        for field, check in lifecycle.DECISION_VALUE_CHECKS.items():
            with self.subTest(field=field):
                self.assertIs(check, metadata_module._RECORD_FIELD_CHECKS[field])


class PressureOrderTests(unittest.TestCase):
    """Spec S14's eight steps, as ordered gates rather than as weights."""

    def test_the_declared_order_is_exactly_the_spec(self):
        self.assertEqual(
            tuple(name for _, name, _ in lifecycle.PRESSURE_STEPS),
            ("EXPIRE_EPHEMERAL", "COMPACT_TELEMETRY_AND_EXPERIENCE",
             "EVICT_REDUNDANT_REPRODUCIBLE", "COMPRESS_COLD_EVIDENCE",
             "REBALANCE_MOVABLE", "PAUSE_NON_CRITICAL_LEARNING_WRITES",
             "RESERVE_CAPACITY_FOR_CRITICAL", "ENTER_DEGRADED_READ_ONLY"))
        self.assertEqual(tuple(number for number, _, _ in lifecycle.PRESSURE_STEPS),
                         tuple(range(1, 9)))

    def test_only_the_first_step_with_anything_to_propose_proposes(self):
        record = ephemeral_object()
        store = healthy_store()
        actions = lifecycle.lifecycle_actions(
            [record, obj(b"cold", storage_tier="COLD")],
            {PRIMARY: "NEAR_FULL"}, now=NOW, metadata_store=store,
            confirmed_copies=all_confirmed(record))
        self.assertTrue(actions)
        self.assertEqual({action.step for action in actions}, {1})

    def test_a_later_step_never_runs_before_an_earlier_one_is_exhausted(self):
        """The same inputs at every pressure: the step that answers is always
        the lowest-numbered one with work, and no amount of pressure reorders
        them."""
        record = ephemeral_object()
        store = healthy_store()
        for state in capacity.PROVIDER_STATES:
            with self.subTest(state=state):
                actions = lifecycle.lifecycle_actions(
                    [record], {PRIMARY: state}, now=NOW, metadata_store=store,
                    confirmed_copies=all_confirmed(record))
                steps = {action.step for action in actions}
                self.assertLessEqual(len(steps), 1)

    def test_compression_waits_until_there_is_nothing_left_to_evict(self):
        evictable = obj(b"redundant")
        cold = obj(b"cold-evidence", storage_tier="COLD",
                   criticality="IMPORTANT", reproducible=False)
        store = healthy_store()
        confirmed = all_confirmed(evictable)
        actions = lifecycle.lifecycle_actions(
            [evictable, cold], {PRIMARY: "NEAR_FULL"}, now=NOW,
            metadata_store=store, confirmed_copies=confirmed)
        self.assertEqual({action.step for action in actions}, {3})
        self.assertTrue(deletes(actions))

        # Remove the evictable object's evidence and step 4 becomes reachable.
        actions = lifecycle.lifecycle_actions(
            [cold], {PRIMARY: "NEAR_FULL"}, now=NOW, metadata_store=store,
            confirmed_copies={})
        self.assertEqual({action.step for action in actions}, {4})
        self.assertEqual(deletes(actions), [])

    def test_degraded_mode_is_the_last_resort_and_not_a_crash(self):
        actions = lifecycle.lifecycle_actions(
            [], {PRIMARY: "OFFLINE", REPLICA: "READ_ONLY"}, now=NOW)
        self.assertEqual([action.kind for action in actions],
                         ["ENTER_DEGRADED_READ_ONLY"])
        self.assertEqual(actions[0].step, 8)

    def test_no_pressure_and_nothing_to_do_is_an_empty_list(self):
        self.assertEqual(
            lifecycle.lifecycle_actions([obj(storage_tier="COLD",
                                             lifecycle_state="ARCHIVED")],
                                        {PRIMARY: "HEALTHY"}, now=NOW),
            [])


class CriticalIsNeverCapacityDeletedTests(unittest.TestCase):
    """policy.yaml ``auto_delete_for_capacity: false``. Tested directly."""

    def test_the_never_deleted_set_is_read_from_policy_not_mirrored(self):
        self.assertIn("CRITICAL", lifecycle.NEVER_CAPACITY_DELETED)
        self.assertIn("IMPORTANT", lifecycle.NEVER_CAPACITY_DELETED)
        self.assertNotIn("REPRODUCIBLE", lifecycle.NEVER_CAPACITY_DELETED)
        self.assertNotIn("EPHEMERAL", lifecycle.NEVER_CAPACITY_DELETED)

    def test_critical_never_capacity_deleted_in_any_single_provider_state(self):
        record = critical_object()
        store = healthy_store()
        for state in capacity.PROVIDER_STATES:
            with self.subTest(state=state):
                actions = lifecycle.lifecycle_actions(
                    [record], {PRIMARY: state}, now=NOW, metadata_store=store,
                    confirmed_copies=all_confirmed(record))
                self.assertEqual(
                    [a for a in actions
                     if a.kind == "DELETE" and a.object_id == record["object_id"]],
                    [])

    def test_critical_never_capacity_deleted_when_every_provider_is_full(self):
        record = critical_object()
        store = healthy_store()
        for size in (1, 2, 3):
            for combination in itertools.combinations(
                    (PRIMARY, REPLICA, THIRD), size):
                states = {name: "NEAR_FULL" for name in combination}
                with self.subTest(states=states):
                    actions = lifecycle.lifecycle_actions(
                        [record], states, now=NOW, metadata_store=store,
                        confirmed_copies=all_confirmed(record))
                    self.assertEqual(deletes(actions), [])

    def test_critical_survives_even_beside_an_object_that_is_being_evicted(self):
        critical = critical_object()
        evictable = obj(b"redundant")
        store = healthy_store()
        confirmed = {**all_confirmed(critical), **all_confirmed(evictable)}
        actions = lifecycle.lifecycle_actions(
            [critical, evictable], {PRIMARY: "NEAR_FULL"}, now=NOW,
            metadata_store=store, confirmed_copies=confirmed)
        self.assertTrue(deletes(actions))
        self.assertEqual(
            [a for a in deletes(actions) if a.object_id == critical["object_id"]],
            [])

    def test_important_is_not_capacity_deleted_either(self):
        record = obj(b"important-evidence", criticality="IMPORTANT",
                     reproducible=False)
        store = healthy_store()
        actions = lifecycle.lifecycle_actions(
            [record], {PRIMARY: "NEAR_FULL"}, now=NOW, metadata_store=store,
            confirmed_copies=all_confirmed(record))
        self.assertEqual(deletes(actions), [])

    def test_the_post_condition_guard_drops_a_forbidden_delete(self):
        """Independent of the steps: a rogue step proposing the forbidden
        deletion has that proposal removed before the caller ever sees it."""
        record = critical_object()

        def rogue(context):
            return [lifecycle.Action(
                step=3, kind="DELETE", object_id=record["object_id"],
                provider_id=PRIMARY, reason="CAPACITY_PRESSURE",
                destructive=True, requires_authorization=True, evidence={})]

        patched = ((3, "EVICT_REDUNDANT_REPRODUCIBLE", rogue),)
        with mock.patch.object(lifecycle, "PRESSURE_STEPS", patched):
            actions = lifecycle.lifecycle_actions(
                [record], {PRIMARY: "NEAR_FULL"}, now=NOW,
                metadata_store=healthy_store(),
                confirmed_copies=all_confirmed(record))
        self.assertEqual(deletes(actions), [])

    def test_the_post_condition_guard_drops_a_delete_for_an_unknown_object(self):
        def rogue(context):
            return [lifecycle.Action(
                step=3, kind="DELETE", object_id="obj_" + "a" * 64,
                provider_id=PRIMARY, reason="CAPACITY_PRESSURE",
                destructive=True, requires_authorization=True, evidence={})]

        patched = ((3, "EVICT_REDUNDANT_REPRODUCIBLE", rogue),)
        with mock.patch.object(lifecycle, "PRESSURE_STEPS", patched):
            actions = lifecycle.lifecycle_actions(
                [obj()], {PRIMARY: "NEAR_FULL"}, now=NOW,
                metadata_store=healthy_store())
        self.assertEqual(deletes(actions), [])


class LastVerifiedCopyTests(unittest.TestCase):
    """A claim in the index is not a copy anybody has seen (Spec S15 step 7)."""

    def test_no_eviction_without_a_confirmed_surviving_copy(self):
        record = obj()
        actions = lifecycle.lifecycle_actions(
            [record], {PRIMARY: "NEAR_FULL"}, now=NOW,
            metadata_store=healthy_store(), confirmed_copies=None)
        self.assertEqual(deletes(actions), [])

    def test_claimed_replicas_are_not_counted_as_copies(self):
        """The record claims three backends; one has been confirmed. Deleting
        on the strength of the claim is how an object ends with zero copies
        anybody has actually seen - the exact bug found in Task 5."""
        record = obj(replica_backends=(REPLICA, THIRD))
        confirmed = {record["object_id"]: {PRIMARY}}
        actions = lifecycle.lifecycle_actions(
            [record], {PRIMARY: "NEAR_FULL"}, now=NOW,
            metadata_store=healthy_store(), confirmed_copies=confirmed)
        self.assertEqual(deletes(actions), [])

    def test_the_last_confirmed_copy_is_never_proposed_for_deletion(self):
        record = obj()
        confirmed = {record["object_id"]: {PRIMARY}}
        actions = lifecycle.lifecycle_actions(
            [record], {PRIMARY: "NEAR_FULL"}, now=NOW,
            metadata_store=healthy_store(), confirmed_copies=confirmed)
        self.assertEqual(deletes(actions), [])

    def test_a_redundant_copy_may_be_evicted_and_a_survivor_is_named(self):
        record = obj()
        confirmed = {record["object_id"]: {PRIMARY, REPLICA}}
        actions = lifecycle.lifecycle_actions(
            [record], {PRIMARY: "NEAR_FULL"}, now=NOW,
            metadata_store=healthy_store(), confirmed_copies=confirmed)
        proposals = deletes(actions)
        self.assertEqual(len(proposals), 1)
        action = proposals[0]
        self.assertEqual(action.object_id, record["object_id"])
        self.assertIn(action.provider_id, {PRIMARY, REPLICA})
        survivors = set(action.evidence["surviving_confirmed_copies"])
        self.assertTrue(survivors)
        self.assertNotIn(action.provider_id, survivors)
        self.assertIs(action.destructive, True)
        self.assertIs(action.requires_authorization, True)

    def test_a_copy_on_an_unregistered_backend_is_not_a_deletion_target(self):
        """It counts as a survivor; it is not something to remove.

        Removing a copy from a holder nothing in the mesh has registered would
        be acting on state the index has never seen.
        """
        record = obj(replica_backends=())
        confirmed = {record["object_id"]: {PRIMARY, "onedrive"}}
        actions = lifecycle.lifecycle_actions(
            [record], {PRIMARY: "NEAR_FULL"}, now=NOW,
            metadata_store=healthy_store(), confirmed_copies=confirmed)
        proposals = deletes(actions)
        self.assertEqual([action.provider_id for action in proposals], [PRIMARY])
        self.assertEqual(set(proposals[0].evidence["surviving_confirmed_copies"]),
                         {"onedrive"})

    def test_eviction_requires_a_hash_verified_record(self):
        record = obj(verification={"hash_verified": False,
                                   "verified_replica_count": 2,
                                   "last_probe_at": OLD})
        confirmed = {record["object_id"]: {PRIMARY, REPLICA}}
        actions = lifecycle.lifecycle_actions(
            [record], {PRIMARY: "NEAR_FULL"}, now=NOW,
            metadata_store=healthy_store(), confirmed_copies=confirmed)
        self.assertEqual(deletes(actions), [])

    def test_eviction_requires_a_parseable_last_verified_at(self):
        record = obj()
        record.pop("last_verified_at")
        confirmed = {record["object_id"]: {PRIMARY, REPLICA}}
        actions = lifecycle.lifecycle_actions(
            [record], {PRIMARY: "NEAR_FULL"}, now=NOW,
            metadata_store=healthy_store(), confirmed_copies=confirmed)
        self.assertEqual(deletes(actions), [])

    def test_confirmed_copies_that_are_not_a_mapping_confirm_nothing(self):
        record = obj()
        for hostile in ("everything", 3, [PRIMARY, REPLICA], object(), True):
            with self.subTest(hostile=type(hostile).__name__):
                actions = lifecycle.lifecycle_actions(
                    [record], {PRIMARY: "NEAR_FULL"}, now=NOW,
                    metadata_store=healthy_store(), confirmed_copies=hostile)
                self.assertEqual(deletes(actions), [])


class FailClosedTests(unittest.TestCase):
    """policy.yaml ``destructive_action_on_uncertain_evidence: FAIL_CLOSED``."""

    def test_no_metadata_store_means_no_destructive_proposal(self):
        record = obj()
        actions = lifecycle.lifecycle_actions(
            [record], {PRIMARY: "NEAR_FULL"}, now=NOW,
            confirmed_copies=all_confirmed(record))
        self.assertEqual(deletes(actions), [])

    def test_an_unhealthy_metadata_store_means_no_destructive_proposal(self):
        record = obj()
        for store in (FakeMetadataStore(healthy=False),
                      FakeMetadataStore(probe_raises=RuntimeError("boom")),
                      object()):
            with self.subTest(store=type(store).__name__):
                actions = lifecycle.lifecycle_actions(
                    [record], {PRIMARY: "NEAR_FULL"}, now=NOW,
                    metadata_store=store,
                    confirmed_copies=all_confirmed(record))
                self.assertEqual(deletes(actions), [])

    def test_a_duck_typed_store_does_not_unlock_a_deletion(self):
        class LooksHealthy:
            def healthy(self):
                return True

        record = obj()
        actions = lifecycle.lifecycle_actions(
            [record], {PRIMARY: "NEAR_FULL"}, now=NOW,
            metadata_store=LooksHealthy(),
            confirmed_copies=all_confirmed(record))
        self.assertEqual(deletes(actions), [])

    def test_a_malformed_record_is_held_rather_than_acted_on(self):
        record = obj()
        broken = dict(record)
        broken["criticality"] = "NOT_A_CLASS"
        actions = lifecycle.lifecycle_actions(
            [broken], {PRIMARY: "NEAR_FULL"}, now=NOW,
            metadata_store=healthy_store(),
            confirmed_copies={record["object_id"]: {PRIMARY, REPLICA}})
        self.assertEqual(deletes(actions), [])
        self.assertTrue(any(action.kind == "HOLD_UNCERTAIN_RECORD"
                            for action in actions))

    def test_an_unknown_provider_state_blocks_destructive_proposals(self):
        record = obj()
        for state in ("SORT_OF_FULL", None, 3, True, ["NEAR_FULL"]):
            with self.subTest(state=state):
                actions = lifecycle.lifecycle_actions(
                    [record], {PRIMARY: state}, now=NOW,
                    metadata_store=healthy_store(),
                    confirmed_copies=all_confirmed(record))
                self.assertEqual(deletes(actions), [])

    def test_an_unparseable_evaluation_instant_blocks_destructive_proposals(self):
        record = obj()
        # ``None`` is absent from this list on purpose: it is the
        # documented default and means "the current instant", not
        # "no instant".
        for instant in ("yesterday", "", 0, True, [NOW],
                        "9999-99-99T99:99:99Z"):
            with self.subTest(instant=instant):
                actions = lifecycle.lifecycle_actions(
                    [record], {PRIMARY: "NEAR_FULL"}, now=instant,
                    metadata_store=healthy_store(),
                    confirmed_copies=all_confirmed(record))
                self.assertEqual(deletes(actions), [])

    def test_a_provider_row_resolves_through_the_capacity_broker(self):
        """A mapping value is a provider record, and the state comes from
        ``capacity.provider_state`` rather than from a second opinion."""
        row = dict(next(r for r in mesh_validator.load_providers()
                        if r["provider_id"] == PRIMARY))
        row.update({
            "health": "HEALTHY", "last_probe_at": OLD,
            "quota_total": 1000, "quota_used": 990, "quota_reserved": 0,
            "free_status": "VERIFIED_RECURRING_FREE",
            "free_status_evidence": {
                "evidence_class": "runtime_account_evidence",
                "verified_at": OLD,
                "evidence_ref": "CHECKPOINTS/evidence/r2_probe.json"},
            "hard_stop_verified": True, "paid_spillover_possible": False,
            "autonomous_write_allowed": True,
            "read_enabled": True, "write_enabled": True,
        })
        self.assertEqual(capacity.provider_state(row, now=NOW), "NEAR_FULL")
        actions = lifecycle.lifecycle_actions([obj()], {PRIMARY: row}, now=NOW)
        self.assertTrue(actions)

    def test_ephemeral_expiry_needs_a_confirmed_copy_and_a_healthy_index(self):
        record = ephemeral_object()
        self.assertEqual(
            deletes(lifecycle.lifecycle_actions(
                [record], {PRIMARY: "HEALTHY"}, now=NOW)),
            [])
        actions = lifecycle.lifecycle_actions(
            [record], {PRIMARY: "HEALTHY"}, now=NOW,
            metadata_store=healthy_store(),
            confirmed_copies=all_confirmed(record))
        self.assertTrue(deletes(actions))
        self.assertEqual({action.step for action in deletes(actions)}, {1})

    def test_a_fresh_ephemeral_object_is_not_expired(self):
        record = ephemeral_object()
        record["last_accessed_at"] = NOW
        actions = lifecycle.lifecycle_actions(
            [record], {PRIMARY: "HEALTHY"}, now=NOW,
            metadata_store=healthy_store(),
            confirmed_copies=all_confirmed(record))
        self.assertEqual(deletes(actions), [])


class DegradeNeverCrashTests(unittest.TestCase):
    """Spec S14: the system must degrade instead of crashing."""

    HOSTILE_OBJECTS = (
        None, 0, "", b"", b"bytes-are-a-sequence", object(), [None], [{}],
        [{"object_id": object()}], {"a": 1}, [[obj()]], iter([obj()]),
        [obj(), None], [obj()] * 3,
    )
    HOSTILE_STATES = (
        None, 0, "", b"", [PRIMARY], object(), {object(): "NEAR_FULL"},
        {PRIMARY: object()}, {"": "NEAR_FULL"}, {"Not A Provider": "NEAR_FULL"},
        {PRIMARY: "NEAR_FULL"},
    )

    def test_lifecycle_actions_never_raises(self):
        for objects in self.HOSTILE_OBJECTS:
            for states in self.HOSTILE_STATES:
                with self.subTest(objects=type(objects).__name__,
                                  states=type(states).__name__):
                    try:
                        actions = lifecycle.lifecycle_actions(objects, states)
                    except BaseException as exc:  # noqa: BLE001 - the subject
                        self.fail(f"{type(exc).__name__}: {exc}")
                    self.assertIsInstance(actions, list)
                    self.assertEqual(deletes(actions), [])

    def test_a_step_that_raises_does_not_take_the_caller_down(self):
        def explode(context):
            raise RuntimeError("step failed")

        patched = ((1, "EXPIRE_EPHEMERAL", explode),
                   (8, "ENTER_DEGRADED_READ_ONLY",
                    lifecycle.PRESSURE_STEPS[7][2]))
        with mock.patch.object(lifecycle, "PRESSURE_STEPS", patched):
            actions = lifecycle.lifecycle_actions(
                [obj()], {PRIMARY: "OFFLINE"}, now=NOW)
        self.assertIsInstance(actions, list)

    def test_the_action_list_is_bounded(self):
        many = [obj(f"object-{index}".encode()) for index in range(64)]
        actions = lifecycle.lifecycle_actions(many, {PRIMARY: "NEAR_FULL"},
                                              now=NOW)
        self.assertLessEqual(len(actions), lifecycle.MAX_ACTIONS)


class PrivacyTests(unittest.TestCase):
    """No credential, prompt or reasoning trace survives into a proposal."""

    def carriers(self):
        record = obj()
        smuggled_value = dict(record)
        smuggled_value["object_class"] = SMUGGLED_CREDENTIAL
        smuggled_key = dict(record)
        smuggled_key[SMUGGLED_CREDENTIAL] = SMUGGLED_CREDENTIAL
        nested = dict(record)
        nested["source_provenance"] = {"origin_class": SMUGGLED_CREDENTIAL}
        return [smuggled_value, smuggled_key, nested,
                {SMUGGLED_CREDENTIAL: SMUGGLED_CREDENTIAL}]

    def test_the_needle_never_reaches_an_action(self):
        for index, carrier in enumerate(self.carriers()):
            with self.subTest(carrier=index):
                actions = lifecycle.lifecycle_actions(
                    [carrier], {PRIMARY: "NEAR_FULL"}, now=NOW,
                    metadata_store=healthy_store(),
                    confirmed_copies={SMUGGLED_CREDENTIAL: {PRIMARY, REPLICA}})
                rendered = repr(actions) + str(actions) + json.dumps(
                    [action.as_dict() for action in actions], default=str)
                self.assertNotIn(SMUGGLED_CREDENTIAL, rendered)
                self.assertEqual(deletes(actions), [])

    def test_the_needle_appears_in_no_traceback(self):
        """Including a chained ``__context__``: a leak of exactly that shape was
        found in Task 5, and ``str(exc)`` hid it."""
        for index, carrier in enumerate(self.carriers()):
            with self.subTest(carrier=index):
                try:
                    lifecycle.lifecycle_actions(
                        [carrier], {SMUGGLED_CREDENTIAL: SMUGGLED_CREDENTIAL},
                        now=SMUGGLED_CREDENTIAL,
                        metadata_store=SMUGGLED_CREDENTIAL,
                        confirmed_copies={SMUGGLED_CREDENTIAL: SMUGGLED_CREDENTIAL})
                except BaseException:  # noqa: BLE001 - the subject
                    self.assertNotIn(SMUGGLED_CREDENTIAL, traceback.format_exc())
                    self.fail("lifecycle_actions raised")

    def test_every_action_string_field_is_bounded(self):
        actions = lifecycle.lifecycle_actions(
            [obj(), critical_object(), ephemeral_object()],
            {PRIMARY: "NEAR_FULL"}, now=NOW, metadata_store=healthy_store(),
            confirmed_copies={})
        for action in actions:
            encoded = json.dumps(action.as_dict(), default=str)
            self.assertLessEqual(len(encoded), lifecycle.MAX_ACTION_BYTES)
            self.assertIn(action.reason, lifecycle.REASONS)

    def test_a_reason_is_drawn_from_a_closed_vocabulary(self):
        for reason in lifecycle.REASONS:
            self.assertRegex(reason, r"\A[A-Z][A-Z0-9_]{2,63}\Z")


if __name__ == "__main__":
    unittest.main()
