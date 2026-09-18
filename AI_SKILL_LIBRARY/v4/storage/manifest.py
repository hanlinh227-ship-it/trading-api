"""Federated Free Storage Mesh - typed manifest model and object identity.

Task 1 checked in the contracts. ``storage_object_manifest.schema.json`` says
what a manifest record may look like and ``mesh_validator.py`` says whether the
backends one names were actually admitted, but neither of them *builds* a
record. Until now every manifest in the lane was a dict literal typed out by
hand, which is a workable way to test a schema and a poor way for the rest of
the mesh to produce rows: the next caller types the dict out too, forgets
``authority_flags``, spells ``origin_class`` as ``kind``, and finds out at
runtime or not at all.

This module is the one typed producer. It is read-only and pure in the same
sense as ``mesh_validator``: it opens no connection, activates no provider
account, touches no credential, writes nothing and performs no cryptography. It
decides no placement either - that is Task 3 - and an object whose home nobody
has chosen yet stays on owned local storage, because defaulting to an external
backend would *be* a placement decision.

Three properties are worth stating, because each one is the answer to a
specific way this goes wrong.

**Identity is the content, and only the content.** ``object_id`` is
``obj_`` + the SHA-256 of the bytes, matching the schema's pattern exactly. It
does not depend on the provider, the tier, the privacy class or the time, so
re-tiering, rebalancing and replication (Spec S15) do not change what an object
*is*. That is also the privacy control: Spec S7 requires that object names carry
no secrets and no unnecessary private text, and a digest is the only shape that
cannot carry any. ``users/alice/tax-return-2025.pdf`` is not rejected by review,
it is unrepresentable.

**A "name" is not an identity.** ``policy.yaml`` object_naming says
``content_addressed: true`` and ``human_readable_names_allowed: false``. No
manifest field is a filename or a storage key. The only human-chosen strings
that reach a manifest are the small controlled-vocabulary classifiers -
``object_class``, ``retention_class``, ``origin_class``, ``producer_id`` - and
``validate_object_name`` is the guard on exactly those. It is deliberately
strict enough that an ``object_id`` fails it: if a digest were an acceptable
name, a name would be an acceptable id.

**Unknown fields are refused structurally.** The plan names six secret-bearing
fields to reject. Six names is a denylist and a denylist is bypassed by the
seventh, so the rejection here is not about those names at all: the model
enumerates the fields it accepts, every other keyword lands in ``**unknown``,
and ``**unknown`` is an error. Nested mappings are whitelisted the same way
against the schema's own closed field sets. Only *on top of* that structural
refusal do values get scanned for the shapes credentials actually have, because
a leaked token rarely arrives under a key helpfully named ``secret``.

Everything here fails closed by raising ``ValueError``. ``mesh_validator``
returns lists because it reports on documents that already exist; this module
refuses to *create* an invalid one, and a half-built manifest has no useful
partial form.
"""

from __future__ import annotations

import dataclasses
import datetime as _datetime
import hashlib
import re
import threading
from functools import lru_cache
from types import MappingProxyType

from AI_SKILL_LIBRARY.v4.storage import (
    AUTHORITY_FLAGS,
    CANONICAL_AUTHORITY,
    CRITICALITY_CLASSES,
    LIFECYCLE_STATES,
    PRIVACY_CLASSES,
    STORAGE_TIERS,
)
from AI_SKILL_LIBRARY.v4.storage import mesh_validator

#: This module holds no authority of any kind, matching the rest of the lane.
AUTHORITY = False

#: Spec S21 and policy.yaml ``encryption.implemented_here``. This module names
#: encryption metadata fields and checks their shape. It chooses no algorithm,
#: derives no key and performs no cryptography; there is deliberately no
#: ``encrypt``/``decrypt``/``derive_key`` symbol here to import by mistake.
ENCRYPTION_IMPLEMENTED_HERE = False

#: ``version`` in the schema is ``const: 1``.
MANIFEST_VERSION = 1

#: Where an object lives until a placement engine says otherwise. Not a
#: provider choice: it is the absence of one, expressed so that it fails closed.
DEFAULT_BACKEND_ID = "local_owned_store"

OBJECT_ID_PREFIX = "obj_"

# --- shapes mirrored from storage_object_manifest.schema.json ----------------
# Mirrored rather than parsed so that construction stays pure and import-time
# cheap. Drift is not left to trust: test_storage_manifest asserts that the
# model's field set equals the schema's property set in both directions and
# that every shape this model can emit validates against the schema on disk.

# Every anchored validator here ends in ``\Z`` rather than ``$``. Python's
# ``$`` also matches immediately before a final newline, so ``"a" * 64 + "\n"``
# passed as a SHA-256 digest and produced a 69-character object_id that the
# schema refuses at maxLength 68. JSON Schema's ``$`` does not behave that way,
# and a validator that is looser than the schema it mirrors is the whole bug
# class this module exists to close.
_CLASS_TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,39}\Z")
_CLASS_TOKEN_MAX = 40
_HEX_TOKEN_RE = re.compile(r"^[0-9a-f]{16,}\Z")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}\Z")
_MIME_RE = re.compile(r"^[a-z0-9][a-z0-9.+-]{0,62}/[a-z0-9][a-z0-9.+-]{0,62}\Z")
_TIMESTAMP_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"([.][0-9]{1,9})?(Z|[+-][0-9]{2}:[0-9]{2})\Z")

#: The schema caps ``evidence_ref`` at 200 characters; the second alternative
#: here was unbounded (``*``), and ``[A-Za-z0-9._/-]`` is a superset of URL-safe
#: base64 and of hex, so the field was a carrier: a review put 2048 characters
#: of opaque material into ``evidence/<...>.dat`` and the model accepted it on
#: both ``source_provenance`` and ``verification``. The quantifiers are bounded
#: to keep the model a strict subset of the schema, and ``_check_evidence_ref``
#: enforces the length and the per-segment opacity rules a pattern states badly.
_EVIDENCE_REF_MAX = 200
_EVIDENCE_REF_RE = re.compile(
    r"^(?:[a-z][a-z0-9+.-]{1,31}://[A-Za-z0-9][A-Za-z0-9._~:/-]{2,180}"
    r"|[A-Za-z0-9][A-Za-z0-9._/-]{0,150}/[A-Za-z0-9][A-Za-z0-9._-]{0,60}"
    r"[.][A-Za-z0-9]{1,16})\Z")

#: Separators inside an evidence reference. What lies *between* them is one
#: undifferentiated run, and a long one is not a path segment - the review got
#: ``evidence/`` + a 64-character hex string and a 39-character AWS-secret-shaped
#: run through both the pattern and the credential scan at well under 200
#: characters. Applied here the way ``validate_object_name`` already applies it.
_EVIDENCE_SEGMENT_SPLIT_RE = re.compile(r"[/:._~+-]+")
_EVIDENCE_SEGMENT_MAX = 31

#: A segment-length bound alone is defeated by the separators themselves. The
#: review's actual input was ``wJalrXUtnFEMI-K7MDENG-bPxRfiCYEXAMPLEKEY``, and
#: because ``-`` is a separator that splits into three short runs and walks
#: through. What distinguishes it from a path segment is not its length but its
#: alphabet: every legitimate evidence reference in this repository is built
#: from words - ``CHECKPOINTS``, ``evidence``, ``r2_probe``,
#: ``WAVE0_CAPABILITY_SMOLLM2_360M`` - and a word segment is upper or lower, not
#: both at once. Base64 key material mixes the two freely, so the alphabet is
#: the signal rather than the length. Digits are deliberately *not* required:
#: ``bPxRfiCYEXAMPLEKEY`` has none, and requiring them let it through.
_EVIDENCE_OPAQUE_MIN = 16
_HAS_LOWER_RE = re.compile(r"[a-z]")
_HAS_UPPER_RE = re.compile(r"[A-Z]")

#: Spec S22. The schemes are the key *locations* the spec allows - an
#: environment secret store, an owned worker secret store, an authorized
#: secret-management backend. An object-storage URL is not among them, which is
#: how key/ciphertext separation is enforced rather than merely recommended.
_KEY_REF_RE = re.compile(
    r"^(env|secretstore|worker-secret|kms)://[A-Za-z0-9][A-Za-z0-9._/-]{2,180}\Z")

ENCRYPTION_STATES = ("NONE", "CLIENT_SIDE_ENCRYPTED")

#: Closed field sets, taken from the schema's ``additionalProperties: false``
#: objects. These are whitelists: a key that is not here is refused whatever it
#: is called.
_PROVENANCE_FIELDS = ("origin_class", "producer_id", "evidence_ref")
_VERIFICATION_FIELDS = ("hash_verified", "verified_replica_count",
                        "last_probe_at", "evidence_ref")
_ENCRYPTION_FIELDS = ("algorithm", "scheme_version", "key_ref",
                      "key_rotation_generation", "nonce", "tag")

#: ``$defs.encryption_metadata`` bounds for ``nonce`` and ``tag``: long enough
#: for a 12-byte nonce and a 16-byte authentication tag, too short for a 256-bit
#: key (44 characters as base64, 64 as hex). Mirrored rather than loaded so that
#: construction stays pure, and asserted equal to the schema in the tests - the
#: three fields below were previously admitted with no check of any kind, so the
#: model emitted documents the checked-in schema rejects.
_OPAQUE_TOKEN_RE = re.compile(r"^[A-Za-z0-9+/=_-]{8,32}\Z")
_OPAQUE_TOKEN_MIN = 8
_OPAQUE_TOKEN_MAX = 32
_KEY_ROTATION_MIN = 0
_KEY_ROTATION_MAX = 65535
_SCHEME_VERSION_MIN = 1
_SCHEME_VERSION_MAX = 4096

_MAX_SIZE_BYTES = 1099511627776
_MAX_REPLICAS = 8

# --- name safety ------------------------------------------------------------

#: Segments that make a classifier a place where secret or private text is
#: about to be written. Compared against whole segments of the name (split on
#: ``-``, ``_`` and ``.``) rather than as substrings, so a legitimate token is
#: not rejected for containing "key" inside "monkey".
_SENSITIVE_SEGMENTS = frozenset({
    "key", "keys", "secret", "secrets", "token", "tokens", "password",
    "passwd", "passphrase", "credential", "credentials", "cred", "creds",
    "auth", "authorization", "oauth", "bearer", "session", "cookie", "jwt",
    "seed", "phrase", "mnemonic", "private", "privkey", "pem", "pfx", "keystore",
    "signature", "hmac", "dek", "kek", "apikey", "ssh", "gpg", "pgp",
    "ssn", "passport", "medical", "diagnosis", "salary", "payroll", "dob",
    "birthdate", "email", "phone", "iban", "cvv",
})

#: Compounds the segment rule cannot see, because they are written as one word.
_SENSITIVE_SUBSTRINGS = (
    "apikey", "privatekey", "publickey", "secretkey", "accesstoken",
    "refreshtoken", "authtoken", "sessiontoken", "seedphrase", "passwd",
    "clientsecret", "bearertoken",
)

#: Shapes of real credential material, borrowed from the lane's existing
#: security regression. About *values*: a leaked token rarely arrives under a
#: key helpfully named "secret".
_CREDENTIAL_VALUE_PATTERNS = (
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b", re.IGNORECASE)),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", re.IGNORECASE)),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b", re.IGNORECASE)),
    ("OpenAI-style key", re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
    ("bearer header", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{20,}=*", re.IGNORECASE)),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("basic-auth URL", re.compile(r"https?://[^/\s:@]+:[^/\s@]+@")),
)

#: A run of digits long enough to be an account number, a phone number or a
#: date of birth rather than a version or a retention window.
_LONG_DIGIT_RUN_RE = re.compile(r"[0-9]{8,}")


def assert_no_credential_material(value, *, where):
    """Refuse a string whose *shape* is that of real credential material."""
    if not isinstance(value, str):
        return
    for label, pattern in _CREDENTIAL_VALUE_PATTERNS:
        if pattern.search(value):
            raise ValueError(
                f"{where}: value looks like {label}; credential material is "
                "never written into a storage manifest (Spec S21/S22)")


def validate_object_name(name):
    """Refuse a classifier label that carries secret or private text.

    A *name* in this mesh is not an object's identity. Identity is
    ``object_id``, the digest of the content, and ``policy.yaml`` object_naming
    records the rule that makes that true: ``content_addressed: true``,
    ``human_readable_names_allowed: false``. No manifest field holds a filename,
    a path or a storage key.

    What this validates is the only human-chosen string a manifest still
    accepts: a classifier drawn from a small controlled vocabulary -
    ``object_class``, ``retention_class``, ``origin_class``, ``producer_id``.
    The shape is the schema's ``class_token``, and the shape is most of the
    control: forty lower-case characters with no spaces, no ``/``, no ``@`` and
    no ``:`` cannot express ``users/alice/tax-return-2025.pdf`` at all, and
    cannot hold a 256-bit key in any common encoding. On top of the shape sit
    three checks a shape cannot make - segments that announce secret or private
    content, values shaped like real credentials, and long digit runs that look
    like account numbers rather than retention windows.

    An ``object_id`` deliberately fails this check. It is 68 characters, and if
    a digest were an acceptable name then a name would be an acceptable id.

    Returns ``None`` and raises ``ValueError`` on anything it will not accept.
    """
    if not isinstance(name, str):
        raise ValueError(
            f"object name must be a string classifier, got {type(name).__name__}")
    if name != name.strip() or not name:
        raise ValueError("object name must be a non-empty, unpadded classifier")
    if len(name) > _CLASS_TOKEN_MAX:
        raise ValueError(
            f"object name {len(name)} characters exceeds the {_CLASS_TOKEN_MAX}-"
            "character classifier bound; a classifier that can hold a sentence "
            "can hold a prompt, and one that can hold 44 characters can hold a key")
    if not _CLASS_TOKEN_RE.match(name):
        raise ValueError(
            f"object name {name!r} is not a controlled-vocabulary classifier: "
            "lower-case, [a-z0-9._-] only. Paths, filenames, addresses and free "
            "text are unrepresentable by construction (Spec S7)")
    if _HEX_TOKEN_RE.match(name):
        raise ValueError(
            f"object name {name!r} is bare hex and indistinguishable from key "
            "material")
    assert_no_credential_material(name, where=f"object name {name!r}")

    lowered = name.replace("-", "").replace("_", "").replace(".", "")
    for needle in _SENSITIVE_SUBSTRINGS:
        if needle in lowered:
            raise ValueError(
                f"object name {name!r} contains {needle!r}; object names carry "
                "no secrets and no unnecessary private text (Spec S7)")
    for segment in re.split(r"[-_.]", name):
        if segment in _SENSITIVE_SEGMENTS:
            raise ValueError(
                f"object name {name!r} names {segment!r}; object names carry no "
                "secrets and no unnecessary private text (Spec S7)")
    if _LONG_DIGIT_RUN_RE.search(name):
        raise ValueError(
            f"object name {name!r} carries a long digit run, which is the shape "
            "of an account, phone or identity number rather than a classifier")
    return None


# --- registry-backed backend identity ---------------------------------------


@lru_cache(maxsize=1)
def _registry():
    """Backend ids and locality, read once from the checked-in registry.

    Registry membership is not admission: whether a row may actually receive a
    byte is ``mesh_validator``'s question and depends on runtime state. This
    only refuses a backend nobody registered, which is the same half the
    schema's ``backend_id`` enum answers - sourced from the registry here so
    the two cannot drift.
    """
    rows = mesh_validator.load_providers()
    all_ids = frozenset(row.get("provider_id") for row in rows
                        if row.get("provider_id"))
    local_ids = frozenset(row.get("provider_id") for row in rows
                          if row.get("provider_id") and not row.get("external"))
    return all_ids, local_ids


def _check_backend(backend_id, *, role):
    all_ids, _ = _registry()
    if not isinstance(backend_id, str) or backend_id not in all_ids:
        raise ValueError(
            f"{role} backend {backend_id!r} is not a row in the provider "
            "registry; a manifest may only name a registered backend "
            "(registry membership is still not admission - mesh_validator.py "
            "decides that)")


def _is_local(backend_id):
    _, local_ids = _registry()
    return backend_id in local_ids


# --- small field validators --------------------------------------------------


def _check_enum(value, allowed, *, field):
    if value not in allowed:
        raise ValueError(
            f"{field} {value!r} is not in the closed vocabulary {tuple(allowed)}")


def _check_timestamp(value, *, field):
    if not isinstance(value, str) or not _TIMESTAMP_RE.match(value):
        raise ValueError(
            f"{field} {value!r} is not an RFC 3339 instant such as "
            "'2026-09-18T00:00:00Z'")


def _check_classifier(value, *, field):
    try:
        validate_object_name(value)
    except ValueError as exc:
        raise ValueError(f"{field}: {exc}") from None


def _check_evidence_ref(value, *, field):
    if not isinstance(value, str):
        raise ValueError(
            f"{field} must be a string evidence pointer, got "
            f"{type(value).__name__}")
    if len(value) > _EVIDENCE_REF_MAX:
        raise ValueError(
            f"{field} is {len(value)} characters, over the "
            f"{_EVIDENCE_REF_MAX}-character bound the schema sets; a pointer "
            "that can hold two kilobytes of opaque material is not a pointer, "
            "it is storage - and it persists whether or not the object itself "
            "stays on owned storage")
    if not _EVIDENCE_REF_RE.match(value):
        raise ValueError(
            f"{field} {value!r} is not an evidence pointer: a scheme-qualified "
            "reference or a repository-relative path with a file extension, and "
            "never one carrying its own authorisation")
    for segment in _EVIDENCE_SEGMENT_SPLIT_RE.split(value):
        if not segment:
            continue
        if _HEX_TOKEN_RE.match(segment):
            raise ValueError(
                f"{field} carries the bare hex run {segment[:12]!r}...; a run of "
                "hex is indistinguishable from key material wherever it appears, "
                "which is why validate_object_name refuses one too")
        if len(segment) > _EVIDENCE_SEGMENT_MAX:
            raise ValueError(
                f"{field} carries a {len(segment)}-character unbroken run, over "
                f"the {_EVIDENCE_SEGMENT_MAX}-character bound; that is the shape "
                "of a secret (an AWS secret access key is 40 characters of "
                "base64) rather than of a path segment")
        if (len(segment) >= _EVIDENCE_OPAQUE_MIN
                and _HAS_LOWER_RE.search(segment)
                and _HAS_UPPER_RE.search(segment)):
            raise ValueError(
                f"{field} carries the run {segment[:12]!r}...: "
                f"{len(segment)} characters mixing upper and lower case. Path "
                "segments in this repository are words and are one case or the "
                "other; that alphabet is base64 key material, and "
                "splitting a secret on '-' or '/' is how it gets past a "
                "length bound alone")
    assert_no_credential_material(value, where=field)


def _check_bounded_int(value, low, high, *, field):
    """A real integer in range. ``isinstance(True, int)`` is True in Python, and
    ``true`` is not an integer to any JSON Schema validator."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(
            f"{field} must be an integer, got {type(value).__name__}")
    if not low <= value <= high:
        raise ValueError(f"{field} {value} is outside {low}..{high}")


def _check_opaque_token(value, *, field):
    """``nonce``/``tag``: bounded opaque material, never a key slot.

    The bound is the control. Unbounded, these two string fields sit directly
    beside ``key_ref`` and will hold whatever is put in them - a wrapped DEK is
    44 base64 characters, a raw 256-bit key is 64 hex characters, and neither
    fits in 32.
    """
    if not isinstance(value, str) or isinstance(value, bool):
        raise ValueError(
            f"{field} must be a string, got {type(value).__name__}")
    if not _OPAQUE_TOKEN_MIN <= len(value) <= _OPAQUE_TOKEN_MAX:
        raise ValueError(
            f"{field} is {len(value)} characters; the schema bounds it to "
            f"{_OPAQUE_TOKEN_MIN}..{_OPAQUE_TOKEN_MAX}, which is long enough "
            "for a 12-byte nonce and a 16-byte tag and too short for a key")
    if not _OPAQUE_TOKEN_RE.match(value):
        raise ValueError(
            f"{field} is not base64/base64url material: "
            f"{_OPAQUE_TOKEN_RE.pattern} only")
    assert_no_credential_material(value, where=field)


def _check_encryption_algorithm(value, *, field):
    allowed = ((mesh_validator.load_policy().get("encryption") or {})
               .get("allowed_algorithms") or [])
    if value not in allowed:
        raise ValueError(
            f"{field} {value!r} is not in policy.yaml "
            "encryption.allowed_algorithms; Spec S21 requires a standard "
            "authenticated construction, and no cryptography is chosen or "
            "invented here")


def _check_key_ref(value, *, field):
    if not isinstance(value, str) or not _KEY_REF_RE.match(value):
        raise ValueError(
            f"{field} {value!r} is not a reference to an allowed key location "
            "(env, secretstore, worker-secret, kms). Spec S22 separates keys "
            "from the ciphertext provider: a bucket URL, a repository file and "
            "a bare blob are all refused, and there is no field here a "
            "plaintext key could be written into")


#: One validator per property of ``$defs.encryption_metadata``. A table rather
#: than a run of ``if`` statements so that completeness is checkable: the tests
#: walk the schema's property set and assert every one of them has an entry
#: here. ``nonce``, ``tag`` and ``key_rotation_generation`` were whitelisted by
#: name in ``_ENCRYPTION_FIELDS`` and then validated by nothing at all, and the
#: reason that survived 49 passing tests is that no hand-picked shape populated
#: them. A field added to the schema later cannot repeat it.
_ENCRYPTION_FIELD_CHECKS = {
    "algorithm": _check_encryption_algorithm,
    "scheme_version": lambda value, *, field: _check_bounded_int(
        value, _SCHEME_VERSION_MIN, _SCHEME_VERSION_MAX, field=field),
    "key_ref": _check_key_ref,
    "key_rotation_generation": lambda value, *, field: _check_bounded_int(
        value, _KEY_ROTATION_MIN, _KEY_ROTATION_MAX, field=field),
    "nonce": _check_opaque_token,
    "tag": _check_opaque_token,
}


def _closed_mapping(value, allowed, *, field, required=()):
    """Whitelist a nested mapping against the schema's closed field set."""
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a mapping, got {type(value).__name__}")
    unknown = sorted(set(value) - set(allowed))
    if unknown:
        raise ValueError(
            f"{field} rejects unknown field(s) {unknown}: the field set is "
            f"closed to {list(allowed)}, so a field nobody anticipated is "
            "refused rather than stored")
    missing = sorted(set(required) - set(value))
    if missing:
        raise ValueError(f"{field} is missing required field(s) {missing}")
    for key, nested in value.items():
        if nested is None:
            raise ValueError(
                f"{field}.{key} is null; an optional field is omitted rather "
                "than emitted as null, because a null here is a document the "
                "schema refuses")
        if not isinstance(nested, (str, bool, int)) or isinstance(nested, float):
            raise ValueError(
                f"{field}.{key} must be a scalar (string, integer or boolean), "
                f"got {type(nested).__name__}: a nested container has no "
                "legitimate use in a manifest mapping, is skipped by the "
                "credential-shape scan, and would stay aliased to the caller's "
                "handle after construction")
        assert_no_credential_material(nested, where=f"{field}.{key}")
    return dict(value)


#: Set only while ``from_bytes`` is hashing content into a record. Direct
#: dataclass construction is an exported path that hashes nothing, so
#: ``StorageObject(object_id="obj_" + "a" * 64, content_sha256="a" * 64,
#: size_bytes=999, ...)`` used to produce a record whose digest and length were
#: caller *assertions* - exactly what ``from_bytes`` refuses a digest parameter
#: in order to avoid. Thread-local so one thread's construction cannot admit
#: another's.
_CONSTRUCTION = threading.local()


def _check_replica_sequence(value):
    """A sequence of backend ids - and a string is not one.

    ``replica_backends="supabase"`` is iterable, so it used to be consumed one
    character at a time and rejected with "replica_backends must be unique",
    which names the wrong problem.
    """
    if isinstance(value, (str, bytes, bytearray)):
        raise ValueError(
            "replica_backends expected a sequence of backend ids, got a "
            f"string ({value!r}); a string is iterated one character at a time, "
            'so ("cloudflare_r2",) is meant rather than "cloudflare_r2"')
    try:
        return tuple(value)
    except TypeError:
        raise ValueError(
            "replica_backends expected a sequence of backend ids, got "
            f"{type(value).__name__}") from None


def _now_instant():
    return _datetime.datetime.now(_datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


@dataclasses.dataclass(frozen=True)
class StorageObject:
    """One managed object, as the mesh is allowed to know it.

    Frozen, because a manifest describes bytes that have already been hashed:
    an instance whose ``privacy_class`` can be reassigned after placement is an
    instance whose placement decision has quietly expired. Every rule the schema
    states as structure is re-checked here, so the model cannot emit a document
    the schema would refuse - and ``to_manifest`` output is asserted against the
    schema on disk in the tests, so the mirroring cannot rot silently.

    The field set is exactly the schema's property set minus ``version``,
    ``authority`` and ``authority_flags``, which are constants this model emits
    and no caller may assert.
    """

    object_id: str
    content_sha256: str
    size_bytes: int
    privacy_class: str
    criticality: str
    storage_tier: str
    encryption_state: str
    primary_backend: str
    replica_backends: tuple
    created_at: str
    lifecycle_state: str
    reproducible: bool
    object_class: str = None
    mime_type: str = None
    retention_class: str = None
    encryption_scheme_version: int = None
    encryption: dict = None
    last_accessed_at: str = None
    last_verified_at: str = None
    source_provenance: dict = None
    verification: dict = None

    # -- construction --------------------------------------------------------

    @classmethod
    def from_bytes(cls, content, *, privacy_class, criticality, storage_tier,
                   object_class=None, mime_type=None, retention_class=None,
                   encryption_state="NONE", encryption_scheme_version=None,
                   encryption=None, primary_backend=DEFAULT_BACKEND_ID,
                   replica_backends=(), created_at=None, last_accessed_at=None,
                   last_verified_at=None, lifecycle_state="RAW",
                   source_provenance=None, reproducible=None, verification=None,
                   **unknown):
        """Hash the content and build the record that describes it.

        ``object_id`` and ``content_sha256`` are derived from ``content`` and
        ``size_bytes`` is measured from it; none of the three is a parameter,
        because a caller-supplied hash or length is an assertion and the bytes
        are the evidence.

        ``**unknown`` is the structural rejection. Every field this model
        accepts is named above, so ``plaintext_key``, ``api_key`` and the
        invented name nobody has thought of yet all arrive by the same route and
        are refused by the same line. There is no list of forbidden names to
        keep up to date, which is the point: a denylist of six is bypassed by
        the seventh.
        """
        if unknown:
            raise ValueError(
                f"unknown manifest field(s) {sorted(unknown)}: the manifest is a "
                "closed field set (schema additionalProperties: false). A field "
                "the model does not name cannot be stored, whether it holds a "
                "key, a token, a filename or something harmless")
        if not isinstance(content, (bytes, bytearray, memoryview)):
            raise ValueError(
                "from_bytes needs the object's bytes; it hashes content rather "
                f"than trusting a caller's digest, got {type(content).__name__}")

        payload = bytes(content)
        digest = hashlib.sha256(payload).hexdigest()

        if reproducible is None:
            # Derived from the declared criticality rather than guessed: Spec S8
            # says REPRODUCIBLE objects may be evicted and regenerated, and every
            # other class may not, so anything else defaults to irreplaceable.
            reproducible = criticality == "REPRODUCIBLE"

        _CONSTRUCTION.hashed = True
        try:
            return cls(
                object_id=f"{OBJECT_ID_PREFIX}{digest}",
                content_sha256=digest,
                size_bytes=len(payload),
                privacy_class=privacy_class,
                criticality=criticality,
                storage_tier=storage_tier,
                encryption_state=encryption_state,
                primary_backend=primary_backend,
                replica_backends=_check_replica_sequence(
                    replica_backends or ()),
                created_at=created_at or _now_instant(),
                lifecycle_state=lifecycle_state,
                reproducible=reproducible,
                object_class=object_class,
                mime_type=mime_type,
                retention_class=retention_class,
                encryption_scheme_version=encryption_scheme_version,
                encryption=encryption,
                last_accessed_at=last_accessed_at,
                last_verified_at=last_verified_at,
                source_provenance=source_provenance,
                verification=verification,
            )
        finally:
            _CONSTRUCTION.hashed = False

    # -- validation ----------------------------------------------------------

    def __post_init__(self):
        if not getattr(_CONSTRUCTION, "hashed", False):
            raise ValueError(
                "StorageObject is built from the object's bytes: use "
                "StorageObject.from_bytes(content, ...). Constructing the "
                "dataclass directly supplies object_id, content_sha256 and "
                "size_bytes as assertions, and an unverified digest is the one "
                "thing a content-addressed identity cannot be")
        self._check_identity()
        self._check_vocabularies()
        self._check_classifiers_and_timestamps()
        backends = self._check_backends()
        self._check_encryption()
        self._check_privacy(backends)
        self._check_tier_and_size(backends)
        self._freeze_nested()

    def _check_identity(self):
        if not isinstance(self.content_sha256, str) or not _SHA256_RE.match(
                self.content_sha256):
            raise ValueError("content_sha256 must be a lower-case SHA-256 digest")
        if self.object_id != f"{OBJECT_ID_PREFIX}{self.content_sha256}":
            raise ValueError(
                "object_id must be the content digest and nothing else: it is "
                "independent of provider, tier and time so that re-tiering and "
                "rebalancing do not change what an object is (Spec S7/S15)")
        if not isinstance(self.size_bytes, int) or isinstance(self.size_bytes, bool):
            raise ValueError("size_bytes must be an integer count of bytes")
        if not 0 <= self.size_bytes <= _MAX_SIZE_BYTES:
            raise ValueError(f"size_bytes {self.size_bytes} is out of range")
        if not isinstance(self.reproducible, bool):
            raise ValueError("reproducible must be a boolean")
        if self.criticality == "REPRODUCIBLE" and not self.reproducible:
            raise ValueError(
                "criticality REPRODUCIBLE with reproducible=False is a "
                "contradiction: Spec S8 permits eviction of a REPRODUCIBLE "
                "object precisely because it can be regenerated")

    def _check_vocabularies(self):
        _check_enum(self.privacy_class, PRIVACY_CLASSES, field="privacy_class")
        _check_enum(self.criticality, CRITICALITY_CLASSES, field="criticality")
        _check_enum(self.storage_tier, STORAGE_TIERS, field="storage_tier")
        _check_enum(self.lifecycle_state, LIFECYCLE_STATES, field="lifecycle_state")
        _check_enum(self.encryption_state, ENCRYPTION_STATES,
                    field="encryption_state")

    def _check_classifiers_and_timestamps(self):
        for field in ("object_class", "retention_class"):
            value = getattr(self, field)
            if value is not None:
                _check_classifier(value, field=field)

        if self.mime_type is not None:
            if not isinstance(self.mime_type, str) or not _MIME_RE.match(self.mime_type):
                raise ValueError(
                    f"mime_type {self.mime_type!r} must be type/subtype only; "
                    "RFC 2045 parameters are excluded because 'name=' and "
                    "'filename=' are exactly the private text Spec S7 forbids")

        _check_timestamp(self.created_at, field="created_at")
        for field in ("last_accessed_at", "last_verified_at"):
            value = getattr(self, field)
            if value is not None:
                _check_timestamp(value, field=field)

        if self.source_provenance is not None:
            provenance = _closed_mapping(
                self.source_provenance, _PROVENANCE_FIELDS,
                field="source_provenance", required=("origin_class",))
            for field in ("origin_class", "producer_id"):
                if provenance.get(field) is not None:
                    _check_classifier(provenance[field],
                                      field=f"source_provenance.{field}")
            if provenance.get("evidence_ref") is not None:
                _check_evidence_ref(provenance["evidence_ref"],
                                    field="source_provenance.evidence_ref")

        if self.verification is not None:
            verification = _closed_mapping(
                self.verification, _VERIFICATION_FIELDS, field="verification")
            if "hash_verified" in verification and not isinstance(
                    verification["hash_verified"], bool):
                raise ValueError("verification.hash_verified must be a boolean")
            count = verification.get("verified_replica_count")
            if count is not None and (not isinstance(count, int)
                                      or isinstance(count, bool)
                                      or not 0 <= count <= 9):
                raise ValueError(
                    "verification.verified_replica_count must be 0..9")
            if verification.get("last_probe_at") is not None:
                _check_timestamp(verification["last_probe_at"],
                                 field="verification.last_probe_at")
            if verification.get("evidence_ref") is not None:
                _check_evidence_ref(verification["evidence_ref"],
                                    field="verification.evidence_ref")

    def _check_backends(self):
        _check_backend(self.primary_backend, role="primary")
        object.__setattr__(self, "replica_backends",
                           _check_replica_sequence(self.replica_backends))
        if len(self.replica_backends) > _MAX_REPLICAS:
            raise ValueError(
                f"replica_backends holds more than {_MAX_REPLICAS} copies; an "
                "object needing more is a policy question, not a manifest one")
        if len(set(self.replica_backends)) != len(self.replica_backends):
            raise ValueError("replica_backends must be unique")
        for backend in self.replica_backends:
            _check_backend(backend, role="replica")
        if self.primary_backend in self.replica_backends:
            raise ValueError(
                f"primary backend {self.primary_backend} is also listed as a "
                "replica; a replica is an independent copy (Spec S9)")
        return (self.primary_backend,) + tuple(self.replica_backends)

    def _check_encryption(self):
        """Spec S21/S22. Declared here; defined and implemented elsewhere."""
        if self.encryption is not None:
            metadata = _closed_mapping(
                self.encryption, _ENCRYPTION_FIELDS, field="encryption",
                required=("algorithm", "scheme_version", "key_ref"))
            # Every admitted field is validated, not only the three the
            # required list happens to name. _closed_mapping has already
            # refused any key outside the table.
            for key, value in metadata.items():
                _ENCRYPTION_FIELD_CHECKS[key](value, field=f"encryption.{key}")
            version = metadata["scheme_version"]
            if (self.encryption_scheme_version is not None
                    and self.encryption_scheme_version != version):
                raise ValueError(
                    "encryption_scheme_version contradicts "
                    "encryption.scheme_version")

        if self.encryption_state == "NONE":
            if self.encryption is not None:
                raise ValueError(
                    "encryption_state NONE with encryption metadata is a record "
                    "saying at once that the object is plaintext and that a key "
                    "opens it; neither half is a safe default to guess")
            if self.encryption_scheme_version is not None:
                raise ValueError(
                    "encryption_state NONE carries no encryption_scheme_version")
        elif self.encryption is None:
            raise ValueError(
                "encryption_state CLIENT_SIDE_ENCRYPTED without encryption "
                "metadata is an unverifiable claim, and an unverifiable "
                "encryption claim is how a plaintext object comes to be treated "
                "as ciphertext")

        if self.encryption_scheme_version is not None and (
                not isinstance(self.encryption_scheme_version, int)
                or isinstance(self.encryption_scheme_version, bool)
                or not 1 <= self.encryption_scheme_version <= 4096):
            raise ValueError("encryption_scheme_version must be 1..4096")

    def _check_privacy(self, backends):
        """Spec S4/S5. Privacy is evaluated first and nothing below overturns it."""
        external = [b for b in backends if not _is_local(b)]
        if self.privacy_class == "LOCAL_ONLY" and external:
            raise ValueError(
                f"privacy class LOCAL_ONLY may not name external backend(s) "
                f"{sorted(set(external))}; it must never be uploaded to "
                "third-party storage (Spec S4)")
        if self.privacy_class == "CONFIDENTIAL" and external:
            if self.encryption_state != "CLIENT_SIDE_ENCRYPTED" or self.encryption is None:
                raise ValueError(
                    "a CONFIDENTIAL object reaches an external backend only as "
                    "ciphertext, and only with the encryption metadata that "
                    "proves it: the flag is an assertion, the metadata is the "
                    "evidence (Spec S4/S21)")

    def _check_tier_and_size(self, backends):
        """Spec S6/S18/S25, mirrored from the schema's tier rules."""
        threshold = mesh_validator.BULK_OBJECT_THRESHOLD_BYTES
        if self.storage_tier in mesh_validator.NON_BULK_TIERS and self.size_bytes > threshold:
            raise ValueError(
                f"storage tier {self.storage_tier} carries pointers, not "
                f"payloads: {self.size_bytes} bytes exceeds {threshold}")
        if "supabase" in backends and self.storage_tier != "METADATA":
            raise ValueError(
                "supabase is a metadata and index backend only; naming it "
                "forces the METADATA tier (Spec S18/S25)")

    def _freeze_nested(self):
        """Copy and freeze the nested mappings so the instance cannot be edited.

        A frozen dataclass freezes its attribute *bindings*; a dict behind one
        is still a mutable handle a caller kept. The copy is one level deep and
        that is sufficient only because ``_closed_mapping`` refuses a nested
        container outright: a one-level copy of a mapping holding another
        mapping leaves the inner one aliased to the caller, who can then edit a
        "frozen" record after construction.
        """
        object.__setattr__(self, "replica_backends", tuple(self.replica_backends))
        for field in ("encryption", "source_provenance", "verification"):
            value = getattr(self, field)
            if value is not None:
                object.__setattr__(self, field, MappingProxyType(dict(value)))

    # -- emission ------------------------------------------------------------

    def to_manifest(self):
        """Render the record the mesh stores, as a plain, freshly-built dict.

        ``version``, ``authority`` and ``authority_flags`` are emitted here and
        are not fields: a manifest record is evidence about an object, never
        authority over one, and the eight authorities are denied by name rather
        than by omission so a later document cannot acquire one by adding a key.
        """
        manifest = {
            "version": MANIFEST_VERSION,
            "authority": False,
            "authority_flags": {flag: False for flag in AUTHORITY_FLAGS},
            "object_id": self.object_id,
            "content_sha256": self.content_sha256,
            "size_bytes": self.size_bytes,
            "privacy_class": self.privacy_class,
            "criticality": self.criticality,
            "storage_tier": self.storage_tier,
            "encryption_state": self.encryption_state,
            "primary_backend": self.primary_backend,
            "replica_backends": list(self.replica_backends),
            "created_at": self.created_at,
            "lifecycle_state": self.lifecycle_state,
            "reproducible": self.reproducible,
        }
        for field in ("object_class", "mime_type", "retention_class",
                      "last_accessed_at", "last_verified_at"):
            value = getattr(self, field)
            if value is not None:
                manifest[field] = value
        if self.encryption_scheme_version is not None:
            manifest["encryption_scheme_version"] = self.encryption_scheme_version
        for field in ("encryption", "source_provenance", "verification"):
            value = getattr(self, field)
            if value is not None:
                manifest[field] = dict(value)
        return manifest


__all__ = [
    "AUTHORITY", "CANONICAL_AUTHORITY", "ENCRYPTION_IMPLEMENTED_HERE",
    "MANIFEST_VERSION", "DEFAULT_BACKEND_ID", "OBJECT_ID_PREFIX",
    "ENCRYPTION_STATES", "StorageObject", "validate_object_name",
    "assert_no_credential_material",
]
