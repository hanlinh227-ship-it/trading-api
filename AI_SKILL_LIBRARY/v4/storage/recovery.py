"""Federated Free Storage Mesh - the bounded GitHub recovery snapshot.

Spec S18 refuses to let the metadata service become a single point of failure,
and names what GitHub keeps instead: the storage policy, the provider registry,
a **bounded** manifest snapshot or pointer set, the schema version, the known
critical-object index, and the last successful export reference. Spec S23 says a
full mesh rebuild must be possible from those plus provider-side object metadata
and content hashes. This module is both halves: ``export_recovery_snapshot``
writes the pointer set, ``rebuild_manifest`` reconstructs records from it.

It reads a metadata store and returns dicts. It contacts no provider, opens no
connection, touches no credential, writes no file and performs no cryptography.

**"Bounded" is the whole design, and it is bounded in several directions.**

``MAX_SNAPSHOT_ENTRIES`` caps how many objects are indexed, ``MAX_SNAPSHOT_BYTES``
caps the serialised document, and ``MAX_SNAPSHOT_STRING`` caps every individual
string inside it. The third is the one that stops a credential. A snapshot can
satisfy both of the first two and still carry two kilobytes of secret in one
allowed field, and a check like ``assert "api_key" not in blob`` would not
notice: that is a substring test on field *names*, and the field a secret
arrives in is never called ``api_key``.

But a per-string cap bounds one string, not a thousand of them.
``manifest_schema_version`` was an allowed field with no validator of any kind,
and 177 KB of attacker-chosen keys and values fitted inside it with every
individual string under 256 characters and the entry cap simply routed around
by not using an entry. So there are two more bounds -
``MAX_SNAPSHOT_FIELD_BYTES`` on any one non-entry field and
``MAX_SNAPSHOT_DEPTH`` on nesting - and, more importantly, the thing that would
have caught it in the first place: **every field is validated through a
declared table**. ``SNAPSHOT_VALUE_CHECKS``, ``ENTRY_VALUE_CHECKS`` and
``PROVIDER_RECORD_VALUE_CHECKS`` map every admitted field to a bounded check,
the field tuples are derived from those tables, and the validators dispatch
through them instead of restating them as a run of ``if``. A field admitted by
name and validated by nothing is the hole this project has now had four times.

**The snapshot is a projection, not a copy.** An entry may carry only the
fields in ``ENTRY_FIELDS``. Everything else in a manifest record is dropped
whatever it holds - ``source_provenance``, ``verification``, ``last_accessed_at``
and the classifiers are simply not in the output, and neither are ``nonce`` and
``tag``, the two encryption fields that sit closest to key material. A field
added to the manifest schema tomorrow does not reach GitHub by default; it
reaches GitHub when somebody adds it to this list on purpose. A denylist would
have the opposite default.

``key_ref`` *is* kept, and that is a deliberate, narrow exception. Spec S23
lists "encryption key references from the authorized secret system" among the
inputs to a rebuild, and without ``key_ref`` an encrypted object cannot be
reconstructed as a valid record at all. What is kept is a reference of the form
``env://NAME`` - a pointer at the secret store, bounded and validated on the way
back in. Key *material* has no field here, in the snapshot or in the manifest.

**The rebuild does not fabricate.** An object is admitted only when a
provider-side hash *and* size match the pointer. Privacy is re-checked, so a
LOCAL_ONLY object observed on an external provider is reported as a loss rather
than written down as a legitimate placement. The old ``verification`` block is
not carried forward - it predates the loss that forced the rebuild, and
re-asserting it would be manufacturing evidence. Objects that cannot be
verified are listed by id (Spec S23 step 9, "mark unrecoverable objects
explicitly") rather than quietly omitted: a rebuild that silently drops what it
could not see is a rebuild that then repairs, migrates or deletes on the basis
of a smaller world than the real one.
"""

from __future__ import annotations

import datetime as _datetime
import json
import re
from collections.abc import Mapping, Sequence

from AI_SKILL_LIBRARY.v4.storage import (
    AUTHORITY_FLAGS,
    CANONICAL_AUTHORITY,
    CRITICALITY_CLASSES,
    LIFECYCLE_STATES,
    OBJECT_MANIFEST_SCHEMA_PATH,
    PORTABLE_STATE_CONTRACT,
    POLICY_PATH,
    PRIVACY_CLASSES,
    PROVIDER_SCHEMA_PATH,
    PROVIDERS_PATH,
    STORAGE_TIERS,
)
from AI_SKILL_LIBRARY.v4.storage import manifest as _manifest
from AI_SKILL_LIBRARY.v4.storage import metadata as _metadata

AUTHORITY = False
ENCRYPTION_IMPLEMENTED_HERE = False

SNAPSHOT_VERSION = 1

#: Where the checked-in snapshot lives, relative to the repository root.
RECOVERY_MANIFEST_PATH = "AI_SKILL_LIBRARY/v4/storage/recovery_manifest.json"

#: How many objects the snapshot indexes.
#:
#: 256, because the snapshot is a *pointer set* that GitHub carries and a human
#: reviews. An entry is roughly 600 bytes, so 256 entries plus the critical
#: index is about 170 KB: a file that still opens in a PR diff, still parses on
#: every bootstrap, and is nowhere near the size at which a repository starts
#: being used as bulk storage - which Spec S6 and Spec S32 both forbid. The cap
#: is not a guess about how many objects the mesh will hold; it is a statement
#: that beyond this, the recovery path is "restore the metadata store", not
#: "read a bigger file out of Git".
MAX_SNAPSHOT_ENTRIES = 256

#: 256 KiB for the serialised document, checked after the entry cap rather than
#: instead of it, because a bound nobody measures is a bound nobody has.
MAX_SNAPSHOT_BYTES = 262144

#: And the bound that matters: no single string in a snapshot may exceed 256
#: characters. The longest legitimate value is a 68-character object id. A
#: credential does not need a field named after it - it needs an unbounded one.
MAX_SNAPSHOT_STRING = 256

#: A pointer is a repository-relative path under ``AI_SKILL_LIBRARY/`` and
#: nothing else - not a URL, not an absolute path, not a traversal. A rebuild
#: reads what these name, so the field is a redirect if it is left open.
_POINTER_RE = re.compile(
    r"^AI_SKILL_LIBRARY/[A-Za-z0-9][A-Za-z0-9._/-]{2,120}\.(?:yaml|yml|json)\Z")

#: Spec S18/S25 and ``policy.yaml`` ``metadata_service``, restated in the
#: checkpoint so that a rebuild reading only this file still learns that the
#: index is not canonical and that no project has been verified to exist.
#:
#: ``last_successful_export_ref`` is the Spec S18 obligation and is a parameter
#: of ``export_recovery_snapshot``, not a constant: a field hard-coded ``None``
#: with no way to set it is that obligation structurally unimplementable. The
#: default stays ``None`` because this repository has no export evidence to
#: point at, and a reference nobody can produce is not one to invent.
_METADATA_SERVICE = {
    "provider_id": "supabase",
    "role": "metadata_and_object_index_only",
    "authority": False,
    "project_exists_verified": False,
    "last_successful_export_ref": None,
}

_POINTERS = {
    "storage_policy": POLICY_PATH,
    "provider_registry": PROVIDERS_PATH,
    "object_manifest_schema": OBJECT_MANIFEST_SCHEMA_PATH,
    "provider_schema": PROVIDER_SCHEMA_PATH,
    "portable_state_contract": PORTABLE_STATE_CONTRACT,
}

#: Of the six encryption metadata fields a manifest may carry, three reach
#: GitHub: what construction was used, which scheme version, and where the key
#: is kept. ``nonce`` and ``tag`` are per-object ciphertext parameters that live
#: with the ciphertext and are not needed to identify or re-place an object, and
#: ``key_rotation_generation`` is not either. Fewer fields in a checkpoint is
#: strictly better (Spec S22 keeps checkpoints out of the key business).
SNAPSHOT_ENCRYPTION_FIELDS = ("algorithm", "scheme_version", "key_ref")

#: A bound on any one snapshot field that is not the entry list.
#:
#: The per-string cap bounds one string; it does not bound a thousand of them.
#: ``manifest_schema_version`` was an allowed field with no validator at all,
#: and 177 KB of attacker-chosen keys and values fitted in it while every
#: individual string stayed under 256 characters and ``MAX_SNAPSHOT_ENTRIES``
#: was simply routed around by not using an entry. Every field now has a
#: declared check, which is the real fix; this is the bound that holds if a
#: field is added tomorrow with a careless one. The largest legitimate non-entry
#: field is a few hundred bytes.
MAX_SNAPSHOT_FIELD_BYTES = 4096

#: And the same for one entry, whose legitimate size is around 600 bytes.
MAX_SNAPSHOT_ENTRY_BYTES = 2048

#: Nesting is bounded too. The deepest legitimate path in a snapshot is
#: ``entries[i].encryption.algorithm`` - four levels. A document that nests
#: forty deep is not a pointer set, and depth is the other way bulk arrives
#: without any single string being long.
MAX_SNAPSHOT_DEPTH = 8

#: Fields bounded by their own element counts rather than by a byte budget:
#: the entry list is capped at ``MAX_SNAPSHOT_ENTRIES`` entries of
#: ``MAX_SNAPSHOT_ENTRY_BYTES`` each, and the critical-object index at
#: ``MAX_SNAPSHOT_ENTRIES`` object ids of a fixed 68 characters.
_ELEMENT_BOUNDED_FIELDS = ("entries", "critical_object_index")


# --- declared value checks ----------------------------------------------------
#
# Three tables, one per document shape, each mapping a field name to a bounded
# validator - and the validators below *dispatch* through them rather than
# restating them as a run of ``if``.
#
# This is not style. ``manifest_schema_version`` was in ``SNAPSHOT_FIELDS``,
# emitted by the exporter and present in the checked-in snapshot, and the
# cleanliness gate validated the other thirteen top-level fields and skipped it
# - so it accepted a credential-shaped string, 177 KB of arbitrary content, and
# a schema version the rebuild does not speak. Nothing could have caught that
# except a reviewer reading a hundred lines of ``if`` and noticing an absence.
# A table makes completeness *checkable*: ``SNAPSHOT_FIELDS`` is derived from
# the table, so a field with no check cannot be an allowed field, and the tests
# assert the entry projection is a subset of the manifest schema's properties.
# ``capacity.PROVIDER_VALUE_CHECKS`` and ``placement.MANIFEST_VALUE_CHECKS``
# are the same pattern; this is the fourth occurrence of the class of bug that
# happens when a module skips it.


def _bounded_int(low, high):
    def check(value, *, field):
        _manifest._check_bounded_int(value, low, high, field=field)
    return check


def _enum(allowed):
    def check(value, *, field):
        _manifest._check_enum(value, allowed, field=field)
    return check


def _check_snapshot_authority(value, *, field):
    if value is not False:
        raise ValueError(
            f"{field}: a recovery snapshot is evidence about objects, never "
            "authority over them")


def _check_canonical_authority(value, *, field):
    if value != CANONICAL_AUTHORITY:
        raise ValueError(
            f"{field} must remain {CANONICAL_AUTHORITY}; the metadata service "
            "is an index and GitHub stays canonical (Spec S18)")


def _check_metadata_service(value, *, field):
    if not isinstance(value, Mapping) or set(value) != set(_METADATA_SERVICE):
        raise ValueError(
            f"{field} must name exactly {sorted(_METADATA_SERVICE)}")
    if value["authority"] is not False or value["role"] != _METADATA_SERVICE["role"]:
        raise ValueError(
            f"{field} must remain a non-authoritative index; a checkpoint that "
            "says otherwise is a checkpoint that promotes Supabase to canonical "
            "by being read (Spec S18/S32)")
    if value["provider_id"] != _METADATA_SERVICE["provider_id"]:
        raise ValueError(
            f"{field}.provider_id must remain "
            f"{_METADATA_SERVICE['provider_id']!r}")
    if value["project_exists_verified"] is not False:
        raise ValueError(
            "project_exists_verified may only be asserted from runtime "
            "evidence, and there is none: Spec S25 records that the connected "
            "account has no projects")
    reference = value["last_successful_export_ref"]
    if reference is not None:
        _manifest._check_evidence_ref(
            reference, field=f"{field}.last_successful_export_ref")


def _check_pointers(value, *, field):
    if not isinstance(value, Mapping) or set(value) != set(_POINTERS):
        raise ValueError(f"{field} must name exactly {sorted(_POINTERS)}")
    for name, path in value.items():
        if not isinstance(path, str) or not _POINTER_RE.match(path):
            raise ValueError(
                f"{field}.{name} must be a repository-relative path under "
                "AI_SKILL_LIBRARY/; GitHub is where the canonical documents "
                "are, and a pointer that can be an arbitrary URL is a pointer "
                "that can send a rebuild somewhere else")


def _check_caps(value, *, field):
    if value != {"max_entries": MAX_SNAPSHOT_ENTRIES,
                 "max_bytes": MAX_SNAPSHOT_BYTES,
                 "max_string": MAX_SNAPSHOT_STRING}:
        raise ValueError(
            f"{field} must state this module's actual bounds; a snapshot "
            "carrying looser numbers than the code enforces documents a "
            "permission nobody granted")


def _check_bool(value, *, field):
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a boolean")


def _check_critical_object_index(value, *, field):
    """A sorted, duplicate-free list of object ids - checked in that order.

    Every member is required to be an object id *before* anything sorts or
    hashes it. ``index != sorted(set(index))`` raises ``TypeError`` on
    ``[[1, 2]]`` and on a list mixing ints with strings, and the contract here
    is ``ValueError``: a caller wrapping a recovery read in ``except
    ValueError`` should not be taken out by an exception it was never told to
    expect.
    """
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    if len(value) > MAX_SNAPSHOT_ENTRIES:
        raise ValueError(
            f"{field} holds {len(value)} ids, over the {MAX_SNAPSHOT_ENTRIES} "
            "a snapshot indexes")
    for position, member in enumerate(value):
        _metadata._check_object_id(member, field=f"{field}[{position}]")
    if value != sorted(set(value)):
        raise ValueError(f"{field} must be a sorted, duplicate-free list")


def _check_entries(value, *, field):
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    if len(value) > MAX_SNAPSHOT_ENTRIES:
        raise ValueError(
            f"recovery snapshot holds {len(value)} entries, over the "
            f"{MAX_SNAPSHOT_ENTRIES} cap")
    for position, entry in enumerate(value):
        _check_entry(entry, where=f"{field}[{position}]")


def _check_entry_encryption(value, *, field):
    admitted = _manifest._closed_mapping(
        value, SNAPSHOT_ENCRYPTION_FIELDS, field=field,
        required=SNAPSHOT_ENCRYPTION_FIELDS)
    for key, nested in admitted.items():
        _manifest._ENCRYPTION_FIELD_CHECKS[key](nested, field=f"{field}.{key}")


def _check_replica_backends(value, *, field):
    if isinstance(value, str) or not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    if len(value) > _manifest._MAX_REPLICAS:
        raise ValueError(f"{field} is over the {_manifest._MAX_REPLICAS} bound")
    for backend in value:
        _manifest._check_backend(backend, role=f"{field}[]")
    if len(set(value)) != len(value):
        raise ValueError(f"{field} names a backend twice")


def _check_backend(value, *, field):
    _manifest._check_backend(value, role=field)


#: One bounded validator per field of a snapshot entry. The set is asserted
#: equal to ``ENTRY_FIELDS`` and a subset of the manifest schema's properties:
#: the entry is a *projection* of a manifest record, so a name here that the
#: schema does not have is a field being invented on the way to GitHub.
ENTRY_VALUE_CHECKS = {
    "object_id": _metadata._check_object_id,
    "content_sha256": _metadata._check_sha256,
    "size_bytes": _bounded_int(0, _manifest._MAX_SIZE_BYTES),
    "privacy_class": _enum(PRIVACY_CLASSES),
    "criticality": _enum(CRITICALITY_CLASSES),
    "storage_tier": _enum(STORAGE_TIERS),
    "encryption_state": _enum(_manifest.ENCRYPTION_STATES),
    "encryption": _check_entry_encryption,
    "primary_backend": _check_backend,
    "replica_backends": _check_replica_backends,
    "created_at": _manifest._check_timestamp,
    "lifecycle_state": _enum(LIFECYCLE_STATES),
    "reproducible": _check_bool,
}

#: The projection. An entry carries these fields and no others, and the list is
#: derived from the check table so that the two cannot drift apart.
ENTRY_FIELDS = tuple(ENTRY_VALUE_CHECKS)

REQUIRED_ENTRY_FIELDS = tuple(f for f in ENTRY_FIELDS if f != "encryption")

#: What a provider scan can actually observe about an object: which backend
#: holds it, what it claims to be, how big it is, and when it was seen. Closed,
#: because an undeclared field is the only way an unbounded string reaches a
#: recovery input at all.
PROVIDER_RECORD_VALUE_CHECKS = {
    "backend_id": _check_backend,
    "object_id": _metadata._check_object_id,
    "content_sha256": _metadata._check_sha256,
    "size_bytes": _bounded_int(0, _manifest._MAX_SIZE_BYTES),
    "observed_at": _manifest._check_timestamp,
}

PROVIDER_RECORD_FIELDS = tuple(PROVIDER_RECORD_VALUE_CHECKS)
REQUIRED_PROVIDER_RECORD_FIELDS = (
    "backend_id", "object_id", "content_sha256", "size_bytes",
)

#: One bounded validator per top-level snapshot field, including the one that
#: had none.
SNAPSHOT_VALUE_CHECKS = {
    "version": _metadata._check_const(SNAPSHOT_VERSION, field="version"),
    # Validated, not merely carried. It is the one field telling a rebuild
    # which schema the entries were written against, and nothing read it,
    # compared it to MANIFEST_VERSION or bounded it: a snapshot could claim
    # version 99 and produce rebuilt records claiming version 1.
    "manifest_schema_version": _metadata._check_const(
        _metadata.MANIFEST_VERSION, field="manifest_schema_version"),
    "generated_at": _manifest._check_timestamp,
    "canonical_authority": _check_canonical_authority,
    "authority": _check_snapshot_authority,
    "authority_flags": _metadata._check_authority_flags,
    "metadata_service": _check_metadata_service,
    "pointers": _check_pointers,
    "caps": _check_caps,
    "entry_count": _bounded_int(0, 2 ** 31 - 1),
    "truncated": _check_bool,
    "omitted_entries": _bounded_int(0, 2 ** 31 - 1),
    "critical_object_index": _check_critical_object_index,
    "entries": _check_entries,
}

SNAPSHOT_FIELDS = tuple(SNAPSHOT_VALUE_CHECKS)

#: Which objects survive truncation. Spec S18 requires the *critical-object
#: index* to be among what GitHub keeps, so CRITICAL is kept first and the cap
#: is a hard error rather than a silent drop if criticals alone exceed it.
_CRITICALITY_RANK = {name: rank for rank, name in enumerate(
    ("CRITICAL", "IMPORTANT", "REPRODUCIBLE", "EPHEMERAL"))}


# --- cleanliness --------------------------------------------------------------


def _walk_values(value, *, where, depth=0):
    """Bound and scan every string in the document, keys included.

    Keys as well as values, because a hand-edited or machine-merged snapshot can
    grow a key as easily as a value, and a 2KB key is exactly as much storage as
    a 2KB value. Depth as well as length, because nesting is the other way a
    document grows without any single string being long.
    """
    if depth > MAX_SNAPSHOT_DEPTH:
        raise ValueError(
            f"{where} nests deeper than {MAX_SNAPSHOT_DEPTH}; the deepest "
            "legitimate path in a snapshot is four levels, and a pointer set "
            "that nests further is carrying something rather than pointing "
            "at it")
    if isinstance(value, str):
        if len(value) > MAX_SNAPSHOT_STRING:
            raise ValueError(
                f"{where} is {len(value)} characters, over the "
                f"{MAX_SNAPSHOT_STRING}-character bound. The longest legitimate "
                "value in a snapshot is a 68-character object id; a field with "
                "room for two kilobytes is a field a credential fits in, "
                "whatever it is named")
        _manifest.assert_no_credential_material(value, where=where)
        return
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, int):
        return
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{where}: keys must be strings")
            _walk_values(key, where=f"{where}.<key>", depth=depth + 1)
            _walk_values(nested, where=f"{where}.{key}", depth=depth + 1)
        return
    if isinstance(value, list):
        for index, nested in enumerate(value):
            _walk_values(nested, where=f"{where}[{index}]", depth=depth + 1)
        return
    raise ValueError(
        f"{where} holds {type(value).__name__}; a recovery snapshot carries "
        "strings, integers, booleans, nulls, lists and mappings - a float is "
        "not round-trippable and anything else is not a pointer")


def _check_serialised_size(value, *, field, limit):
    """A byte budget for one field, measured rather than assumed."""
    try:
        encoded = json.dumps(value, sort_keys=True)
    except (TypeError, ValueError):
        raise ValueError(f"{field} is not JSON-serialisable") from None
    if len(encoded) > limit:
        raise ValueError(
            f"{field} serialises to {len(encoded)} bytes, over its {limit}-byte "
            "budget. GitHub carries pointers, not bulk (Spec S6/S32), and a "
            "per-string bound stops one long string rather than a thousand "
            "short ones")


def _check_entry(entry, *, where):
    if not isinstance(entry, Mapping):
        raise ValueError(f"{where} must be a mapping, got {type(entry).__name__}")
    unknown = sorted(set(entry) - set(ENTRY_VALUE_CHECKS))
    if unknown:
        raise ValueError(
            f"{where} rejects field(s) {unknown}: a snapshot entry is a "
            f"projection onto {list(ENTRY_FIELDS)}, so a field nobody put on "
            "that list does not reach GitHub whatever it holds")
    missing = sorted(set(REQUIRED_ENTRY_FIELDS) - set(entry))
    if missing:
        raise ValueError(f"{where} is missing required field(s) {missing}")

    for field, value in entry.items():
        ENTRY_VALUE_CHECKS[field](value, field=f"{where}.{field}")
    _check_serialised_size(dict(entry), field=where,
                           limit=MAX_SNAPSHOT_ENTRY_BYTES)

    encryption = entry.get("encryption")
    if encryption is None:
        if entry["encryption_state"] != "NONE":
            raise ValueError(
                f"{where} claims ciphertext with no encryption metadata")
    elif entry["encryption_state"] == "NONE":
        raise ValueError(
            f"{where} says plaintext and carries encryption metadata")

    # The invariants no single field can state on its own, shared with the
    # metadata store rather than restated. Without them the public cleanliness
    # gate certified a checkpoint asserting that LOCAL_ONLY data is on
    # Cloudflare R2, and a legitimately-edited entry became "unrecoverable" -
    # reported data loss - instead of a named contradiction.
    _metadata.check_placement_cross_field_rules(entry, where=where)


def assert_snapshot_is_clean(snapshot):
    """Refuse a snapshot that is malformed, unbounded or credential-shaped.

    Run by the exporter on its own output before returning it, and by the
    rebuild on any snapshot handed to it. The second use is the important one:
    a snapshot read back from GitHub has been through a merge, a rebase, an
    editor and possibly a hand edit, and a recovery path that trusts its input
    is a recovery path that will one day rebuild from someone else's file.

    Every field is checked through ``SNAPSHOT_VALUE_CHECKS``; what is left here
    afterwards is only what no single field can answer.
    """
    if not isinstance(snapshot, Mapping):
        raise ValueError(
            f"a recovery snapshot must be a mapping, got {type(snapshot).__name__}")
    unknown = sorted(set(snapshot) - set(SNAPSHOT_VALUE_CHECKS))
    if unknown:
        raise ValueError(f"recovery snapshot rejects unknown field(s) {unknown}")
    missing = sorted(set(SNAPSHOT_FIELDS) - set(snapshot))
    if missing:
        raise ValueError(f"recovery snapshot is missing field(s) {missing}")

    for field in SNAPSHOT_FIELDS:
        value = snapshot[field]
        SNAPSHOT_VALUE_CHECKS[field](value, field=field)
        if field not in _ELEMENT_BOUNDED_FIELDS:
            _check_serialised_size(value, field=field,
                                   limit=MAX_SNAPSHOT_FIELD_BYTES)

    entries = snapshot["entries"]
    ids = [entry["object_id"] for entry in entries]
    if ids != sorted(ids) or len(set(ids)) != len(ids):
        raise ValueError(
            "entries must be ordered by object_id and each object named once; "
            "a snapshot that is not deterministic cannot be reviewed as a diff")

    if not set(snapshot["critical_object_index"]) <= set(ids):
        raise ValueError(
            "critical_object_index names an object the snapshot does not carry")

    if snapshot["entry_count"] - len(entries) != snapshot["omitted_entries"]:
        raise ValueError(
            "omitted_entries must equal entry_count minus the entries carried; "
            "truncation is declared, never silent")
    if snapshot["truncated"] != (snapshot["omitted_entries"] > 0):
        raise ValueError("truncated contradicts omitted_entries")

    _walk_values(snapshot, where="snapshot")
    encoded = json.dumps(snapshot, sort_keys=True)
    if len(encoded) > MAX_SNAPSHOT_BYTES:
        raise ValueError(
            f"recovery snapshot is {len(encoded)} bytes, over the "
            f"{MAX_SNAPSHOT_BYTES}-byte cap; GitHub carries pointers, not bulk "
            "(Spec S6/S32)")
    return snapshot


# --- export -------------------------------------------------------------------


def _project(record):
    """A manifest record, narrowed to what GitHub keeps."""
    entry = {}
    for field in ENTRY_FIELDS:
        if field == "encryption":
            continue
        entry[field] = (list(record[field]) if field == "replica_backends"
                        else record[field])
    encryption = record.get("encryption")
    if encryption is not None:
        entry["encryption"] = {field: encryption[field]
                               for field in SNAPSHOT_ENCRYPTION_FIELDS}
    return entry


def _now_instant():
    return _datetime.datetime.now(_datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def export_recovery_snapshot(store, *, generated_at=None,
                             last_successful_export_ref=None):
    """Render the bounded pointer set GitHub keeps (Spec S18).

    Refuses an unhealthy store rather than exporting what it managed to read:
    a partial snapshot presented as a complete one is worse than no snapshot,
    because the next rebuild treats everything missing from it as lost.

    ``last_successful_export_ref`` is the sixth thing Spec S18 lists among what
    GitHub retains. It is a parameter rather than a constant because a field
    hard-coded ``None`` with no way to set it is an obligation that cannot be
    met by any caller. It is a bounded evidence reference - a path to a
    checkpoint the export actually produced - and it stays ``None`` when the
    caller has none, because a reference nobody can produce is not one to
    invent.
    """
    if not isinstance(store, _metadata.MetadataStore):
        raise ValueError(
            "export_recovery_snapshot needs a MetadataStore; an object that "
            "merely answers list_manifests() has not been through the "
            "validation that makes its answer mean anything")

    export_ref = last_successful_export_ref
    if export_ref is not None:
        _manifest._check_evidence_ref(export_ref,
                                      field="last_successful_export_ref")

    records = store.list_manifests()
    entries = [_project(record) for record in records]
    critical = sorted(entry["object_id"] for entry in entries
                      if entry["criticality"] == "CRITICAL")
    if len(critical) > MAX_SNAPSHOT_ENTRIES:
        raise ValueError(
            f"{len(critical)} CRITICAL objects exceed the "
            f"{MAX_SNAPSHOT_ENTRIES}-entry cap. Spec S18 requires the "
            "critical-object index to be among what GitHub keeps, so this fails "
            "closed rather than dropping criticals or growing the file: the "
            "answer is compaction or a restored metadata store, not a bigger "
            "checkpoint")

    ordered = sorted(entries, key=lambda entry: (
        _CRITICALITY_RANK[entry["criticality"]], entry["object_id"]))
    kept = sorted(ordered[:MAX_SNAPSHOT_ENTRIES],
                  key=lambda entry: entry["object_id"])
    omitted = len(entries) - len(kept)

    snapshot = {
        "version": SNAPSHOT_VERSION,
        "manifest_schema_version": _metadata.MANIFEST_VERSION,
        "generated_at": generated_at or _now_instant(),
        "canonical_authority": CANONICAL_AUTHORITY,
        "authority": False,
        "authority_flags": {flag: False for flag in AUTHORITY_FLAGS},
        "metadata_service": dict(_METADATA_SERVICE,
                                 last_successful_export_ref=export_ref),
        "pointers": dict(_POINTERS),
        "caps": {
            "max_entries": MAX_SNAPSHOT_ENTRIES,
            "max_bytes": MAX_SNAPSHOT_BYTES,
            "max_string": MAX_SNAPSHOT_STRING,
        },
        "entry_count": len(entries),
        "truncated": omitted > 0,
        "omitted_entries": omitted,
        "critical_object_index": sorted(
            entry["object_id"] for entry in kept
            if entry["criticality"] == "CRITICAL"),
        "entries": kept,
    }
    return assert_snapshot_is_clean(snapshot)


# --- rebuild ------------------------------------------------------------------


def _validate_provider_record(row):
    """One observation from a provider scan, bounded field by field."""
    if not isinstance(row, Mapping):
        raise ValueError(
            f"a provider record must be a mapping, got {type(row).__name__}")
    unknown = sorted(set(row) - set(PROVIDER_RECORD_VALUE_CHECKS))
    if unknown:
        raise ValueError(
            f"provider record rejects unknown field(s) {unknown}: the field set "
            f"is closed to {list(PROVIDER_RECORD_FIELDS)}, so an object tag, an "
            "ETag, a signed URL or a note cannot ride into the rebuild")
    missing = sorted(set(REQUIRED_PROVIDER_RECORD_FIELDS) - set(row))
    if missing:
        raise ValueError(f"provider record is missing field(s) {missing}")

    for field, value in row.items():
        PROVIDER_RECORD_VALUE_CHECKS[field](
            value, field=f"provider record {field}")
    _check_serialised_size(dict(row), field="provider record",
                           limit=MAX_SNAPSHOT_ENTRY_BYTES)
    return {field: row[field] for field in PROVIDER_RECORD_FIELDS if field in row}


def _record_from(entry, verified_backends):
    """Rebuild a manifest record from a pointer plus what providers still hold.

    The placement is taken from the observation, not from the pointer: the whole
    reason a rebuild is happening is that what the index believed may no longer
    be where the bytes are. The choice is deterministic - the recorded primary
    if a verified copy is still there, otherwise the first backend by id.
    """
    primary = (entry["primary_backend"] if entry["primary_backend"] in
               verified_backends else verified_backends[0])
    record = {
        "version": _metadata.MANIFEST_VERSION,
        "authority": False,
        "authority_flags": {flag: False for flag in AUTHORITY_FLAGS},
        "object_id": entry["object_id"],
        "content_sha256": entry["content_sha256"],
        "size_bytes": entry["size_bytes"],
        "privacy_class": entry["privacy_class"],
        "criticality": entry["criticality"],
        "storage_tier": entry["storage_tier"],
        "encryption_state": entry["encryption_state"],
        "primary_backend": primary,
        "replica_backends": [backend for backend in verified_backends
                             if backend != primary],
        "created_at": entry["created_at"],
        "lifecycle_state": entry["lifecycle_state"],
        "reproducible": entry["reproducible"],
    }
    if "encryption" in entry:
        record["encryption"] = dict(entry["encryption"])
        record["encryption_scheme_version"] = entry["encryption"]["scheme_version"]
    return record


def rebuild_report(provider_records, recovery_snapshot):
    """Reconstruct what can be reconstructed, and name what cannot.

    Returns four keys:

    ``rebuilt``
        validated manifest records, ordered by object id, ready to be written
        back into a restored metadata store.
    ``unrecoverable``
        object ids the snapshot knows about that no provider still holds, or
        whose reconstruction would violate policy (a LOCAL_ONLY object seen on
        an external backend is a loss with a story, not a placement).
    ``unverified``
        object ids some provider holds under a content hash or size that does
        not match the pointer. Not admitted: a content-addressed mesh whose
        content does not match its address has one bug, and pretending
        otherwise gives it two.
    ``unknown``
        object ids observed on providers that the snapshot has never heard of.
        Reported rather than adopted - the snapshot is the authority for what
        the mesh was managing, and a rebuild is not the moment to adopt an
        object of unknown privacy class.
    """
    snapshot = assert_snapshot_is_clean(recovery_snapshot)
    if isinstance(provider_records, (str, bytes, Mapping)) or not isinstance(
            provider_records, Sequence):
        raise ValueError(
            "provider_records must be a sequence of provider observations, got "
            f"{type(provider_records).__name__}")

    rows = [_validate_provider_record(row) for row in provider_records]
    index = {entry["object_id"]: entry for entry in snapshot["entries"]}

    seen = {}
    for row in rows:
        seen.setdefault(row["object_id"], []).append(row)

    rebuilt, unrecoverable, unverified = [], [], []
    for object_id in sorted(index):
        entry = index[object_id]
        observations = seen.get(object_id, [])
        if not observations:
            unrecoverable.append(object_id)
            continue
        verified = sorted({row["backend_id"] for row in observations
                           if row["content_sha256"] == entry["content_sha256"]
                           and row["size_bytes"] == entry["size_bytes"]})
        if not verified:
            unverified.append(object_id)
            continue
        try:
            rebuilt.append(_metadata.validate_metadata_record(
                _record_from(entry, verified)))
        except ValueError:
            # The reconstruction would be an invalid or policy-violating
            # record. It is a loss to report, never a row to write.
            unrecoverable.append(object_id)

    return {
        "rebuilt": rebuilt,
        "unrecoverable": sorted(unrecoverable),
        "unverified": sorted(unverified),
        "unknown": sorted(object_id for object_id in seen if object_id not in index),
    }


def rebuild_manifest(provider_records, recovery_snapshot):
    """The records a rebuild can prove (Spec S18/S23).

    ``rebuild_report`` is the fuller answer and is what a recovery run should
    look at; this is the manifest half of it.
    """
    return rebuild_report(provider_records, recovery_snapshot)["rebuilt"]


__all__ = [
    "AUTHORITY", "AUTHORITY_FLAGS", "CANONICAL_AUTHORITY",
    "ENCRYPTION_IMPLEMENTED_HERE", "SNAPSHOT_VERSION", "RECOVERY_MANIFEST_PATH",
    "MAX_SNAPSHOT_ENTRIES", "MAX_SNAPSHOT_BYTES", "MAX_SNAPSHOT_STRING",
    "MAX_SNAPSHOT_FIELD_BYTES", "MAX_SNAPSHOT_ENTRY_BYTES",
    "MAX_SNAPSHOT_DEPTH", "SNAPSHOT_FIELDS", "SNAPSHOT_VALUE_CHECKS",
    "ENTRY_FIELDS", "ENTRY_VALUE_CHECKS", "REQUIRED_ENTRY_FIELDS",
    "SNAPSHOT_ENCRYPTION_FIELDS", "PROVIDER_RECORD_FIELDS",
    "PROVIDER_RECORD_VALUE_CHECKS",
    "REQUIRED_PROVIDER_RECORD_FIELDS", "assert_snapshot_is_clean",
    "export_recovery_snapshot", "rebuild_manifest", "rebuild_report",
]
