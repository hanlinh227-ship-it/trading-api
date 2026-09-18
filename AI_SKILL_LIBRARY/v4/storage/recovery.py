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

**"Bounded" is the whole design, and it is three bounds, not one.**

``MAX_SNAPSHOT_ENTRIES`` caps how many objects are indexed, ``MAX_SNAPSHOT_BYTES``
caps the serialised document, and ``MAX_SNAPSHOT_STRING`` caps every individual
string inside it. The third is the one that actually stops a credential. A
snapshot can satisfy both of the first two and still carry two kilobytes of
secret in one allowed field, and a check like ``assert "api_key" not in blob``
would not notice: that is a substring test on field *names*, and the field a
secret arrives in is never called ``api_key``.

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

#: The projection. An entry carries these fields and no others.
ENTRY_FIELDS = (
    "object_id", "content_sha256", "size_bytes", "privacy_class", "criticality",
    "storage_tier", "encryption_state", "encryption", "primary_backend",
    "replica_backends", "created_at", "lifecycle_state", "reproducible",
)

REQUIRED_ENTRY_FIELDS = tuple(f for f in ENTRY_FIELDS if f != "encryption")

#: Of the six encryption metadata fields a manifest may carry, three reach
#: GitHub: what construction was used, which scheme version, and where the key
#: is kept. ``nonce`` and ``tag`` are per-object ciphertext parameters that live
#: with the ciphertext and are not needed to identify or re-place an object, and
#: ``key_rotation_generation`` is not either. Fewer fields in a checkpoint is
#: strictly better (Spec S22 keeps checkpoints out of the key business).
SNAPSHOT_ENCRYPTION_FIELDS = ("algorithm", "scheme_version", "key_ref")

#: What a provider scan can actually observe about an object: which backend
#: holds it, what it claims to be, how big it is, and when it was seen. Closed,
#: because an undeclared field is the only way an unbounded string reaches a
#: recovery input at all.
PROVIDER_RECORD_FIELDS = (
    "backend_id", "object_id", "content_sha256", "size_bytes", "observed_at",
)
REQUIRED_PROVIDER_RECORD_FIELDS = (
    "backend_id", "object_id", "content_sha256", "size_bytes",
)

SNAPSHOT_FIELDS = (
    "version", "manifest_schema_version", "generated_at", "canonical_authority",
    "authority", "authority_flags", "metadata_service", "pointers", "caps",
    "entry_count", "truncated", "omitted_entries", "critical_object_index",
    "entries",
)

#: Which objects survive truncation. Spec S18 requires the *critical-object
#: index* to be among what GitHub keeps, so CRITICAL is kept first and the cap
#: is a hard error rather than a silent drop if criticals alone exceed it.
_CRITICALITY_RANK = {name: rank for rank, name in enumerate(
    ("CRITICAL", "IMPORTANT", "REPRODUCIBLE", "EPHEMERAL"))}

#: A pointer is a repository-relative path under ``AI_SKILL_LIBRARY/`` and
#: nothing else - not a URL, not an absolute path, not a traversal. A rebuild
#: reads what these name, so the field is a redirect if it is left open.
_POINTER_RE = re.compile(
    r"^AI_SKILL_LIBRARY/[A-Za-z0-9][A-Za-z0-9._/-]{2,120}\.(?:yaml|yml|json)\Z")

#: Spec S18/S25 and ``policy.yaml`` ``metadata_service``, restated in the
#: checkpoint so that a rebuild reading only this file still learns that the
#: index is not canonical and that no project has been verified to exist.
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


# --- cleanliness --------------------------------------------------------------


def _walk_values(value, *, where):
    """Bound and scan every string in the document, keys included.

    Keys as well as values, because a hand-edited or machine-merged snapshot can
    grow a key as easily as a value, and a 2KB key is exactly as much storage as
    a 2KB value.
    """
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
            _walk_values(key, where=f"{where}.<key>")
            _walk_values(nested, where=f"{where}.{key}")
        return
    if isinstance(value, list):
        for index, nested in enumerate(value):
            _walk_values(nested, where=f"{where}[{index}]")
        return
    raise ValueError(
        f"{where} holds {type(value).__name__}; a recovery snapshot carries "
        "strings, integers, booleans, nulls, lists and mappings - a float is "
        "not round-trippable and anything else is not a pointer")


def _check_entry(entry, *, where):
    if not isinstance(entry, Mapping):
        raise ValueError(f"{where} must be a mapping, got {type(entry).__name__}")
    unknown = sorted(set(entry) - set(ENTRY_FIELDS))
    if unknown:
        raise ValueError(
            f"{where} rejects field(s) {unknown}: a snapshot entry is a "
            f"projection onto {list(ENTRY_FIELDS)}, so a field nobody put on "
            "that list does not reach GitHub whatever it holds")
    missing = sorted(set(REQUIRED_ENTRY_FIELDS) - set(entry))
    if missing:
        raise ValueError(f"{where} is missing required field(s) {missing}")

    _metadata._check_object_id(entry["object_id"], field=f"{where}.object_id")
    _metadata._check_sha256(entry["content_sha256"],
                            field=f"{where}.content_sha256")
    if entry["object_id"] != f"{_manifest.OBJECT_ID_PREFIX}{entry['content_sha256']}":
        raise ValueError(f"{where}.object_id is not the content digest")
    _manifest._check_bounded_int(entry["size_bytes"], 0, _manifest._MAX_SIZE_BYTES,
                                 field=f"{where}.size_bytes")
    for field, allowed in (("privacy_class", PRIVACY_CLASSES),
                           ("criticality", CRITICALITY_CLASSES),
                           ("storage_tier", STORAGE_TIERS),
                           ("lifecycle_state", LIFECYCLE_STATES),
                           ("encryption_state", _manifest.ENCRYPTION_STATES)):
        _manifest._check_enum(entry[field], allowed, field=f"{where}.{field}")
    _manifest._check_timestamp(entry["created_at"], field=f"{where}.created_at")
    if not isinstance(entry["reproducible"], bool):
        raise ValueError(f"{where}.reproducible must be a boolean")
    _manifest._check_backend(entry["primary_backend"],
                             role=f"{where}.primary_backend")
    replicas = entry["replica_backends"]
    if isinstance(replicas, str) or not isinstance(replicas, list):
        raise ValueError(f"{where}.replica_backends must be a list")
    if len(replicas) > _manifest._MAX_REPLICAS or len(set(replicas)) != len(replicas):
        raise ValueError(f"{where}.replica_backends is duplicated or over bound")
    for backend in replicas:
        _manifest._check_backend(backend, role=f"{where}.replica_backends[]")

    encryption = entry.get("encryption")
    if encryption is None:
        if entry["encryption_state"] != "NONE":
            raise ValueError(
                f"{where} claims ciphertext with no encryption metadata")
    else:
        if entry["encryption_state"] == "NONE":
            raise ValueError(
                f"{where} says plaintext and carries encryption metadata")
        admitted = _manifest._closed_mapping(
            encryption, SNAPSHOT_ENCRYPTION_FIELDS, field=f"{where}.encryption",
            required=SNAPSHOT_ENCRYPTION_FIELDS)
        for key, value in admitted.items():
            _manifest._ENCRYPTION_FIELD_CHECKS[key](
                value, field=f"{where}.encryption.{key}")


def assert_snapshot_is_clean(snapshot):
    """Refuse a snapshot that is malformed, unbounded or credential-shaped.

    Run by the exporter on its own output before returning it, and by the
    rebuild on any snapshot handed to it. The second use is the important one:
    a snapshot read back from GitHub has been through a merge, a rebase, an
    editor and possibly a hand edit, and a recovery path that trusts its input
    is a recovery path that will one day rebuild from someone else's file.
    """
    if not isinstance(snapshot, Mapping):
        raise ValueError(
            f"a recovery snapshot must be a mapping, got {type(snapshot).__name__}")
    unknown = sorted(set(snapshot) - set(SNAPSHOT_FIELDS))
    if unknown:
        raise ValueError(f"recovery snapshot rejects unknown field(s) {unknown}")
    missing = sorted(set(SNAPSHOT_FIELDS) - set(snapshot))
    if missing:
        raise ValueError(f"recovery snapshot is missing field(s) {missing}")

    if snapshot["version"] != SNAPSHOT_VERSION or isinstance(
            snapshot["version"], bool):
        raise ValueError(
            f"recovery snapshot version must be {SNAPSHOT_VERSION}")
    if snapshot["authority"] is not False:
        raise ValueError(
            "a recovery snapshot is evidence about objects, never authority "
            "over them")
    _metadata._check_authority_flags(snapshot["authority_flags"],
                                     field="authority_flags")
    if snapshot["canonical_authority"] != CANONICAL_AUTHORITY:
        raise ValueError(
            f"canonical_authority must remain {CANONICAL_AUTHORITY}; the "
            "metadata service is an index and GitHub stays canonical (Spec S18)")
    _manifest._check_timestamp(snapshot["generated_at"], field="generated_at")

    service = snapshot["metadata_service"]
    if not isinstance(service, Mapping) or set(service) != set(_METADATA_SERVICE):
        raise ValueError(
            f"metadata_service must name exactly {sorted(_METADATA_SERVICE)}")
    if service["authority"] is not False or service["role"] != _METADATA_SERVICE["role"]:
        raise ValueError(
            "metadata_service must remain a non-authoritative index; a "
            "checkpoint that says otherwise is a checkpoint that promotes "
            "Supabase to canonical by being read (Spec S18/S32)")
    if service["project_exists_verified"] is not False:
        raise ValueError(
            "project_exists_verified may only be asserted from runtime "
            "evidence, and there is none: Spec S25 records that the connected "
            "account has no projects")
    reference = service["last_successful_export_ref"]
    if reference is not None:
        _manifest._check_evidence_ref(
            reference, field="metadata_service.last_successful_export_ref")

    if snapshot["caps"] != {"max_entries": MAX_SNAPSHOT_ENTRIES,
                            "max_bytes": MAX_SNAPSHOT_BYTES,
                            "max_string": MAX_SNAPSHOT_STRING}:
        raise ValueError(
            "caps must state this module's actual bounds; a snapshot carrying "
            "looser numbers than the code enforces documents a permission "
            "nobody granted")

    pointers = snapshot["pointers"]
    if not isinstance(pointers, Mapping) or set(pointers) != set(_POINTERS):
        raise ValueError(f"pointers must name exactly {sorted(_POINTERS)}")
    for name, path in pointers.items():
        if not isinstance(path, str) or not _POINTER_RE.match(path):
            raise ValueError(
                f"pointers.{name} must be a repository-relative path under "
                "AI_SKILL_LIBRARY/; GitHub is where the canonical documents "
                "are, and a pointer that can be an arbitrary URL is a pointer "
                "that can send a rebuild somewhere else")

    entries = snapshot["entries"]
    if not isinstance(entries, list):
        raise ValueError("entries must be a list")
    if len(entries) > MAX_SNAPSHOT_ENTRIES:
        raise ValueError(
            f"recovery snapshot holds {len(entries)} entries, over the "
            f"{MAX_SNAPSHOT_ENTRIES} cap")
    for index, entry in enumerate(entries):
        _check_entry(entry, where=f"entries[{index}]")

    ids = [entry["object_id"] for entry in entries]
    if ids != sorted(ids) or len(set(ids)) != len(ids):
        raise ValueError(
            "entries must be ordered by object_id and each object named once; "
            "a snapshot that is not deterministic cannot be reviewed as a diff")

    index = snapshot["critical_object_index"]
    if not isinstance(index, list) or index != sorted(set(index)):
        raise ValueError(
            "critical_object_index must be a sorted, duplicate-free list")
    if not set(index) <= set(ids):
        raise ValueError(
            "critical_object_index names an object the snapshot does not carry")

    for field in ("entry_count", "omitted_entries"):
        _manifest._check_bounded_int(snapshot[field], 0, 2 ** 31 - 1, field=field)
    if not isinstance(snapshot["truncated"], bool):
        raise ValueError("truncated must be a boolean")
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


def export_recovery_snapshot(store, *, generated_at=None):
    """Render the bounded pointer set GitHub keeps (Spec S18).

    Refuses an unhealthy store rather than exporting what it managed to read:
    a partial snapshot presented as a complete one is worse than no snapshot,
    because the next rebuild treats everything missing from it as lost.
    """
    if not isinstance(store, _metadata.MetadataStore):
        raise ValueError(
            "export_recovery_snapshot needs a MetadataStore; an object that "
            "merely answers list_manifests() has not been through the "
            "validation that makes its answer mean anything")

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
        "metadata_service": dict(_METADATA_SERVICE),
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
    unknown = sorted(set(row) - set(PROVIDER_RECORD_FIELDS))
    if unknown:
        raise ValueError(
            f"provider record rejects unknown field(s) {unknown}: the field set "
            f"is closed to {list(PROVIDER_RECORD_FIELDS)}, so an object tag, an "
            "ETag, a signed URL or a note cannot ride into the rebuild")
    missing = sorted(set(REQUIRED_PROVIDER_RECORD_FIELDS) - set(row))
    if missing:
        raise ValueError(f"provider record is missing field(s) {missing}")

    _manifest._check_backend(row["backend_id"], role="provider record backend_id")
    _metadata._check_object_id(row["object_id"], field="provider record object_id")
    _metadata._check_sha256(row["content_sha256"],
                            field="provider record content_sha256")
    _manifest._check_bounded_int(row["size_bytes"], 0, _manifest._MAX_SIZE_BYTES,
                                 field="provider record size_bytes")
    if "observed_at" in row:
        _manifest._check_timestamp(row["observed_at"],
                                   field="provider record observed_at")
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
    "SNAPSHOT_FIELDS", "ENTRY_FIELDS", "REQUIRED_ENTRY_FIELDS",
    "SNAPSHOT_ENCRYPTION_FIELDS", "PROVIDER_RECORD_FIELDS",
    "REQUIRED_PROVIDER_RECORD_FIELDS", "assert_snapshot_is_clean",
    "export_recovery_snapshot", "rebuild_manifest", "rebuild_report",
]
