"""Did the mesh actually come back, and what did it lose?

    python AI_SKILL_LIBRARY/v4/tools/storage_mesh_recovery_drill.py

``reconstruct_mesh(recovery_snapshot, providers, metadata)`` is the disaster
half of Task 9. The metadata service is gone; what is left is the bounded
GitHub pointer set (Spec S18) and whatever the providers still hold (Spec S23).
The answer is three **explicit, disjoint** sets of object ids:

``recovered``
    the object's bytes were read back from enough *independent* providers,
    hashed here, matched against the snapshot pointer, and its rebuilt record
    was written into the destination index.
``degraded``
    at least one verified copy exists, but fewer than its criticality class is
    owed (Spec S8). The record is restored and the shortfall is stated, because
    Spec S19 requires a degraded state to be surfaced rather than hidden.
``unrecoverable``
    nobody could produce the bytes. It is named, it is never in ``recovered``,
    and no record is written that says otherwise.

**``unrecoverable`` cannot be fabricated into ``recovered``.** An id reaches
``recovered`` only by being in ``restored`` - the list ``recovery.restore_into_store``
returns from records *it* rebuilt - and the rebuild admits an object only when a
provider-side hash and size match the pointer. On top of that,
``assert_report_is_clean`` runs on every report before it leaves this module and
refuses one whose sets intersect, whose ``recovered`` is not a subset of
``restored``, or whose ``unrecoverable`` appears in ``restored``. Marking an
object recovered because its metadata survived is not a thing this module can
express.

**The scan asks, it does not enumerate.** ``ObjectStore`` offers put, get, head
and delete and no listing operation, so this drill asks each configured provider
about exactly the ids the snapshot names. ``unknown`` - objects observed on a
provider that the snapshot never heard of - is carried through from
``recovery.rebuild_report`` and is therefore empty here in practice. That is a
real limit and it is stated rather than papered over: an object outside the
snapshot is never adopted, and it is also never seen.

**Observations come from bytes, never from a ``head``.** A provider's own head
asserting a digest is a claim by the thing being checked. Every row handed to
the production rebuild is built from a payload this process read and hashed, so
a store that claims the right digest and holds nothing recovers nothing.

**There is no second recovery path.** The snapshot goes through
``recovery.assert_snapshot_is_clean`` and the rebuild through
``recovery.restore_into_store`` - the production cleanliness gate, the
production hash-and-size admission, the production privacy re-check and the
validated ``put_manifest`` boundary. A looser reconstruction written beside the
real one is the one an edit would get to use. The only things this module adds
are the provider scan, the independence arithmetic and the report.

**Bounded.** ``MAX_PROVIDERS_SCANNED`` providers and never more than the caller
configured; ``MAX_OBJECTS_RECONSTRUCTED`` objects, which is the snapshot's own
entry cap; ``MAX_READS`` reads in total, which is the product of the two. Each
(object, provider) pair is read at most once: there is no retry loop.

**Nothing is deleted.** ``PERFORMS_DELETION`` is false, there is no removal in
this file, and ``destructive_cleanup_enabled`` stays false unless the index is
healthy and every object in the snapshot came back with the copies its class is
owed (Spec S18, ``destructive_action_on_uncertain_evidence: FAIL_CLOSED``).

No network, no SDK, no provisioning, no credential. Transports are injected.
The command line runs the same function against temporary filesystem-backed
stores, so the integrity checks exercised there are the production ones.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import re
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

# Run as a script as well as imported as a module, like the other tools here.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_SKILL_LIBRARY.v4.storage import AUTHORITY_FLAGS as _AUTHORITY_FLAG_NAMES
from AI_SKILL_LIBRARY.v4.storage import CANONICAL_AUTHORITY
from AI_SKILL_LIBRARY.v4.storage import manifest as storage_manifest
from AI_SKILL_LIBRARY.v4.storage import metadata as storage_metadata
from AI_SKILL_LIBRARY.v4.storage import recovery as storage_recovery
from AI_SKILL_LIBRARY.v4.storage import repair as storage_repair
from AI_SKILL_LIBRARY.v4.storage import replication as storage_replication
from AI_SKILL_LIBRARY.v4.storage.adapters import s3_object as storage_object
from AI_SKILL_LIBRARY.v4.tools.storage_restore_drill import JsonFileMetadataStore

#: This tool reports a fact. It grants nothing, repairs nothing, promotes
#: nothing, and is not the authority that reads its report.
AUTHORITY = False
AUTHORITY_FLAGS = {flag: False for flag in _AUTHORITY_FLAG_NAMES}

ROUTED_BY = "task_router"

ENCRYPTION_IMPLEMENTED_HERE = False
CREATES_EXTERNAL_RESOURCES = False
PROVISIONING_AUTHORIZED = False

#: No mesh object is ever removed by this module: there is no call to an
#: object store's removal operation in this file, and the drill's own
#: transport answers that operation with None, which the adapter refuses as an
#: unacknowledged outcome. (``run_drill`` does unlink its own temporary index
#: file inside a temporary directory - that is the disaster it is simulating,
#: and it touches no object and no repository state.)
PERFORMS_DELETION = False

# --- bounds -------------------------------------------------------------------
# Every anchored pattern ends in ``\Z`` and never in ``$``: Python's ``$`` also
# matches immediately before a trailing newline, so a ``$``-anchored check
# passes a string one character longer than the bound allowed.

#: Providers one reconstruction may scan, shared with ``repair.py`` so the two
#: cannot drift. The scan never exceeds the configured provider list either.
MAX_PROVIDERS_SCANNED = storage_repair.MAX_PROVIDERS_SCANNED

#: Objects one reconstruction may rebuild. Taken from the snapshot's own entry
#: cap rather than restated: a document carrying more entries than that has
#: already been refused by the production cleanliness gate, and this is the
#: bound that still holds if that cap is ever raised carelessly.
MAX_OBJECTS_RECONSTRUCTED = storage_recovery.MAX_SNAPSHOT_ENTRIES

#: Total provider reads. Each (object, provider) pair is read at most once, so
#: this is the product of the two caps above and not a budget that a retry could
#: consume. There is no retry.
MAX_READS = MAX_PROVIDERS_SCANNED * MAX_OBJECTS_RECONSTRUCTED

MAX_DETAIL = 400
MAX_BACKEND = 64
MAX_STATUS = 64
MAX_OBJECT_ID = 68

RECOVERY_STATUSES = (
    "RECONSTRUCTED",
    "RECONSTRUCTED_WITH_LOSS",
    "NOTHING_RECOVERABLE",
    "DEGRADED_RESTORE_INCOMPLETE",
    "BLOCKED_METADATA_UNCERTAIN",
)

_STATUS_RE = re.compile(r"[A-Z][A-Z_]{0,63}\Z")
_BACKEND_RE = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_OBJECT_ID_RE = re.compile(r"obj_[0-9a-f]{64}\Z")
_DETAIL_RE = re.compile(r"[a-z][A-Za-z0-9 ,.;:()/_'-]{0,399}\Z")

#: The production object-id checker, bound rather than rewritten. The tests
#: assert it is the identical callable: a seventh independently-written copy of
#: "what a content address looks like" is a copy that will drift, and the looser
#: one is the one an edit gets to use.
OBJECT_ID_CHECK = storage_metadata._check_object_id

#: The provider-observation contract, taken whole from ``recovery.py``. Every
#: row this module builds is validated by the *production* checkers for the
#: *production* field set, so an observation this drill can make is exactly an
#: observation the real rebuild accepts - no more and no less.
OBSERVATION_VALUE_CHECKS = dict(storage_recovery.PROVIDER_RECORD_VALUE_CHECKS)
OBSERVATION_FIELDS = storage_recovery.PROVIDER_RECORD_FIELDS


class RecoveryRefused(ValueError):
    """A request this module will not act on. Never quotes its input."""


class RecoveryReportRejected(ValueError):
    """A report that cannot be trusted is refused, never repaired."""


def _refuse(exception_type, message):
    """Raise without chaining, whatever is being handled.

    The production validators quote their input, which is right for a document
    built from repository data and wrong for one handed in by a runtime caller.
    ``from None`` is what keeps the quoted value out of ``__context__`` - which
    ``str(exc)`` hides and every traceback prints under "During handling of the
    above exception". That leak has been found twice in this lane.
    """
    raise exception_type(
        f"{message}. The value is deliberately not quoted: a refusal that "
        "echoes its input is how a mistyped credential reaches a log") from None


# --- the report ----------------------------------------------------------------


def _bounded_string(value, pattern, limit, *, field):
    if not isinstance(value, str):
        _refuse(RecoveryReportRejected, f"{field} must be a string")
    if len(value) > limit:
        _refuse(RecoveryReportRejected,
                f"{field} is {len(value)} characters, over its {limit} bound")
    if not pattern.fullmatch(value):
        _refuse(RecoveryReportRejected,
                f"{field} does not match its bounded pattern")
    try:
        storage_manifest.assert_no_credential_material(value, where=field)
    except Exception:  # noqa: BLE001 - the text is discarded on purpose
        _refuse(RecoveryReportRejected,
                f"{field} carries something shaped like credential material")


def _check_status(value, *, field):
    _bounded_string(value, _STATUS_RE, MAX_STATUS, field=field)
    if value not in RECOVERY_STATUSES:
        _refuse(RecoveryReportRejected,
                f"{field} is not one of this module's declared statuses")


def _check_detail(value, *, field):
    _bounded_string(value, _DETAIL_RE, MAX_DETAIL, field=field)


def _check_object_id_set(value, *, field):
    if not isinstance(value, (frozenset, set)):
        _refuse(RecoveryReportRejected,
                f"{field} must be a set of object ids, so that a reader cannot "
                "mistake an ordering for a ranking")
    if len(value) > MAX_OBJECTS_RECONSTRUCTED:
        _refuse(RecoveryReportRejected,
                f"{field} names more objects than a snapshot can carry")
    for object_id in value:
        _bounded_string(object_id, _OBJECT_ID_RE, MAX_OBJECT_ID,
                        field=f"{field} member")
        try:
            OBJECT_ID_CHECK(object_id, field=field)
        except Exception:  # noqa: BLE001 - the text is discarded on purpose
            _refuse(RecoveryReportRejected,
                    f"{field} names something that is not a content address")


def _check_object_id_tuple(value, *, field):
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(
            value, (tuple, list)):
        _refuse(RecoveryReportRejected,
                f"{field} must be a tuple of object ids, and note that bytes is "
                "a Sequence")
    if len(value) > MAX_OBJECTS_RECONSTRUCTED:
        _refuse(RecoveryReportRejected,
                f"{field} names more objects than a snapshot can carry")
    _check_object_id_set(set(value), field=field)
    if len(set(value)) != len(value):
        _refuse(RecoveryReportRejected, f"{field} names an object twice")
    if list(value) != sorted(value):
        _refuse(RecoveryReportRejected,
                f"{field} must be ordered, so two runs of one drill produce the "
                "same document")


def _check_backend_tuple(value, *, field):
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(
            value, (tuple, list)):
        _refuse(RecoveryReportRejected,
                f"{field} must be a tuple of backend ids, and note that bytes "
                "is a Sequence")
    if len(value) > MAX_PROVIDERS_SCANNED:
        _refuse(RecoveryReportRejected,
                f"{field} names more backends than one scan may reach")
    for backend in value:
        _bounded_string(backend, _BACKEND_RE, MAX_BACKEND,
                        field=f"{field} member")
        try:
            storage_manifest._check_backend(backend, role=field)
        except Exception:  # noqa: BLE001 - the text is discarded on purpose
            _refuse(RecoveryReportRejected,
                    f"{field} names a backend the provider registry does not")
    if len(set(value)) != len(value):
        _refuse(RecoveryReportRejected, f"{field} names a backend twice")
    if list(value) != sorted(value):
        _refuse(RecoveryReportRejected, f"{field} must be ordered")


def _check_bool(value, *, field):
    if value is not True and value is not False:
        _refuse(RecoveryReportRejected,
                f"{field} must be literally true or false; a truthy value is "
                "not an observation")


@dataclasses.dataclass(frozen=True)
class RecoveryReport:
    """What came back, what came back short, and what did not come back.

    The three sets are the contract and they are disjoint by construction and
    again by ``assert_report_is_clean``. ``detail`` is drawn from a fixed set of
    sentences written in this file: it never quotes a snapshot, a provider
    answer or an exception, because a report travels into logs.
    """

    status: str
    #: Verified, restored, and holding the independent copies its class is owed.
    recovered: frozenset
    #: Verified and restored, and short of those copies (Spec S19).
    degraded: frozenset
    #: Not reconstructable. Explicit, never fabricated, never in ``recovered``.
    unrecoverable: frozenset
    #: A provider held something under the id whose bytes are not the object.
    #: A subset of ``unrecoverable``: a content-addressed mesh whose content
    #: does not match its address has one bug, and admitting it gives it two.
    unverified: frozenset
    #: Observed on a provider and absent from the snapshot. Reported, never
    #: adopted: a rebuild is not the moment to take on an object of unknown
    #: privacy class. Empty in practice - the object adapter has no listing
    #: operation, so this drill only ever asks about ids the snapshot names.
    unknown: frozenset
    #: The object ids written into the destination index, in order.
    restored: tuple
    scanned_backends: tuple
    #: Backends that could not be reached at all (Spec S19: mark OFFLINE).
    unreachable_backends: tuple
    destructive_cleanup_enabled: bool
    detail: str

    def as_dict(self):
        """A plain copy. The sets stay sets; nothing here is a handle."""
        return dataclasses.asdict(self)


#: One bounded validator per field of a ``RecoveryReport``. A table rather than
#: a run of ``if`` statements, so the field tuple is *derived* from it and a
#: field that is allowed but validated by nothing cannot exist.
REPORT_VALUE_CHECKS = {
    "status": _check_status,
    "recovered": _check_object_id_set,
    "degraded": _check_object_id_set,
    "unrecoverable": _check_object_id_set,
    "unverified": _check_object_id_set,
    "unknown": _check_object_id_set,
    "restored": _check_object_id_tuple,
    "scanned_backends": _check_backend_tuple,
    "unreachable_backends": _check_backend_tuple,
    "destructive_cleanup_enabled": _check_bool,
    "detail": _check_detail,
}

#: Derived, not declared a second time.
REPORT_FIELDS = tuple(REPORT_VALUE_CHECKS)

#: The pattern-bounded string fields and their bounds, exposed so the tests can
#: assert the anchor and the length of every one. The collection fields appear
#: here because the bound is per element.
REPORT_FIELD_PATTERNS = {
    "status": _STATUS_RE,
    "recovered": _OBJECT_ID_RE,
    "degraded": _OBJECT_ID_RE,
    "unrecoverable": _OBJECT_ID_RE,
    "unverified": _OBJECT_ID_RE,
    "unknown": _OBJECT_ID_RE,
    "restored": _OBJECT_ID_RE,
    "scanned_backends": _BACKEND_RE,
    "unreachable_backends": _BACKEND_RE,
    "detail": _DETAIL_RE,
}

REPORT_FIELD_MAX_LENGTHS = {
    "status": MAX_STATUS,
    "recovered": MAX_OBJECT_ID,
    "degraded": MAX_OBJECT_ID,
    "unrecoverable": MAX_OBJECT_ID,
    "unverified": MAX_OBJECT_ID,
    "unknown": MAX_OBJECT_ID,
    "restored": MAX_OBJECT_ID,
    "scanned_backends": MAX_BACKEND,
    "unreachable_backends": MAX_BACKEND,
    "detail": MAX_DETAIL,
}


def assert_report_is_clean(report):
    """Refuse a report that is malformed, unbounded or self-contradictory.

    Run on every report before it leaves this module, and available to anything
    that reads one afterwards. The cross-field rules are the ones no single
    field can state, and they are the reason an ``unrecoverable`` object cannot
    be presented as a ``recovered`` one: the three sets must be pairwise
    disjoint, ``recovered`` must be a subset of what was actually written into
    the destination index, ``unrecoverable`` must appear nowhere in it, and
    cleanup may not be enabled while anything is degraded or lost.

    Returns the argument it was given. Raises ``RecoveryReportRejected``, never
    anything else, and never quotes.
    """
    document = report.as_dict() if isinstance(report, RecoveryReport) else report
    if not isinstance(document, Mapping):
        _refuse(RecoveryReportRejected,
                "a recovery report must be a mapping or a RecoveryReport")
    unknown = sorted(set(document) - set(REPORT_VALUE_CHECKS))
    if unknown:
        _refuse(RecoveryReportRejected,
                f"a recovery report rejects {len(unknown)} unknown field(s): "
                "the field set is closed and derived from the checker table, so "
                "a field nobody wrote a checker for cannot ride in")
    missing = sorted(set(REPORT_FIELDS) - set(document))
    if missing:
        _refuse(RecoveryReportRejected,
                f"a recovery report is missing {len(missing)} field(s)")

    for field in REPORT_FIELDS:
        REPORT_VALUE_CHECKS[field](document[field], field=field)

    recovered = frozenset(document["recovered"])
    degraded = frozenset(document["degraded"])
    lost = frozenset(document["unrecoverable"])
    restored = frozenset(document["restored"])

    if recovered & lost:
        _refuse(RecoveryReportRejected,
                "an object cannot be recovered and unrecoverable at once; the "
                "loss is the honest half and inventing the other is how a drill "
                "certifies data that is gone (Spec S23)")
    if recovered & degraded or degraded & lost:
        _refuse(RecoveryReportRejected,
                "the three sets must be pairwise disjoint, so a reader cannot "
                "be told two things about one object")
    if not recovered <= restored:
        _refuse(RecoveryReportRejected,
                "a recovered object must be one whose rebuilt record was "
                "actually written into the destination index; nothing is "
                "recovered by being described")
    if lost & restored:
        _refuse(RecoveryReportRejected,
                "no record may be written for an object reported as lost")
    if not frozenset(document["unverified"]) <= lost:
        _refuse(RecoveryReportRejected,
                "an object whose bytes do not match its address is not "
                "reconstructable, so it belongs to the unrecoverable set too")
    if document["destructive_cleanup_enabled"] and (degraded or lost):
        _refuse(RecoveryReportRejected,
                "destructive cleanup may not be enabled while anything is "
                "degraded or lost (Spec S18, fail closed on uncertain "
                "evidence)")
    if document["status"] == "RECONSTRUCTED" and (degraded or lost):
        _refuse(RecoveryReportRejected,
                "a reconstruction with a loss says so in its status")
    return report


def _report(status, detail, **fields):
    values = {
        "status": status,
        "recovered": frozenset(),
        "degraded": frozenset(),
        "unrecoverable": frozenset(),
        "unverified": frozenset(),
        "unknown": frozenset(),
        "restored": (),
        "scanned_backends": (),
        "unreachable_backends": (),
        "destructive_cleanup_enabled": False,
        "detail": detail,
    }
    values.update(fields)
    report = RecoveryReport(**values)
    assert_report_is_clean(report)
    return report


# --- the scan ------------------------------------------------------------------


def _observe(store, entry):
    """Read one backend's copy of one object back and hash it.

    Returns ``("HELD", row)`` with an observation in the production
    ``PROVIDER_RECORD_FIELDS`` shape, ``("MISMATCH", None)`` when the store
    answered with something that is not this object, ``("ABSENT", None)`` when
    it was reached and holds nothing, or ``("UNREACHABLE", None)``.

    The digest is computed here from bytes. A provider's ``head`` is never
    consulted: it is a claim by the thing being checked, and a check that asks
    its subject for the answer is not a check (Spec S15).
    """
    object_id = entry["object_id"]
    try:
        payload = store.get(object_id)
    except storage_object.ObjectNotFound:
        return "ABSENT", None
    except storage_object.ObjectIntegrityError:
        return "MISMATCH", None
    except Exception:  # noqa: BLE001 - unreachable is not absent
        return "UNREACHABLE", None
    if not isinstance(payload, (bytes, bytearray)):
        return "MISMATCH", None
    digest = hashlib.sha256(bytes(payload)).hexdigest()
    if digest != entry["content_sha256"] or len(payload) != entry["size_bytes"]:
        return "MISMATCH", None
    return "HELD", {
        "backend_id": store.backend_id,
        "object_id": object_id,
        "content_sha256": digest,
        "size_bytes": len(payload),
        "observed_at": entry["created_at"],
    }


def _independent_copies(record):
    """How many independent provider copies a rebuilt record really has.

    The record was built by ``recovery.rebuild_report`` from verified
    observations only, so every backend it names was read and hashed. What is
    still needed is the independence arithmetic: two aliases on one host are one
    copy, which is why the count is over failure domains rather than names.
    """
    backends = {record["primary_backend"], *record["replica_backends"]}
    return len({storage_repair.independence_domain(b) for b in backends})


def reconstruct_mesh(recovery_snapshot, providers, metadata):
    """Rebuild what the providers can prove, and name what they cannot.

    ``recovery_snapshot`` is the bounded GitHub pointer set; it goes through the
    production cleanliness gate before anything is read. ``providers`` is the
    configured ``{backend_id: ObjectStore}`` map - or a sequence of stores, or
    an empty one - and is the bound on the scan. ``metadata`` is the
    *destination* ``MetadataStore`` the rebuilt index is written into.

    Returns a ``RecoveryReport``. Raises ``RecoveryRefused`` for a request or a
    snapshot this module will not act on; an unhealthy or duck-typed destination
    index is reported as ``BLOCKED_METADATA_UNCERTAIN`` rather than raised,
    because that is a finding about the mesh and not a caller's mistake.
    """
    configured = storage_repair.configured_providers(providers)
    if configured is None:
        _refuse(RecoveryRefused,
                "providers must be a mapping of backend id to ObjectStore, or a "
                "sequence of them, no longer than the scan cap, each filed "
                "under its own backend id and named once; an alias to one "
                "physical provider is not a second independent copy")

    try:
        snapshot = storage_recovery.assert_snapshot_is_clean(recovery_snapshot)
    except Exception:  # noqa: BLE001 - the text is discarded on purpose
        _refuse(RecoveryRefused,
                "the recovery snapshot did not pass the production cleanliness "
                "gate; a rebuild that trusts its input is a rebuild that will "
                "one day rebuild from somebody else's file (Spec S18)")

    entries = snapshot["entries"]
    if len(entries) > MAX_OBJECTS_RECONSTRUCTED:
        _refuse(RecoveryRefused,
                "the snapshot carries more entries than one reconstruction may "
                "rebuild")

    scanned = tuple(sorted(configured)[:MAX_PROVIDERS_SCANNED])
    known = frozenset(entry["object_id"] for entry in entries)

    # -- Spec S18: an uncertain destination index stops the whole thing -------
    if not storage_metadata.can_perform_destructive_lifecycle(metadata):
        return _report(
            "BLOCKED_METADATA_UNCERTAIN",
            "the destination is not a healthy MetadataStore, so a rebuilt "
            "record could not be written or read back; nothing was scanned, "
            "nothing is claimed, and every object stays unaccounted for rather "
            "than being called lost (Spec S18)",
            scanned_backends=scanned)

    # -- scan: bytes, hashed here, never a provider's own claim ---------------
    observations = []
    mismatched = set()
    reachable = set()
    reads = 0
    for entry in entries:
        for backend in scanned:
            if reads >= MAX_READS:
                break
            reads += 1
            state, row = _observe(configured[backend], entry)
            if state != "UNREACHABLE":
                reachable.add(backend)
            if state == "HELD":
                observations.append(row)
            elif state == "MISMATCH":
                mismatched.add(entry["object_id"])

    unreachable = tuple(sorted(set(scanned) - reachable))

    # -- rebuild and restore, through production code only --------------------
    try:
        outcome = storage_recovery.restore_into_store(
            metadata, observations, snapshot, require_complete=False)
    except Exception:  # noqa: BLE001 - the text is discarded on purpose
        return _report(
            "DEGRADED_RESTORE_INCOMPLETE",
            "the rebuilt records could not be written into the destination "
            "index, so nothing is reported as recovered; what the providers "
            "still hold is unchanged and the reconstruction can be run again "
            "against a healthy index (Spec S14)",
            degraded=frozenset(known - mismatched),
            unrecoverable=frozenset(mismatched),
            unverified=frozenset(mismatched),
            scanned_backends=scanned, unreachable_backends=unreachable)

    restored = tuple(outcome["restored"])
    lost = frozenset(outcome["unrecoverable"]) | frozenset(
        outcome["unverified"]) | mismatched
    lost -= frozenset(restored)

    recovered, degraded = set(), set()
    by_id = {record["object_id"]: record for record in outcome["rebuilt"]}
    for object_id in restored:
        record = by_id[object_id]
        owed = storage_replication.replication_requirement(record["criticality"])
        if _independent_copies(record) >= owed:
            recovered.add(object_id)
        else:
            degraded.add(object_id)

    lost |= (known - frozenset(restored) - lost)

    if not restored:
        status, detail = "NOTHING_RECOVERABLE", (
            "no configured provider returned the bytes of any object the "
            "snapshot names. The objects are listed as unrecoverable rather "
            "than omitted: a rebuild that silently drops what it could not see "
            "is a rebuild that then repairs, migrates or deletes on the basis "
            "of a smaller world than the real one (Spec S23)")
    elif degraded or lost:
        status, detail = "RECONSTRUCTED_WITH_LOSS", (
            "what the providers could prove was rebuilt and written; the rest "
            "is named. A degraded object has a verified copy and fewer than its "
            "class is owed, and an unrecoverable one has none and is never "
            "reported as recovered because its metadata survived (Spec S19/S23)")
    else:
        status, detail = "RECONSTRUCTED", (
            "every object the snapshot names came back from enough independent "
            "providers, was hashed against its own address and was written into "
            "the destination index")

    return _report(
        status, detail,
        recovered=frozenset(recovered),
        degraded=frozenset(degraded),
        unrecoverable=frozenset(lost),
        unverified=(frozenset(outcome["unverified"]) | mismatched)
        - frozenset(restored),
        unknown=frozenset(outcome["unknown"]),
        restored=tuple(sorted(restored)),
        scanned_backends=scanned,
        unreachable_backends=unreachable,
        destructive_cleanup_enabled=not (degraded or lost))


# --- the command line ----------------------------------------------------------
#
# The same function, run against temporary filesystem-backed stores. The
# transports are injected and read and write files inside one temporary
# directory; the adapters, the snapshot gate, the rebuild and the index
# boundary are all the production ones, so what this exercises is production
# recovery rather than a demonstration of itself.

_DRILL_ENDPOINT = "https://object-storage.example.invalid"
_DRILL_BUCKET = "mesh-objects"
_DRILL_TIME = "2026-09-18T00:00:00Z"
_DRILL_BACKENDS = ("cloudflare_r2", "oracle_object_storage")
_DRILL_PAYLOADS = (b"mesh-recovery-drill-object-one",
                   b"mesh-recovery-drill-object-two")

NO_FAULT = "none"
FAULTS = (NO_FAULT, "one_provider_offline", "object_lost", "object_corrupt")


def _drill_credential():
    """What a runtime secret store would hand back. Never a module constant."""
    return "injected-drill-credential"


def _filesystem_transport(root, *, offline=False):
    """An S3-compatible transport backed by one temporary directory.

    It cannot remove anything: the removal operation is answered with ``None``,
    which the adapter refuses as an unacknowledged outcome. A drill has no
    business holding a capability it must never use.
    """
    base = Path(root)

    def transport(operation, payload, *, endpoint, bucket, credential):
        if offline:
            raise RuntimeError("this provider is offline for the drill")
        path = base / payload["key"]
        if operation == "put":
            base.mkdir(parents=True, exist_ok=True)
            path.write_bytes(bytes(payload["body"]))
            return True
        if operation == "get":
            return path.read_bytes() if path.is_file() else None
        if operation == "head":
            if not path.is_file():
                return None
            body = path.read_bytes()
            return {"size_bytes": len(body),
                    "content_sha256": hashlib.sha256(body).hexdigest()}
        return None

    return transport


def _drill_store(backend_id, root, *, offline=False):
    return storage_object.ObjectStore(
        backend_id=backend_id,
        endpoint=_DRILL_ENDPOINT,
        bucket=_DRILL_BUCKET,
        credential_provider=_drill_credential,
        transport=_filesystem_transport(root, offline=offline),
        clock=lambda: _DRILL_TIME,
    )


def run_drill(*, workspace, fault=NO_FAULT):
    """Build a small mesh in ``workspace``, lose the index, and rebuild it."""
    if fault not in FAULTS:
        raise ValueError(f"fault must be one of {list(FAULTS)}")
    work = Path(workspace)

    records = [
        storage_manifest.StorageObject.from_bytes(
            payload,
            privacy_class="PUBLIC",
            criticality="CRITICAL",
            storage_tier="WARM",
            object_class="benchmark-bundle",
            mime_type="application/octet-stream",
            retention_class="short-window",
            primary_backend=_DRILL_BACKENDS[0],
            replica_backends=(_DRILL_BACKENDS[1],),
            created_at=_DRILL_TIME,
            lifecycle_state="RAW",
            reproducible=False,
        ).to_manifest()
        for payload in _DRILL_PAYLOADS
    ]

    primary_index = JsonFileMetadataStore(work / "primary" / "index.json")
    for record in records:
        primary_index.put_manifest(record)
    snapshot = storage_recovery.export_recovery_snapshot(
        primary_index, generated_at=_DRILL_TIME)

    roots = {backend: work / "providers" / backend
             for backend in _DRILL_BACKENDS}
    for backend, root in roots.items():
        root.mkdir(parents=True, exist_ok=True)
        for record, payload in zip(records, _DRILL_PAYLOADS):
            if fault == "object_lost" and record is records[0]:
                continue
            body = (b"tampered" if fault == "object_corrupt"
                    and record is records[0] else payload)
            (root / record["object_id"]).write_bytes(body)

    # The index is destroyed. Everything below rebuilds from the snapshot plus
    # what the providers still hold, which is exactly Spec S23's input set.
    primary_index.path.unlink(missing_ok=True)

    providers = {
        backend: _drill_store(
            backend, roots[backend],
            offline=(fault == "one_provider_offline"
                     and backend == _DRILL_BACKENDS[1]))
        for backend in _DRILL_BACKENDS
    }
    destination = JsonFileMetadataStore(work / "restored" / "index.json")
    return reconstruct_mesh(snapshot, providers, destination)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fault", choices=FAULTS, default=NO_FAULT,
                        help="damage the drill's own mesh, to demonstrate that "
                             "loss is reported rather than fabricated away")
    parser.add_argument("--strict", action="store_true",
                        help="exit non-zero when anything is degraded or lost")
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="storage-mesh-recovery-") as tmp:
        report = run_drill(workspace=Path(tmp), fault=args.fault)

    document = {
        "status": report.status,
        "recovered": sorted(report.recovered),
        "degraded": sorted(report.degraded),
        "unrecoverable": sorted(report.unrecoverable),
        "unverified": sorted(report.unverified),
        "unknown": sorted(report.unknown),
        "restored": list(report.restored),
        "scanned_backends": list(report.scanned_backends),
        "unreachable_backends": list(report.unreachable_backends),
        "destructive_cleanup_enabled": report.destructive_cleanup_enabled,
    }
    print(json.dumps(document, indent=2))
    incomplete = bool(report.degraded or report.unrecoverable)
    return 1 if (args.strict and incomplete) else 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "AUTHORITY", "AUTHORITY_FLAGS", "CANONICAL_AUTHORITY", "ROUTED_BY",
    "ENCRYPTION_IMPLEMENTED_HERE", "CREATES_EXTERNAL_RESOURCES",
    "PROVISIONING_AUTHORIZED", "PERFORMS_DELETION", "MAX_PROVIDERS_SCANNED",
    "MAX_OBJECTS_RECONSTRUCTED", "MAX_READS", "MAX_DETAIL",
    "RECOVERY_STATUSES", "OBJECT_ID_CHECK", "OBSERVATION_FIELDS",
    "OBSERVATION_VALUE_CHECKS", "REPORT_FIELDS", "REPORT_VALUE_CHECKS",
    "REPORT_FIELD_PATTERNS", "REPORT_FIELD_MAX_LENGTHS", "RecoveryReport",
    "RecoveryRefused", "RecoveryReportRejected", "assert_report_is_clean",
    "reconstruct_mesh", "run_drill", "main",
]
