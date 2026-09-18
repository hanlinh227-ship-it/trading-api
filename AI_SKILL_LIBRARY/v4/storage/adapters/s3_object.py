"""Federated Free Storage Mesh - the S3-compatible object adapter.

Tasks 1-4 built a mesh that has never held a byte. ``manifest.py`` says what an
object *is*, ``placement.py`` says where it may go, ``metadata.py`` remembers
that it went there, ``recovery.py`` can rebuild the index when the service
holding it disappears - and not one of them can put an object anywhere. This is
the edge where bytes cross out of the process, and it is written on the
assumption that everything on the far side is broken, confused or hostile.

Spec S17 names R2, B2 and Oracle Object Storage as the three S3-compatible
roles, and Spec S31 asks for *one* S3-compatible adapter rather than three
provider integrations. This is that one. It is transport-neutral by
construction: there is no endpoint, region, bucket, account or credential in
this file, and there is no code path that could acquire one.

Five properties, each the answer to a specific way an object adapter goes
wrong.

**It cannot reach the network.** There is no HTTP client here, no
``boto3``, no ``urllib``, no ``socket``. Every byte that leaves goes through an
injected ``transport`` callable, and a store without one is not a stub standing
in for a real implementation - it is the accurate state of a provider account
nobody has admitted, and it fails closed on every operation. That is the same
honesty ``adapters/supabase_metadata.py`` already applies to a Supabase project
that does not exist.

**Identity is recomputed, never accepted.** ``put`` refuses to store bytes
under an ``object_id`` that is not their digest; ``get`` re-hashes what came
back before handing it to a caller; a receipt built from a ``head`` is marked as
the provider's *claim* and carries ``verified=False``. A content-addressed
store that believes the address it was given is not content-addressed, it is a
key-value store with a long key - and every guarantee in Spec S15 rests on the
address being a fact about the bytes.

**The credential is never held.** It is not a parameter, not an attribute and
not a default. What the constructor takes is a zero-argument provider, called
at the moment of a request and never at import or construction, so the secret
lives in the runtime secret store and passes through a call frame. It is handed
to the transport as a keyword and never placed in the request payload, which is
the part a transport logs. Nothing in this module quotes a caller's value back:
refusals name the *field*, never its contents, and a transport's own exception
is not re-raised or chained, because a signed URL and an ``Authorization``
header are exactly what such an exception tends to contain.

**Every attachable field is bounded, and the completeness is structural.** The
metadata a caller may attach to an object is a projection of
``storage_object_manifest.schema.json``: every property of that schema is either
in ``OBJECT_METADATA_VALUE_CHECKS``, with the bounded checker ``metadata.py``
already wrote for it, or in ``REFUSED_METADATA_FIELDS`` with the reason it may
never ride on the object itself. The tests drive that partition *from the schema
on disk*, so a property added to the contract later is in neither table and
fails the day it is added. This lane has shipped "an allowed field whose value
nothing bounds" three times; a hand-written list of field names is how that
keeps happening, and the checkers are imported rather than restated because a
fourth independently-written copy of "what a bounded classifier looks like" is
a copy that will drift, and the looser one is the one an attacker gets to use.

**Privacy outranks the transport.** A LOCAL_ONLY object is refused on an
external backend and a CONFIDENTIAL object is refused unless it is already
ciphertext, checked at the last possible moment before the bytes leave. Those
decisions belong to ``placement.py`` and are made there; re-checking them here
is not a second placement authority, it is the door declining to open on a
decision that was already wrong. This module chooses nothing, ranks nothing and
admits no provider.

No cryptography is implemented, chosen or performed here. The client-side
encryption contract is Task 6's; this adapter reads an ``encryption_state`` and
refuses to carry plaintext where policy requires ciphertext, which is a check
on a declaration rather than an act of cryptography.
"""

from __future__ import annotations

import dataclasses
import datetime as _datetime
import hashlib
import re
from collections.abc import Mapping

from AI_SKILL_LIBRARY.v4.storage import AUTHORITY_FLAGS as _AUTHORITY_FLAG_NAMES
from AI_SKILL_LIBRARY.v4.storage import CANONICAL_AUTHORITY
from AI_SKILL_LIBRARY.v4.storage import manifest as _manifest
from AI_SKILL_LIBRARY.v4.storage import mesh_validator as _mesh_validator
from AI_SKILL_LIBRARY.v4.storage import metadata as _metadata

#: This module holds no authority of any kind. Denied by name rather than by
#: omission, so a later edit cannot acquire one by adding a key.
AUTHORITY = False
AUTHORITY_FLAGS = {flag: False for flag in _AUTHORITY_FLAG_NAMES}

ROUTED_BY = "task_router"

#: Spec S21 and ``policy.yaml`` ``encryption.implemented_here``. There is
#: deliberately no ``encrypt``/``decrypt``/``derive_key`` symbol here to import
#: by mistake.
ENCRYPTION_IMPLEMENTED_HERE = False

#: Nothing external is created by this module, and no approval to create
#: anything has been given. Stated as constants so a test can assert it rather
#: than a reviewer having to read for it.
CREATES_EXTERNAL_RESOURCES = False
PROVISIONING_AUTHORIZED = False

#: The registry ``adapter_type`` this adapter serves. R2, B2 and Oracle all
#: declare it; Hugging Face, Drive, OneDrive, Dropbox and Supabase do not, and
#: none of them may be driven through here.
ADAPTER_TYPE = "s3_compatible"

#: The operations this adapter will ask a transport to perform. A closed
#: vocabulary: an adapter that could ask for an arbitrary operation is an
#: adapter through which an arbitrary request could be sent.
OPERATIONS = ("put", "get", "head", "delete")

#: What a ``head`` answer may contain. A row is not trustworthy for having been
#: found, and an unrecognised key is refused rather than ignored.
HEAD_FIELDS = ("size_bytes", "content_sha256", "metadata")

#: How a receipt came by its digest. ``computed`` means this process hashed the
#: bytes; ``provider_asserted`` means a store said so and nothing checked it;
#: ``unknown`` means nobody said anything at all. Only the first is evidence.
DIGEST_SOURCES = ("computed", "provider_asserted", "unknown")

#: The single-request object ceiling. The mesh's own manifest bound is a
#: terabyte, which is a statement about the *mesh*; one PUT is not a terabyte on
#: any S3-compatible service, and a bound nobody can state is a bound nobody
#: enforces. A provider row's ``object_size_limits.max_object_bytes`` narrows
#: this further when the registry states one; it never widens it.
MAX_OBJECT_BYTES = 5 * 1024 * 1024 * 1024

#: The whole attached metadata block. Every field in it is individually bounded,
#: so the largest well-formed set is a few hundred bytes; this cap is therefore
#: unreachable in normal operation and is meant to stay that way. It exists so
#: that a field added later with a careless check still cannot turn an object
#: tag into a payload slot, and the tests assert the gap rather than the cap.
MAX_METADATA_BYTES = 1024

MAX_ENDPOINT = 128
MAX_BUCKET = 63
MAX_KEY_PREFIX = 64

#: ``\Z`` rather than ``$`` throughout. Python's ``$`` also matches immediately
#: before a trailing newline, and a validator looser than the contract it
#: mirrors is a bug this lane has already had to fix once.

#: HTTPS only, host only. No userinfo, so ``https://user:key@host`` cannot
#: smuggle a credential into a field that gets logged; no path and no query, so
#: ``?X-Amz-Signature=`` has nowhere to live; no ``http``, because a zero-cost
#: mesh that ships object bytes in plaintext has saved the wrong resource.
_ENDPOINT_RE = re.compile(
    r"^https://[a-z0-9][a-z0-9.-]{1,60}[a-z0-9](:[0-9]{2,5})?\Z")

#: S3 bucket naming, minus the parts that are not ours to relax: lower-case,
#: 3..63, no underscores, no adjacent dots, not an IP address, and not a bare
#: hex run - a 32-character hex bucket name is indistinguishable from key
#: material, which is the same reason ``validate_object_name`` refuses one.
_BUCKET_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]\Z")
_BUCKET_BAD_RE = re.compile(r"(\.\.|\.-|-\.|^[0-9.]+\Z)")

#: One or two lower-case path segments and a trailing slash, or nothing at all.
#: A prefix is an operator's filing convenience; it is not a name, and anything
#: expressive enough to be one is refused.
_KEY_PREFIX_RE = re.compile(r"^([a-z0-9][a-z0-9_-]{0,31}/){1,2}\Z")

_OBJECT_ID_RE = re.compile(r"^obj_[0-9a-f]{64}\Z")
_SHA256_HEX = 64

#: Fields a caller may attach to the stored object itself. The rest of the
#: manifest is the index's business: it changes as the mesh rebalances, and a
#: copy of it welded to the object would be wrong the moment it moved.
_ATTACHABLE_FIELDS = (
    "version",
    "content_sha256",
    "size_bytes",
    "privacy_class",
    "criticality",
    "storage_tier",
    "lifecycle_state",
    "encryption_state",
    "encryption_scheme_version",
    "mime_type",
    "object_class",
    "retention_class",
    "created_at",
    "reproducible",
)

#: One bounded checker per attachable field, taken from ``metadata.py`` rather
#: than restated. That module already holds the bounded validator for every
#: property of ``storage_object_manifest.schema.json``, and importing it is a
#: deliberate choice: a second, independently-written copy of "what a bounded
#: classifier looks like" is a copy that will drift, and the looser of the two
#: is the one that gets used.
OBJECT_METADATA_VALUE_CHECKS = {
    field: _metadata._RECORD_FIELD_CHECKS[field] for field in _ATTACHABLE_FIELDS
}

#: The other half of the partition, with the reason attached. Together with the
#: table above this covers every property of the manifest schema, and the tests
#: assert that from the schema on disk - so a property added to the contract
#: later is in neither set and fails the test the day it is added, rather than
#: arriving as an unchecked field on an object in somebody's bucket.
REFUSED_METADATA_FIELDS = {
    "object_id": (
        "the object id is the storage key, not a tag; writing it twice invites "
        "the two to disagree and makes the tag the one somebody trusts"),
    "authority": (
        "a stored object asserts no authority; the flag belongs to the manifest "
        "record, where mesh_validator can hold it to const false (Spec S2)"),
    "authority_flags": (
        "the eight authority flags are a property of a manifest record and of "
        "this lane's modules, never of a blob sitting in a bucket (Spec S2)"),
    "encryption": (
        "encryption metadata carries key_ref, nonce and tag. Spec S22 separates "
        "keys from the ciphertext provider, and the ciphertext's own object "
        "tags are the one place they must never be written"),
    "source_provenance": (
        "provenance carries evidence references and a producer id; it is index "
        "state that belongs in the metadata store, and an opaque reference on a "
        "public object is a pointer somebody else can follow"),
    "verification": (
        "verification is what the mesh observed about an object, not what the "
        "object says about itself; a blob asserting hash_verified is a blob "
        "vouching for itself (Spec S15)"),
    "primary_backend": (
        "where an object lives is placement state that changes on every "
        "rebalance; welded to the object it is wrong the moment it moves, and "
        "it is the index's answer in any case (Spec S15)"),
    "replica_backends": (
        "the replica set changes on every rebalance and repair, and an object "
        "tag naming the other providers that hold a copy is a map for anyone "
        "who can read the bucket (Spec S8/S15)"),
    "last_accessed_at": (
        "access time is runtime state the mesh keeps in its index; rewriting "
        "the object to record a read would be a write amplification loop"),
    "last_verified_at": (
        "verification time is what the mesh observed, and an object that dates "
        "its own verification is vouching for itself (Spec S15)"),
}

#: An object whose privacy class the adapter does not know must not leave, and
#: an object whose encryption state it does not know must not leave either.
#: Unknown fails closed rather than defaulting, because either default here
#: would be a guess about privacy.
REQUIRED_METADATA_FIELDS = ("privacy_class", "encryption_state")


# --- errors -------------------------------------------------------------------


class ObjectStoreError(RuntimeError):
    """Base class for object store failures.

    A ``RuntimeError`` rather than a ``ValueError`` on purpose: a refusal of the
    caller's *argument* is a ``ValueError`` and is the caller's bug, while these
    are facts about the far side of the transport and are nobody's bug in
    particular.
    """


class ObjectStoreUnavailable(ObjectStoreError):
    """The store could not be reached, or there is no transport to reach it with.

    Raised rather than returned so it cannot be mistaken for "no such object".
    Absence and unreachability are the same shape and opposite facts, and
    treating the second as the first is how a repair run concludes that an
    object needs re-creating.
    """


class ObjectNotFound(ObjectStoreError):
    """The store was reached and does not hold this object."""


class ObjectIntegrityError(ObjectStoreError):
    """The bytes that came back are not the bytes the address names."""


# --- helpers ------------------------------------------------------------------


def content_digest(payload):
    """The SHA-256 of ``payload``, as lower-case hex.

    ``bytes`` and ``bytearray`` only. A ``str`` is refused rather than encoded:
    picking an encoding on the caller's behalf would make the digest - and
    therefore the object's identity - depend on a guess made here. A
    ``memoryview`` is refused because it can be a non-contiguous or
    non-byte-typed view of something else.
    """
    if not isinstance(payload, (bytes, bytearray)) or isinstance(payload, bool):
        raise ValueError(
            "a payload must be bytes or bytearray, got "
            f"{type(payload).__name__}; text is refused rather than encoded, "
            "because identity in this mesh is the content and an encoding "
            "chosen here would be a guess that changes it")
    return hashlib.sha256(bytes(payload)).hexdigest()


def _now_instant():
    return _datetime.datetime.now(_datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


#: A metadata key is safe to name in a refusal only when its shape makes it a
#: field name. Anything else gets redacted: a caller who builds metadata from a
#: mapping they did not write can put a credential in a *key*, and "unknown
#: field 'X'" that quotes X is the same leak as one that quotes a value.
_SAFE_FIELD_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}\Z")


def _namable(field):
    if isinstance(field, str) and _SAFE_FIELD_NAME_RE.match(field):
        return repr(field)
    return "'<redacted>'"


def _refuse(field, reason):
    """Raise a refusal that names the field and never quotes the value.

    Every other module in this lane echoes the offending value into its message,
    which is right for a manifest built from repository data and wrong here: the
    values crossing this boundary come from a runtime caller, and a refusal that
    quotes its input is a refusal that writes a credential into a log the moment
    somebody passes one to the wrong parameter.

    ``from None`` is load-bearing and not tidiness. The bounded checkers this
    module borrows from ``metadata.py`` do quote their input, and a refusal
    raised from inside the ``except`` that caught one carries it as
    ``__context__`` - which a clean ``str(exc)`` hides and every traceback
    prints, under "During handling of the above exception". Suppressing the
    context is what actually keeps the value out of the log.
    """
    raise ValueError(
        f"object metadata field {_namable(field)} {reason}. The value is deliberately "
        "not quoted: a refusal that echoes its input is how a mistyped "
        "credential reaches a log (Spec S21/S22)") from None


def _bounded(field, value):
    """Run ``metadata.py``'s bounded checker for a field, silently."""
    try:
        OBJECT_METADATA_VALUE_CHECKS[field](value, field=field)
    except Exception:  # noqa: BLE001 - the text is discarded on purpose
        _refuse(field, "is outside the bound the manifest schema sets for it")


def _registry_row(backend_id):
    for row in _mesh_validator.load_providers():
        if row.get("provider_id") == backend_id:
            return row
    return None


# --- receipts -----------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ObjectReceipt:
    """What this process observed about one object at one moment.

    A receipt is a record, not a verdict. ``digest_source`` is the load-bearing
    field: a digest this process computed from bytes it holds is evidence, and a
    digest a store asserted about an object it holds is a claim by the thing
    being checked. ``replication.verify_copy`` recomputes either way and never
    reads the claim as an answer.

    The payload is deliberately not a field. A receipt travels into logs,
    results and metadata, and the object's content must not travel with it.
    """

    object_id: str
    backend_id: str
    content_sha256: str | None
    size_bytes: int
    observed_at: str
    digest_source: str
    verified: bool

    def __post_init__(self):
        if not isinstance(self.object_id, str) or not _OBJECT_ID_RE.match(
                self.object_id):
            raise ValueError(
                "object_id must be 'obj_' followed by a lower-case SHA-256 "
                "digest; identity in this mesh is the content and nothing else")
        _manifest._check_backend(self.backend_id, role="backend_id")
        if self.content_sha256 is not None and (
                not isinstance(self.content_sha256, str)
                or not _manifest._SHA256_RE.match(self.content_sha256)):
            raise ValueError(
                "content_sha256 must be a lower-case SHA-256 digest, or None "
                "where the store asserted nothing at all")
        if (not isinstance(self.size_bytes, int)
                or isinstance(self.size_bytes, bool)
                or not 0 <= self.size_bytes <= MAX_OBJECT_BYTES):
            raise ValueError("size_bytes must be a bounded, non-negative integer")
        _manifest._check_timestamp(self.observed_at, field="observed_at")
        if self.digest_source not in DIGEST_SOURCES:
            raise ValueError(f"digest_source must be one of {DIGEST_SOURCES}")
        if not isinstance(self.verified, bool):
            raise ValueError("verified must be a boolean")

    def as_dict(self):
        """A plain, JSON-safe copy. Nothing here is a handle on anything."""
        return dataclasses.asdict(self)


# --- the store ----------------------------------------------------------------


class ObjectStore:
    """An S3-compatible object store reached through an injected transport.

    Construction validates and binds nothing external: no connection is opened,
    no credential is fetched, no bucket is created or checked. Without a
    ``transport`` the store is simply unusable and every operation fails closed.

    The transport contract is four operations and one shape::

        transport(operation, payload, *, endpoint, bucket, credential)

    ``put``      payload ``{"key", "body", "metadata"}``  -> ``True``
    ``get``      payload ``{"key"}``                      -> ``bytes`` or ``None``
    ``head``     payload ``{"key"}``                      -> mapping or ``None``
    ``delete``   payload ``{"key"}``                      -> ``True``

    The credential is passed as a keyword and never appears in ``payload``,
    because ``payload`` is the part a transport logs.
    """

    #: An adapter is a door, not a decision (Spec S2).
    AUTHORITY = False
    ENCRYPTION_IMPLEMENTED_HERE = False

    def __init__(self, *, backend_id, endpoint, bucket, credential_provider,
                 transport=None, key_prefix="", max_object_bytes=None,
                 clock=None):
        row = self._validated_backend(backend_id)
        self._backend_id = backend_id
        self._external = bool(row.get("external"))
        self._endpoint = self._validated_endpoint(endpoint)
        self._bucket = self._validated_bucket(bucket)
        self._key_prefix = self._validated_key_prefix(key_prefix)
        self._max_object_bytes = self._validated_ceiling(max_object_bytes, row)
        if not callable(credential_provider):
            raise ValueError(
                "credential_provider must be a zero-argument callable that "
                "fetches the key from the runtime secret store at call time. A "
                "literal credential is refused: a secret passed as a value "
                "becomes an attribute, and an attribute reaches a repr, a log "
                "line and a traceback (Spec S22)")
        if transport is not None and not callable(transport):
            raise ValueError("transport must be a callable or None")
        if clock is not None and not callable(clock):
            raise ValueError("clock must be a zero-argument callable or None")
        #: Held as a callable, never as a value. Nothing is fetched here.
        self._credential_provider = credential_provider
        self._transport = transport
        self._clock = clock or _now_instant

    # -- construction-time validation ----------------------------------------

    @staticmethod
    def _validated_backend(backend_id):
        """A registry row, and an S3-compatible one.

        Registry membership is still not admission - whether this row may
        actually receive a byte is ``mesh_validator``'s question and depends on
        runtime state this adapter does not read. What is settled here is only
        that the backend exists and speaks the protocol this file implements:
        Supabase is a metadata index, Hugging Face is an artifact hub, and
        neither becomes an object store by being passed to this constructor.
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
        if row.get("adapter_type") != ADAPTER_TYPE:
            raise ValueError(
                f"backend_id does not declare adapter_type {ADAPTER_TYPE!r} in "
                "the provider registry; a backend does not become an object "
                "store by being handed to an object store")
        return row

    @staticmethod
    def _validated_endpoint(endpoint):
        if not isinstance(endpoint, str):
            raise ValueError(
                f"endpoint must be a string, got {type(endpoint).__name__}")
        if len(endpoint) > MAX_ENDPOINT:
            raise ValueError(
                f"endpoint is over the {MAX_ENDPOINT}-character bound; a URL "
                "field long enough to hold a signed query string is a URL field "
                "that will one day hold one")
        if not _ENDPOINT_RE.match(endpoint):
            raise ValueError(
                "endpoint must be https://<host>[:<port>] with no userinfo, "
                "path or query: 'https://user:key@host' and "
                "'...?X-Amz-Signature=...' are exactly how a credential ends up "
                "in a config file and then in a log")
        _manifest.assert_no_credential_material(endpoint, where="endpoint")
        return endpoint

    @staticmethod
    def _validated_bucket(bucket):
        if not isinstance(bucket, str):
            raise ValueError(
                f"bucket must be a string, got {type(bucket).__name__}")
        if not 3 <= len(bucket) <= MAX_BUCKET:
            raise ValueError(
                f"bucket must be 3..{MAX_BUCKET} characters, which is the "
                "S3-compatible naming rule and not ours to relax")
        if not _BUCKET_RE.match(bucket) or _BUCKET_BAD_RE.search(bucket):
            raise ValueError(
                "bucket must be lower-case [a-z0-9.-], must not contain "
                "adjacent separators and must not be an address literal")
        if _manifest._HEX_TOKEN_RE.match(bucket):
            raise ValueError(
                "bucket is a bare hex run and indistinguishable from key "
                "material, which is why object names are refused the same shape")
        _manifest.assert_no_credential_material(bucket, where="bucket")
        return bucket

    @staticmethod
    def _validated_key_prefix(key_prefix):
        if not isinstance(key_prefix, str):
            raise ValueError(
                f"key_prefix must be a string, got {type(key_prefix).__name__}")
        if key_prefix == "":
            return ""
        if len(key_prefix) > MAX_KEY_PREFIX:
            raise ValueError(
                f"key_prefix is over the {MAX_KEY_PREFIX}-character bound")
        if not _KEY_PREFIX_RE.match(key_prefix):
            raise ValueError(
                "key_prefix must be one or two lower-case segments ending in "
                "'/'. It is a filing convenience, never a name: Spec S7 keeps "
                "filenames, paths and private text out of object naming, and a "
                "prefix expressive enough to be a name is expressive enough to "
                "leak one")
        _manifest.assert_no_credential_material(key_prefix, where="key_prefix")
        return key_prefix

    @staticmethod
    def _validated_ceiling(max_object_bytes, row):
        """The smaller of the module ceiling and the registry's, never larger."""
        ceiling = MAX_OBJECT_BYTES
        limits = row.get("object_size_limits") or {}
        declared = limits.get("max_object_bytes") if isinstance(limits, Mapping) else None
        if isinstance(declared, int) and not isinstance(declared, bool) and declared > 0:
            ceiling = min(ceiling, declared)
        if max_object_bytes is None:
            return ceiling
        if (not isinstance(max_object_bytes, int)
                or isinstance(max_object_bytes, bool)
                or not 1 <= max_object_bytes <= MAX_OBJECT_BYTES):
            raise ValueError(
                "max_object_bytes must be a positive integer no larger than "
                f"{MAX_OBJECT_BYTES}; a caller may narrow this ceiling and "
                "never widen it")
        return min(ceiling, max_object_bytes)

    # -- identity -------------------------------------------------------------

    @property
    def backend_id(self):
        return self._backend_id

    @property
    def key_prefix(self):
        return self._key_prefix

    @property
    def max_object_bytes(self):
        return self._max_object_bytes

    def __repr__(self):
        """Deliberately almost empty.

        A repr reaches logs, tracebacks and debugger dumps. The backend id is a
        registry key and safe; the endpoint, the bucket and the prefix are
        caller-supplied and are simply not worth printing.
        """
        transport = "injected" if self._transport is not None else "none"
        return f"<ObjectStore backend={self._backend_id} transport={transport}>"

    # -- transport ------------------------------------------------------------

    def _call(self, operation, payload):
        if operation not in OPERATIONS:
            raise ValueError(f"unknown object operation {operation!r}")
        if self._transport is None:
            raise ObjectStoreUnavailable(
                "no transport is injected, so this object store cannot be "
                "reached. An adapter without a transport is not a stub standing "
                "in for a real one: it is the honest state of a provider "
                "account nobody has admitted, and it fails closed")
        try:
            credential = self._credential_provider()
        except BaseException:  # noqa: BLE001 - see below
            raise ObjectStoreUnavailable(
                "the credential provider did not return a credential; the "
                "original error is not chained here because a secret-store "
                "failure routinely quotes the thing it failed to fetch"
            ) from None
        try:
            return self._transport(operation, payload,
                                   endpoint=self._endpoint,
                                   bucket=self._bucket,
                                   credential=credential)
        except BaseException:  # noqa: BLE001 - see below
            # Neither re-raised nor chained. A transport's own exception is the
            # single most likely place for a signed URL, an Authorization
            # header or a request body to appear, and `raise ... from exc`
            # prints the cause for anyone who catches this one.
            raise ObjectStoreUnavailable(
                f"the transport failed during {operation!r}. The underlying "
                "error is deliberately not chained: a transport's exception "
                "text routinely carries a signed URL or an Authorization "
                "header (Spec S21/S22)") from None

    def _key(self, object_id):
        if not isinstance(object_id, str) or not _OBJECT_ID_RE.match(object_id):
            raise ValueError(
                "object_id must be 'obj_' followed by a lower-case SHA-256 "
                "digest. Identity in this mesh is the content and only the "
                "content, which is also why no name, path or key can be "
                "written into it (Spec S7). The value is not quoted here")
        return f"{self._key_prefix}{object_id}"

    # -- metadata -------------------------------------------------------------

    def _validated_metadata(self, metadata, *, digest, size_bytes):
        if not isinstance(metadata, Mapping):
            raise ValueError(
                "object metadata must be a mapping, got "
                f"{type(metadata).__name__}")

        for field in metadata:
            if not isinstance(field, str):
                raise ValueError("object metadata keys must be strings")
            if field in REFUSED_METADATA_FIELDS:
                raise ValueError(
                    f"object metadata field {field!r} may never be attached to "
                    f"a stored object: {REFUSED_METADATA_FIELDS[field]}")
            if field not in OBJECT_METADATA_VALUE_CHECKS:
                raise ValueError(
                    f"object metadata rejects the unknown field "
                    f"{_namable(field)}: the "
                    "field set is closed, so 'api_key', 'plaintext_key' and the "
                    "name nobody has thought of yet are all refused by the same "
                    "line rather than by a denylist the next one walks past")

        missing = sorted(set(REQUIRED_METADATA_FIELDS) - set(metadata))
        if missing:
            raise ValueError(
                f"object metadata is missing required field(s) {missing}; an "
                "object whose privacy class or encryption state the adapter "
                "does not know does not leave, because either default here "
                "would be a guess about privacy (Spec S4)")

        attached = {}
        for field in _ATTACHABLE_FIELDS:
            if field not in metadata:
                continue
            value = metadata[field]
            if value is None:
                _refuse(field, "is null; an optional field is omitted rather "
                               "than emitted as null")
            _bounded(field, value)
            attached[field] = value

        self._check_consistency(attached, digest=digest, size_bytes=size_bytes)
        self._check_privacy(attached)

        encoded_length = sum(len(field) + len(repr(value)) + 4
                             for field, value in attached.items())
        if encoded_length > MAX_METADATA_BYTES:
            raise ValueError(
                f"the attached metadata is {encoded_length} bytes, over the "
                f"{MAX_METADATA_BYTES}-byte bound. Every field is individually "
                "bounded, so this is not reachable by a well-formed set: it "
                "means a field has grown a way to hold bulk")
        return attached

    @staticmethod
    def _check_consistency(attached, *, digest, size_bytes):
        """A tag that describes the object must describe *this* object."""
        if attached.get("content_sha256", digest) != digest:
            raise ValueError(
                "object metadata content_sha256 does not match the payload's "
                "digest; a tag that disagrees with the bytes is worse than no "
                "tag, because something will eventually believe it")
        if attached.get("size_bytes", size_bytes) != size_bytes:
            raise ValueError(
                "object metadata size_bytes does not match the payload length")

    @staticmethod
    def _check_privacy(attached):
        """Spec S4/S5, at the last possible moment before the bytes leave.

        This is not a second placement authority. ``placement.py`` decides;
        this is the door declining to open on a decision that was already wrong,
        and it is here because a placement bug that reaches this line is a
        privacy incident rather than a failed test.
        """
        privacy = attached.get("privacy_class")
        encryption_state = attached.get("encryption_state")
        if privacy == "LOCAL_ONLY":
            raise ValueError(
                "a LOCAL_ONLY object is never uploaded to third-party cloud "
                "storage, and an S3-compatible provider is third-party cloud "
                "storage whatever its quota says (Spec S4)")
        if privacy == "CONFIDENTIAL" and encryption_state != "CLIENT_SIDE_ENCRYPTED":
            raise ValueError(
                "a CONFIDENTIAL object leaves owned storage only as ciphertext "
                "(Spec S4/S21). This adapter checks the declared state and "
                "performs no cryptography of its own; encrypting it is Task 6's "
                "contract and must already have happened")
        if encryption_state == "NONE" and "encryption_scheme_version" in attached:
            raise ValueError(
                "encryption_state NONE carries no scheme version; the manifest "
                "schema encodes that as structure and an object tag that "
                "contradicts it is a document nobody agreed to")
        if (encryption_state == "CLIENT_SIDE_ENCRYPTED"
                and "encryption_scheme_version" not in attached):
            raise ValueError(
                "ciphertext must carry its encryption_scheme_version so a "
                "reader knows which contract produced it. The key reference, "
                "nonce and tag stay in the index and never on the ciphertext "
                "provider (Spec S22)")

    # -- the four operations --------------------------------------------------

    def put(self, object_id, payload, metadata):
        """Store ``payload`` under ``object_id``. Returns an ``ObjectReceipt``.

        Nothing leaves this process until the address has been recomputed from
        the bytes, the metadata has been bounded and the privacy class has been
        checked - in that order, so a refusal is a refusal rather than a
        cleanup.
        """
        key = self._key(object_id)
        digest = content_digest(payload)
        body = bytes(payload)
        if len(body) > self._max_object_bytes:
            raise ValueError(
                f"the payload is {len(body)} bytes, over this store's "
                f"{self._max_object_bytes}-byte single-request ceiling")
        if object_id != f"{_manifest.OBJECT_ID_PREFIX}{digest}":
            raise ValueError(
                "object_id is not the digest of this payload. Identity in this "
                "mesh is the content, so storing bytes under an address that is "
                "not theirs would break every verification that follows "
                "(Spec S15). The id is not quoted here")
        attached = self._validated_metadata(metadata, digest=digest,
                                            size_bytes=len(body))

        acknowledged = self._call("put", {"key": key, "body": body,
                                          "metadata": attached})
        if acknowledged is not True:
            raise ObjectStoreError(
                "the transport did not acknowledge the write with True. "
                "Anything else is an unknown outcome, and an unknown write is "
                "not a stored object")
        return ObjectReceipt(
            object_id=object_id,
            backend_id=self._backend_id,
            content_sha256=digest,
            size_bytes=len(body),
            observed_at=self._instant(),
            digest_source="computed",
            verified=True,
        )

    def get(self, object_id):
        """Return the object's bytes, re-hashed before they are handed over."""
        key = self._key(object_id)
        answer = self._call("get", {"key": key})
        if answer is None:
            raise ObjectNotFound(
                "the store does not hold this object. Absence is raised rather "
                "than returned as empty bytes, because an empty object and a "
                "missing one are opposite facts")
        if not isinstance(answer, (bytes, bytearray)) or isinstance(answer, bool):
            raise ObjectStoreError(
                f"the transport returned {type(answer).__name__} where object "
                "bytes were expected; an unrecognised answer is not content")
        body = bytes(answer)
        if content_digest(body) != object_id[len(_manifest.OBJECT_ID_PREFIX):]:
            raise ObjectIntegrityError(
                "the bytes returned are not the bytes this address names. They "
                "are refused rather than returned: a content-addressed mesh "
                "that hands back content not matching its address has one bug, "
                "and pretending otherwise gives it two (Spec S15)")
        return body

    def head(self, object_id):
        """What the store *claims* about the object, or None if it holds none.

        The receipt that comes back carries ``verified=False`` and
        ``digest_source="provider_asserted"``. That is the whole point of the
        method: it is the cheap question, and a cheap answer is a claim.
        """
        key = self._key(object_id)
        answer = self._call("head", {"key": key})
        if answer is None:
            return None
        if not isinstance(answer, Mapping):
            raise ObjectStoreError(
                f"the transport returned {type(answer).__name__} where an "
                "object head was expected")
        unknown = sorted(set(answer) - set(HEAD_FIELDS))
        if unknown:
            raise ObjectStoreError(
                f"the head answer carries unrecognised field(s) {unknown}; a "
                "row is not trustworthy for having been found, and an "
                "unrecognised key is refused rather than ignored")
        digest = answer.get("content_sha256")
        if digest is not None and (not isinstance(digest, str)
                                   or not _manifest._SHA256_RE.match(digest)):
            raise ObjectStoreError(
                "the head answer's content_sha256 is not a SHA-256 digest")
        size = answer.get("size_bytes")
        if size is None:
            size = 0
        if (not isinstance(size, int) or isinstance(size, bool)
                or not 0 <= size <= MAX_OBJECT_BYTES):
            raise ObjectStoreError(
                "the head answer's size_bytes is not a bounded, non-negative "
                "integer")
        return ObjectReceipt(
            object_id=object_id,
            backend_id=self._backend_id,
            content_sha256=digest,
            size_bytes=size,
            observed_at=self._instant(),
            digest_source="provider_asserted" if digest else "unknown",
            verified=False,
        )

    def delete(self, object_id):
        """Remove the object. Returns None.

        Whether a deletion is *allowed* is not this method's question. Spec S15
        and Spec S18 put that gate in ``replication.rebalance_object``, which
        checks the index and the verified replacement first; an adapter that
        decided for itself would be a second lifecycle authority and a much
        easier one to call by accident.
        """
        key = self._key(object_id)
        acknowledged = self._call("delete", {"key": key})
        if acknowledged is not True:
            raise ObjectStoreError(
                "the transport did not acknowledge the delete with True; an "
                "unknown outcome is not a completed deletion, and a caller that "
                "believed it would drop the last verified copy")
        return None

    def _instant(self):
        try:
            value = self._clock()
        except Exception:  # noqa: BLE001 - a clock is an input, not a permission
            raise ObjectStoreError("the injected clock did not return an "
                                   "instant") from None
        _manifest._check_timestamp(value, field="observed_at")
        return value


__all__ = [
    "AUTHORITY", "AUTHORITY_FLAGS", "CANONICAL_AUTHORITY", "ROUTED_BY",
    "ENCRYPTION_IMPLEMENTED_HERE", "CREATES_EXTERNAL_RESOURCES",
    "PROVISIONING_AUTHORIZED", "ADAPTER_TYPE", "OPERATIONS", "HEAD_FIELDS",
    "DIGEST_SOURCES", "MAX_OBJECT_BYTES", "MAX_METADATA_BYTES", "MAX_ENDPOINT",
    "MAX_BUCKET", "MAX_KEY_PREFIX", "OBJECT_METADATA_VALUE_CHECKS",
    "REFUSED_METADATA_FIELDS", "REQUIRED_METADATA_FIELDS", "ObjectStore",
    "ObjectReceipt", "ObjectStoreError", "ObjectStoreUnavailable",
    "ObjectNotFound", "ObjectIntegrityError", "content_digest",
]
