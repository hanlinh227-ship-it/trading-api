"""Federated Free Storage Mesh - the Hugging Face AI-artifact adapter.

Spec S17 admits the Hub for "legitimate models, datasets, AI artifacts and
benchmark corpora suitable for Hub usage" and then says the part that matters:
"It must not be used as a generic log dump." The registry says the same thing in
one field - ``acceptable_use_class: ai-artifacts-only`` - and a sentence in a
registry row stops nobody. This file is that sentence turned into a door.

**Only a declared artifact class gets through.** ``ARTIFACT_CLASSES`` is a
closed vocabulary and the descriptor's ``object_class`` must be in it. There is
deliberately no catch-all member: "ai-artifact" would admit anything anybody was
willing to call one, and a vocabulary that refuses nothing is a comment. The
check runs the lane's own classifier bound first and the vocabulary second, so
it can only ever be the stricter of the two.

**The Hub serves one tier.** COLD, which is what the registry row says and what
Spec S6 means by an archive of models, datasets and benchmark corpora. CANONICAL
belongs to GitHub, METADATA to the object index, and a descriptor naming either
is a placement that went wrong before it reached this file.

**A repository is addressed, never created.** There is no ``create_repo``, no
``ensure_repo`` and no SDK to call one with: ``repo_id`` is a bounded, validated
string naming a repository a human with authorization made, and the adapter is
simply unusable without an injected transport. Spec S25's honesty about the
Supabase project applies here unchanged - an account nobody has connected is
unhealthy rather than empty.

The rest is the discipline the S3 adapter established, reused rather than
restated: identity recomputed and never accepted, a credential that is a
zero-argument provider called at request time and never a parameter or an
attribute, no HTTP client anywhere, refusals that name a field and never quote a
value, and bounded checkers bound from ``metadata.py`` through ``s3_object.py``
as the identical callables.

No cryptography is implemented, chosen or performed here. Nothing here is an
authority; GitHub stays canonical.
"""

from __future__ import annotations

import re
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

#: The registry ``adapter_type`` this adapter serves, and the only backend row
#: that declares it.
ADAPTER_TYPE = "huggingface_hub"
ACCEPTABLE_USE_CLASS = "ai-artifacts-only"

#: Spec S6/S17: the Hub is a cold archive of models, datasets and benchmark
#: corpora. Checked against the registry row at construction time.
TIERS_ALLOWED = ("COLD",)

#: Spec S17's sentence as a closed vocabulary. Every member is a classifier the
#: lane's own ``validate_object_name`` accepts, and there is no catch-all: a
#: class named "artifact", "data" or "ai-artifact" would admit the log dump the
#: spec forbids by the simple method of calling it an artifact. Adding a member
#: is a deliberate edit to this tuple, which is the point.
ARTIFACT_CLASSES = (
    "model",
    "model-weights",
    "tokenizer",
    "dataset",
    "benchmark-corpus",
    "eval-results",
)

#: Hub repository kinds. Spaces are an application surface rather than an
#: artifact archive and are not among them.
REPO_TYPES = ("model", "dataset")

#: The operations this adapter will ask a transport to perform. A closed
#: vocabulary, and no destructive verb: Spec S15/S18 keep deletion behind
#: ``replication.rebalance_object``, which checks the index and a verified
#: replacement first.
OPERATIONS = ("upload_artifact", "list_artifacts", "fetch_artifact")

#: The whole descriptor block, bounded as a unit and to the same number the S3
#: adapter uses, so the two cannot drift.
MAX_DESCRIPTOR_BYTES = _s3.MAX_METADATA_BYTES

#: A path prefix inside the repository, under the same rule and the same bound
#: as the S3 adapter's key prefix - called rather than copied. It is a filing
#: convenience; the artifact's name is its content address and nothing else.
MAX_PATH_PREFIX = _s3.MAX_KEY_PREFIX

MAX_REPO_ID = 96

#: ``namespace/name``, lower-case, no userinfo, no scheme, no query. ``\Z``
#: rather than ``$``, because Python's ``$`` also matches before a trailing
#: newline. A repo id that could hold ``user:token@host`` is a repo id that will
#: one day hold one.
_REPO_ID_RE = re.compile(
    r"^[a-z0-9][a-z0-9._-]{1,38}/[a-z0-9][a-z0-9._-]{1,62}\Z")


def _check_artifact_class(value, *, field):
    """The lane's classifier bound, then Spec S17's vocabulary.

    The borrowed checker runs first, so this can only ever be stricter than the
    bound the manifest schema sets - it refuses the shapes a classifier may not
    have (over-long, upper-case, bare hex, credential-shaped, a path) and this
    then refuses the classifiers the Hub may not hold.
    """
    _s3.OBJECT_METADATA_VALUE_CHECKS["object_class"](value, field=field)
    if value not in ARTIFACT_CLASSES:
        raise ValueError(
            f"{field} is not one of the declared AI artifact classes "
            f"{ARTIFACT_CLASSES}. Spec S17 admits models, datasets and "
            "benchmark corpora to the Hub and says the Hub is not a generic "
            "log dump; an artifact class nobody declared is refused rather "
            "than warned about. The value is deliberately not quoted")


#: The accepted half of the descriptor partition, bound from
#: ``s3_object.OBJECT_METADATA_VALUE_CHECKS`` - itself built from
#: ``metadata._RECORD_FIELD_CHECKS``, the module that holds one bounded
#: validator per property of the manifest schema. The tests assert identity with
#: ``is``, so a hand-written copy of these bounds fails rather than drifts.
ARTIFACT_DESCRIPTOR_VALUE_CHECKS = dict(_s3.OBJECT_METADATA_VALUE_CHECKS)

#: The one field whose borrowed checker is not sufficient at this boundary.
#: Overridden rather than replaced: the schema bound still runs first inside it.
ARTIFACT_DESCRIPTOR_VALUE_CHECKS["object_class"] = _check_artifact_class

#: The field list, derived from the checker table rather than written beside it,
#: so a field with no check cannot be an allowed field.
ARTIFACT_DESCRIPTOR_FIELDS = tuple(ARTIFACT_DESCRIPTOR_VALUE_CHECKS)

#: The fields whose borrowed checker this boundary overrides, declared rather
#: than discovered. Every other entry in the table above is the *identical*
#: callable the lane already uses, asserted with ``is`` by the tests; an
#: override that is not named here is a copy somebody wrote by hand, which is
#: the thing that drifts. An override may only ever be stricter, and each one
#: runs the borrowed checker first.
DESCRIPTOR_CHECK_OVERRIDES = ("object_class",)

#: The other half of the partition, with the reason attached. Together these two
#: tables cover every property of the manifest schema, and the tests assert that
#: from the schema on disk - so a property added to the contract later is in
#: neither table and fails the day it is added, rather than arriving as an
#: unchecked field on a file in a public model repository.
REFUSED_DESCRIPTOR_FIELDS = {
    "object_id": (
        "the object id is the artifact's path in the repository, not a field "
        "inside it; writing it twice invites the two to disagree and makes the "
        "copy the one somebody trusts"),
    "authority": (
        "an uploaded artifact asserts no authority; the flag belongs to the "
        "manifest record, where mesh_validator can hold it to const false "
        "(Spec S2)"),
    "authority_flags": (
        "the eight authority flags are a property of a manifest record and of "
        "this lane's modules, never of a file in a model repository (Spec S2)"),
    "encryption": (
        "encryption metadata carries key_ref, nonce and tag. Spec S22 separates "
        "keys from the ciphertext provider, and a Hub repository is about as "
        "public a place as a key could be published"),
    "source_provenance": (
        "provenance carries evidence references and a producer id; it is index "
        "state that belongs in the metadata store, and an opaque reference on a "
        "public artifact is a pointer anyone can follow"),
    "verification": (
        "verification is what the mesh observed about an object, not what the "
        "object says about itself; an artifact asserting hash_verified is an "
        "artifact vouching for itself (Spec S15)"),
    "primary_backend": (
        "where an object lives is placement state that changes on every "
        "rebalance; welded to the artifact it is wrong the moment it moves, and "
        "publishing the mesh's backend list is a map anyone can read "
        "(Spec S8/S15)"),
    "replica_backends": (
        "the replica set changes on every repair, and naming the providers that "
        "hold a copy is that same map with more entries on it (Spec S8/S15)"),
    "last_accessed_at": (
        "access time is runtime state the mesh keeps in its index; rewriting an "
        "artifact to record a read would be a write amplification loop into a "
        "repository's revision history"),
    "last_verified_at": (
        "verification time is what the mesh observed, and an artifact that "
        "dates its own verification is vouching for itself (Spec S15)"),
}

#: An artifact whose privacy class the adapter does not know must not leave, one
#: whose encryption state it does not know must not leave, one that does not say
#: which tier it belongs to is not placed, and one that does not declare what
#: kind of artifact it is is exactly the upload Spec S17 refuses. Unknown fails
#: closed rather than defaulting.
REQUIRED_DESCRIPTOR_FIELDS = (
    "privacy_class", "encryption_state", "storage_tier", "object_class",
)


# --- errors -------------------------------------------------------------------


class ArtifactStoreError(_s3.ObjectStoreError):
    """Base class for artifact-hub failures.

    Derived from the lane's existing object-store error so that a caller
    already catching the lane's failures catches these too.
    """


class ArtifactStoreUnavailable(ArtifactStoreError):
    """The hub could not be reached, or there is no transport to reach it with.

    Raised rather than returned so it cannot be mistaken for "no such
    artifact". Absence and unreachability are the same shape and opposite facts.
    """


class ArtifactNotFound(ArtifactStoreError):
    """The repository was reached and holds no artifact at that address."""


class ArtifactIntegrityError(ArtifactStoreError):
    """The bytes that came back are not the bytes the address names."""


# --- helpers ------------------------------------------------------------------


def _bounded(field, value):
    """Run this module's bounded checker for a field, silently.

    Dispatches through ``ARTIFACT_DESCRIPTOR_VALUE_CHECKS`` so the table this
    module publishes is the table it enforces. The checker's own message is
    discarded because those checkers quote their input - right for a manifest
    built from repository data, wrong at a boundary a runtime caller reaches.
    """
    try:
        ARTIFACT_DESCRIPTOR_VALUE_CHECKS[field](value, field=field)
    except Exception:  # noqa: BLE001 - the text is discarded on purpose
        _s3._refuse(field, "is outside the bound the manifest schema sets for "
                           "it, or is not a declared AI artifact class")


def _registry_row(backend_id):
    for row in _mesh_validator.load_providers():
        if row.get("provider_id") == backend_id:
            return row
    return None


# --- the store ----------------------------------------------------------------


class HuggingFaceArtifactStore:
    """A Hub repository reached through an injected transport.

    Construction validates and binds nothing external: no connection is opened,
    no credential is fetched, no repository is created or checked for
    existence. Without a ``transport`` the store is unusable and every operation
    fails closed.

    The transport contract is three operations and one shape::

        transport(operation, payload, *, repo_id, repo_type, credential)

    ``upload_artifact``  payload ``{"path", "body", "descriptor"}`` -> ``True``
    ``list_artifacts``   payload ``{}``                             -> list of paths
    ``fetch_artifact``   payload ``{"path"}``                       -> ``bytes`` or ``None``

    The credential is passed as a keyword and never appears in ``payload``,
    because ``payload`` is the part a transport logs.
    """

    #: An adapter is a door, not a decision (Spec S2).
    AUTHORITY = False
    ENCRYPTION_IMPLEMENTED_HERE = False

    def __init__(self, *, repo_id, repo_type, credential_provider,
                 backend_id="huggingface_hub", transport=None, clock=None,
                 path_prefix=""):
        row = self._validated_backend(backend_id)
        self._backend_id = backend_id
        self._repo_id = self._validated_repo_id(repo_id)
        self._repo_type = self._validated_repo_type(repo_type)
        self._path_prefix = _s3.ObjectStore._validated_key_prefix(path_prefix)
        self._max_object_bytes = self._validated_ceiling(row)
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
        """A registry row, and the Hugging Face one.

        Registry membership is still not admission. What is settled here is that
        the backend exists, declares this adapter's type, carries the
        artifacts-only role and serves the tier this adapter serves - so a
        bucket does not become an artifact hub by being handed to one.
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
                "the provider registry")
        if row.get("acceptable_use_class") != ACCEPTABLE_USE_CLASS:
            raise ValueError(
                f"backend_id is not registered with the {ACCEPTABLE_USE_CLASS!r} "
                "role; Spec S17 admits the Hub for AI artifacts and nothing "
                "else")
        if tuple(row.get("tiers_allowed") or ()) != TIERS_ALLOWED:
            raise ValueError(
                f"backend_id does not serve exactly the tiers {TIERS_ALLOWED}")
        return row

    @staticmethod
    def _validated_repo_id(repo_id):
        if not isinstance(repo_id, str):
            raise ValueError(
                f"repo_id must be a string, got {type(repo_id).__name__}")
        if len(repo_id) > MAX_REPO_ID:
            raise ValueError(
                f"repo_id is over the {MAX_REPO_ID}-character bound; an "
                "identifier field long enough to hold a token is one that will "
                "one day hold one")
        if not _REPO_ID_RE.match(repo_id):
            raise ValueError(
                "repo_id must be '<namespace>/<name>', lower-case, with no "
                "scheme, userinfo, query or extra path segments: a URL "
                "carrying 'user:token@host' and one carrying a token query "
                "parameter are exactly how a credential ends up in a config "
                "file and then in a log. The value is deliberately not quoted")
        for part in repo_id.split("/"):
            if _manifest._HEX_TOKEN_RE.match(part):
                raise ValueError(
                    "repo_id carries a bare hex run, which is indistinguishable "
                    "from key material wherever it appears")
        _manifest.assert_no_credential_material(repo_id, where="repo_id")
        return repo_id

    @staticmethod
    def _validated_repo_type(repo_type):
        if repo_type not in REPO_TYPES:
            raise ValueError(
                f"repo_type must be one of {REPO_TYPES}; a Space is an "
                "application surface rather than an artifact archive, and the "
                "value handed in is deliberately not quoted")
        return repo_type

    @staticmethod
    def _validated_ceiling(row):
        """The module ceiling, narrowed by the registry and never widened.

        The S3 adapter's single-request ceiling is the mesh's number for "one
        request is not a terabyte"; the registry narrows it when a row states an
        observed limit. No row states one today, which is the honest state of a
        provider nobody has probed.
        """
        ceiling = _s3.MAX_OBJECT_BYTES
        limits = row.get("object_size_limits") or {}
        declared = limits.get("max_object_bytes") if isinstance(limits, Mapping) else None
        if isinstance(declared, int) and not isinstance(declared, bool) and declared > 0:
            ceiling = min(ceiling, declared)
        return ceiling

    # -- identity -------------------------------------------------------------

    @property
    def backend_id(self):
        return self._backend_id

    @property
    def repo_type(self):
        return self._repo_type

    @property
    def max_object_bytes(self):
        return self._max_object_bytes

    def __repr__(self):
        """Deliberately almost empty: a repr reaches logs and debugger dumps."""
        transport = "injected" if self._transport is not None else "none"
        return (f"<HuggingFaceArtifactStore backend={self._backend_id} "
                f"transport={transport}>")

    # -- transport ------------------------------------------------------------

    def _call(self, operation, payload):
        if operation not in OPERATIONS:
            raise ValueError(f"unknown artifact operation {operation!r}")
        if self._transport is None:
            raise ArtifactStoreUnavailable(
                "no transport is injected, so this artifact repository cannot "
                "be reached. An adapter without a transport is not a stub "
                "standing in for a real one: it is the honest state of a "
                "provider account nobody has admitted, and it fails closed")
        try:
            credential = self._credential_provider()
        except BaseException:  # noqa: BLE001 - see below
            raise ArtifactStoreUnavailable(
                "the credential provider did not return a credential; the "
                "original error is not chained here because a secret-store "
                "failure routinely quotes the thing it failed to fetch"
            ) from None
        try:
            return self._transport(operation, payload,
                                   repo_id=self._repo_id,
                                   repo_type=self._repo_type,
                                   credential=credential)
        except BaseException:  # noqa: BLE001 - see below
            # Neither re-raised nor chained: a transport's exception is the most
            # likely place for an authorization header or a request body to
            # appear, and ``raise ... from exc`` prints the cause to anyone who
            # catches this one.
            raise ArtifactStoreUnavailable(
                f"the transport failed during {operation!r}. The underlying "
                "error is deliberately not chained: a transport's exception "
                "text routinely carries an authorization header (Spec S21/S22)"
            ) from None

    def _path(self, object_id):
        if not isinstance(object_id, str) or not _s3._OBJECT_ID_RE.match(object_id):
            raise ValueError(
                "object_id must be 'obj_' followed by a lower-case SHA-256 "
                "digest. Identity in this mesh is the content and only the "
                "content, which is also why no name, path or key can be written "
                "into it (Spec S7). The value is not quoted here")
        return f"{self._path_prefix}{object_id}"

    def _instant(self):
        try:
            value = self._clock()
        except Exception:  # noqa: BLE001 - a clock is an input, not a permission
            raise ArtifactStoreError("the injected clock did not return an "
                                     "instant") from None
        try:
            _manifest._check_timestamp(value, field="observed_at")
        except Exception:  # noqa: BLE001 - the text is discarded on purpose
            _s3._redacted(ArtifactStoreError,
                          "the injected clock did not return an RFC 3339 "
                          "instant. Its answer is deliberately not quoted: a "
                          "clock is an injected input like any other "
                          "(Spec S21/S22)")
        return value

    # -- the descriptor -------------------------------------------------------

    def _validated_descriptor(self, descriptor, *, digest, size_bytes):
        if not isinstance(descriptor, Mapping):
            raise ValueError(
                "an artifact descriptor must be a mapping, got "
                f"{_s3._type_name(descriptor)}")

        for field in descriptor:
            if not isinstance(field, str):
                raise ValueError("artifact descriptor keys must be strings")
            if field in REFUSED_DESCRIPTOR_FIELDS:
                raise ValueError(
                    f"artifact descriptor field {field!r} may never be uploaded "
                    f"with an artifact: {REFUSED_DESCRIPTOR_FIELDS[field]}")
            if field not in ARTIFACT_DESCRIPTOR_VALUE_CHECKS:
                raise ValueError(
                    f"the artifact descriptor rejects the unknown field "
                    f"{_s3._namable(field)}: the field set is closed, so "
                    "'api_key', 'plaintext_key' and the name nobody has thought "
                    "of yet are all refused by the same line rather than by a "
                    "denylist the next one walks past")

        missing = sorted(set(REQUIRED_DESCRIPTOR_FIELDS) - set(descriptor))
        if missing:
            raise ValueError(
                f"the artifact descriptor is missing required field(s) "
                f"{missing}; an upload that does not declare what kind of "
                "artifact it is, what privacy class it carries, whether it is "
                "ciphertext and which tier it belongs to is exactly the upload "
                "Spec S17 refuses")

        attached = {}
        for field in ARTIFACT_DESCRIPTOR_FIELDS:
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
                "individually bounded, so this is not reachable by a "
                "well-formed descriptor: it means a field has grown a way to "
                "hold bulk")
        return attached

    @staticmethod
    def _check_consistency(attached, *, digest, size_bytes):
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
        if attached.get("storage_tier") not in TIERS_ALLOWED:
            raise ValueError(
                f"the Hub serves the tiers {TIERS_ALLOWED} and this descriptor "
                "names another. CANONICAL is GitHub's and METADATA is the "
                "object index's; neither is a model repository's (Spec S6/S17)")

    @staticmethod
    def _check_privacy(attached):
        """Spec S4/S5, at the last possible moment before the bytes leave."""
        privacy = attached.get("privacy_class")
        encryption_state = attached.get("encryption_state")
        if privacy == "LOCAL_ONLY":
            raise ValueError(
                "a LOCAL_ONLY object is never uploaded to third-party cloud "
                "storage, and a public artifact hub is third-party cloud "
                "storage with an audience attached (Spec S4)")
        if privacy == "CONFIDENTIAL" and encryption_state != "CLIENT_SIDE_ENCRYPTED":
            raise ValueError(
                "a CONFIDENTIAL object leaves owned storage only as ciphertext "
                "(Spec S4/S21). This adapter checks the declared state and "
                "performs no cryptography of its own")
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
                "nonce and tag stay in the index and never travel to the "
                "ciphertext's provider (Spec S22)")

    # -- the three operations -------------------------------------------------

    def upload_artifact(self, object_id, payload, descriptor):
        """Publish one declared AI artifact. Returns an ``ObjectReceipt``.

        Nothing leaves this process until the address has been recomputed from
        the bytes, the descriptor has been bounded, the artifact class has been
        checked against the declared vocabulary, the tier has been checked and
        the privacy class has been checked.
        """
        path = self._path(object_id)
        digest = _s3.content_digest(payload)
        body = bytes(payload)
        if len(body) > self._max_object_bytes:
            raise ValueError(
                f"the artifact is {len(body)} bytes, over this store's "
                f"{self._max_object_bytes}-byte single-request ceiling")
        if object_id != f"{_manifest.OBJECT_ID_PREFIX}{digest}":
            raise ValueError(
                "object_id is not the digest of this payload. Identity in this "
                "mesh is the content, so storing bytes under an address that is "
                "not theirs would break every verification that follows "
                "(Spec S15). The id is not quoted here")
        attached = self._validated_descriptor(descriptor, digest=digest,
                                              size_bytes=len(body))

        acknowledged = self._call("upload_artifact", {"path": path, "body": body,
                                                      "descriptor": attached})
        if acknowledged is not True:
            raise ArtifactStoreError(
                "the transport did not acknowledge the upload with True. "
                "Anything else is an unknown outcome, and an unknown upload is "
                "not a stored artifact")
        return _s3.ObjectReceipt(
            object_id=object_id,
            backend_id=self._backend_id,
            content_sha256=digest,
            size_bytes=len(body),
            observed_at=self._instant(),
            digest_source="computed",
            verified=True,
        )

    def list_artifacts(self):
        """The object ids this repository holds, as a tuple.

        A ``str`` and a ``bytes`` are both sequences, and iterating either one
        yields characters or integers that are not object ids - so the answer
        must be a ``list`` and nothing else. An unrecognised answer is refused
        rather than iterated.
        """
        answer = self._call("list_artifacts", {})
        if isinstance(answer, (str, bytes, bytearray)) or not isinstance(answer, list):
            raise ArtifactStoreError(
                f"the transport returned {_s3._type_name(answer)} where a list "
                "of artifact paths was expected; an unrecognised answer is not "
                "an empty repository")
        found = []
        for entry in answer:
            if not isinstance(entry, str) or not entry.startswith(self._path_prefix):
                raise ArtifactStoreError(
                    "a listed artifact path is not under this store's prefix; "
                    "the path is deliberately not quoted, because a listing "
                    "comes from the far side of the transport")
            object_id = entry[len(self._path_prefix):]
            if not _s3._OBJECT_ID_RE.match(object_id):
                raise ArtifactStoreError(
                    "a listed artifact path is not a content address. A "
                    "repository is a shared surface and a file the mesh did not "
                    "write is reported rather than adopted (Spec S7/S15)")
            found.append(object_id)
        return tuple(found)

    def fetch_artifact(self, object_id):
        """Return one artifact's bytes, re-hashed before they are handed over."""
        path = self._path(object_id)
        answer = self._call("fetch_artifact", {"path": path})
        if answer is None:
            raise ArtifactNotFound(
                "this repository holds no artifact at that address. Absence is "
                "raised rather than returned as empty bytes, because an empty "
                "artifact and a missing one are opposite facts")
        if not isinstance(answer, (bytes, bytearray)) or isinstance(answer, bool):
            raise ArtifactStoreError(
                f"the transport returned {_s3._type_name(answer)} where "
                "artifact bytes were expected; an unrecognised answer is not "
                "content")
        body = bytes(answer)
        if _s3.content_digest(body) != object_id[len(_manifest.OBJECT_ID_PREFIX):]:
            raise ArtifactIntegrityError(
                "the bytes returned are not the bytes this address names. They "
                "are refused rather than returned: a public repository is a "
                "surface other people can commit to, and a mesh that hands back "
                "content not matching its address has one bug while pretending "
                "otherwise gives it two (Spec S15)")
        return body


__all__ = [
    "AUTHORITY", "AUTHORITY_FLAGS", "CANONICAL_AUTHORITY", "ROUTED_BY",
    "ENCRYPTION_IMPLEMENTED_HERE", "CREATES_EXTERNAL_RESOURCES",
    "PROVISIONING_AUTHORIZED", "ADAPTER_TYPE", "ACCEPTABLE_USE_CLASS",
    "TIERS_ALLOWED", "ARTIFACT_CLASSES", "REPO_TYPES", "OPERATIONS",
    "MAX_DESCRIPTOR_BYTES", "MAX_PATH_PREFIX", "MAX_REPO_ID",
    "ARTIFACT_DESCRIPTOR_VALUE_CHECKS", "ARTIFACT_DESCRIPTOR_FIELDS",
    "DESCRIPTOR_CHECK_OVERRIDES",
    "REFUSED_DESCRIPTOR_FIELDS", "REQUIRED_DESCRIPTOR_FIELDS",
    "HuggingFaceArtifactStore", "ArtifactStoreError",
    "ArtifactStoreUnavailable", "ArtifactNotFound", "ArtifactIntegrityError",
]
