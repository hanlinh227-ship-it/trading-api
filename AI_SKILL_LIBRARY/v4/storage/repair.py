"""Federated Free Storage Mesh - automated repair of a replica set.

Spec S19 says what happens when a provider is lost: mark it OFFLINE, stop new
writes to it, serve reads from a *verified* replica, enqueue repair, restore the
required replica count on another eligible free provider, and update the
manifest only after hash verification. Spec S8 says how many copies each
criticality class is owed. Spec S18 blocks destructive lifecycle while the index
is uncertain. This module is the repair half of that, for one object at a time.

**A replica count is a count of confirmed copies, never of index claims.**
``replica_backends`` records the backends the mesh registered at some moment;
a provider that has since gone offline, expired the object, been quarantined or
never really took it still appears in it. Task 5 counted those claims, had to be
fixed, and the fix is the load-bearing idea here: a backend counts when this
process read the object's bytes back from it and hashed them to the object's own
address. Everything else - a name in the record, a provider's own ``head``
asserting a digest, a store that could not be reached - is unknown, and unknown
is not a copy. A repair that believes the index is a repair that loses data.

**Independent copies, not merely several.** Two aliases pointing at one physical
provider are one copy, and two paths on one host survive that host exactly as
well as one does. So the provider list is keyed by each store's own
``backend_id`` and a store filed under any other key is refused; a provider named
twice is refused; and every local backend collapses into a single independence
domain (``independence_domain``). The count that decides a repair is a count of
domains.

**Nothing here deletes anything.** There is no call to remove an object in this
file, and ``PERFORMS_DELETION`` says so as a constant a test can assert. What
this module produces is ``destructive_cleanup_enabled``: false unless the index
is healthy *and* the object's replication obligation is met by confirmed copies.
The act itself stays in ``replication.rebalance_object``, which already carries
the Spec S15 ordering and the "never delete before verifying the replacement"
rule. A repair module that could delete is a repair module that can drop the
last verified copy on the strength of a claim.

**Bounded in four directions, stated as constants.** One object per call;
``MAX_PROVIDERS_SCANNED`` providers, and never more than the caller configured;
``MAX_REPAIR_WRITES`` write attempts, with each destination attempted **at most
once** so there is no retry loop to run away; and ``MAX_TARGET_COPIES`` copies,
which is the manifest schema's own replica bound.

**Placement is not decided here.** A destination must be reachable, must not
already hold a confirmed copy, must be in a different independence domain, and
must survive ``destination_is_eligible`` - which builds the record the repair
would write and hands it to ``metadata.validate_metadata_record``. That is the
existing cross-field rule set (LOCAL_ONLY never leaves owned storage,
CONFIDENTIAL leaves only as ciphertext, Supabase forces the METADATA tier), not
a second placement engine. This module ranks nothing and admits no provider.

It opens no connection, reads no credential, creates nothing external and
performs no cryptography. Content identity is a ``hashlib`` digest comparison
made in ``adapters/s3_object.py``. It returns results rather than raising,
because it is the path a caller takes under provider failure and Spec S14
requires that path to degrade rather than crash.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping, Sequence

from AI_SKILL_LIBRARY.v4.storage import AUTHORITY_FLAGS as _AUTHORITY_FLAG_NAMES
from AI_SKILL_LIBRARY.v4.storage import CANONICAL_AUTHORITY
from AI_SKILL_LIBRARY.v4.storage import CRITICALITY_CLASSES
from AI_SKILL_LIBRARY.v4.storage import manifest as _manifest
from AI_SKILL_LIBRARY.v4.storage import metadata as _metadata
from AI_SKILL_LIBRARY.v4.storage import replication as _replication
from AI_SKILL_LIBRARY.v4.storage.adapters import s3_object as _object

#: This module holds no authority of any kind. Denied by name rather than by
#: omission, so a later edit cannot acquire one by adding a key.
AUTHORITY = False
AUTHORITY_FLAGS = {flag: False for flag in _AUTHORITY_FLAG_NAMES}

ROUTED_BY = "task_router"

#: No cryptography is chosen, implemented or performed here (Spec S21).
ENCRYPTION_IMPLEMENTED_HERE = False

#: Nothing external is created, provisioned or admitted by this module.
CREATES_EXTERNAL_RESOURCES = False
PROVISIONING_AUTHORIZED = False

#: The structural half of "never delete the final verified required copy":
#: this file contains no deletion at all, and the tests assert the absence in
#: the source as well as the constant.
PERFORMS_DELETION = False

# --- bounds -------------------------------------------------------------------
# Every anchored pattern below ends in ``\Z`` and never in ``$``. Python's ``$``
# also matches immediately before a trailing newline, so a ``$``-anchored check
# passes a string one character longer than the bound allowed. This lane has
# already paid for that bug once.

#: How many providers one repair may scan. The checked-in registry holds eight
#: rows; sixteen leaves room for the registry to grow without this becoming the
#: thing that breaks, and it is small enough that a scan is a bounded, bounded-
#: cost operation rather than a sweep of whatever mapping was passed in. The
#: real bound is tighter in practice: the scan never exceeds the provider list
#: the caller configured, so an empty list scans nothing.
MAX_PROVIDERS_SCANNED = 16

#: How many copies one call may write. Four, because the largest replication
#: requirement any criticality class carries is two and
#: ``replication.UNKNOWN_REQUIREMENT`` is two: four leaves headroom for a policy
#: that raises a class to three or four copies without letting a single call
#: turn into a fan-out across every provider in the registry. Each destination
#: is attempted at most once, so this is a cap on a loop that is already finite.
MAX_REPAIR_WRITES = 4

#: The most copies any object may be owed, taken from the manifest schema's own
#: replica bound rather than restated: an object needing more independent copies
#: than the schema can record is a policy question, not a repair question.
MAX_TARGET_COPIES = _manifest._MAX_REPLICAS

#: The detail sentence is drawn from a fixed set written in this file. The bound
#: exists anyway, because a bound nobody can exceed is the one that catches the
#: edit that made it exceedable.
MAX_DETAIL = 400
MAX_BACKEND = 64
MAX_STATUS = 64
MAX_CRITICALITY = 32
MAX_OBJECT_ID = 68

#: All local backends share one independence domain. A second copy on the same
#: host is not a second provider: it survives that host exactly as well as the
#: first one does, and Spec S8 asks for *independent provider* copies.
LOCAL_INDEPENDENCE_DOMAIN = "local_host"

#: The closed vocabulary of outcomes. Every path out of ``repair_replica_set``
#: ends at one of these, so a caller switching on the status is switching on a
#: set that cannot silently grow a member meaning "it went fine, probably".
REPAIR_STATUSES = (
    # the object is owed no more than it has
    "ALREADY_SATISFIED",
    # copies were written, verified and registered, and the obligation is met
    "REPAIRED",
    # the obligation is not met, and the reason is named
    "DEGRADED_INSUFFICIENT_DESTINATIONS",
    "DEGRADED_NO_VERIFIED_COPY",
    "DEGRADED_COPY_UNREGISTERED",
    # nothing was attempted
    "BLOCKED_METADATA_UNCERTAIN",
    "REFUSED_INVALID_REQUEST",
    "REFUSED_UNKNOWN_OBJECT",
)

_STATUS_RE = re.compile(r"[A-Z][A-Z_]{0,63}\Z")
_BACKEND_RE = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_CRITICALITY_RE = re.compile(r"[A-Z][A-Z_]{0,31}\Z")
_OBJECT_ID_RE = re.compile(r"obj_[0-9a-f]{64}\Z")
#: A closed alphabet: letters, digits and the punctuation the sentences below
#: use. No quotes, no braces, no backslashes - nothing that could carry a
#: structured value out of this module and into a log.
_DETAIL_RE = re.compile(r"[a-z][A-Za-z0-9 ,.;:()/_'-]{0,399}\Z")


class RepairResultRejected(ValueError):
    """A result that cannot be trusted is refused, never repaired."""


# --- the manifest fields this module reads ------------------------------------
#
# The structural guard. ``MANIFEST_FIELDS_READ`` binds, for every field this
# module consults or carries, the *identical* bounded checker ``metadata.py``
# already wrote for it - the same callable object, which the tests assert with
# ``is``. ``MANIFEST_FIELDS_NOT_READ`` names every other property of
# ``storage_object_manifest.schema.json`` with the reason repair does not touch
# it. Together they are asserted equal to the schema's property set *read from
# disk*, so a property added to the contract later is in neither table and fails
# the day it is added.
#
# This is the seventh place in this lane where "an allowed field whose value
# nothing bounds" could have been introduced, and the six previous ones were all
# hand-written field lists. A hand-written list closes the fields somebody
# thought of; a table derived from the contract closes the rest.

_READ_FIELDS = (
    # identity and content, which is what a verified copy is compared against
    "version", "object_id", "content_sha256", "size_bytes",
    # what may be written where
    "privacy_class", "criticality", "storage_tier", "encryption_state",
    "encryption_scheme_version",
    # placement, which is the claim this module refuses to take on trust
    "primary_backend", "replica_backends",
    # the classifiers that travel with the object when a copy is written
    "mime_type", "object_class", "retention_class", "created_at",
    "lifecycle_state", "reproducible",
)

MANIFEST_FIELDS_READ = {
    field: _metadata._RECORD_FIELD_CHECKS[field] for field in _READ_FIELDS
}

MANIFEST_FIELDS_NOT_READ = {
    "authority": (
        "a manifest record asserts no authority and a repair grants none; the "
        "flag is validated where the record is written and is not an input to "
        "any decision made here"),
    "authority_flags": (
        "the eight authorities are denied by name in the record and in this "
        "module; a repair does not read them because there is no branch they "
        "could legitimately change"),
    "encryption": (
        "encryption metadata carries key_ref, nonce and tag. Spec S22 keeps key "
        "material away from the ciphertext provider, and a repair copies bytes "
        "it never interprets, so it has no reason to hold any of the three"),
    "source_provenance": (
        "provenance is evidence about where an object came from; a repair "
        "changes where a copy of it lives and must not rewrite, re-assert or "
        "carry that evidence onto a provider"),
    "verification": (
        "verification is what the mesh observed at some earlier moment. It is "
        "precisely the stale claim this module exists to replace with a fresh "
        "observation, so reading it would be reading the answer off the "
        "question"),
    "last_accessed_at": (
        "access time is runtime index state; a repair is not an access by the "
        "object's user and must not look like one"),
    "last_verified_at": (
        "the previous verification timestamp predates the loss that forced the "
        "repair; re-asserting it would be manufacturing evidence, which is the "
        "one thing a repair report must never do"),
}

MANIFEST_FIELDS = tuple(MANIFEST_FIELDS_READ)


# --- how many copies, and whose ------------------------------------------------


def independence_domain(backend_id):
    """The failure domain a backend belongs to (Spec S8).

    Every *local* backend answers ``LOCAL_INDEPENDENCE_DOMAIN``: a second copy
    on the same host is not an independent provider copy, it is the same copy
    written twice, and it survives the loss of that host exactly as well as the
    first one does. Every external backend is its own domain, named by its
    registry ``provider_id``.

    This is the only notion of independence this module can honestly enforce.
    The other shape of the same mistake - two aliases pointing at one physical
    provider - is refused earlier and structurally: the provider list is keyed
    by each store's own ``backend_id``, a store filed under any other key is
    refused, and a provider named twice is refused.

    Never raises.
    """
    try:
        if _manifest._is_local(backend_id):
            return LOCAL_INDEPENDENCE_DOMAIN
    except Exception:  # noqa: BLE001 - an unreadable registry names no domain
        return ""
    return backend_id if isinstance(backend_id, str) else ""


def destination_is_eligible(record, backend_id):
    """May this object legitimately gain a copy on this backend?

    Answered by building the record the repair would write and handing it to
    ``metadata.validate_metadata_record`` - the existing closed field set,
    bounded checkers and cross-field rules, which already encode that LOCAL_ONLY
    never leaves owned storage, that CONFIDENTIAL leaves only as ciphertext with
    the metadata proving it, that Supabase forces the METADATA tier, and that a
    non-bulk tier carries no payload.

    That is deliberately not a second placement engine: it ranks nothing, reads
    no quota and admits no provider. It is the same validator that will refuse
    the write later, asked first so that the write is not attempted.

    Returns exactly ``True`` or exactly ``False`` for every input, and raises for
    none of them.
    """
    try:
        holders = {record["primary_backend"], *record["replica_backends"]}
        _manifest._check_backend(backend_id, role="destination")
        candidate = _replication._registered(
            dict(record), holders=holders | {backend_id})
        _metadata.validate_metadata_record(candidate)
        return True
    except Exception:  # noqa: BLE001 - an unprovable placement is not permission
        return False


# --- the result ----------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class RepairResult:
    """What a repair confirmed, what it wrote, and what it could not prove.

    ``verified_copies_before`` and ``verified_copies_after`` are the two fields
    that matter and neither is ever derived from ``replica_backends``: a backend
    appears in them only when this call read the object's bytes back from it and
    hashed them to the object's own address.

    ``detail`` is drawn from a fixed set of sentences written in this file. It
    never quotes an argument, a record, a provider answer or an exception, since
    every one of those can carry a credential and a result travels into logs.
    """

    status: str
    object_id: str | None
    criticality: str | None
    #: How many independent provider copies this class is owed (Spec S8).
    target_replica_count: int
    #: Confirmed before anything was written. Not claimed - confirmed.
    verified_copies_before: tuple
    #: Confirmed after, including copies this call wrote, verified and
    #: registered. A copy that could not be registered is absent from it.
    verified_copies_after: tuple
    #: The backend the bytes were read from, or ``None`` when none could be.
    read_source: str | None
    #: The backends that gained a verified, registered copy in this call.
    repaired_to: tuple
    #: Backends the record names or the caller configured that hold no copy this
    #: call could confirm: unreachable, empty, or answering with other bytes.
    unconfirmed: tuple
    #: Whether the object still has fewer confirmed independent copies than its
    #: class is owed (Spec S19: surface the degraded state, never hide it).
    degraded: bool
    #: Whether a destructive lifecycle action may now proceed for this object.
    #: Never performed here; this module deletes nothing.
    destructive_cleanup_enabled: bool
    detail: str

    def as_dict(self):
        """A plain, JSON-safe copy."""
        return dataclasses.asdict(self)


def _redacted(message):
    """Raise a refusal with no chained context, whatever is being handled.

    The bounded checkers borrowed from ``manifest.py`` and ``metadata.py`` quote
    their input, which is right for a manifest built from repository data and
    wrong for one built from a runtime caller's mapping. ``from None`` is what
    keeps the quoted value out of ``__context__`` - which ``str(exc)`` hides and
    every traceback prints under "During handling of the above exception". That
    leak has been found twice in this lane.
    """
    raise RepairResultRejected(
        f"{message}. The value is deliberately not quoted: a refusal that "
        "echoes its input is how a mistyped credential reaches a log") from None


def _bounded_string(value, pattern, limit, *, field):
    if not isinstance(value, str):
        _redacted(f"{field} must be a string")
    if len(value) > limit:
        _redacted(f"{field} is {len(value)} characters, over its {limit} bound")
    if not pattern.fullmatch(value):
        _redacted(f"{field} does not match its bounded pattern")
    try:
        _manifest.assert_no_credential_material(value, where=field)
    except Exception:  # noqa: BLE001 - the text is discarded on purpose
        _redacted(f"{field} carries something shaped like credential material")
    return value


def _check_status(value, *, field):
    _bounded_string(value, _STATUS_RE, MAX_STATUS, field=field)
    if value not in REPAIR_STATUSES:
        _redacted(f"{field} is not one of this module's declared statuses")


def _check_detail(value, *, field):
    _bounded_string(value, _DETAIL_RE, MAX_DETAIL, field=field)


def _check_optional_object_id(value, *, field):
    if value is None:
        return
    _bounded_string(value, _OBJECT_ID_RE, MAX_OBJECT_ID, field=field)
    try:
        _metadata._check_object_id(value, field=field)
    except Exception:  # noqa: BLE001 - the text is discarded on purpose
        _redacted(f"{field} is not a content address")


def _check_optional_criticality(value, *, field):
    if value is None:
        return
    _bounded_string(value, _CRITICALITY_RE, MAX_CRITICALITY, field=field)
    if value not in CRITICALITY_CLASSES:
        _redacted(f"{field} is not a criticality class")


def _check_optional_backend(value, *, field):
    if value is None:
        return
    _bounded_string(value, _BACKEND_RE, MAX_BACKEND, field=field)
    try:
        _manifest._check_backend(value, role=field)
    except Exception:  # noqa: BLE001 - the text is discarded on purpose
        _redacted(f"{field} is not a backend the provider registry names")


def _check_backend_tuple(value, *, field):
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(
            value, (tuple, list)):
        _redacted(f"{field} must be a tuple of backend ids, and note that "
                  "bytes is a Sequence")
    if len(value) > MAX_TARGET_COPIES + 1:
        _redacted(f"{field} names more backends than the schema can record")
    for backend in value:
        _check_optional_backend(backend, field=f"{field} member")
    if len(set(value)) != len(value):
        _redacted(f"{field} names a backend twice; a second copy on one "
                  "provider is not an independent replica")
    if list(value) != sorted(value):
        _redacted(f"{field} must be ordered, so two runs of the same repair "
                  "produce the same document")


def _check_target(value, *, field):
    try:
        _manifest._check_bounded_int(value, 0, MAX_TARGET_COPIES, field=field)
    except Exception:  # noqa: BLE001 - the text is discarded on purpose
        _redacted(f"{field} must be an integer replica obligation")


def _check_bool(value, *, field):
    if value is not True and value is not False:
        _redacted(f"{field} must be literally true or false; a truthy value is "
                  "not an observation")


#: One bounded validator per field of a ``RepairResult``. A table rather than a
#: run of ``if`` statements, so the field tuple can be *derived* from it: a
#: field that is allowed but validated by nothing therefore cannot exist.
RESULT_VALUE_CHECKS = {
    "status": _check_status,
    "object_id": _check_optional_object_id,
    "criticality": _check_optional_criticality,
    "target_replica_count": _check_target,
    "verified_copies_before": _check_backend_tuple,
    "verified_copies_after": _check_backend_tuple,
    "read_source": _check_optional_backend,
    "repaired_to": _check_backend_tuple,
    "unconfirmed": _check_backend_tuple,
    "degraded": _check_bool,
    "destructive_cleanup_enabled": _check_bool,
    "detail": _check_detail,
}

#: Derived, not declared a second time.
RESULT_FIELDS = tuple(RESULT_VALUE_CHECKS)

#: The pattern-bounded string fields and their bounds, exposed so the tests can
#: assert the anchor and the length of every one without repeating the list.
#: The tuple fields appear here because the bound is per element: the pattern is
#: what each backend id must match.
RESULT_FIELD_PATTERNS = {
    "status": _STATUS_RE,
    "object_id": _OBJECT_ID_RE,
    "criticality": _CRITICALITY_RE,
    "read_source": _BACKEND_RE,
    "verified_copies_before": _BACKEND_RE,
    "verified_copies_after": _BACKEND_RE,
    "repaired_to": _BACKEND_RE,
    "unconfirmed": _BACKEND_RE,
    "detail": _DETAIL_RE,
}

RESULT_FIELD_MAX_LENGTHS = {
    "status": MAX_STATUS,
    "object_id": MAX_OBJECT_ID,
    "criticality": MAX_CRITICALITY,
    "read_source": MAX_BACKEND,
    "verified_copies_before": MAX_BACKEND,
    "verified_copies_after": MAX_BACKEND,
    "repaired_to": MAX_BACKEND,
    "unconfirmed": MAX_BACKEND,
    "detail": MAX_DETAIL,
}


def assert_result_is_clean(result):
    """Refuse a result that is malformed, unbounded or self-contradictory.

    Run by ``repair_replica_set`` on its own answer before it is returned, and
    available to anything that reads one afterwards. The cross-field rules are
    the ones no single field can state: a repaired backend must be a confirmed
    one, a confirmed copy must not have been claimed as repaired without being
    verified, and cleanup may not be enabled while the object is degraded.

    Returns the argument it was given, so a caller can wrap a result in it.
    Raises ``RepairResultRejected``, never anything else, and never quotes.
    """
    document = result.as_dict() if isinstance(result, RepairResult) else result
    if not isinstance(document, Mapping):
        _redacted("a repair result must be a mapping or a RepairResult")
    unknown = sorted(set(document) - set(RESULT_VALUE_CHECKS))
    if unknown:
        _redacted(
            f"a repair result rejects {len(unknown)} unknown field(s): the "
            "field set is closed and derived from the checker table, so a "
            "field nobody wrote a checker for cannot ride into the document")
    missing = sorted(set(RESULT_FIELDS) - set(document))
    if missing:
        _redacted(f"a repair result is missing {len(missing)} field(s)")

    for field in RESULT_FIELDS:
        RESULT_VALUE_CHECKS[field](document[field], field=field)

    confirmed_after = set(document["verified_copies_after"])
    if not set(document["repaired_to"]) <= confirmed_after:
        _redacted("repaired_to names a backend that is not a confirmed copy; a "
                  "write nobody verified is not a repair")
    if set(document["unconfirmed"]) & confirmed_after:
        _redacted("a backend cannot be both confirmed and unconfirmed")
    if document["read_source"] is not None and document["read_source"] not in set(
            document["verified_copies_before"]):
        _redacted("the read source must itself be a confirmed copy")
    if document["degraded"] and document["destructive_cleanup_enabled"]:
        _redacted("destructive cleanup may not be enabled while the object is "
                  "short of the copies its class is owed (Spec S18)")
    if document["status"] == "REPAIRED" and not document["repaired_to"]:
        _redacted("a repair that wrote nothing is not REPAIRED")
    return result


def _result(status, detail, **fields):
    values = {
        "status": status,
        "object_id": None,
        "criticality": None,
        "target_replica_count": 0,
        "verified_copies_before": (),
        "verified_copies_after": (),
        "read_source": None,
        "repaired_to": (),
        "unconfirmed": (),
        "degraded": False,
        "destructive_cleanup_enabled": False,
        "detail": detail,
    }
    values.update(fields)
    result = RepairResult(**values)
    assert_result_is_clean(result)
    return result


# --- the provider list --------------------------------------------------------


def configured_providers(providers):
    """The bounded ``{backend_id: ObjectStore}`` map, or ``None`` to refuse.

    Accepts a mapping or a sequence of stores. ``bytes`` and ``bytearray`` are
    ``collections.abc.Sequence`` instances and are excluded by name, along with
    ``str``: iterating one of them yields characters, which is a different and
    much stranger provider list than the one that was meant.

    The key must be the store's own ``backend_id``. That single line is what
    stops a duplicate alias to one physical provider from being counted twice,
    and a provider named twice is refused outright rather than deduplicated,
    because a caller who listed it twice believes something this module does
    not.
    """
    if isinstance(providers, (str, bytes, bytearray, memoryview)):
        return None
    if isinstance(providers, Mapping):
        items = list(providers.items())
    elif isinstance(providers, Sequence):
        items = []
        for store in providers:
            if not isinstance(store, _object.ObjectStore):
                return None
            items.append((store.backend_id, store))
    else:
        return None
    if len(items) > MAX_PROVIDERS_SCANNED:
        return None
    configured = {}
    for key, store in items:
        if not isinstance(store, _object.ObjectStore):
            return None
        if not isinstance(key, str) or key != store.backend_id:
            return None
        if key in configured:
            return None
        configured[key] = store
    return configured


def _probe(store, record):
    """Read one backend's copy back and hash it. Returns a payload or a reason.

    Three answers, and the difference between them decides whether the backend
    may later be a destination:

    ``("HELD", payload)``
        the bytes came back and hash to the object's own address.
    ``("ABSENT", None)``
        the store was reached and does not hold the object. It is a candidate.
    ``("UNUSABLE", None)``
        unreachable, or it answered with something that is not this object.
        Spec S19 marks a lost provider OFFLINE and stops new writes to it, and
        a store that returned other bytes is not one to hand a copy to either.
    """
    try:
        payload = store.get(record["object_id"])
    except _object.ObjectNotFound:
        return "ABSENT", None
    except Exception:  # noqa: BLE001 - unreachable and corrupt are both unusable
        return "UNUSABLE", None
    if not isinstance(payload, (bytes, bytearray)):
        return "UNUSABLE", None
    try:
        digest = _object.content_digest(payload)
    except Exception:  # noqa: BLE001 - unhashable is not verified
        return "UNUSABLE", None
    if digest != record["content_sha256"] or len(payload) != record["size_bytes"]:
        return "UNUSABLE", None
    return "HELD", bytes(payload)


def _write_verified_copy(store, record, payload):
    """Write one copy and prove it, or answer ``False``.

    The same three independent facts ``replication.rebalance_object`` requires:
    the destination accepted the write, bytes read back *from the destination*
    re-hash to the object's address, and the destination's own ``head`` agrees
    with the receipt. Verifying the payload that was uploaded would prove
    something about this process's memory and nothing about the far side.
    """
    object_id = record["object_id"]
    try:
        receipt = store.put(object_id, payload, _replication._attachable(record))
    except Exception:  # noqa: BLE001 - a refused write is not a copy
        return False
    try:
        readback = store.get(object_id)
    except Exception:  # noqa: BLE001 - a write that cannot be read is not a copy
        return False
    if _replication.verify_copy(readback, receipt) is not True:
        return False
    try:
        head = store.head(object_id)
    except Exception:  # noqa: BLE001 - a copy nobody can confirm is not one
        return False
    if head is None or head.content_sha256 != receipt.content_sha256 or (
            head.size_bytes != receipt.size_bytes):
        return False
    return True


# --- the repair ----------------------------------------------------------------


def repair_replica_set(manifest, providers, metadata):
    """Restore one object's confirmed independent copy count, or explain why not.

    ``manifest`` is the object's record; the index's own row for it is what is
    actually used, because the index is where the placement claim lives and a
    caller-supplied record could be stale. ``providers`` is the configured
    ``{backend_id: ObjectStore}`` map - or a sequence of stores - and is the
    bound on every scan. ``metadata`` is the ``MetadataStore``.

    In order: refuse a request that cannot be read; stop entirely while the
    index is uncertain (Spec S18); probe every configured provider once and keep
    only the copies that came back and hashed correctly; count *independence
    domains* rather than backends; and, while the object is short of what its
    class is owed, write to eligible reachable destinations - at most
    ``MAX_REPAIR_WRITES`` of them, each attempted once - verifying and
    registering each before it is counted.

    Returns a ``RepairResult``. It does not raise: this is the path a caller
    takes under provider failure, and Spec S14 requires that path to degrade
    rather than crash. Nothing is deleted, here or anywhere below this call.
    """
    configured = configured_providers(providers)
    if configured is None:
        return _result(
            "REFUSED_INVALID_REQUEST",
            "providers must be a mapping of backend id to ObjectStore, or a "
            "sequence of them, no longer than the scan cap, each filed under "
            "its own backend id and named once; an alias to one physical "
            "provider is not a second independent copy (Spec S8)")

    # -- Spec S18: an uncertain index pauses the whole repair ------------------
    if not _metadata.can_perform_destructive_lifecycle(metadata):
        return _result(
            "BLOCKED_METADATA_UNCERTAIN",
            "the metadata store is not a healthy MetadataStore; while the "
            "record of what exists is uncertain, a repair cannot register what "
            "it writes and is not started (Spec S18)")

    try:
        subject = _metadata.validate_metadata_record(manifest)
    except Exception:  # noqa: BLE001 - the text is discarded on purpose
        return _result(
            "REFUSED_INVALID_REQUEST",
            "the manifest did not pass the metadata record validator; a row "
            "that has not been through it is not a statement about what "
            "exists. The answer is deliberately not quoted")

    object_id = subject["object_id"]
    try:
        record = metadata.get_manifest(object_id)
    except Exception:  # noqa: BLE001 - an unreadable index is not an empty one
        return _result(
            "BLOCKED_METADATA_UNCERTAIN",
            "the metadata store could not be read; absence and unreachability "
            "are the same shape and opposite facts, and neither authorises a "
            "repair (Spec S18)",
            object_id=object_id)
    if record is None:
        return _result(
            "REFUSED_UNKNOWN_OBJECT",
            "the index holds no record for this object; a repair is not the "
            "moment to adopt an object of unknown privacy class",
            object_id=object_id)

    criticality = record["criticality"]
    requirement = min(_replication.replication_requirement(criticality),
                      MAX_TARGET_COPIES)
    claimed = {record["primary_backend"], *record["replica_backends"]}

    # -- probe: a copy is bytes that came back and hashed, never a name -------
    confirmed = {}
    reachable_empty = []
    for backend in sorted(configured)[:MAX_PROVIDERS_SCANNED]:
        state, payload = _probe(configured[backend], record)
        if state == "HELD":
            confirmed[backend] = payload
        elif state == "ABSENT":
            reachable_empty.append(backend)

    domains = {independence_domain(backend) for backend in confirmed}
    before = tuple(sorted(confirmed))

    def answer(status, detail, *, repaired=(), degraded=None):
        held = set(confirmed) | set(repaired)
        short = (len({independence_domain(b) for b in held}) < requirement
                 if degraded is None else degraded)
        return _result(
            status, detail,
            object_id=object_id,
            criticality=criticality,
            target_replica_count=requirement,
            verified_copies_before=before,
            verified_copies_after=tuple(sorted(held)),
            read_source=sorted(confirmed)[0] if confirmed else None,
            repaired_to=tuple(sorted(repaired)),
            unconfirmed=tuple(sorted((claimed | set(configured)) - held)),
            degraded=short,
            destructive_cleanup_enabled=not short)

    if len(domains) >= requirement:
        return answer(
            "ALREADY_SATISFIED",
            "the object already has at least as many confirmed independent "
            "provider copies as its criticality class is owed, so nothing was "
            "written (Spec S8)")

    if not confirmed:
        return answer(
            "DEGRADED_NO_VERIFIED_COPY",
            "no configured provider returned this object's bytes, so there is "
            "nothing to copy from. The loss is reported rather than repaired: "
            "a replica is never reconstructed from a record, and an object is "
            "not recovered because its metadata survived (Spec S19)")

    source = sorted(confirmed)[0]
    payload = confirmed[source]

    # -- repair: eligible, reachable, in a different failure domain ------------
    candidates = [backend for backend in reachable_empty
                  if independence_domain(backend) not in domains
                  and destination_is_eligible(record, backend)]

    repaired = []
    attempts = 0
    for backend in candidates:
        if len(domains) >= requirement or attempts >= MAX_REPAIR_WRITES:
            break
        attempts += 1
        if not _write_verified_copy(configured[backend], record, payload):
            # Attempted once and not revisited: there is no retry loop here.
            continue
        holders = {record["primary_backend"], *record["replica_backends"]}
        try:
            metadata.put_manifest(
                _replication._registered(record, holders=holders | {backend}))
        except Exception:  # noqa: BLE001 - an unregistered copy is not a repair
            return answer(
                "DEGRADED_COPY_UNREGISTERED",
                "a verified copy was written and the index would not record "
                "it. It is not counted and the object stays degraded: a copy "
                "nobody can find is not a copy anybody can rely on, and the "
                "safe direction is to under-state what exists (Spec S15/S18)",
                repaired=(), degraded=True)
        try:
            record = metadata.get_manifest(object_id) or record
        except Exception:  # noqa: BLE001 - keep the record already proved good
            pass
        repaired.append(backend)
        domains.add(independence_domain(backend))

    if len(domains) >= requirement:
        return answer(
            "REPAIRED",
            "the required copies were read from a verified replica, written, "
            "read back, confirmed by the destination's own head and registered "
            "before being counted (Spec S15/S19)",
            repaired=repaired)
    return answer(
        "DEGRADED_INSUFFICIENT_DESTINATIONS",
        "fewer confirmed independent provider copies exist than this "
        "criticality class is owed, and no further eligible, reachable "
        "destination in a different failure domain accepted a verified copy. "
        "The shortfall is surfaced rather than hidden, and no cleanup is "
        "enabled (Spec S14/S19)",
        repaired=repaired)


__all__ = [
    "AUTHORITY", "AUTHORITY_FLAGS", "CANONICAL_AUTHORITY", "ROUTED_BY",
    "ENCRYPTION_IMPLEMENTED_HERE", "CREATES_EXTERNAL_RESOURCES",
    "PROVISIONING_AUTHORIZED", "PERFORMS_DELETION", "MAX_PROVIDERS_SCANNED",
    "MAX_REPAIR_WRITES", "MAX_TARGET_COPIES", "MAX_DETAIL",
    "LOCAL_INDEPENDENCE_DOMAIN", "REPAIR_STATUSES", "MANIFEST_FIELDS",
    "MANIFEST_FIELDS_READ", "MANIFEST_FIELDS_NOT_READ", "RESULT_FIELDS",
    "RESULT_VALUE_CHECKS", "RESULT_FIELD_PATTERNS", "RESULT_FIELD_MAX_LENGTHS",
    "RepairResult", "RepairResultRejected", "assert_result_is_clean",
    "independence_domain", "destination_is_eligible", "configured_providers",
    "repair_replica_set",
]
