"""Federated Free Storage Mesh - the human-backup export adapter.

Google Drive, OneDrive and Dropbox are the HUMAN_BACKUP tier of Spec S6: the
place a person goes to find a recovery export when the rest of the mesh is gone.
``policy.yaml`` says what they are not, in the field name itself -
``tiers.HUMAN_BACKUP.canonical_runtime_object_store: false`` - and Spec S17
calls them "bounded human recovery snapshots", "exported backup bundles",
"tertiary human backup", "emergency recovery copy". Not a backend. Not a tier
the placement logic reaches for when a bucket fills up.

That distinction is the entire design of this file, and it is structural rather
than documented.

**There is no generic object-store surface here.** The three operations are
``export_backup``, ``list_backups`` and ``fetch_backup``. There is no ``put``,
no ``get``, no ``head`` and no ``delete``; this class does not inherit from
``s3_object.ObjectStore`` and cannot be handed to something expecting one. A
caller cannot address a human backup target the way it addresses a primary,
because the methods it would call do not exist. A backup surface that can be
used like a primary eventually is used like one, usually by a retry path
somebody wrote at two in the morning.

**A descriptor naming any tier but HUMAN_BACKUP is refused**, CANONICAL first
among them. GitHub is canonical (Spec S2/S6) and a recovery export in somebody's
Drive is a copy of evidence, never the evidence itself.

**There is no deletion.** Spec S15/S18 put destructive lifecycle behind
``replication.rebalance_object``, which checks the index and a verified
replacement first. An emergency recovery copy that this process can erase is an
emergency recovery copy that a bug can erase.

Everything else is the discipline the S3 adapter already established and this
file *reuses* rather than restates: identity is recomputed and never accepted, a
credential is a zero-argument provider called at request time and never a
parameter or an attribute, there is no HTTP client and every byte leaves through
an injected transport, refusals name a field and never quote a value, and the
bounded checkers come from ``metadata.py`` through ``s3_object.py`` by binding
the identical callables. A second, independently-written copy of "what a bounded
classifier looks like" is a copy that will drift, and the looser of the two is
the one that gets used.

Nothing here creates a folder, a drive, an account or a share, at import time, at
construction time or at any other time, and no approval to create one has been
given. The destination folder is a path that a human with authorization created;
this module only validates that the string it was handed is a filing convenience
rather than a name.

No cryptography is implemented, chosen or performed here.
"""

from __future__ import annotations

from collections.abc import Mapping

from AI_SKILL_LIBRARY.v4.storage import AUTHORITY_FLAGS as _AUTHORITY_FLAG_NAMES
from AI_SKILL_LIBRARY.v4.storage import CANONICAL_AUTHORITY
from AI_SKILL_LIBRARY.v4.storage import manifest as _manifest
from AI_SKILL_LIBRARY.v4.storage import mesh_validator as _mesh_validator
from AI_SKILL_LIBRARY.v4.storage.adapters import s3_object as _s3

#: This module holds no authority of any kind. Denied by name rather than by
#: omission, so a later edit cannot acquire one by adding a key.
AUTHORITY = False
AUTHORITY_FLAGS = {flag: False for flag in _AUTHORITY_FLAG_NAMES}

ROUTED_BY = "task_router"

#: Spec S21 and ``policy.yaml`` ``encryption.implemented_here``.
ENCRYPTION_IMPLEMENTED_HERE = False

#: Nothing external is created by this module, and no approval to create
#: anything has been given.
CREATES_EXTERNAL_RESOURCES = False
PROVISIONING_AUTHORIZED = False

#: The registry ``adapter_type`` values this adapter serves. R2, B2, Oracle,
#: Hugging Face and Supabase declare none of them and may not be driven here.
ADAPTER_TYPES = ("google_drive_api", "microsoft_graph_api", "dropbox_api")

#: The one tier a human backup target serves, and the role the registry gives
#: it. Both are asserted against the row at construction time.
TIER = "HUMAN_BACKUP"
ACCEPTABLE_USE_CLASS = "human-backup-only"

#: Said out loud so a test can assert it rather than a reviewer reading for it.
#: ``policy.yaml`` ``tiers.HUMAN_BACKUP.canonical_runtime_object_store: false``.
CANONICAL_PRIMARY_ALLOWED = False
CANONICAL_RUNTIME_OBJECT_STORE = False
GENERIC_OBJECT_STORE = False

#: The operations this adapter will ask a transport to perform. A closed
#: vocabulary, and deliberately an export vocabulary: there is no "store" verb
#: here to mistake for a primary's, and no destructive verb at all.
OPERATIONS = ("export_backup", "list_backups", "fetch_backup")

#: A human recovery export is something a person can download and restore from.
#: The S3 adapter's 5 GiB is a bulk-object number for a service built to hold
#: bulk objects; this is a backup surface with a human on the other end of it,
#: and Spec S17 says "bounded human recovery snapshots" rather than "mirror".
#: A registry row's ``object_size_limits.max_object_bytes`` narrows this further
#: when one is stated, and a caller may narrow it; neither may widen it.
MAX_EXPORT_BYTES = 256 * 1024 * 1024

#: The whole descriptor block, bounded as a unit exactly as the S3 adapter
#: bounds its object metadata - and to the same number, so the two cannot
#: drift. Every field inside is individually bounded, so this cap is unreachable
#: by a well-formed descriptor and exists to catch a field that has grown a way
#: to hold bulk.
MAX_DESCRIPTOR_BYTES = _s3.MAX_METADATA_BYTES

#: The destination folder is validated by the S3 adapter's key-prefix rule,
#: called rather than copied: one or two lower-case segments and a trailing
#: slash. It is an operator's filing convenience, never a name - Spec S7 keeps
#: filenames, paths and private text out of object naming, and a folder
#: expressive enough to be a name is expressive enough to leak one.
MAX_FOLDER = _s3.MAX_KEY_PREFIX

#: The accepted half of the descriptor partition. Bound from
#: ``s3_object.OBJECT_METADATA_VALUE_CHECKS``, which is itself built from
#: ``metadata._RECORD_FIELD_CHECKS`` - the module that already holds one bounded
#: validator per property of ``storage_object_manifest.schema.json``. Binding
#: the identical callables is the point: the tests assert identity with ``is``,
#: so a seventh hand-written copy of these bounds fails rather than drifts.
BACKUP_DESCRIPTOR_VALUE_CHECKS = dict(_s3.OBJECT_METADATA_VALUE_CHECKS)

#: The field list, derived from the checker table rather than written beside it,
#: so a field with no check cannot be an allowed field.
BACKUP_DESCRIPTOR_FIELDS = tuple(BACKUP_DESCRIPTOR_VALUE_CHECKS)

#: The fields whose borrowed checker this boundary overrides: none. An export
#: descriptor needs nothing stricter than the bounds the manifest schema already
#: sets, so every entry in the table above is the *identical* callable the lane
#: already uses and the tests assert that with ``is``. The constant exists so
#: that an override added later has to be declared rather than discovered.
DESCRIPTOR_CHECK_OVERRIDES = ()

#: The other half of the partition, with the reason attached. Together these two
#: tables cover every property of the manifest schema, and the tests assert that
#: from the schema on disk - so a property added to the contract later is in
#: neither table and fails the day it is added, rather than arriving as an
#: unchecked field on a file in somebody's Drive.
REFUSED_DESCRIPTOR_FIELDS = {
    "object_id": (
        "the object id is the export's name in the backup folder, not a field "
        "inside it; writing it twice invites the two to disagree and makes the "
        "copy the one somebody trusts"),
    "authority": (
        "an exported file asserts no authority; the flag belongs to the "
        "manifest record, where mesh_validator can hold it to const false "
        "(Spec S2)"),
    "authority_flags": (
        "the eight authority flags are a property of a manifest record and of "
        "this lane's modules, never of a bundle sitting in a consumer cloud "
        "drive (Spec S2)"),
    "encryption": (
        "encryption metadata carries key_ref, nonce and tag. Spec S22 separates "
        "keys from the ciphertext provider, and a human backup file is the one "
        "place a key would sit beside the ciphertext it opens, in a folder a "
        "person shares by accident"),
    "source_provenance": (
        "provenance carries evidence references and a producer id; it is index "
        "state that belongs in the metadata store, and an opaque reference in a "
        "shared drive is a pointer somebody else can follow"),
    "verification": (
        "verification is what the mesh observed about an object, not what the "
        "object says about itself; a backup bundle asserting hash_verified is a "
        "bundle vouching for itself (Spec S15)"),
    "primary_backend": (
        "where the live object lives is placement state that changes on every "
        "rebalance, and a recovery export that names the mesh's current "
        "backends is a map of the estate handed to whoever finds the file "
        "(Spec S8/S15)"),
    "replica_backends": (
        "the replica set changes on every repair, and naming the other "
        "providers that hold a copy is the same map as above with more entries "
        "on it (Spec S8/S15)"),
    "last_accessed_at": (
        "access time is runtime state the mesh keeps in its index; rewriting an "
        "exported bundle to record a read would be a write amplification loop "
        "into somebody's personal storage quota"),
    "last_verified_at": (
        "verification time is what the mesh observed, and a bundle that dates "
        "its own verification is vouching for itself (Spec S15)"),
}

#: An export whose privacy class the adapter does not know must not leave, an
#: export whose encryption state it does not know must not leave, and an export
#: that does not say it is a human backup is not one. Unknown fails closed
#: rather than defaulting, because every default here would be a guess.
REQUIRED_DESCRIPTOR_FIELDS = ("privacy_class", "encryption_state", "storage_tier")


# --- errors -------------------------------------------------------------------


class HumanBackupError(_s3.ObjectStoreError):
    """Base class for human-backup failures.

    Derived from the lane's existing object-store error so that a caller
    already catching the lane's failures catches these too. Derived, not
    inherited-from-``ObjectStore``: sharing an exception hierarchy is not the
    same as being a storage backend, and the class below is deliberately not one.
    """


class HumanBackupUnavailable(HumanBackupError):
    """The target could not be reached, or there is no transport to reach it.

    Raised rather than returned so it cannot be mistaken for "no such backup".
    Absence and unreachability are the same shape and opposite facts, and
    treating the second as the first is how a recovery run concludes there is
    nothing to recover.
    """


class BackupNotFound(HumanBackupError):
    """The target was reached and holds no export under that address."""


class BackupIntegrityError(HumanBackupError):
    """The bytes that came back are not the bytes the address names."""


# --- helpers ------------------------------------------------------------------


def _bounded(field, value):
    """Run this module's bounded checker for a field, silently.

    Dispatches through ``BACKUP_DESCRIPTOR_VALUE_CHECKS`` rather than the S3
    table it is bound from, so the table this module publishes is the table this
    module enforces. The checker's own message is discarded because those
    checkers quote their input - right for a manifest built from repository
    data, wrong at a boundary a runtime caller reaches.
    """
    try:
        BACKUP_DESCRIPTOR_VALUE_CHECKS[field](value, field=field)
    except Exception:  # noqa: BLE001 - the text is discarded on purpose
        _s3._refuse(field, "is outside the bound the manifest schema sets for it")


def _registry_row(backend_id):
    for row in _mesh_validator.load_providers():
        if row.get("provider_id") == backend_id:
            return row
    return None


# --- the target ---------------------------------------------------------------


class HumanBackupTarget:
    """A human backup surface reached through an injected transport.

    Construction validates and binds nothing external: no connection is opened,
    no credential is fetched, no folder is created or checked for existence.
    Without a ``transport`` the target is simply unusable and every operation
    fails closed, which is the honest state of a consumer cloud account nobody
    has connected.

    The transport contract is three operations and one shape::

        transport(operation, payload, *, folder, credential)

    ``export_backup``  payload ``{"name", "body", "descriptor"}`` -> ``True``
    ``list_backups``   payload ``{}``                             -> list of names
    ``fetch_backup``   payload ``{"name"}``                       -> ``bytes`` or ``None``

    The credential is passed as a keyword and never appears in ``payload``,
    because ``payload`` is the part a transport logs.
    """

    #: An adapter is a door, not a decision (Spec S2).
    AUTHORITY = False
    ENCRYPTION_IMPLEMENTED_HERE = False

    def __init__(self, *, backend_id, folder, credential_provider,
                 transport=None, clock=None, max_export_bytes=None):
        row = self._validated_backend(backend_id)
        self._backend_id = backend_id
        self._folder = self._validated_folder(folder)
        self._max_export_bytes = self._validated_ceiling(max_export_bytes, row)
        if not callable(credential_provider):
            raise ValueError(
                "credential_provider must be a zero-argument callable that "
                "fetches the token from the runtime secret store at call time. "
                "A literal credential is refused: a secret passed as a value "
                "becomes an attribute, and an attribute reaches a repr, a log "
                "line and a traceback (Spec S22)")
        if transport is not None and not callable(transport):
            raise ValueError("transport must be a callable or None")
        if clock is not None and not callable(clock):
            raise ValueError("clock must be a zero-argument callable or None")
        #: Held as a callable, never as a value. Nothing is fetched here.
        self._credential_provider = credential_provider
        self._transport = transport
        self._clock = clock or _s3._now_instant

    # -- construction-time validation ----------------------------------------

    @staticmethod
    def _validated_backend(backend_id):
        """A registry row, and a human-backup one.

        Registry membership is still not admission - whether this row may
        receive a byte is ``mesh_validator``'s question and depends on runtime
        state this adapter does not read. What is settled here is that the
        backend exists, that it is one of the three human-backup surfaces, and
        that the registry gives it the human-backup role and tier. An object
        store does not become a backup surface by being passed to this
        constructor, and a backup surface does not become a primary by being
        passed to an object store.
        """
        if not isinstance(backend_id, str):
            raise ValueError(
                f"backend_id must be a string, got {type(backend_id).__name__}")
        row = _registry_row(backend_id)
        if row is None:
            raise ValueError(
                "backend_id is not a row in the provider registry; an adapter "
                "may only be pointed at a registered backend, and registry "
                "membership is still not admission")
        if row.get("adapter_type") not in ADAPTER_TYPES:
            raise ValueError(
                f"backend_id does not declare one of the human-backup adapter "
                f"types {ADAPTER_TYPES} in the provider registry")
        if row.get("acceptable_use_class") != ACCEPTABLE_USE_CLASS:
            raise ValueError(
                f"backend_id is not registered with the {ACCEPTABLE_USE_CLASS!r} "
                "role; a human backup adapter drives a human backup surface and "
                "nothing else (Spec S17)")
        if list(row.get("tiers_allowed") or []) != [TIER]:
            raise ValueError(
                f"backend_id does not serve the {TIER} tier alone; a target "
                "that also serves an object tier would be addressable as a "
                "canonical runtime object store, which policy.yaml denies")
        return row

    @staticmethod
    def _validated_folder(folder):
        """The S3 adapter's key-prefix rule, called rather than copied.

        Empty is refused here where the object adapter allows it: an export
        lands in a named backup area that somebody authorized, not at the root
        of a person's drive next to their photographs.
        """
        if not isinstance(folder, str):
            raise ValueError(
                f"folder must be a string, got {type(folder).__name__}")
        if folder == "":
            raise ValueError(
                "folder must name the backup area an export lands in; the root "
                "of somebody's drive is not a backup area")
        return _s3.ObjectStore._validated_key_prefix(folder)

    @staticmethod
    def _validated_ceiling(max_export_bytes, row):
        """The smallest of the module, registry and caller ceilings."""
        ceiling = MAX_EXPORT_BYTES
        limits = row.get("object_size_limits") or {}
        declared = limits.get("max_object_bytes") if isinstance(limits, Mapping) else None
        if isinstance(declared, int) and not isinstance(declared, bool) and declared > 0:
            ceiling = min(ceiling, declared)
        if max_export_bytes is None:
            return ceiling
        if (not isinstance(max_export_bytes, int)
                or isinstance(max_export_bytes, bool)
                or not 1 <= max_export_bytes <= MAX_EXPORT_BYTES):
            raise ValueError(
                "max_export_bytes must be a positive integer no larger than "
                f"{MAX_EXPORT_BYTES}; a caller may narrow this ceiling and "
                "never widen it. The value is not quoted here")
        return min(ceiling, max_export_bytes)

    # -- identity -------------------------------------------------------------

    @property
    def backend_id(self):
        return self._backend_id

    @property
    def folder(self):
        return self._folder

    @property
    def max_export_bytes(self):
        return self._max_export_bytes

    def __repr__(self):
        """Deliberately almost empty.

        A repr reaches logs, tracebacks and debugger dumps. The backend id is a
        registry key and safe; the folder is caller-supplied and is simply not
        worth printing.
        """
        transport = "injected" if self._transport is not None else "none"
        return (f"<HumanBackupTarget backend={self._backend_id} "
                f"transport={transport}>")

    # -- transport ------------------------------------------------------------

    def _call(self, operation, payload):
        if operation not in OPERATIONS:
            raise ValueError(f"unknown human backup operation {operation!r}")
        if self._transport is None:
            raise HumanBackupUnavailable(
                "no transport is injected, so this backup target cannot be "
                "reached. An adapter without a transport is not a stub standing "
                "in for a real one: it is the honest state of a consumer cloud "
                "account nobody has connected, and it fails closed")
        try:
            credential = self._credential_provider()
        except BaseException:  # noqa: BLE001 - see below
            raise HumanBackupUnavailable(
                "the credential provider did not return a credential; the "
                "original error is not chained here because a secret-store "
                "failure routinely quotes the thing it failed to fetch"
            ) from None
        try:
            return self._transport(operation, payload,
                                   folder=self._folder,
                                   credential=credential)
        except BaseException:  # noqa: BLE001 - see below
            # Neither re-raised nor chained. A transport's own exception is the
            # single most likely place for an OAuth token, a signed URL or a
            # request body to appear, and ``raise ... from exc`` prints the
            # cause for anyone who catches this one.
            raise HumanBackupUnavailable(
                f"the transport failed during {operation!r}. The underlying "
                "error is deliberately not chained: a transport's exception "
                "text routinely carries an authorization header (Spec S21/S22)"
            ) from None

    def _name(self, object_id):
        """The export's name in the backup folder: the content address.

        Not a filename. Spec S7 and ``policy.yaml`` ``object_naming`` keep
        names, paths and private text out of object naming, and a recovery
        export in a shared drive is the last place a descriptive filename
        belongs.
        """
        if not isinstance(object_id, str) or not _s3._OBJECT_ID_RE.match(object_id):
            raise ValueError(
                "object_id must be 'obj_' followed by a lower-case SHA-256 "
                "digest. Identity in this mesh is the content and only the "
                "content, which is also why no name, path or key can be written "
                "into it (Spec S7). The value is not quoted here")
        return f"{self._folder}{object_id}"

    def _instant(self):
        try:
            value = self._clock()
        except Exception:  # noqa: BLE001 - a clock is an input, not a permission
            raise HumanBackupError("the injected clock did not return an "
                                   "instant") from None
        try:
            _manifest._check_timestamp(value, field="observed_at")
        except Exception:  # noqa: BLE001 - the text is discarded on purpose
            _s3._redacted(HumanBackupError,
                          "the injected clock did not return an RFC 3339 "
                          "instant. Its answer is deliberately not quoted: a "
                          "clock is an injected input like any other "
                          "(Spec S21/S22)")
        return value

    # -- the descriptor -------------------------------------------------------

    def _validated_descriptor(self, descriptor, *, digest, size_bytes):
        if not isinstance(descriptor, Mapping):
            raise ValueError(
                "a backup descriptor must be a mapping, got "
                f"{_s3._type_name(descriptor)}")

        for field in descriptor:
            if not isinstance(field, str):
                raise ValueError("backup descriptor keys must be strings")
            if field in REFUSED_DESCRIPTOR_FIELDS:
                raise ValueError(
                    f"backup descriptor field {field!r} may never be written "
                    f"into an export: {REFUSED_DESCRIPTOR_FIELDS[field]}")
            if field not in BACKUP_DESCRIPTOR_VALUE_CHECKS:
                raise ValueError(
                    f"the backup descriptor rejects the unknown field "
                    f"{_s3._namable(field)}: the field set is closed, so "
                    "'api_key', 'plaintext_key' and the name nobody has thought "
                    "of yet are all refused by the same line rather than by a "
                    "denylist the next one walks past")

        missing = sorted(set(REQUIRED_DESCRIPTOR_FIELDS) - set(descriptor))
        if missing:
            raise ValueError(
                f"the backup descriptor is missing required field(s) {missing}; "
                "an export whose privacy class, encryption state or tier the "
                "adapter does not know does not leave, because every default "
                "here would be a guess (Spec S4/S6)")

        attached = {}
        for field in BACKUP_DESCRIPTOR_FIELDS:
            if field not in descriptor:
                continue
            value = descriptor[field]
            if value is None:
                _s3._refuse(field, "is null; an optional field is omitted "
                                   "rather than emitted as null")
            _bounded(field, value)
            attached[field] = value

        self._check_consistency(attached, digest=digest, size_bytes=size_bytes)
        self._check_tier(attached)
        self._check_privacy(attached)

        encoded_length = sum(len(field) + len(repr(value)) + 4
                             for field, value in attached.items())
        if encoded_length > MAX_DESCRIPTOR_BYTES:
            raise ValueError(
                f"the descriptor is {encoded_length} bytes, over the "
                f"{MAX_DESCRIPTOR_BYTES}-byte bound. Every field is "
                "individually bounded, so this is not reachable by a well-formed "
                "descriptor: it means a field has grown a way to hold bulk")
        return attached

    @staticmethod
    def _check_consistency(attached, *, digest, size_bytes):
        """A descriptor that describes the export must describe *this* one."""
        if attached.get("content_sha256", digest) != digest:
            raise ValueError(
                "the descriptor's content_sha256 does not match the payload's "
                "digest; a record that disagrees with the bytes is worse than "
                "no record, because something will eventually believe it")
        if attached.get("size_bytes", size_bytes) != size_bytes:
            raise ValueError(
                "the descriptor's size_bytes does not match the payload length")

    @staticmethod
    def _check_tier(attached):
        """The rule that keeps a backup surface from becoming a primary.

        Spec S6 and ``policy.yaml`` ``tiers.HUMAN_BACKUP``: these targets hold
        human-oriented backup copies and recovery exports. CANONICAL is
        GitHub's and the object tiers belong to backends that were admitted as
        backends; a descriptor naming one of them is a placement that went wrong
        somewhere else, and this is the door declining to open on it.
        """
        tier = attached.get("storage_tier")
        if tier != TIER:
            raise ValueError(
                f"a human backup target accepts the {TIER} tier only, and this "
                "descriptor names another. Drive, OneDrive and Dropbox are "
                "backup surfaces, not canonical runtime object stores "
                "(policy.yaml tiers.HUMAN_BACKUP, Spec S6/S17)")

    @staticmethod
    def _check_privacy(attached):
        """Spec S4/S5, at the last possible moment before the bytes leave.

        Not a second placement authority. ``placement.py`` decides; this is the
        door declining to open on a decision that was already wrong, and it is
        here because a placement bug that reaches this line is a privacy
        incident rather than a failed test.
        """
        privacy = attached.get("privacy_class")
        encryption_state = attached.get("encryption_state")
        if privacy == "LOCAL_ONLY":
            raise ValueError(
                "a LOCAL_ONLY object is never uploaded to third-party cloud "
                "storage, and a consumer cloud drive is third-party cloud "
                "storage however personal the account feels (Spec S4)")
        if privacy == "CONFIDENTIAL" and encryption_state != "CLIENT_SIDE_ENCRYPTED":
            raise ValueError(
                "a CONFIDENTIAL object leaves owned storage only as ciphertext "
                "(Spec S4/S21). This adapter checks the declared state and "
                "performs no cryptography of its own; encrypting it is the "
                "encryption contract's job and must already have happened")
        if encryption_state == "NONE" and "encryption_scheme_version" in attached:
            raise ValueError(
                "encryption_state NONE carries no scheme version; the manifest "
                "schema encodes that as structure and a descriptor that "
                "contradicts it is a document nobody agreed to")
        if (encryption_state == "CLIENT_SIDE_ENCRYPTED"
                and "encryption_scheme_version" not in attached):
            raise ValueError(
                "ciphertext must carry its encryption_scheme_version so a "
                "reader knows which contract produced it. The key reference, "
                "nonce and tag stay in the index and never travel with the "
                "backup file (Spec S22)")

    # -- the three operations -------------------------------------------------

    def export_backup(self, object_id, payload, descriptor):
        """Write one bounded recovery export. Returns an ``ObjectReceipt``.

        Nothing leaves this process until the address has been recomputed from
        the bytes, the descriptor has been bounded, the tier has been checked
        and the privacy class has been checked - in that order, so a refusal is
        a refusal rather than a cleanup.
        """
        name = self._name(object_id)
        digest = _s3.content_digest(payload)
        body = bytes(payload)
        if len(body) > self._max_export_bytes:
            raise ValueError(
                f"the export is {len(body)} bytes, over this target's "
                f"{self._max_export_bytes}-byte ceiling. A human recovery "
                "export is something a person can download and restore from; "
                "a mirror of the mesh is not one (Spec S17)")
        if object_id != f"{_manifest.OBJECT_ID_PREFIX}{digest}":
            raise ValueError(
                "object_id is not the digest of this payload. Identity in this "
                "mesh is the content, so writing bytes under an address that is "
                "not theirs would break every verification that follows "
                "(Spec S15). The id is not quoted here")
        attached = self._validated_descriptor(descriptor, digest=digest,
                                              size_bytes=len(body))

        acknowledged = self._call("export_backup", {"name": name, "body": body,
                                                    "descriptor": attached})
        if acknowledged is not True:
            raise HumanBackupError(
                "the transport did not acknowledge the export with True. "
                "Anything else is an unknown outcome, and an unknown export is "
                "not a backup anybody can recover from")
        return _s3.ObjectReceipt(
            object_id=object_id,
            backend_id=self._backend_id,
            content_sha256=digest,
            size_bytes=len(body),
            observed_at=self._instant(),
            digest_source="computed",
            verified=True,
        )

    def list_backups(self):
        """The object ids this target holds, as a tuple.

        A ``str`` and a ``bytes`` are both sequences, and iterating either one
        yields characters or integers that are not object ids - so the answer
        must be a ``list`` and nothing else. An unrecognised answer is refused
        rather than iterated.
        """
        answer = self._call("list_backups", {})
        if isinstance(answer, (str, bytes, bytearray)) or not isinstance(answer, list):
            raise HumanBackupError(
                f"the transport returned {_s3._type_name(answer)} where a list "
                "of backup names was expected; an unrecognised answer is not an "
                "empty backup folder")
        found = []
        for entry in answer:
            if not isinstance(entry, str) or not entry.startswith(self._folder):
                raise HumanBackupError(
                    "a listed backup name is not in this target's backup "
                    "folder; the name is deliberately not quoted, because a "
                    "listing comes from the far side of the transport")
            object_id = entry[len(self._folder):]
            if not _s3._OBJECT_ID_RE.match(object_id):
                raise HumanBackupError(
                    "a listed backup name is not a content address. Exports are "
                    "named by digest and nothing else, so a file the mesh did "
                    "not write is reported rather than adopted (Spec S7/S15)")
            found.append(object_id)
        return tuple(found)

    def fetch_backup(self, object_id):
        """Return one export's bytes, re-hashed before they are handed over."""
        name = self._name(object_id)
        answer = self._call("fetch_backup", {"name": name})
        if answer is None:
            raise BackupNotFound(
                "this target holds no export under that address. Absence is "
                "raised rather than returned as empty bytes, because an empty "
                "backup and a missing one are opposite facts")
        if not isinstance(answer, (bytes, bytearray)) or isinstance(answer, bool):
            raise HumanBackupError(
                f"the transport returned {_s3._type_name(answer)} where export "
                "bytes were expected; an unrecognised answer is not content")
        body = bytes(answer)
        if _s3.content_digest(body) != object_id[len(_manifest.OBJECT_ID_PREFIX):]:
            raise BackupIntegrityError(
                "the bytes returned are not the bytes this address names. They "
                "are refused rather than returned: a human backup folder is a "
                "surface a person can edit, and a recovery that trusts what it "
                "finds there is a recovery that restores somebody's holiday "
                "photographs over the evidence (Spec S15)")
        return body


__all__ = [
    "AUTHORITY", "AUTHORITY_FLAGS", "CANONICAL_AUTHORITY", "ROUTED_BY",
    "ENCRYPTION_IMPLEMENTED_HERE", "CREATES_EXTERNAL_RESOURCES",
    "PROVISIONING_AUTHORIZED", "ADAPTER_TYPES", "TIER", "ACCEPTABLE_USE_CLASS",
    "CANONICAL_PRIMARY_ALLOWED", "CANONICAL_RUNTIME_OBJECT_STORE",
    "GENERIC_OBJECT_STORE", "OPERATIONS", "MAX_EXPORT_BYTES",
    "MAX_DESCRIPTOR_BYTES", "MAX_FOLDER", "BACKUP_DESCRIPTOR_VALUE_CHECKS",
    "BACKUP_DESCRIPTOR_FIELDS", "DESCRIPTOR_CHECK_OVERRIDES",
    "REFUSED_DESCRIPTOR_FIELDS",
    "REQUIRED_DESCRIPTOR_FIELDS", "HumanBackupTarget", "HumanBackupError",
    "HumanBackupUnavailable", "BackupNotFound", "BackupIntegrityError",
]
