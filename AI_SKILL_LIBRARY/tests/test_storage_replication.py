"""Task 5b - selective replication, and the one rule that must never bend.

Spec S15 states the rebalance protocol as seven ordered steps and then, in case
the ordering was read as advice, says it again in one line: **never delete
before verifying the replacement**. ``policy.yaml`` records the same fact as
``rebalance_deletes_source_before_destination_verified: false``. Everything in
this file is built around making that difficult to break by accident.

The single most important test here is not the happy path. It is the sweep that
takes every way a verification can fail to say yes - it returns ``False``, it
raises, it returns something merely truthy, the destination acknowledges the
write but its own ``head`` disagrees, the index is uncertain, the recovery
pointer could not be persisted - and requires the same two things every time: a
status that names the failure, and a source object that is still there. A
rebalance that loses data is worse than a rebalance that does nothing, and the
asymmetry is the whole design.

Three further themes:

**Verification recomputes.** ``verify_copy`` hashes the payload it is given and
compares. It does not read a digest off a receipt and agree with it: a receipt
asserting a digest is a claim by the thing being checked, and a check that
consults its subject for the answer is not a check. The tests construct a
receipt that is internally consistent and simply not about the payload, which
is exactly the shape a confused or hostile store produces, and require False.

**Replication is by criticality and by full copies.** ``replication_requirement``
reads ``policy.yaml``'s ``min_independent_provider_copies``, so the numbers
cannot drift from the document that sets them. There is no erasure coding and
no chunk striping here, and the tests assert the absence rather than trusting
it - Spec S9 puts both explicitly out of scope, because one missing chunk
making a file unreadable is a worse failure than one missing replica.

**Fail closed, degrade, never crash.** ``rebalance_object`` returns a result;
it does not raise. Hostile arguments of every shape produce a refusal with a
status, an untouched source and a detail string that echoes none of its input.

Nothing here opens a connection, writes a file or touches a provider account.
"""

from __future__ import annotations

import json
import unittest

from AI_SKILL_LIBRARY.v4.storage import manifest as manifest_module
from AI_SKILL_LIBRARY.v4.storage import mesh_validator, replication
from AI_SKILL_LIBRARY.v4.storage.adapters import s3_object

from AI_SKILL_LIBRARY.tests.test_storage_metadata import (
    AUTHORITY_FLAGS,
    FakeMetadataStore,
    SMUGGLED_CREDENTIAL,
    TIME,
)
from AI_SKILL_LIBRARY.tests.test_storage_s3_adapter import (
    BUCKET,
    ENDPOINT,
    FakeS3Transport,
    credential,
    object_metadata,
)

PAYLOAD = b"federated-free-storage-mesh-object"
DIGEST = s3_object.content_digest(PAYLOAD)
OBJECT_ID = "obj_" + DIGEST

SOURCE_BACKEND = "cloudflare_r2"
DESTINATION_BACKEND = "backblaze_b2"


def record(criticality="IMPORTANT", **overrides):
    """A manifest record for an object the source backend holds."""
    kwargs = dict(
        privacy_class="PUBLIC",
        criticality=criticality,
        storage_tier="WARM",
        object_class="benchmark-bundle",
        mime_type="application/octet-stream",
        retention_class="short-window",
        primary_backend=SOURCE_BACKEND,
        replica_backends=(),
        created_at=TIME,
        lifecycle_state="RAW",
        reproducible=True,
    )
    kwargs.update(overrides)
    return manifest_module.StorageObject.from_bytes(
        PAYLOAD, **kwargs).to_manifest()


class LoggingTransport(FakeS3Transport):
    """A fake endpoint that appends to a shared ordered log.

    Ordering is the whole subject here - "register the destination, then
    delete the source" is a claim about *sequence*, and a test that only looks
    at the final state cannot tell a correct order from a lucky one.
    """

    def __init__(self, log, **kwargs):
        super().__init__(**kwargs)
        self.log = log

    def __call__(self, operation, payload, **kwargs):
        answer = super().__call__(operation, payload, **kwargs)
        self.log.append((operation, payload.get("key")))
        return answer


class RecordingIndex(FakeMetadataStore):
    """The in-memory index, with the writes it received in order."""

    def __init__(self, *, log=None, fail_put=False, **kwargs):
        super().__init__(**kwargs)
        self.log = log if log is not None else []
        self.fail_put = fail_put
        self.writes = []

    def _put_record(self, object_id, record_):
        if self.fail_put:
            raise RuntimeError("the index refused the write")
        self.writes.append(json.loads(json.dumps(record_)))
        self.log.append(("metadata", object_id))
        return super()._put_record(object_id, record_)


def object_store(backend_id, transport, **overrides):
    kwargs = {
        "backend_id": backend_id,
        "endpoint": ENDPOINT,
        "bucket": BUCKET,
        "credential_provider": credential,
        "transport": transport,
        "clock": lambda: TIME,
    }
    kwargs.update(overrides)
    return s3_object.ObjectStore(**kwargs)


def mesh(criticality="IMPORTANT", *, source_kwargs=None, destination_kwargs=None,
         records=None, store_healthy=True, log=None, fail_put=False):
    """A source holding the object, an empty destination and an index.

    The fakes are real ``ObjectStore``s driven by in-memory transports rather
    than hand-rolled doubles. A hand-rolled double would let these tests pass
    while the validation that lives in the adapter goes unexercised, and that
    validation is half of what makes a verified copy mean anything.
    """
    shared_log = log if log is not None else []
    source_transport = LoggingTransport(shared_log, **(source_kwargs or {}))
    source_transport.objects[OBJECT_ID] = (PAYLOAD, {})
    destination_transport = LoggingTransport(shared_log,
                                             **(destination_kwargs or {}))
    source = object_store(SOURCE_BACKEND, source_transport)
    destination = object_store(DESTINATION_BACKEND, destination_transport)
    index = RecordingIndex(
        log=shared_log, fail_put=fail_put,
        records=records if records is not None else [record(criticality)],
        healthy=store_healthy)
    return source, destination, index


def holders(index, object_id=OBJECT_ID):
    stored = index.get_manifest(object_id)
    return {stored["primary_backend"], *stored["replica_backends"]}


def receipt_for(payload=PAYLOAD, **overrides):
    digest = s3_object.content_digest(payload)
    fields = {
        "object_id": "obj_" + digest,
        "backend_id": DESTINATION_BACKEND,
        "content_sha256": digest,
        "size_bytes": len(payload),
        "observed_at": TIME,
        "digest_source": "computed",
        "verified": True,
    }
    fields.update(overrides)
    return s3_object.ObjectReceipt(**fields)


def accept(pointer):
    """A recovery pointer sink that acknowledges. Spec S15 step 5.

    A delete now requires one. The default call - no checkpoint - is a copy,
    because a move GitHub holds no pointer to is a move a rebuild cannot follow
    and Supabase must not be the only record of it (Spec S18/S23).
    """
    return True


def holder_store(backend_id, *, holds=True, **kwargs):
    """A third backend that claims-and-really-holds, or claims and does not."""
    transport = FakeS3Transport(**kwargs)
    if holds:
        transport.objects[OBJECT_ID] = (PAYLOAD, {})
    return object_store(backend_id, transport)


HOSTILE = (SMUGGLED_CREDENTIAL, "A" * 300, "", None, -1, 10 ** 30, True,
           False, 1.5, 2, [], {}, (), b"bytes", bytearray(b"bytes"),
           memoryview(b"bytes"), object(), "unexpected", set())


class AuthorityTests(unittest.TestCase):
    """Replication decides nothing about placement (Spec S2/S5)."""

    def test_no_authority_of_any_kind(self):
        self.assertIs(replication.AUTHORITY, False)
        for flag in AUTHORITY_FLAGS:
            self.assertIs(replication.AUTHORITY_FLAGS[flag], False, flag)
        self.assertEqual(set(replication.AUTHORITY_FLAGS), set(AUTHORITY_FLAGS))

    def test_github_remains_canonical(self):
        self.assertEqual(replication.CANONICAL_AUTHORITY, "GITHUB_BRAIN_V4")

    def test_no_cryptography_is_implemented_here(self):
        self.assertIs(replication.ENCRYPTION_IMPLEMENTED_HERE, False)
        for name in ("encrypt", "decrypt", "derive_key", "wrap_key"):
            self.assertFalse(hasattr(replication, name), name)

    def test_this_module_chooses_no_destination(self):
        # Spec S15 step 1 - "choose eligible destination" - is Task 3's, and a
        # module that could choose one would be a second placement engine.
        for name in ("choose_destination", "select_backend", "place",
                     "placement_candidates", "rank_providers"):
            self.assertFalse(hasattr(replication, name), name)


class FullCopyOnlyTests(unittest.TestCase):
    """Spec S9: one primary, optional full replicas. Nothing is striped."""

    def test_the_policy_puts_striping_out_of_scope(self):
        policy = mesh_validator.load_policy()["replication"]
        self.assertEqual(policy["erasure_coding"], "out_of_scope")
        self.assertEqual(policy["chunk_striping"], "out_of_scope")
        self.assertIs(policy["rebalance_deletes_source_before_destination_verified"],
                      False)

    def test_the_module_declares_full_copies_only(self):
        self.assertEqual(replication.REPLICATION_MODEL,
                         "single_primary_with_optional_full_replicas")
        self.assertIs(replication.ERASURE_CODING_IMPLEMENTED_HERE, False)
        self.assertIs(replication.CHUNK_STRIPING_IMPLEMENTED_HERE, False)

    def test_no_chunking_machinery_exists(self):
        for name in ("split", "chunk", "shard", "stripe", "encode_fragments",
                     "reassemble", "parity"):
            self.assertFalse(hasattr(replication, name), name)


class ReplicationRequirementTests(unittest.TestCase):
    """The number of independent copies comes from policy, not from memory."""

    def test_critical_requires_two_independent_copies(self):
        self.assertEqual(replication.replication_requirement("CRITICAL"), 2)

    def test_every_class_matches_the_policy_document(self):
        policy = mesh_validator.load_policy()["criticality"]
        for name, rules in policy.items():
            with self.subTest(criticality=name):
                self.assertEqual(replication.replication_requirement(name),
                                 rules["min_independent_provider_copies"])

    def test_the_ladder_is_the_one_the_spec_describes(self):
        self.assertEqual(replication.replication_requirement("IMPORTANT"), 1)
        self.assertEqual(replication.replication_requirement("REPRODUCIBLE"), 1)
        self.assertEqual(replication.replication_requirement("EPHEMERAL"), 0)

    def test_an_unknown_criticality_demands_the_strictest_obligation(self):
        # Fail closed. Understating a requirement is what authorises a delete,
        # so an unrecognised class asks for the most copies rather than the
        # fewest, and no input makes this function raise.
        for value in HOSTILE + ("critical", "Critical", "UNKNOWN", "ARCHIVE"):
            with self.subTest(value=repr(value)[:24]):
                answer = replication.replication_requirement(value)
                self.assertEqual(answer, replication.UNKNOWN_REQUIREMENT)
                self.assertEqual(answer, 2)

    def test_the_answer_is_always_a_plain_integer(self):
        for value in HOSTILE + ("CRITICAL", "EPHEMERAL"):
            with self.subTest(value=repr(value)[:24]):
                answer = replication.replication_requirement(value)
                self.assertIsInstance(answer, int)
                self.assertNotIsInstance(answer, bool)


class VerifyCopyTests(unittest.TestCase):
    """Spec S15: verification recomputes the content. It trusts no claim."""

    def test_a_true_copy_verifies(self):
        self.assertIs(replication.verify_copy(PAYLOAD, receipt_for()), True)

    def test_a_bytearray_payload_verifies(self):
        self.assertIs(replication.verify_copy(bytearray(PAYLOAD), receipt_for()),
                      True)

    def test_a_receipts_claim_is_not_evidence(self):
        # The receipt is internally consistent - its digest, its object id and
        # its size all agree with each other - and simply is not about this
        # payload. A verifier that read the receipt's own numbers would say yes.
        other = b"a different object entirely"
        self.assertIs(replication.verify_copy(PAYLOAD, receipt_for(other)),
                      False)

    def test_a_forged_digest_does_not_verify(self):
        self.assertIs(
            replication.verify_copy(PAYLOAD, receipt_for(content_sha256="a" * 64)),
            False)

    def test_an_object_id_that_disagrees_with_the_digest_does_not_verify(self):
        self.assertIs(
            replication.verify_copy(PAYLOAD, receipt_for(object_id="obj_" + "b" * 64)),
            False)

    def test_a_size_that_disagrees_does_not_verify(self):
        self.assertIs(replication.verify_copy(PAYLOAD, receipt_for(size_bytes=1)),
                      False)

    def test_a_receipt_asserting_nothing_does_not_verify(self):
        self.assertIs(
            replication.verify_copy(PAYLOAD, receipt_for(content_sha256=None,
                                                         digest_source="unknown",
                                                         verified=False)),
            False)

    def test_a_duck_typed_receipt_does_not_verify(self):
        class LooksLikeOne:
            object_id = OBJECT_ID
            content_sha256 = DIGEST
            size_bytes = len(PAYLOAD)
            digest_source = "computed"
            verified = True

        self.assertIs(replication.verify_copy(PAYLOAD, LooksLikeOne()), False)
        self.assertIs(replication.verify_copy(PAYLOAD, {
            "object_id": OBJECT_ID, "content_sha256": DIGEST,
            "size_bytes": len(PAYLOAD)}), False)

    def test_a_payload_that_is_not_bytes_does_not_verify(self):
        for payload in (PAYLOAD.decode(), None, 1, True, [], {},
                        memoryview(PAYLOAD), SMUGGLED_CREDENTIAL):
            with self.subTest(payload=repr(payload)[:24]):
                self.assertIs(replication.verify_copy(payload, receipt_for()),
                              False)

    def test_no_input_of_any_shape_raises(self):
        for payload in HOSTILE:
            for candidate in HOSTILE + (receipt_for(),):
                with self.subTest(payload=repr(payload)[:16],
                                  receipt=repr(candidate)[:16]):
                    self.assertIsInstance(
                        replication.verify_copy(payload, candidate), bool)

    def test_the_answer_is_exactly_true_or_exactly_false(self):
        answer = replication.verify_copy(PAYLOAD, receipt_for())
        self.assertIs(type(answer), bool)


class RebalanceNeverDeletesFirstTests(unittest.TestCase):
    """The rule this whole task exists for."""

    def test_rebalance_never_deletes_before_verified_destination(self):
        source, destination, index = mesh()
        result = replication.rebalance_object(
            OBJECT_ID, source, destination, index, verify=lambda *_: False)
        self.assertEqual(result.status, "VERIFY_FAILED")
        self.assertEqual(source._transport.deleted, [])
        self.assertIs(result.source_deleted, False)
        self.assertEqual(source.get(OBJECT_ID), PAYLOAD)

    def test_a_verifier_that_raises_leaves_the_source_alone(self):
        def explode(*args, **kwargs):
            raise RuntimeError("verification blew up")

        source, destination, index = mesh()
        result = replication.rebalance_object(
            OBJECT_ID, source, destination, index, verify=explode)
        self.assertEqual(result.status, "VERIFY_FAILED")
        self.assertEqual(source._transport.deleted, [])
        self.assertEqual(source.get(OBJECT_ID), PAYLOAD)

    def test_a_truthy_non_true_verification_is_not_a_verification(self):
        # "if verify(...):" is the bug. A verifier that returns a non-empty
        # string, a 1, a list or an object is a verifier that has not said yes.
        for answer in ("yes", "VERIFIED", 1, 1.0, [1], {"ok": True}, object(),
                       (0,), {0}):
            with self.subTest(answer=repr(answer)[:24]):
                source, destination, index = mesh()
                result = replication.rebalance_object(
                    OBJECT_ID, source, destination, index,
                    verify=lambda *_, _a=answer: _a)
                self.assertEqual(result.status, "VERIFY_FAILED")
                self.assertEqual(source._transport.deleted, [])

    def test_a_destination_that_writes_but_disagrees_on_head(self):
        # The write is acknowledged and the read-back is clean, and then the
        # destination's own head says the object is something else. That is a
        # store nobody should delete a copy on the strength of.
        source, destination, index = mesh(destination_kwargs={
            "head_override": {"size_bytes": 1, "content_sha256": "c" * 64}})
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index)
        self.assertEqual(result.status, "VERIFY_FAILED")
        self.assertEqual(source._transport.deleted, [])
        self.assertEqual(source.get(OBJECT_ID), PAYLOAD)

    def test_a_destination_that_forgets_the_object_after_writing_it(self):
        source, destination, index = mesh(destination_kwargs={
            "head_override": None})
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index)
        self.assertEqual(result.status, "VERIFY_FAILED")
        self.assertEqual(source._transport.deleted, [])

    def test_a_destination_that_returns_different_bytes_on_read_back(self):
        source, destination, index = mesh(
            destination_kwargs={"corrupt_get": True})
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index)
        self.assertEqual(result.status, "VERIFY_FAILED")
        self.assertEqual(source._transport.deleted, [])

    def test_a_delete_that_fails_after_a_successful_verification(self):
        source, destination, index = mesh(
            source_kwargs={"raise_on": ("delete",)})
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index, checkpoint=accept)
        self.assertEqual(result.status, "DELETE_FAILED")
        self.assertIs(result.source_deleted, False)
        self.assertIs(result.destination_verified, True)
        # Both copies exist. That is the safe side of this failure and the
        # metadata must still list both.
        self.assertEqual(source.get(OBJECT_ID), PAYLOAD)
        self.assertEqual(destination.get(OBJECT_ID), PAYLOAD)
        self.assertEqual(holders(index),
                         {SOURCE_BACKEND, DESTINATION_BACKEND})

    def test_the_destination_write_is_never_assumed(self):
        source, destination, index = mesh(destination_kwargs={"raise_on": ("put",)})
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index)
        self.assertEqual(result.status, "DESTINATION_WRITE_FAILED")
        self.assertEqual(source._transport.deleted, [])

    def test_an_unreadable_source_is_not_a_reason_to_delete_it(self):
        source, destination, index = mesh(source_kwargs={"raise_on": ("get",)})
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index)
        self.assertEqual(result.status, "SOURCE_READ_FAILED")
        self.assertEqual(source._transport.deleted, [])

    def test_a_source_whose_bytes_do_not_match_their_address(self):
        source, destination, index = mesh(source_kwargs={"corrupt_get": True})
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index)
        self.assertEqual(result.status, "SOURCE_READ_FAILED")
        self.assertEqual(source._transport.deleted, [])
        self.assertEqual(destination.head(OBJECT_ID), None,
                         "corrupt bytes must not be propagated to a second "
                         "provider under a content address they do not have")


class RebalanceMetadataGateTests(unittest.TestCase):
    """Spec S18: an uncertain index pauses destructive lifecycle entirely."""

    def test_an_unhealthy_index_blocks_the_rebalance(self):
        source, destination, index = mesh(store_healthy=False)
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index)
        self.assertEqual(result.status, "BLOCKED_METADATA_UNCERTAIN")
        self.assertEqual(source._transport.deleted, [])
        self.assertEqual(destination._transport.calls, [],
                         "nothing is copied while the index is uncertain")

    def test_an_index_whose_probe_raises_blocks_the_rebalance(self):
        source, destination, _ = mesh()
        index = FakeMetadataStore(records=[record()],
                                  probe_raises=RuntimeError("down"))
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index)
        self.assertEqual(result.status, "BLOCKED_METADATA_UNCERTAIN")
        self.assertEqual(source._transport.deleted, [])

    def test_a_duck_typed_index_is_not_an_index(self):
        class LooksLikeOne:
            def healthy(self):
                return True

            def get_manifest(self, object_id):
                return record()

            def put_manifest(self, manifest):
                return None

        source, destination, _ = mesh()
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              LooksLikeOne())
        self.assertEqual(result.status, "BLOCKED_METADATA_UNCERTAIN")
        self.assertEqual(source._transport.deleted, [])

    def test_an_object_the_index_never_heard_of_is_refused(self):
        source, destination, index = mesh(records=[])
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index)
        self.assertEqual(result.status, "REFUSED_UNKNOWN_OBJECT")
        self.assertEqual(source._transport.deleted, [])

    def test_a_metadata_write_that_fails_stops_the_move(self):
        source, destination, index = mesh(fail_put=True)
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index)
        self.assertEqual(result.status, "METADATA_UPDATE_FAILED")
        self.assertEqual(source._transport.deleted, [])
        self.assertEqual(source.get(OBJECT_ID), PAYLOAD)

    def test_the_destination_is_registered_before_any_delete(self):
        # Spec S15 steps 4 and 6, in that order. The proof is the write order
        # the index actually saw.
        log = []
        source, destination, index = mesh(log=log)
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index, checkpoint=accept)
        self.assertEqual(result.status, "MOVED")
        first_registration = index.writes[0]
        self.assertIn(DESTINATION_BACKEND,
                      {first_registration["primary_backend"],
                       *first_registration["replica_backends"]})
        self.assertLess(log.index(("metadata", OBJECT_ID)),
                        log.index(("delete", OBJECT_ID)))


class RebalanceSuccessTests(unittest.TestCase):
    """What a completed move looks like."""

    def test_a_verified_move_completes(self):
        source, destination, index = mesh()
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index, checkpoint=accept)
        self.assertEqual(result.status, "MOVED")
        self.assertIs(result.source_deleted, True)
        self.assertIs(result.destination_verified, True)
        self.assertEqual(result.object_id, OBJECT_ID)
        self.assertEqual(result.source_backend, SOURCE_BACKEND)
        self.assertEqual(result.destination_backend, DESTINATION_BACKEND)
        self.assertEqual(destination.get(OBJECT_ID), PAYLOAD)
        self.assertEqual(source._transport.deleted, [OBJECT_ID])
        self.assertEqual(holders(index), {DESTINATION_BACKEND})

    def test_the_copy_is_a_full_copy(self):
        source, destination, index = mesh()
        replication.rebalance_object(OBJECT_ID, source, destination, index)
        self.assertEqual(destination._transport.objects[OBJECT_ID][0], PAYLOAD)

    def test_a_critical_object_keeps_two_copies_rather_than_moving(self):
        # CRITICAL requires two independent provider copies. Deleting the
        # source would leave one, so the source is kept and the result says so.
        source, destination, index = mesh("CRITICAL")
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index)
        self.assertEqual(result.status, "COPIED_SOURCE_RETAINED")
        self.assertIs(result.source_deleted, False)
        self.assertIs(result.destination_verified, True)
        self.assertEqual(source.get(OBJECT_ID), PAYLOAD)
        self.assertEqual(destination.get(OBJECT_ID), PAYLOAD)
        self.assertEqual(holders(index),
                         {SOURCE_BACKEND, DESTINATION_BACKEND})

    def test_a_critical_object_with_a_confirmed_replica_may_move(self):
        # The other holder is *probed*, not counted. Its store is supplied, it
        # answers head with the right digest and length, and only then does the
        # source become removable.
        source, destination, index = mesh(
            records=[record("CRITICAL", replica_backends=("oracle_object_storage",))])
        result = replication.rebalance_object(
            OBJECT_ID, source, destination, index, checkpoint=accept,
            holder_stores={"oracle_object_storage":
                           holder_store("oracle_object_storage")})
        self.assertEqual(result.status, "MOVED")
        self.assertEqual(holders(index),
                         {DESTINATION_BACKEND, "oracle_object_storage"})
        self.assertEqual(set(result.verified_copies),
                         {DESTINATION_BACKEND, "oracle_object_storage"})

    def test_the_caller_may_forbid_deleting_the_source(self):
        source, destination, index = mesh()
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index, delete_source=False)
        self.assertEqual(result.status, "COPIED_SOURCE_RETAINED")
        self.assertEqual(source._transport.deleted, [])
        self.assertEqual(holders(index),
                         {SOURCE_BACKEND, DESTINATION_BACKEND})

    def test_a_checkpoint_hook_runs_before_the_delete(self):
        seen = []
        source, destination, index = mesh()

        def checkpoint(payload):
            seen.append(payload["object_id"])
            return True

        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index, checkpoint=checkpoint)
        self.assertEqual(result.status, "MOVED")
        self.assertEqual(seen, [OBJECT_ID])

    def test_a_checkpoint_that_fails_stops_the_delete(self):
        for hook in (lambda payload: False,
                     lambda payload: "ok",
                     lambda payload: None):
            with self.subTest(hook=repr(hook)):
                source, destination, index = mesh()
                result = replication.rebalance_object(
                    OBJECT_ID, source, destination, index, checkpoint=hook)
                self.assertEqual(result.status, "CHECKPOINT_FAILED")
                self.assertEqual(source._transport.deleted, [])

    def test_a_checkpoint_that_raises_stops_the_delete(self):
        def explode(payload):
            raise RuntimeError("no checkpoint")

        source, destination, index = mesh()
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index, checkpoint=explode)
        self.assertEqual(result.status, "CHECKPOINT_FAILED")
        self.assertEqual(source._transport.deleted, [])


class RebalanceRefusalTests(unittest.TestCase):
    """Fail closed on every malformed request, and never crash (Spec S14)."""

    def test_the_status_vocabulary_is_closed(self):
        self.assertIn("VERIFY_FAILED", replication.REBALANCE_STATUSES)
        self.assertIn("MOVED", replication.REBALANCE_STATUSES)
        self.assertEqual(len(set(replication.REBALANCE_STATUSES)),
                         len(replication.REBALANCE_STATUSES))

    def test_a_move_to_the_same_backend_is_refused(self):
        source, _, index = mesh()
        twin = object_store(SOURCE_BACKEND, FakeS3Transport())
        result = replication.rebalance_object(OBJECT_ID, source, twin, index)
        self.assertEqual(result.status, "REFUSED_SAME_BACKEND")
        self.assertEqual(source._transport.deleted, [])

    def test_a_backend_the_record_does_not_place_the_object_on(self):
        source, destination, index = mesh(
            records=[record(primary_backend="oracle_object_storage")])
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index)
        self.assertEqual(result.status, "REFUSED_SOURCE_NOT_A_HOLDER")
        self.assertEqual(source._transport.deleted, [])

    def test_hostile_arguments_never_raise_and_never_delete(self):
        for position in range(4):
            for value in HOSTILE:
                with self.subTest(position=position, value=repr(value)[:24]):
                    source, destination, index = mesh()
                    args = [OBJECT_ID, source, destination, index]
                    args[position] = value
                    result = replication.rebalance_object(*args)
                    self.assertIn(result.status, replication.REBALANCE_STATUSES)
                    self.assertIs(result.source_deleted, False)
                    self.assertEqual(source._transport.deleted, [])

    def test_a_non_callable_verifier_is_refused(self):
        for value in HOSTILE:
            with self.subTest(value=repr(value)[:24]):
                source, destination, index = mesh()
                result = replication.rebalance_object(
                    OBJECT_ID, source, destination, index, verify=value)
                self.assertEqual(result.status, "REFUSED_INVALID_REQUEST")
                self.assertEqual(source._transport.deleted, [])

    def test_a_non_callable_checkpoint_is_refused(self):
        for value in HOSTILE:
            if value is None:
                continue
            with self.subTest(value=repr(value)[:24]):
                source, destination, index = mesh()
                result = replication.rebalance_object(
                    OBJECT_ID, source, destination, index, checkpoint=value)
                self.assertEqual(result.status, "REFUSED_INVALID_REQUEST")
                self.assertEqual(source._transport.deleted, [])

    def test_a_bytes_argument_where_a_store_was_expected(self):
        # bytes is a collections.abc.Sequence. A duck-typed check that asked
        # "is this a sequence" would accept it, and this lane has had that bug.
        source, destination, index = mesh()
        for value in (b"cloudflare_r2", bytearray(b"cloudflare_r2"),
                      memoryview(b"cloudflare_r2")):
            with self.subTest(value=repr(value)[:24]):
                result = replication.rebalance_object(OBJECT_ID, value,
                                                      destination, index)
                self.assertEqual(result.status, "REFUSED_INVALID_REQUEST")

    def test_a_result_is_immutable_and_json_safe(self):
        source, destination, index = mesh()
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index)
        with self.assertRaises(Exception):
            result.status = "MOVED"
        json.dumps(result.as_dict())


class RebalanceLeakTests(unittest.TestCase):
    """A needle fed through any input appears in no result and no exception."""

    def test_no_result_ever_echoes_a_hostile_value(self):
        blobs = []
        for position in range(4):
            source, destination, index = mesh()
            args = [OBJECT_ID, source, destination, index]
            args[position] = SMUGGLED_CREDENTIAL
            blobs.append(json.dumps(
                replication.rebalance_object(*args).as_dict(), default=repr))
        source, destination, index = mesh()
        blobs.append(json.dumps(replication.rebalance_object(
            OBJECT_ID, source, destination, index,
            verify=SMUGGLED_CREDENTIAL).as_dict(), default=repr))
        for blob in blobs:
            self.assertNotIn("sk-A7bQ", blob)

    def test_a_leaking_transport_is_not_quoted_into_the_result(self):
        def leaking(operation, payload, *, endpoint, bucket, credential):
            raise RuntimeError(f"HTTP 403 {credential} {SMUGGLED_CREDENTIAL}")

        source, _, index = mesh()
        destination = object_store(DESTINATION_BACKEND, leaking)
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index)
        self.assertEqual(result.status, "DESTINATION_WRITE_FAILED")
        blob = json.dumps(result.as_dict(), default=repr) + repr(result)
        self.assertNotIn("sk-A7bQ", blob)
        self.assertNotIn("injected-credential-value", blob)

    def test_the_object_metadata_attached_to_the_copy_carries_no_secret(self):
        source, destination, index = mesh()
        replication.rebalance_object(OBJECT_ID, source, destination, index)
        sent = [call for call in destination._transport.calls
                if call["operation"] == "put"]
        self.assertEqual(len(sent), 1)
        attached = sent[0]["payload"]["metadata"]
        self.assertEqual(set(attached) - set(s3_object.OBJECT_METADATA_VALUE_CHECKS),
                         set())
        for field in s3_object.REFUSED_METADATA_FIELDS:
            self.assertNotIn(field, attached)

    def test_object_metadata_is_the_same_shape_the_adapter_accepts(self):
        # A guard against the two modules drifting: whatever rebalance attaches
        # must be exactly what put() would accept on its own.
        source, destination, index = mesh()
        replication.rebalance_object(OBJECT_ID, source, destination, index)
        attached = [call for call in destination._transport.calls
                    if call["operation"] == "put"][0]["payload"]["metadata"]
        fresh = object_store("oracle_object_storage", FakeS3Transport())
        fresh.put(OBJECT_ID, PAYLOAD, attached)

    def test_unused_fixture_import_is_exercised(self):
        # object_metadata() is imported for the adapter-compatibility checks
        # above; assert it still describes the same object so a change there
        # fails here rather than silently weakening the comparison.
        self.assertEqual(object_metadata()["content_sha256"], DIGEST)


class RecoveryPointerRequiredTests(unittest.TestCase):
    """Spec S15 step 5 is not optional before step 6.

    The module's own docstring calls the ordering "the whole of it", and step 5
    is persisting the recovery pointer. Spec S18 is explicit that Supabase must
    not be a single point of failure, and the GitHub pointer is what survives a
    Supabase outage - so the *default* call, the one with no checkpoint, is a
    copy and not a move.
    """

    def test_the_default_call_does_not_delete(self):
        source, destination, index = mesh()
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index)
        self.assertEqual(result.status, "COPIED_SOURCE_RETAINED")
        self.assertIs(result.source_deleted, False)
        self.assertIs(result.destination_verified, True)
        self.assertEqual(source._transport.deleted, [])
        self.assertEqual(source.get(OBJECT_ID), PAYLOAD)
        self.assertEqual(destination.get(OBJECT_ID), PAYLOAD)

    def test_the_detail_names_the_missing_pointer(self):
        source, destination, index = mesh()
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index)
        self.assertIn("recovery pointer", result.detail)

    def test_both_copies_are_registered_without_a_pointer(self):
        source, destination, index = mesh()
        replication.rebalance_object(OBJECT_ID, source, destination, index)
        self.assertEqual(holders(index), {SOURCE_BACKEND, DESTINATION_BACKEND})

    def test_a_copy_is_always_allowed_without_a_pointer(self):
        source, destination, index = mesh()
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index, delete_source=False)
        self.assertEqual(result.status, "COPIED_SOURCE_RETAINED")
        self.assertEqual(destination.get(OBJECT_ID), PAYLOAD)

    def test_the_pointer_is_what_unlocks_the_delete(self):
        source, destination, index = mesh()
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index, checkpoint=accept)
        self.assertEqual(result.status, "MOVED")
        self.assertEqual(source._transport.deleted, [OBJECT_ID])


class VerifiedReplicaCountTests(unittest.TestCase):
    """Spec S15 step 7 verifies *copies*, not a number.

    ``len(holders_after - {source})`` counts the backends the manifest claims.
    Only the destination was ever read back and head-checked, so a record naming
    a replica that no longer exists reached the requirement on paper and the
    source was deleted - leaving a CRITICAL object with exactly one copy
    anybody had verified, against Spec S8's two independent providers.
    """

    def _critical(self, **kwargs):
        return mesh(records=[record(
            "CRITICAL", replica_backends=("oracle_object_storage",))], **kwargs)

    def test_a_claimed_holder_that_is_never_probed_does_not_count(self):
        source, destination, index = self._critical()
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index, checkpoint=accept)
        self.assertEqual(result.status, "COPIED_SOURCE_RETAINED")
        self.assertIs(result.source_deleted, False)
        self.assertEqual(source._transport.deleted, [])
        self.assertEqual(source.get(OBJECT_ID), PAYLOAD)
        self.assertEqual(tuple(result.verified_copies), (DESTINATION_BACKEND,))

    def test_the_detail_says_an_unsupplied_store_cannot_be_confirmed(self):
        source, destination, index = self._critical()
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index, checkpoint=accept)
        self.assertIn("not supplied", result.detail)

    def test_a_claimed_holder_that_denies_holding_it_does_not_count(self):
        source, destination, index = self._critical()
        result = replication.rebalance_object(
            OBJECT_ID, source, destination, index, checkpoint=accept,
            holder_stores={"oracle_object_storage":
                           holder_store("oracle_object_storage", holds=False)})
        self.assertEqual(result.status, "COPIED_SOURCE_RETAINED")
        self.assertEqual(source._transport.deleted, [])
        self.assertEqual(tuple(result.verified_copies), (DESTINATION_BACKEND,))

    def test_a_claimed_holder_whose_head_disagrees_does_not_count(self):
        source, destination, index = self._critical()
        result = replication.rebalance_object(
            OBJECT_ID, source, destination, index, checkpoint=accept,
            holder_stores={"oracle_object_storage": holder_store(
                "oracle_object_storage",
                head_override={"size_bytes": 1, "content_sha256": "c" * 64})})
        self.assertEqual(result.status, "COPIED_SOURCE_RETAINED")
        self.assertEqual(source._transport.deleted, [])

    def test_a_claimed_holder_asserting_no_digest_does_not_count(self):
        source, destination, index = self._critical()
        result = replication.rebalance_object(
            OBJECT_ID, source, destination, index, checkpoint=accept,
            holder_stores={"oracle_object_storage": holder_store(
                "oracle_object_storage",
                head_override={"size_bytes": len(PAYLOAD)})})
        self.assertEqual(result.status, "COPIED_SOURCE_RETAINED")
        self.assertEqual(source._transport.deleted, [])

    def test_a_claimed_holder_that_cannot_be_reached_does_not_count(self):
        source, destination, index = self._critical()
        result = replication.rebalance_object(
            OBJECT_ID, source, destination, index, checkpoint=accept,
            holder_stores={"oracle_object_storage": holder_store(
                "oracle_object_storage", raise_on=("head",))})
        self.assertEqual(result.status, "COPIED_SOURCE_RETAINED")
        self.assertEqual(source._transport.deleted, [])

    def test_a_store_filed_under_another_backends_name_does_not_count(self):
        # The mapping is the caller's, and a store answering for a backend it
        # is not is a confirmation of the wrong provider (Spec S8 independence).
        source, destination, index = self._critical()
        result = replication.rebalance_object(
            OBJECT_ID, source, destination, index, checkpoint=accept,
            holder_stores={"oracle_object_storage":
                           holder_store(DESTINATION_BACKEND)})
        self.assertEqual(result.status, "COPIED_SOURCE_RETAINED")
        self.assertEqual(source._transport.deleted, [])

    def test_a_duck_typed_holder_store_does_not_count(self):
        class LooksLikeOne:
            backend_id = "oracle_object_storage"

            def head(self, object_id):
                return True

        source, destination, index = self._critical()
        result = replication.rebalance_object(
            OBJECT_ID, source, destination, index, checkpoint=accept,
            holder_stores={"oracle_object_storage": LooksLikeOne()})
        self.assertEqual(result.status, "COPIED_SOURCE_RETAINED")
        self.assertEqual(source._transport.deleted, [])

    def test_a_confirmed_holder_counts_and_the_move_completes(self):
        source, destination, index = self._critical()
        result = replication.rebalance_object(
            OBJECT_ID, source, destination, index, checkpoint=accept,
            holder_stores={"oracle_object_storage":
                           holder_store("oracle_object_storage")})
        self.assertEqual(result.status, "MOVED")
        self.assertIs(result.source_deleted, True)
        self.assertEqual(set(result.verified_copies),
                         {DESTINATION_BACKEND, "oracle_object_storage"})

    def test_a_hostile_holder_stores_argument_is_refused(self):
        for value in HOSTILE:
            if value is None:
                continue
            with self.subTest(value=repr(value)[:24]):
                source, destination, index = mesh()
                result = replication.rebalance_object(
                    OBJECT_ID, source, destination, index,
                    holder_stores=value)
                self.assertIn(result.status, replication.REBALANCE_STATUSES)
                self.assertIs(result.source_deleted, False)
                self.assertEqual(source._transport.deleted, [])

    def test_a_single_copy_class_needs_no_other_holder(self):
        # IMPORTANT is owed one copy, the destination is that copy, and it was
        # verified here rather than counted.
        source, destination, index = mesh()
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index, checkpoint=accept)
        self.assertEqual(result.status, "MOVED")
        self.assertEqual(tuple(result.verified_copies), (DESTINATION_BACKEND,))

    def test_verified_copies_never_include_the_deleted_source(self):
        source, destination, index = mesh()
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index, checkpoint=accept)
        self.assertNotIn(SOURCE_BACKEND, result.verified_copies)


class MalformedIndexRecordTests(unittest.TestCase):
    """The docstring promises it does not raise. The index answer was unguarded.

    ``can_perform_destructive_lifecycle`` only requires a ``MetadataStore``, and
    any subclass - a caching layer, a partial-record fast path - can answer with
    something ``validate_metadata_record`` never saw. The two field extractions
    that followed were the only statements in the function without a guard.
    """

    class UnvalidatedIndex(FakeMetadataStore):
        """A real MetadataStore whose read path is overridden, as a cache's is."""

        def __init__(self, answer, **kwargs):
            super().__init__(records=[record()], **kwargs)
            self.answer = answer

        def get_manifest(self, object_id):
            return self.answer

    def _answers(self):
        good = record()
        without_primary = {key: value for key, value in good.items()
                           if key != "primary_backend"}
        without_replicas = {key: value for key, value in good.items()
                            if key != "replica_backends"}
        without_criticality = {key: value for key, value in good.items()
                               if key != "criticality"}
        return {
            "missing primary_backend": without_primary,
            "missing replica_backends": without_replicas,
            "missing criticality": without_criticality,
            "null replica_backends": dict(good, replica_backends=None),
            "string replica_backends": dict(good, replica_backends="r2"),
            "unhashable replica entry": dict(good, replica_backends=[["r2"]]),
            "non-string replica entry": dict(good, replica_backends=[1, 2, 3]),
            "non-string primary": dict(good, primary_backend=1),
            "a list": [1, 2, 3],
            "bytes": b"not a record",
            "an object": object(),
            "a string": "not a record",
            "an integer": 7,
            "a needle": SMUGGLED_CREDENTIAL,
        }

    def test_a_non_validated_record_returns_rather_than_raises(self):
        for label, answer in self._answers().items():
            with self.subTest(answer=label):
                source, destination, _ = mesh()
                index = self.UnvalidatedIndex(answer)
                result = replication.rebalance_object(OBJECT_ID, source,
                                                      destination, index,
                                                      checkpoint=accept)
                self.assertIn(result.status, replication.REBALANCE_STATUSES)
                self.assertIs(result.source_deleted, False)
                self.assertEqual(source._transport.deleted, [])
                self.assertEqual(source.get(OBJECT_ID), PAYLOAD)

    def test_a_shape_it_cannot_read_blocks_on_metadata_uncertainty(self):
        for label, answer in self._answers().items():
            with self.subTest(answer=label):
                source, destination, _ = mesh()
                index = self.UnvalidatedIndex(answer)
                result = replication.rebalance_object(OBJECT_ID, source,
                                                      destination, index,
                                                      checkpoint=accept)
                self.assertEqual(result.status, "BLOCKED_METADATA_UNCERTAIN")

    def test_nothing_is_copied_on_a_record_it_cannot_read(self):
        source, destination, _ = mesh()
        index = self.UnvalidatedIndex(object())
        replication.rebalance_object(OBJECT_ID, source, destination, index,
                                     checkpoint=accept)
        self.assertEqual(destination._transport.calls, [])

    def test_a_malformed_record_is_never_echoed_into_the_result(self):
        source, destination, _ = mesh()
        index = self.UnvalidatedIndex({"primary_backend": SMUGGLED_CREDENTIAL})
        result = replication.rebalance_object(OBJECT_ID, source, destination,
                                              index, checkpoint=accept)
        blob = json.dumps(result.as_dict(), default=repr) + repr(result)
        self.assertNotIn("sk-A7bQ", blob)



if __name__ == "__main__":
    unittest.main()
