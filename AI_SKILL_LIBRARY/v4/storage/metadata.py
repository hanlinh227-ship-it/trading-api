"""Federated Free Storage Mesh - the metadata store boundary.

Task 1 checked in the contracts, Task 2 built the typed manifest, Task 3 the
capacity broker and the placement engine. None of them remembers anything: a
``StorageObject`` exists for as long as the caller holds it. This module is
where a manifest record is handed to something that keeps it, and where it is
checked on the way in and again on the way out.

It is an index, not an authority. Spec S18 and ``policy.yaml``
``metadata_service`` both say so, and the practical consequence is the rule this
module exists to enforce: **when the index is uncertain, nothing destructive may
proceed**. ``policy.yaml`` states it twice - as
``lifecycle.destructive_action_on_uncertain_evidence: FAIL_CLOSED`` and as
``metadata_service.on_unavailable.new_destructive_lifecycle_actions: BLOCKED``
- and ``can_perform_destructive_lifecycle`` is the one function that answers it.
It returns ``True`` for exactly one input shape and ``False`` for every other,
including the plausible-looking object that answers ``healthy() -> True``
without being a metadata store at all. A permission derived from duck typing is
a permission derived from nothing.

This module opens no connection, reads no credential, creates no external
resource and performs no cryptography. It is the abstract boundary; the one
adapter that could talk to a real service lives in ``adapters/`` and cannot
either, until a transport is injected at runtime.

Three properties, each the answer to a specific way this goes wrong.

**Validation happens in the base class, not in the adapters.** ``put_manifest``,
``get_manifest`` and ``list_manifests`` are concrete and final in spirit;
adapters implement ``_put_record``/``_get_record``/``_all_records`` and never
see an unvalidated record or return one that has not been re-checked. An
adapter that validated its own input would be an adapter that could forget to.

**Records are re-validated on the way out.** A metadata table is a shared
surface. A row can be written by an older build, a half-finished migration or
something that is not this system at all, and a row that is believed because it
was found is a row that can carry anything. Reading fails closed: a malformed
row raises rather than being returned or silently skipped.

**Every string field is bounded, and the bound is where a credential dies.**
The field table below covers every property of
``storage_object_manifest.schema.json`` - the tests assert that set equality in
both directions - and every entry in it is a *bounded* check: a pattern and a
length, never "is a string". An allowed-but-unbounded field is how two
kilobytes of secret gets persisted under a name nobody thought to deny. On top
of that, ``MAX_RECORD_BYTES`` bounds the whole record; it is deliberately
unreachable by any record the field table admits, which is the point of having
it.

The per-field checks are imported from ``manifest.py`` rather than restated.
They are private names there, and reaching for them is a deliberate choice: a
second, independently-written copy of "what a bounded evidence reference looks
like" is a copy that will drift, and the looser of the two is the one an
attacker gets to use.
"""

from __future__ import annotations

import abc
import json
import re
from collections.abc import Mapping, Sequence

from AI_SKILL_LIBRARY.v4.storage import (
    AUTHORITY_FLAGS,
    CANONICAL_AUTHORITY,
    CRITICALITY_CLASSES,
    LIFECYCLE_STATES,
    PRIVACY_CLASSES,
    STORAGE_TIERS,
)
from AI_SKILL_LIBRARY.v4.storage import manifest as _manifest
from AI_SKILL_LIBRARY.v4.storage import mesh_validator

#: No authority of any kind, matching the rest of the lane. Supabase in
#: particular is an index and never canonical (Spec S18/S25).
AUTHORITY = False

#: No cryptography is chosen, implemented or performed here.
ENCRYPTION_IMPLEMENTED_HERE = False

MANIFEST_VERSION = _manifest.MANIFEST_VERSION

#: A whole-record bound, on top of the per-field bounds. Every field is
#: individually bounded, so the largest record the table below can admit is
#: around 1.6 KB; this cap is therefore unreachable in normal operation and is
#: meant to stay that way. It exists so that a field added later with a careless
#: check still cannot turn a manifest row into a payload slot, and the tests
#: assert the gap rather than the cap.
MAX_RECORD_BYTES = 4096

#: ``obj_`` plus a SHA-256 digest, and nothing else. ``\Z`` rather than ``$``:
#: Python's ``$`` also matches before a trailing newline, and a validator looser
#: than the schema it mirrors is the bug this lane has already had to fix once.
_OBJECT_ID_RE = re.compile(r"^obj_[0-9a-f]{64}\Z")


class MetadataStoreError(RuntimeError):
    """Base class for metadata store failures."""


class MetadataStoreUnavailable(MetadataStoreError):
    """The index cannot be reached, or says it is not healthy.

    Raised rather than returned so that it cannot be mistaken for "no records".
    An empty list and an unreachable service are the same shape and opposite
    facts, and treating the second as the first is how a rebuild deletes
    everything it could not see.
    """


# --- the record contract -----------------------------------------------------


def _check_const(expected, *, field):
    """An exact constant, with ``True`` refused where ``1`` is meant.

    ``isinstance(True, int)`` is True in Python, so ``version: true`` compared
    equal to ``version: 1`` and walked through - while every JSON Schema
    validator refuses it. The type is compared before the value for that reason.
    """
    def check(value, *, field=field):
        if isinstance(value, bool) != isinstance(expected, bool) or value != expected:
            raise ValueError(
                f"{field} must be exactly {expected!r}, got {value!r}; it is a "
                "constant this record emits, never something a caller asserts")
    return check


def _check_authority_flags(value, *, field):
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a mapping, got {type(value).__name__}")
    if set(value) != set(AUTHORITY_FLAGS):
        raise ValueError(
            f"{field} must name exactly the eight authorities "
            f"{list(AUTHORITY_FLAGS)}; they are denied by name rather than by "
            "omission so that a later document cannot acquire one by adding a key")
    for flag, held in value.items():
        if held is not False:
            raise ValueError(
                f"{field}.{flag} is {held!r}; a storage record is evidence "
                "about an object, never authority over one")


def _check_object_id(value, *, field="object_id"):
    if not isinstance(value, str) or not _OBJECT_ID_RE.match(value):
        raise ValueError(
            f"{field} must be 'obj_' followed by a lower-case SHA-256 digest; "
            "identity in this mesh is the content and only the content, which "
            "is also why no name, path or key can be written into it (Spec S7)")
    return value


def _check_sha256(value, *, field):
    if not isinstance(value, str) or not _manifest._SHA256_RE.match(value):
        raise ValueError(f"{field} must be a lower-case SHA-256 digest")


def _check_bool(value, *, field):
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a boolean, got {type(value).__name__}")


def _check_size_bytes(value, *, field):
    _manifest._check_bounded_int(value, 0, _manifest._MAX_SIZE_BYTES, field=field)


def _check_mime_type(value, *, field):
    if not isinstance(value, str) or not _manifest._MIME_RE.match(value):
        raise ValueError(
            f"{field} must be a type/subtype pair with no RFC 2045 parameters; "
            "'name=' and 'filename=' are exactly the private text Spec S7 keeps "
            "out of object naming")


def _check_backend_id(value, *, field):
    _manifest._check_backend(value, role=field)


def _check_replica_backends(value, *, field):
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ValueError(
            f"{field} must be a sequence of backend ids; a string is iterated "
            "one character at a time, which is a different and much stranger "
            "record than the one that was meant")
    if len(value) > _manifest._MAX_REPLICAS:
        raise ValueError(
            f"{field} holds {len(value)} entries, over the "
            f"{_manifest._MAX_REPLICAS} the schema allows: an object needing "
            "more independent copies than that is a policy question, not a "
            "manifest question (Spec S9/S27)")
    if len(set(value)) != len(value):
        raise ValueError(
            f"{field} repeats a backend; a second copy on the same provider is "
            "not an independent replica (Spec S8)")
    for backend in value:
        _manifest._check_backend(backend, role=f"{field}[]")


def _check_enum_factory(allowed):
    def check(value, *, field):
        _manifest._check_enum(value, allowed, field=field)
    return check


def _nested_factory(allowed, required, checks):
    def check(value, *, field):
        admitted = _manifest._closed_mapping(
            value, allowed, field=field, required=required)
        for key, nested in admitted.items():
            checks[key](nested, field=f"{field}.{key}")
    return check


_PROVENANCE_CHECKS = {
    "origin_class": _manifest._check_classifier,
    "producer_id": _manifest._check_classifier,
    "evidence_ref": _manifest._check_evidence_ref,
}

_VERIFICATION_CHECKS = {
    "hash_verified": _check_bool,
    "verified_replica_count": lambda value, *, field: _manifest._check_bounded_int(
        value, 0, 9, field=field),
    "last_probe_at": _manifest._check_timestamp,
    "evidence_ref": _manifest._check_evidence_ref,
}

#: One bounded validator per property of the checked-in manifest schema. A
#: table rather than a run of ``if`` statements so that completeness is
#: *checkable*: the tests walk the schema's property set and assert every one of
#: them has an entry here, and that nothing here is absent from the schema. A
#: field admitted by name and validated by nothing is the exact hole this lane
#: has now had twice.
_RECORD_FIELD_CHECKS = {
    "version": _check_const(MANIFEST_VERSION, field="version"),
    "authority": _check_const(False, field="authority"),
    "authority_flags": _check_authority_flags,
    "object_id": _check_object_id,
    "content_sha256": _check_sha256,
    "size_bytes": _check_size_bytes,
    "privacy_class": _check_enum_factory(PRIVACY_CLASSES),
    "criticality": _check_enum_factory(CRITICALITY_CLASSES),
    "storage_tier": _check_enum_factory(STORAGE_TIERS),
    "lifecycle_state": _check_enum_factory(LIFECYCLE_STATES),
    "encryption_state": _check_enum_factory(_manifest.ENCRYPTION_STATES),
    "encryption_scheme_version": lambda value, *, field: (
        _manifest._check_bounded_int(value, 1, 4096, field=field)),
    "encryption": _nested_factory(
        _manifest._ENCRYPTION_FIELDS,
        ("algorithm", "scheme_version", "key_ref"),
        _manifest._ENCRYPTION_FIELD_CHECKS),
    "primary_backend": _check_backend_id,
    "replica_backends": _check_replica_backends,
    "created_at": _manifest._check_timestamp,
    "last_accessed_at": _manifest._check_timestamp,
    "last_verified_at": _manifest._check_timestamp,
    "object_class": _manifest._check_classifier,
    "retention_class": _manifest._check_classifier,
    "mime_type": _check_mime_type,
    "source_provenance": _nested_factory(
        _manifest._PROVENANCE_FIELDS, ("origin_class",), _PROVENANCE_CHECKS),
    "verification": _nested_factory(
        _manifest._VERIFICATION_FIELDS, (), _VERIFICATION_CHECKS),
    "reproducible": _check_bool,
}

#: Exported so a caller - and the tests - can see the closed field set without
#: reaching into a private table.
RECORD_FIELDS = tuple(_RECORD_FIELD_CHECKS)

REQUIRED_RECORD_FIELDS = (
    "version", "authority", "authority_flags", "object_id", "content_sha256",
    "size_bytes", "privacy_class", "criticality", "storage_tier",
    "encryption_state", "primary_backend", "replica_backends", "created_at",
    "lifecycle_state", "reproducible",
)


def _check_cross_field_rules(record):
    """The invariants no single field can state on its own.

    Restated here rather than delegated to ``StorageObject`` because a record
    arriving at the index has no bytes behind it: it may have come from a
    provider scan during a rebuild, and ``StorageObject`` quite correctly
    refuses to be built from anything but content.
    """
    if record["object_id"] != f"{_manifest.OBJECT_ID_PREFIX}{record['content_sha256']}":
        raise ValueError(
            "object_id must be the content digest and nothing else, so that "
            "re-tiering and rebalancing cannot change what an object is")

    if record["criticality"] == "REPRODUCIBLE" and not record["reproducible"]:
        raise ValueError(
            "criticality REPRODUCIBLE with reproducible=False is a "
            "contradiction: Spec S8 permits eviction precisely because the "
            "object can be regenerated")

    encryption = record.get("encryption")
    if record["encryption_state"] == "NONE":
        if encryption is not None:
            raise ValueError(
                "encryption_state NONE with encryption metadata says at once "
                "that the object is plaintext and that a key opens it")
        if record.get("encryption_scheme_version") is not None:
            raise ValueError(
                "encryption_state NONE carries no encryption_scheme_version")
    elif encryption is None:
        raise ValueError(
            "encryption_state CLIENT_SIDE_ENCRYPTED without encryption "
            "metadata is an unverifiable claim, and an unverifiable encryption "
            "claim is how a plaintext object comes to be treated as ciphertext")
    elif (record.get("encryption_scheme_version") is not None
            and record["encryption_scheme_version"] != encryption["scheme_version"]):
        raise ValueError(
            "encryption_scheme_version contradicts encryption.scheme_version")

    backends = [record["primary_backend"], *record["replica_backends"]]
    external = sorted({b for b in backends if not _manifest._is_local(b)})
    if record["privacy_class"] == "LOCAL_ONLY" and external:
        raise ValueError(
            f"privacy class LOCAL_ONLY may not name external backend(s) "
            f"{external}; it never leaves owned storage (Spec S4), and an index "
            "row saying otherwise is the record that authorises the upload")
    if record["privacy_class"] == "CONFIDENTIAL" and external and (
            record["encryption_state"] != "CLIENT_SIDE_ENCRYPTED"
            or encryption is None):
        raise ValueError(
            "a CONFIDENTIAL object reaches an external backend only as "
            "ciphertext, and only with the encryption metadata that proves it "
            "(Spec S4/S21)")

    if record["storage_tier"] in mesh_validator.NON_BULK_TIERS and (
            record["size_bytes"] > mesh_validator.BULK_OBJECT_THRESHOLD_BYTES):
        raise ValueError(
            f"storage tier {record['storage_tier']} carries pointers, not "
            f"payloads: {record['size_bytes']} bytes exceeds "
            f"{mesh_validator.BULK_OBJECT_THRESHOLD_BYTES} (Spec S6)")
    if "supabase" in backends and record["storage_tier"] != "METADATA":
        raise ValueError(
            "supabase is a metadata and index backend only; naming it forces "
            "the METADATA tier (Spec S18/S25)")


def validate_metadata_record(record):
    """Admit a manifest record, or refuse it. There is no third answer.

    Returns a freshly-built dict: the store never holds the caller's handle and
    the caller never holds the store's, because a record that can be edited
    after it was checked was not really checked.
    """
    if not isinstance(record, Mapping):
        raise ValueError(
            "a metadata record must be a mapping, got "
            f"{type(record).__name__}")

    unknown = sorted(set(record) - set(_RECORD_FIELD_CHECKS))
    if unknown:
        raise ValueError(
            f"metadata record rejects unknown field(s) {unknown}: the field set "
            "is closed, so 'api_key', 'plaintext_key' and the name nobody has "
            "thought of yet are all refused by the same line rather than by a "
            "denylist that the next one walks past")

    missing = sorted(set(REQUIRED_RECORD_FIELDS) - set(record))
    if missing:
        raise ValueError(
            f"metadata record is missing required field(s) {missing}; an "
            "omitted field is refused rather than defaulted, because every "
            "default here would be a guess about privacy, cost or integrity")

    for field, value in record.items():
        if value is None:
            raise ValueError(
                f"{field} is null; an optional field is omitted rather than "
                "emitted as null, because a null is a document the schema "
                "refuses and a value the next reader has to guess about")
        _RECORD_FIELD_CHECKS[field](value, field=field)

    _check_cross_field_rules(record)

    admitted = {}
    for field in RECORD_FIELDS:
        if field not in record:
            continue
        value = record[field]
        if field == "authority_flags":
            admitted[field] = {flag: False for flag in AUTHORITY_FLAGS}
        elif field == "replica_backends":
            admitted[field] = list(value)
        elif isinstance(value, Mapping):
            admitted[field] = dict(value)
        else:
            admitted[field] = value

    encoded = json.dumps(admitted, sort_keys=True)
    if len(encoded) > MAX_RECORD_BYTES:
        raise ValueError(
            f"metadata record is {len(encoded)} bytes, over the "
            f"{MAX_RECORD_BYTES}-byte bound. Every field is individually "
            "bounded, so this is not reachable by a well-formed record: it "
            "means a field has grown a way to hold bulk")
    return admitted


# --- the store boundary -------------------------------------------------------


class MetadataStore(abc.ABC):
    """The mesh's index, as an abstract boundary.

    Subclasses implement four private hooks and nothing else. The public
    methods do the validating, the health gating and the copying, so that no
    adapter can accidentally be the loose one.
    """

    #: An index is not an authority (Spec S18).
    AUTHORITY = False

    # -- hooks ---------------------------------------------------------------

    @abc.abstractmethod
    def _probe_healthy(self):
        """Answer whether the store is reachable and accepting work."""

    @abc.abstractmethod
    def _put_record(self, object_id, record):
        """Persist an already-validated record."""

    @abc.abstractmethod
    def _get_record(self, object_id):
        """Return the stored row for ``object_id``, or None."""

    @abc.abstractmethod
    def _all_records(self):
        """Return every stored row, in any order."""

    # -- public boundary ------------------------------------------------------

    def healthy(self):
        """``True`` only when the store said so, in those words.

        Every other outcome is ``False``: a probe that returned ``1``, ``"yes"``
        or ``None``, and a probe that raised anything at all. The breadth of the
        except clause is deliberate - this is an I/O boundary, an escape from it
        means "unknown", and unknown fails closed. A health check that can
        propagate an exception is a health check whose caller has to remember to
        handle one, and the caller here is a destructive-action gate.
        """
        try:
            answer = self._probe_healthy()
        except BaseException:  # noqa: BLE001 - unknown fails closed, see above
            return False
        return answer is True

    def put_manifest(self, manifest):
        """Validate a record and persist it. Returns None."""
        record = validate_metadata_record(manifest)
        if not self.healthy():
            raise MetadataStoreUnavailable(
                "the metadata store is not healthy; a write into an index that "
                "cannot confirm it accepted the write is a manifest entry "
                "nobody can rely on (Spec S18)")
        self._put_record(record["object_id"], record)
        return None

    def get_manifest(self, object_id):
        """Return the record for ``object_id``, or None if there is none.

        ``None`` means "no such object". It never means "could not reach the
        index" - that raises, because the two are the same shape and opposite
        facts.
        """
        key = _check_object_id(object_id)
        if not self.healthy():
            raise MetadataStoreUnavailable(
                "the metadata store is not healthy; absence cannot be "
                "distinguished from unreachability, so no answer is given")
        raw = self._get_record(key)
        if raw is None:
            return None
        return validate_metadata_record(raw)

    def list_manifests(self):
        """Every record, validated, ordered by ``object_id``.

        A malformed row raises rather than being skipped. Skipping is the
        dangerous option: a rebuild that silently omits what it could not parse
        is a rebuild that reports fewer replicas than exist and then repairs,
        deletes or migrates on that basis.
        """
        if not self.healthy():
            raise MetadataStoreUnavailable(
                "the metadata store is not healthy; an empty list and an "
                "unreachable index are the same shape and opposite facts")
        records = [validate_metadata_record(raw) for raw in self._all_records()]
        return sorted(records, key=lambda record: record["object_id"])


def can_perform_destructive_lifecycle(store):
    """May a destructive lifecycle action proceed against this index?

    ``policy.yaml``: ``destructive_action_on_uncertain_evidence: FAIL_CLOSED``
    and ``metadata_service.on_unavailable.new_destructive_lifecycle_actions:
    BLOCKED``. Spec S18 spells out what "destructive" covers - deletion,
    rebalance, replica replacement, expiry - and none of it may proceed while
    the record of what exists is uncertain.

    ``True`` requires two independent facts: the argument really is a
    ``MetadataStore``, and that store really answered ``True``. The isinstance
    check is not ceremony. An object that answers ``healthy() -> True`` has
    asserted nothing; it has not been through the validation that makes the
    answer mean anything, and accepting it would make the gate satisfiable by
    any two-line stub that happened to be passed in by mistake.

    This function grants no authority and performs no action. It answers a
    question; the caller with the authority decides what to do with it.
    """
    if not isinstance(store, MetadataStore):
        return False
    return store.healthy() is True


__all__ = [
    "AUTHORITY", "AUTHORITY_FLAGS", "CANONICAL_AUTHORITY",
    "ENCRYPTION_IMPLEMENTED_HERE", "MANIFEST_VERSION", "MAX_RECORD_BYTES",
    "RECORD_FIELDS", "REQUIRED_RECORD_FIELDS", "MetadataStore",
    "MetadataStoreError", "MetadataStoreUnavailable",
    "validate_metadata_record", "can_perform_destructive_lifecycle",
]
