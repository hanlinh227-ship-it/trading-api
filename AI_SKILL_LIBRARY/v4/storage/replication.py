"""Federated Free Storage Mesh - selective replication and the rebalance protocol.

Spec S8 says how many copies an object is owed, Spec S9 says what a copy is,
and Spec S15 says how a copy is moved. The third of those is the one this
module exists for, and it is stated twice in the design because the ordering is
the whole of it::

    1 choose eligible destination     5 persist recovery checkpoint/pointer
    2 copy object                     6 only then remove old copy if policy permits
    3 verify content hash             7 verify final replica count
    4 register destination replica

    "Never delete before verifying the replacement."

``policy.yaml`` records the same fact as
``rebalance_deletes_source_before_destination_verified: false``. Everything
below is arranged so that breaking it requires deleting a line rather than
forgetting one: there is exactly one call to ``source.delete`` in this file, it
is the last statement of the last branch, and every path that does not reach it
returns a status naming why.

**Step 1 is not here.** Choosing a destination is ``placement.py``'s, and a
module that could choose one would be a second placement engine. ``rebalance_object``
is handed a destination and executes; it ranks nothing, admits no provider and
holds no authority.

**Verification recomputes.** ``verify_copy`` hashes the payload it is given and
compares. It does not read a digest off the receipt and agree with it: a receipt
is a claim made by the thing being checked, and a check that consults its
subject for the answer is not a check (Spec S15). The rebalance goes further and
hashes bytes *read back from the destination*, because verifying the payload
that was uploaded proves something about this process's memory and nothing at
all about the far side.

**Four independent facts gate a delete.** The destination read back correctly,
the destination's own ``head`` agrees, the index accepted the new replica, and
a recovery pointer was persisted. The fourth is not optional and has no default:
a rebalance called without a ``checkpoint`` is a copy, because Spec S18 forbids
the metadata service being the single point of failure and the pointer is what
survives its outage. On top of all four sits Spec S18 again: while the metadata
service is uncertain, a rebalance does not start at all - not even the copy -
because a move whose registration cannot be persisted is a move nobody can
recover from.

**Step 7 verifies copies, not a number.** "Verify final replica count" is
satisfiable by counting the backends a record names, and a record names the
replicas the mesh registered at some point rather than the ones that are there
now. Only the destination is read back and head-checked as a matter of course;
every other claimed holder of an object owed more than one copy is probed
through a store the caller supplies, and a holder that cannot be probed cannot
be confirmed and does not count. ``RebalanceResult.verified_copies`` records
what was confirmed rather than what was claimed.

**Full copies only.** Spec S9 puts erasure coding and chunk striping explicitly
out of scope, and the reason is worth keeping in view: a missing chunk makes a
file unreadable, while a missing replica makes it merely less redundant. There
is no splitting, sharding, striping or parity anywhere in this module.

Nothing here opens a connection, reads a credential, writes a file or performs
any cryptography. It returns results rather than raising, because it is the
path a caller uses under capacity pressure and provider failure, and Spec S14
requires that path to degrade rather than crash.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping
from functools import lru_cache

from AI_SKILL_LIBRARY.v4.storage import AUTHORITY_FLAGS as _AUTHORITY_FLAG_NAMES
from AI_SKILL_LIBRARY.v4.storage import CANONICAL_AUTHORITY
from AI_SKILL_LIBRARY.v4.storage import CRITICALITY_CLASSES
from AI_SKILL_LIBRARY.v4.storage import mesh_validator as _mesh_validator
from AI_SKILL_LIBRARY.v4.storage import metadata as _metadata
from AI_SKILL_LIBRARY.v4.storage.adapters import s3_object as _object

#: This module holds no authority of any kind. Denied by name rather than by
#: omission, so a later edit cannot acquire one by adding a key.
AUTHORITY = False
AUTHORITY_FLAGS = {flag: False for flag in _AUTHORITY_FLAG_NAMES}

ROUTED_BY = "task_router"

#: No cryptography is chosen, implemented or performed here (Spec S21).
ENCRYPTION_IMPLEMENTED_HERE = False

#: Spec S9 and ``policy.yaml`` ``replication``. Stated as constants so a test
#: can assert the absence rather than a reviewer having to read for it.
REPLICATION_MODEL = "single_primary_with_optional_full_replicas"
ERASURE_CODING_IMPLEMENTED_HERE = False
CHUNK_STRIPING_IMPLEMENTED_HERE = False

#: What an unrecognised criticality is owed. Fail closed means the *strictest*
#: obligation here, not the loosest: understating a requirement is precisely
#: what authorises a delete, so an unknown class asks for the most copies any
#: known class asks for rather than the fewest.
UNKNOWN_REQUIREMENT = 2

_OBJECT_ID_RE = re.compile(r"^obj_[0-9a-f]{64}\Z")

#: The closed vocabulary of outcomes. Every path out of ``rebalance_object``
#: ends at one of these, and a caller that switches on the status is switching
#: on a set that cannot silently grow a member meaning "it went fine, probably".
REBALANCE_STATUSES = (
    # the two ways it can succeed
    "MOVED",
    "COPIED_SOURCE_RETAINED",
    # the ways it can stop with the source intact
    "BLOCKED_METADATA_UNCERTAIN",
    "REFUSED_INVALID_REQUEST",
    "REFUSED_UNKNOWN_OBJECT",
    "REFUSED_SAME_BACKEND",
    "REFUSED_SOURCE_NOT_A_HOLDER",
    "SOURCE_READ_FAILED",
    "DESTINATION_WRITE_FAILED",
    "VERIFY_FAILED",
    "METADATA_UPDATE_FAILED",
    "CHECKPOINT_FAILED",
    # verified, and the removal itself did not complete
    "DELETE_FAILED",
    "METADATA_UPDATE_FAILED_AFTER_DELETE",
)


# --- how many copies ----------------------------------------------------------


@lru_cache(maxsize=1)
def _requirements():
    """``min_independent_provider_copies`` per class, read from policy.yaml.

    Read from the document rather than mirrored as a literal, because the
    numbers here decide whether a copy may be deleted and a second statement of
    them is a second statement to drift. A class the policy describes with a
    value that is not a plain non-negative integer is dropped rather than
    guessed at, which sends it to ``UNKNOWN_REQUIREMENT``.
    """
    table = {}
    try:
        declared = _mesh_validator.load_policy().get("criticality") or {}
    except Exception:  # noqa: BLE001 - an unreadable policy is not a permission
        return table
    for name in CRITICALITY_CLASSES:
        rules = declared.get(name)
        if not isinstance(rules, dict):
            continue
        value = rules.get("min_independent_provider_copies")
        if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 8:
            table[name] = value
    return table


def replication_requirement(criticality):
    """How many independent provider copies this criticality class is owed.

    Spec S8: CRITICAL is at least two independent provider copies, IMPORTANT is
    a primary plus a replica where free headroom exists, REPRODUCIBLE needs one
    cloud copy, EPHEMERAL needs none.

    Never raises and never returns anything but a plain integer. An
    unrecognised class - a typo, a value from an older build, a list, ``None``,
    a credential passed to the wrong parameter - is owed
    ``UNKNOWN_REQUIREMENT``, which is the largest obligation any known class
    carries. The asymmetry is deliberate: over-stating a requirement retains a
    copy nobody needed, and under-stating one deletes a copy somebody did.
    """
    try:
        value = _requirements().get(criticality, UNKNOWN_REQUIREMENT)
    except Exception:  # noqa: BLE001 - an unhashable argument is not a class
        return UNKNOWN_REQUIREMENT
    if not isinstance(value, int) or isinstance(value, bool):
        return UNKNOWN_REQUIREMENT
    return value


# --- what a verified copy is ---------------------------------------------------


def verify_copy(payload, receipt):
    """Does ``receipt`` describe *these* bytes? Recomputed, never read off.

    Spec S15 step 3. The digest is computed here from the payload and then
    compared against all three of the receipt's assertions - its digest, the
    content address in its ``object_id``, and its length. A receipt that is
    internally consistent and simply not about this payload fails, which is the
    exact shape a confused or hostile store produces, and a receipt asserting
    no digest at all fails too: nothing is not agreement.

    Returns exactly ``True`` or exactly ``False`` for every input in the
    universe, and raises for none of them. It is called on failure paths, by a
    caller deciding whether to delete data, and a verifier that can raise is a
    verifier whose caller has to remember to catch.

    A duck-typed stand-in is refused. An object that happens to have the right
    four attributes has asserted nothing: it has not been through the bounds
    ``ObjectReceipt`` applies, and accepting it would make this gate satisfiable
    by any two-line stub somebody passed in by mistake.
    """
    try:
        if not isinstance(receipt, _object.ObjectReceipt):
            return False
        if not isinstance(payload, (bytes, bytearray)):
            return False
        digest = _object.content_digest(payload)
        return bool(
            receipt.content_sha256 == digest
            and receipt.object_id == f"obj_{digest}"
            and receipt.size_bytes == len(payload)
        )
    except Exception:  # noqa: BLE001 - unknown is not verified
        return False


# --- the result ----------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class RebalanceResult:
    """What a rebalance did, and to what.

    ``source_deleted`` is the field that matters and it is never inferred from
    the status: a caller reading this to decide whether an object still has two
    copies should be reading a recorded fact, not re-deriving one from a string.

    ``detail`` is drawn from a fixed set of sentences written in this file. It
    never quotes an argument, a record, a provider answer or an exception, since
    every one of those can carry a credential and a result travels into logs.
    """

    status: str
    object_id: str | None
    source_backend: str | None
    destination_backend: str | None
    source_deleted: bool
    destination_verified: bool
    detail: str
    #: The backends whose copy this call *confirmed*, in order. Spec S15 step 7
    #: says "verify final replica count", and a count is what the record claims:
    #: only the destination is read back and head-checked as a matter of course,
    #: so every other holder that appears here was probed through a store the
    #: caller supplied. A claimed holder that could not be confirmed is absent,
    #: which is the difference between a number and a copy.
    verified_copies: tuple = ()

    def as_dict(self):
        """A plain, JSON-safe copy."""
        return dataclasses.asdict(self)


def _result(status, detail, *, object_id=None, source=None, destination=None,
            source_deleted=False, destination_verified=False,
            verified_copies=()):
    return RebalanceResult(
        status=status,
        object_id=object_id,
        source_backend=source,
        destination_backend=destination,
        source_deleted=source_deleted,
        destination_verified=destination_verified,
        detail=detail,
        verified_copies=tuple(verified_copies),
    )


# --- the rebalance --------------------------------------------------------------


def _attachable(record):
    """The object's own metadata: the part of a record that travels with bytes.

    A projection rather than the whole record. What backends hold an object,
    when it was last touched, where its evidence lives and which key opens it
    are all index state; welded to the object they would be wrong the moment it
    moved, and two of them must never reach a provider at all (Spec S22).
    ``s3_object`` refuses them by name; this simply does not offer them.
    """
    return {field: record[field]
            for field in _object.OBJECT_METADATA_VALUE_CHECKS
            if field in record}


def _readable(record):
    """The three fields a rebalance reads, or ``None`` if it cannot read them.

    ``metadata.MetadataStore.get_manifest`` validates what it returns, but
    ``can_perform_destructive_lifecycle`` only requires *a* ``MetadataStore``:
    a caching layer, a partial-record fast path or any other subclass can put a
    shape in front of this function that the validator never saw. Indexing the
    answer directly was the only unguarded pair of statements in the protocol,
    and this module's contract is that it returns rather than raises.

    Nothing here is a second validator. It reads exactly what the delete gate
    needs - who holds the object and what class it is - and answers ``None`` for
    every shape it cannot read, which sends the caller to
    ``BLOCKED_METADATA_UNCERTAIN``.
    """
    try:
        if not isinstance(record, Mapping):
            return None
        primary = record["primary_backend"]
        replicas = record["replica_backends"]
        criticality = record["criticality"]
        if not isinstance(primary, str):
            return None
        if not isinstance(replicas, (list, tuple, set, frozenset)):
            return None
        if not all(isinstance(name, str) for name in replicas):
            return None
        return {"primary_backend": primary,
                "holders": {primary, *replicas},
                "criticality": criticality,
                "attachable": _attachable(record)}
    except Exception:  # noqa: BLE001 - an unreadable record is not a record
        return None


def _confirmed_holders(object_id, receipt, backends, holder_stores):
    """Which of ``backends`` can be shown, right now, to hold this object.

    Spec S15 step 7 asks for the final replica count to be *verified*. The
    record's own list is a claim: the mesh registered those backends at some
    point and nothing has looked since, so a replica that has been lifecycled
    away, expired or lost still appears in it. Deleting the source on the
    strength of that claim is how a CRITICAL object ends with one copy anybody
    has actually seen.

    A backend is confirmed only when the caller supplied a store for it, that
    store is a real ``ObjectStore`` answering for that backend, and its own
    ``head`` asserts the same digest and the same length as the copy that was
    just verified. Everything else - no store supplied, an unreachable store, a
    store that denies holding the object, a store that asserts nothing - is
    unknown, and unknown is not a copy.
    """
    confirmed = set()
    stores = holder_stores if isinstance(holder_stores, Mapping) else {}
    for backend in backends:
        try:
            store = stores.get(backend)
        except Exception:  # noqa: BLE001 - an unusable mapping confirms nothing
            continue
        if not isinstance(store, _object.ObjectStore):
            continue
        if store.backend_id != backend:
            continue
        try:
            head = store.head(object_id)
        except Exception:  # noqa: BLE001 - unreachable is not present
            continue
        if head is None:
            continue
        if head.content_sha256 != receipt.content_sha256:
            continue
        if head.size_bytes != receipt.size_bytes:
            continue
        confirmed.add(backend)
    return confirmed


def _registered(record, *, holders):
    """A copy of ``record`` whose backend fields state ``holders``."""
    primary = record["primary_backend"]
    if primary not in holders:
        primary = sorted(holders)[0]
    updated = dict(record)
    updated["primary_backend"] = primary
    updated["replica_backends"] = sorted(holders - {primary})
    return updated


def rebalance_object(object_id, source, destination, metadata_store, *,
                     verify=verify_copy, checkpoint=None, delete_source=True,
                     holder_stores=None):
    """Move one object from ``source`` to ``destination``, or explain why not.

    Spec S15, in the spec's order, with the source removed last and only after
    three independent facts agree: the destination read back as the right bytes,
    the destination's own ``head`` agrees, and the index accepted the registered
    replica. Spec S8's replication requirement is then consulted, so an object
    owed two copies keeps both rather than becoming a move.

    ``verify`` is injectable so a caller can demand something stricter; it
    cannot be used to demand something looser, because the read-back, the head
    cross-check and the metadata registration happen either way. Only exactly
    ``True`` counts as verification - a truthy string, a ``1`` or a non-empty
    list is a verifier that has not said yes.

    ``checkpoint`` is Spec S15 step 5: a callable handed a small pointer
    mapping, which must return exactly ``True`` before any deletion. It is
    required for a *move*. Without one the outcome is capped at
    ``COPIED_SOURCE_RETAINED``: step 5 sits between the registration and the
    removal for a reason, and Spec S18 is explicit that the metadata service
    must not be a single point of failure - the pointer is what survives its
    outage, so a delete gated only on the index is a delete nobody can follow.
    A copy is always allowed without one.

    ``holder_stores`` is an optional ``{backend_id: ObjectStore}`` mapping used
    for Spec S15 step 7. The record's replica list is a claim; only the
    destination is read back and head-checked here. When the object's class is
    owed more than one copy, every *other* claimed holder is probed through the
    store supplied for it, and a holder with no store supplied cannot be
    confirmed and does not count - which fails closed, towards keeping the
    source. ``RebalanceResult.verified_copies`` records what was confirmed.

    Returns a ``RebalanceResult``. It does not raise: this is the path a caller
    takes under capacity pressure and provider failure, and Spec S14 requires
    that path to degrade rather than crash.
    """
    # -- the request itself ---------------------------------------------------
    if not isinstance(source, _object.ObjectStore) or not isinstance(
            destination, _object.ObjectStore):
        return _result(
            "REFUSED_INVALID_REQUEST",
            "source and destination must both be ObjectStore instances; a "
            "duck-typed stand-in has not been through the bounds an adapter "
            "applies, and note that bytes is a Sequence")
    source_backend = source.backend_id
    destination_backend = destination.backend_id

    if not isinstance(object_id, str) or not _OBJECT_ID_RE.match(object_id):
        return _result(
            "REFUSED_INVALID_REQUEST",
            "object_id must be 'obj_' followed by a lower-case SHA-256 digest",
            source=source_backend, destination=destination_backend)
    if not callable(verify):
        return _result(
            "REFUSED_INVALID_REQUEST",
            "verify must be a callable taking (payload, receipt)",
            object_id=object_id, source=source_backend,
            destination=destination_backend)
    if checkpoint is not None and not callable(checkpoint):
        return _result(
            "REFUSED_INVALID_REQUEST",
            "checkpoint must be a callable taking a pointer mapping, or None",
            object_id=object_id, source=source_backend,
            destination=destination_backend)
    if holder_stores is not None and not isinstance(holder_stores, Mapping):
        return _result(
            "REFUSED_INVALID_REQUEST",
            "holder_stores must be a mapping of backend id to ObjectStore, or "
            "None",
            object_id=object_id, source=source_backend,
            destination=destination_backend)
    if not isinstance(delete_source, bool):
        return _result(
            "REFUSED_INVALID_REQUEST",
            "delete_source must be a boolean; a deletion is not authorised by "
            "a truthy value",
            object_id=object_id, source=source_backend,
            destination=destination_backend)
    if source_backend == destination_backend:
        return _result(
            "REFUSED_SAME_BACKEND",
            "source and destination are the same backend; a second copy on one "
            "provider is not an independent replica (Spec S8), and a 'move' "
            "that ends by deleting its own destination is data loss",
            object_id=object_id, source=source_backend,
            destination=destination_backend)

    def stop(status, detail, **kwargs):
        return _result(status, detail, object_id=object_id,
                       source=source_backend, destination=destination_backend,
                       **kwargs)

    # -- Spec S18: an uncertain index pauses destructive lifecycle entirely ----
    if not _metadata.can_perform_destructive_lifecycle(metadata_store):
        return stop(
            "BLOCKED_METADATA_UNCERTAIN",
            "the metadata store is not a healthy MetadataStore; while the "
            "record of what exists is uncertain, rebalance and deletion are "
            "paused and no copy is started (Spec S18)")
    try:
        record = metadata_store.get_manifest(object_id)
    except Exception:  # noqa: BLE001 - an unreadable index is not an empty one
        return stop(
            "BLOCKED_METADATA_UNCERTAIN",
            "the metadata store could not be read; absence and unreachability "
            "are the same shape and opposite facts, and neither authorises a "
            "move (Spec S18)")
    if record is None:
        return stop(
            "REFUSED_UNKNOWN_OBJECT",
            "the index holds no record for this object; a rebalance is not the "
            "moment to adopt an object of unknown privacy class")

    readable = _readable(record)
    if readable is None:
        return stop(
            "BLOCKED_METADATA_UNCERTAIN",
            "the index answered with something this module cannot read as a "
            "manifest record; a row that has not been through the validator is "
            "not a statement about what exists, and nothing is copied, "
            "registered or removed on the strength of one (Spec S18). The "
            "answer is deliberately not quoted")
    holders = readable["holders"]
    criticality = readable["criticality"]
    attachable = readable["attachable"]
    if source_backend not in holders:
        return stop(
            "REFUSED_SOURCE_NOT_A_HOLDER",
            "the record does not place this object on the source backend; "
            "moving from a provider the index does not believe holds a copy "
            "would delete something nobody is tracking")

    # -- Spec S15 step 2: copy -------------------------------------------------
    try:
        payload = source.get(object_id)
    except Exception:  # noqa: BLE001 - see detail
        return stop(
            "SOURCE_READ_FAILED",
            "the source copy could not be read back as the bytes its address "
            "names; an unreadable or corrupt source is a repair job, and it is "
            "never a reason to delete it or to propagate it (Spec S19)")

    try:
        receipt = destination.put(object_id, payload, attachable)
    except Exception:  # noqa: BLE001 - see detail
        return stop(
            "DESTINATION_WRITE_FAILED",
            "the destination did not accept the copy; nothing has changed and "
            "the source is untouched")

    # -- Spec S15 step 3: verify the *destination*, not this process's memory --
    try:
        readback = destination.get(object_id)
    except Exception:  # noqa: BLE001 - see detail
        return stop(
            "VERIFY_FAILED",
            "the destination could not be read back after the write; a write "
            "that cannot be read is not a verified copy")
    try:
        verified = verify(readback, receipt)
    except Exception:  # noqa: BLE001 - a verifier that raises has not said yes
        return stop(
            "VERIFY_FAILED",
            "the verifier raised rather than answering; an escape from a "
            "verification is 'unknown', and unknown is not verified")
    if verified is not True:
        return stop(
            "VERIFY_FAILED",
            "the verifier did not answer exactly True; a truthy value is not a "
            "verification, and this is the one place that distinction is worth "
            "data")
    try:
        head = destination.head(object_id)
    except Exception:  # noqa: BLE001 - see detail
        return stop(
            "VERIFY_FAILED",
            "the destination could not be asked what it holds; a copy nobody "
            "can confirm exists is not a replacement")
    if head is None or head.content_sha256 != receipt.content_sha256 or (
            head.size_bytes != receipt.size_bytes):
        return stop(
            "VERIFY_FAILED",
            "the destination's own head disagrees with the copy that was just "
            "written; a store that contradicts itself is not one to delete the "
            "last other copy on")

    # -- Spec S15 step 4: register the destination replica --------------------
    holders_after = holders | {destination_backend}
    try:
        metadata_store.put_manifest(_registered(record, holders=holders_after))
    except Exception:  # noqa: BLE001 - see detail
        return stop(
            "METADATA_UPDATE_FAILED",
            "the new replica could not be registered in the index; the copy "
            "exists but is unrecorded, so the source stays where it is rather "
            "than becoming a copy nobody can find (Spec S15/S18)",
            destination_verified=True,
            verified_copies=(destination_backend,))

    # -- Spec S15 step 5: persist the recovery pointer ------------------------
    if checkpoint is not None:
        try:
            acknowledged = checkpoint({
                "object_id": object_id,
                "content_sha256": receipt.content_sha256,
                "size_bytes": receipt.size_bytes,
                "source_backend": source_backend,
                "destination_backend": destination_backend,
                "observed_at": receipt.observed_at,
            })
        except Exception:  # noqa: BLE001 - see detail
            acknowledged = None
        if acknowledged is not True:
            return stop(
                "CHECKPOINT_FAILED",
                "the recovery pointer was not persisted; both copies exist and "
                "the source is retained, because a move GitHub has no pointer "
                "to is a move a rebuild cannot follow (Spec S15/S23)",
                destination_verified=True,
                verified_copies=(destination_backend,))

    # -- Spec S15 steps 6 and 7: remove the old copy only if policy permits ---
    if not delete_source:
        return stop(
            "COPIED_SOURCE_RETAINED",
            "the caller asked for a copy rather than a move; both copies exist "
            "and both are registered",
            destination_verified=True, verified_copies=(destination_backend,))
    if checkpoint is None:
        return stop(
            "COPIED_SOURCE_RETAINED",
            "no recovery pointer was persisted because no checkpoint callable "
            "was supplied, and a delete is not gated on the index alone: Spec "
            "S15 step 5 sits between registering the replica and removing the "
            "old copy, and Spec S18 forbids the metadata service being the "
            "single point of failure that a rebuild would then have to follow. "
            "Both copies exist and both are registered",
            destination_verified=True, verified_copies=(destination_backend,))

    # Step 7 verifies copies rather than counting claims. The destination is
    # already confirmed - it was read back, re-hashed and cross-checked against
    # its own head - and every other backend the record names is a claim until
    # a store supplied for it says otherwise.
    requirement = replication_requirement(criticality)
    confirmed = {destination_backend}
    if requirement > 1:
        confirmed |= _confirmed_holders(
            object_id, receipt,
            sorted(holders_after - {source_backend, destination_backend}),
            holder_stores)
    verified_copies = tuple(sorted(confirmed))
    if len(confirmed) < requirement:
        return stop(
            "COPIED_SOURCE_RETAINED",
            "deleting the source would leave fewer *confirmed* independent "
            "provider copies than this criticality class is owed, so the copy "
            "is kept and the source stays (Spec S8/S15). A backend the record "
            "merely names is a claim: it counts only when a store was supplied "
            "for it and that store's own head agreed, and a holder whose store "
            "was not supplied cannot be confirmed and does not count",
            destination_verified=True, verified_copies=verified_copies)

    try:
        source.delete(object_id)
    except Exception:  # noqa: BLE001 - see detail
        return stop(
            "DELETE_FAILED",
            "the verified copy exists and the source could not be removed; "
            "both copies are present and both are registered, which is the "
            "safe side of this failure",
            destination_verified=True, verified_copies=verified_copies)

    holders_final = holders_after - {source_backend}
    try:
        metadata_store.put_manifest(_registered(record, holders=holders_final))
    except Exception:  # noqa: BLE001 - see detail
        return stop(
            "METADATA_UPDATE_FAILED_AFTER_DELETE",
            "the source was removed and the index still lists it; the record "
            "now over-states the copies that exist, which is the direction that "
            "causes a repair rather than a deletion, and it is surfaced rather "
            "than hidden (Spec S19)",
            source_deleted=True, destination_verified=True,
            verified_copies=verified_copies)

    return stop(
        "MOVED",
        "the destination was written, read back, confirmed by its own head and "
        "registered before the source was removed (Spec S15)",
        source_deleted=True, destination_verified=True,
        verified_copies=verified_copies)


__all__ = [
    "AUTHORITY", "AUTHORITY_FLAGS", "CANONICAL_AUTHORITY", "ROUTED_BY",
    "ENCRYPTION_IMPLEMENTED_HERE", "REPLICATION_MODEL",
    "ERASURE_CODING_IMPLEMENTED_HERE", "CHUNK_STRIPING_IMPLEMENTED_HERE",
    "UNKNOWN_REQUIREMENT", "REBALANCE_STATUSES", "RebalanceResult",
    "replication_requirement", "verify_copy", "rebalance_object",
]
