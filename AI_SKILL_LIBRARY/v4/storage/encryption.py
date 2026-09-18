"""Federated Free Storage Mesh - the client-side encryption contract (Task 6).

Spec S4 says a CONFIDENTIAL object may leave owned storage only after
client-side encryption. Spec S21 says the first implementation uses a
well-supported standard construction rather than inventing cryptography, and
that encryption metadata carries algorithm, version and a key *reference* only.
Spec S22 says the key and the ciphertext never share a home. This module is
where those three sentences become code, and everything in it follows from one
awkward fact about this repository.

**There is no approved crypto library to import.** ``cryptography`` 41.0.7
imports in the development container, but ``AI_SKILL_LIBRARY/requirements.txt``
is two lines - ``PyYAML`` and ``jsonschema`` - and every CI workflow installs
exactly that file. ``cryptography`` is present here only as an unselected extra
of PyJWT and oauthlib. A module that begins ``import cryptography`` is therefore
green on a laptop and red in CI, and adding the dependency is a decision for the
repository owner and not for this task.

So the AEAD primitive is **injected, never imported**. This module imports with
no crypto library present at all - ``PERMITTED_IMPORTS`` is asserted from the
AST by the tests, and the tests import it in a subprocess with ``cryptography``,
``nacl`` and ``Crypto`` blocked at the meta path - and every operation fails
closed when nobody supplies a primitive. What the module owns is the *contract*:
what a provider must look like, what the metadata may contain, what is bound as
associated data, and what must be refused. A reviewer who wants real encryption
adds one line to ``requirements.txt`` and roughly twenty lines of adapter; the
refusals here do not move.

Four properties are worth stating, because each is the answer to a specific way
this goes wrong.

**No cryptography is invented, approximated or stood in for.**
``CRYPTOGRAPHY_IMPLEMENTED_HERE`` is ``False`` and there is no cipher, no
key-derivation function, no MAC and no random-looking arithmetic anywhere in
this file. The only primitive-shaped thing here is ``secrets.token_bytes`` for
the nonce, which is the operating system's CSPRNG and not a construction. A
stand-in used for testing has to declare itself (``is_test_double``) *and* carry
``TEST_DOUBLE_ACKNOWLEDGEMENT``, and the call site has to pass
``allow_test_double=True``; miss any one of the three and the operation refuses.
A non-cryptographic fake cannot be mistaken for a backend by accident.

**The key never comes back out.** ``EncryptedObject`` holds ciphertext, a nonce,
a tag and a key *reference*; it has no field a key could be written into, its
``repr`` prints neither, and ``metadata()`` emits exactly the six properties of
``storage_object_manifest.schema.json``'s ``encryption_metadata``. Refusals
never quote their input and are raised ``from None``: the bounded checkers this
module borrows from ``manifest.py`` do quote theirs, and a refusal raised inside
the ``except`` that caught one carries the offending value as ``__context__`` -
which ``str(exc)`` hides and every traceback prints. Suppressing the context is
what actually keeps a mistyped credential out of the log.

**The bounds are borrowed, not rewritten.** Every metadata field is validated by
``manifest._ENCRYPTION_FIELD_CHECKS[field]`` - the same callable object, so the
two cannot drift - and ``ENCRYPTION_METADATA_FIELDS`` is *derived* from that
table rather than typed out beside it. Four times in this project a field has
been whitelisted by name and then validated by nothing at all; a derived tuple
plus a test that walks the schema on disk is the remedy Tasks 4 and 5
established, and it is what is used here.

**Tampering is never a partial success.** ``key_ref``, ``algorithm``,
``scheme_version`` and ``key_rotation_generation`` are bound as associated data,
so re-pointing a ciphertext at a different key is an authentication failure
rather than a decrypt-with-whatever-is-there. Every failure on the decrypt path
after an attacker-controlled field has been read raises ``DecryptionFailed``
with one identical message - including a ``key_ref`` the secret store cannot
resolve at all, which used to escape as ``EncryptionUnavailable`` and therefore
told a caller which references exist - so a caller cannot use the refusal, its
text *or its type*, as an oracle for which part they got wrong.

Two things that sentence does not claim, stated here rather than left to be
discovered:

*"No path returns bytes that were not authenticated" is true modulo the
injected primitive.* This module verifies nothing itself and cannot: a
``seal``/``open`` pair that returns attacker-chosen bytes for any input - a
primitive that lies - has those bytes returned to the caller, and no check here
would notice. The gates around injection (``is_test_double``, the
acknowledgement, ``allow_test_double``, the algorithm vocabulary and now the
parameter shapes) are about which provider gets used; the authentication itself
is the provider's, and trusting it is the design.

*Constructing an ``EncryptedObject`` with an unknown keyword raises ``TypeError``
from the dataclass machinery, and that message does quote the keyword name.* The
redaction discipline in this file covers the paths it owns; the dataclass
constructor is not one of them. ``replace()`` is the supported way to change a
field, its keyword set is closed, and its refusals redact.

This module decides no placement. ``AUTHORITY`` is ``False`` and so are all
eight flags.
"""

from __future__ import annotations

import base64
import dataclasses
import json
import re
import secrets

from AI_SKILL_LIBRARY.v4.storage import AUTHORITY_FLAGS as _AUTHORITY_FLAG_NAMES
from AI_SKILL_LIBRARY.v4.storage import CANONICAL_AUTHORITY
from AI_SKILL_LIBRARY.v4.storage import PRIVACY_CLASSES
from AI_SKILL_LIBRARY.v4.storage import manifest as _manifest
from AI_SKILL_LIBRARY.v4.storage import mesh_validator as _mesh_validator
from AI_SKILL_LIBRARY.v4.storage import metadata as _metadata

#: This module holds no authority of any kind. Denied by name rather than by
#: omission, so a later edit cannot acquire one by adding a key.
AUTHORITY = False
AUTHORITY_FLAGS = {flag: False for flag in _AUTHORITY_FLAG_NAMES}

ROUTED_BY = "task_router"

#: The load-bearing claim of this file. No cipher, no KDF, no MAC, no keystream
#: and no "good enough" construction is implemented, approximated or stood in
#: for here. The AEAD arrives from outside or nothing happens.
CRYPTOGRAPHY_IMPLEMENTED_HERE = False
AEAD_PROVIDER_REQUIRED = True

#: Asserted from this file's own AST by the tests. ``cryptography`` is not a
#: declared dependency of this repository and CI does not install it, so a hard
#: import of one here is a red pipeline; the set is the standing guard against
#: somebody adding one back. ``secrets`` is the operating system's CSPRNG, used
#: for the nonce, and is not a cryptographic construction.
PERMITTED_IMPORTS = frozenset({
    "__future__", "base64", "dataclasses", "json", "re", "secrets",
    "AI_SKILL_LIBRARY",
})

#: The wire format version of what this module produces. Bumped only when the
#: bytes or the associated-data binding change; a ciphertext carrying any other
#: value is refused rather than guessed at.
SCHEME_VERSION = 1

#: Domain separation for the associated data, so a byte string authenticated by
#: some other part of this system can never be replayed as one of these.
_AAD_DOMAIN = b"ffsm-storage-encryption-v1\x00"

#: The acknowledgement a non-cryptographic stand-in must carry before this
#: module will speak to it, alongside ``allow_test_double=True`` at the call
#: site. Deliberately unpleasant to type and impossible to produce by accident.
TEST_DOUBLE_ACKNOWLEDGEMENT = (
    "I ACKNOWLEDGE THIS PROVIDER IS NOT CRYPTOGRAPHY, PROVIDES NO "
    "CONFIDENTIALITY, AND MUST NEVER PROTECT REAL DATA"
)

#: Spec S21's closed vocabulary, read from ``policy.yaml`` rather than restated.
#: Adding a construction is a deliberate edit to that file, which is the point.
#:
#: This is a **snapshot taken at import**, while ``manifest._check_encryption_
#: algorithm`` re-reads ``policy.yaml`` on every call. In a long-lived process
#: that edits the policy file in place the two can disagree, and the manifest's
#: fresh read is the authority; treat this tuple as advisory - it is here so a
#: caller can see the vocabulary without a file read, not so anything can be
#: decided from it. ``_algorithm_of`` validates through the manifest checker and
#: not against this tuple, so the drift cannot make anything more permissive.
def _policy_algorithms():
    """The current ``encryption.allowed_algorithms``, read fresh."""
    return tuple((_mesh_validator.load_policy().get("encryption") or {})
                 .get("allowed_algorithms") or ())


ALLOWED_ALGORITHMS = _policy_algorithms()

#: Key sizes a standard AEAD accepts. Not a preference: a construction that
#: wants some other length is not one of the constructions ``policy.yaml``
#: allows, and a 7-byte "key" is the shape of a passphrase somebody typed.
ALLOWED_KEY_BYTES = (16, 24, 32)

#: Nonce and tag travel in the manifest, where the schema bounds both strings to
#: 32 characters. 24 raw bytes is exactly 32 base64 characters, which is also
#: the largest standard AEAD nonce (XChaCha20's 192-bit nonce), and 12 bytes
#: (96 bits) is the standard tag floor. The upper bounds are not taste - a
#: longer value cannot be represented in the metadata field at all, so it is
#: refused up front rather than after the expensive part.
#:
#: These are coarse gates and not the check that matters: ``ALGORITHM_SHAPES``
#: below reconciles all three against the algorithm the provider *names*.
#:
#: The nonce floor is 12 and not 8 because **this module generates the nonce
#: itself** (``secrets.token_bytes(aead.nonce_length)``). The question is
#: therefore not "what is the smallest nonce some AEAD accepts" but "what is the
#: smallest nonce that is safe to pick at random": 64 bits collides near 2**32
#: objects by the birthday bound, and a repeated nonce under GCM is not a
#: degraded property but authenticator recovery. 96 bits is the floor, and no
#: construction in ``policy.yaml`` wanted less anyway.
MIN_NONCE_BYTES = 12
MAX_NONCE_BYTES = 24
MIN_TAG_BYTES = 12
MAX_TAG_BYTES = 24

#: The parameters that go with each construction's **name**.
#:
#: Key, nonce and tag lengths used to be bounded independently of each other and
#: of the algorithm, and the algorithm was checked separately against
#: ``policy.yaml``. Nothing reconciled the two, so a provider could declare
#: ``aes-256-gcm`` with a 128-bit key, a 64-bit nonce and a 96-bit tag, round
#: trip cleanly, and write ``"algorithm": "aes-256-gcm"`` into ``metadata()`` -
#: which lands in the manifest, which Spec S23 makes a rebuild input. The
#: metadata would be attesting a construction that was not performed.
#:
#: These are the standard parameters of the named constructions and not a
#: choice made here: AES-GCM, AES-GCM-SIV and ChaCha20-Poly1305 are 256-bit key,
#: 96-bit nonce, 128-bit tag; XChaCha20-Poly1305 differs only in its 192-bit
#: nonce, which is the whole point of the X. ``aead-standard-library`` is the
#: neutral placeholder ``policy.yaml`` carries for the contract tests while the
#: backend is owned elsewhere; it is given an **explicit** entry at the modern
#: standard shape (32/12/16) rather than being exempted, because an exemption is
#: a hole shaped exactly like the thing this table exists to close - a provider
#: that wants looser parameters would simply name the placeholder.
_KNOWN_ALGORITHM_SHAPES = {
    "aead-standard-library": (32, 12, 16),
    "aes-256-gcm": (32, 12, 16),
    "aes-256-gcm-siv": (32, 12, 16),
    "chacha20-poly1305": (32, 12, 16),
    "xchacha20-poly1305": (32, 24, 16),
}

#: Derived from ``policy.yaml``, never typed out beside it. An algorithm the
#: policy allows and this table has no shape for is absent here and therefore
#: **refused**: a construction whose parameters nobody has written down cannot
#: be reconciled with the name it puts in the manifest, and failing closed makes
#: adding one a deliberate two-line edit rather than a silent widening.
ALGORITHM_SHAPES = {name: _KNOWN_ALGORITHM_SHAPES[name]
                    for name in ALLOWED_ALGORITHMS
                    if name in _KNOWN_ALGORITHM_SHAPES}

#: Named rather than left implicit, so a policy edit that outruns the shape
#: table is visible to a reader and to a test instead of only to a refusal.
ALGORITHMS_WITHOUT_A_KNOWN_SHAPE = tuple(
    name for name in ALLOWED_ALGORITHMS if name not in _KNOWN_ALGORITHM_SHAPES)

#: Client-side encryption buffers the whole object in memory twice, once as
#: plaintext and once as ciphertext. 64 MiB is the point past which that stops
#: being a reasonable thing to do in a process that also holds a manifest; a
#: larger object needs chunking, which is a contract this module does not have.
MAX_PAYLOAD_BYTES = 64 * 1024 * 1024

#: What ``prepare_upload`` will read from a record. The set is closed against
#: the manifest schema's own properties, so a key nobody anticipated is refused
#: rather than ignored - and the refusal never quotes it, because a caller who
#: builds a record from a mapping they did not write can put a credential in a
#: *key*.
_RECORD_FIELDS = frozenset(_metadata._RECORD_FIELD_CHECKS)

#: Spec S4. LOCAL_ONLY never leaves, encrypted or not; that is the whole content
#: of the class, and an encrypted LOCAL_ONLY object is still an upload.
NEVER_UPLOADED = ("LOCAL_ONLY",)

#: Spec S4 and ``policy.yaml`` ``privacy.CONFIDENTIAL.client_encryption_required``.
ENCRYPTION_REQUIRED_CLASSES = ("CONFIDENTIAL",)


# --- errors -------------------------------------------------------------------


class EncryptionUnavailable(RuntimeError):
    """There is no usable AEAD backend, or no usable key, so nothing happened.

    A ``RuntimeError`` rather than a ``ValueError`` on purpose: the caller's
    arguments may be perfectly well formed and the fact being reported is about
    the environment - no primitive was injected, the secret store did not
    answer, the key that came back is not a key. Raised rather than returned so
    it cannot be mistaken for "encrypted with nothing".
    """


class DecryptionFailed(RuntimeError):
    """The ciphertext did not authenticate, so no plaintext is returned.

    One exception with one message for every cause - wrong key, tampered
    ciphertext, tampered tag, tampered nonce, re-pointed key reference, a key
    reference the secret store cannot resolve at all, a secret store that is
    down, truncation, a non-canonical base64 spelling, an unknown scheme
    version. Distinguishing them for the caller would hand an attacker an
    oracle, and none of the distinctions is useful to a legitimate caller, who
    has exactly one recovery: get the right key and the untouched bytes.

    The *type* is part of that. An unresolvable key reference used to raise
    ``EncryptionUnavailable`` instead, which let anyone who could submit objects
    and read the exception type enumerate which references exist in the secret
    store - the namespace Spec S22/S23 treat as sensitive rebuild input.
    Environment problems found *before* any attacker-controlled field is read
    (no provider, no AEAD, a provider whose shape contradicts its name) still
    raise ``EncryptionUnavailable``: they are facts about the caller's own
    process and say nothing about the object.
    """


#: The single message. A constant so that no future edit can accidentally make
#: one path distinguishable from another.
_DECRYPTION_FAILED = (
    "the object did not authenticate and no plaintext is returned. The cause "
    "is deliberately not reported: wrong key, altered ciphertext, altered tag, "
    "altered nonce, a re-pointed key reference and truncation are one failure "
    "here, because telling them apart is an oracle (Spec S21)"
)


# --- redaction ----------------------------------------------------------------

#: A name is safe to quote in a refusal only when its shape makes it a field
#: name. 32 characters is comfortably more than the longest property in the
#: manifest schema (``encryption_scheme_version``, 25) and comfortably less than
#: anything credential-shaped, so a caller who puts a token in a *key* gets
#: "'<redacted>'" rather than their token echoed into a log.
_SAFE_FIELD_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}\Z")


def _namable(field):
    if isinstance(field, str) and _SAFE_FIELD_NAME_RE.match(field):
        return repr(field)
    return "'<redacted>'"


def _refuse(subject, reason):
    """Raise a ``ValueError`` that names the field and never quotes the value.

    ``from None`` is load-bearing and not tidiness: the bounded checkers this
    module borrows from ``manifest.py`` *do* quote their input, and a refusal
    raised from inside the ``except`` that caught one carries it as
    ``__context__`` - hidden by ``str(exc)``, printed by every traceback under
    "During handling of the above exception".
    """
    raise ValueError(
        f"{_namable(subject)} {reason}. The value is deliberately not quoted: a "
        "refusal that echoes its input is how a mistyped credential reaches a "
        "log (Spec S21/S22)") from None


def _unavailable(reason):
    raise EncryptionUnavailable(
        f"{reason}. No cryptography is implemented, chosen or approximated in "
        "this module, so without a usable AEAD provider and a usable key the "
        "operation fails closed rather than degrading to something weaker "
        "(Spec S21)") from None


def _failed():
    raise DecryptionFailed(_DECRYPTION_FAILED) from None


# --- the metadata field table -------------------------------------------------

#: One bounded checker per property of ``$defs.encryption_metadata``, taken from
#: ``manifest.py`` rather than restated. The *same callable object*, asserted as
#: such by the tests: a second, independently written copy of "what a bounded
#: nonce looks like" is a copy that will drift, and the looser of the two is the
#: one that gets used. ``manifest.py`` also owns the Spec S22 rule that a
#: ``key_ref`` names a secret store and never an object-storage location.
ENCRYPTION_METADATA_VALUE_CHECKS = {
    "algorithm": _manifest._ENCRYPTION_FIELD_CHECKS["algorithm"],
    "scheme_version": _manifest._ENCRYPTION_FIELD_CHECKS["scheme_version"],
    "key_ref": _manifest._ENCRYPTION_FIELD_CHECKS["key_ref"],
    "key_rotation_generation":
        _manifest._ENCRYPTION_FIELD_CHECKS["key_rotation_generation"],
    "nonce": _manifest._ENCRYPTION_FIELD_CHECKS["nonce"],
    "tag": _manifest._ENCRYPTION_FIELD_CHECKS["tag"],
}

#: Derived, never typed out. This is the whole remedy: a field cannot be listed
#: as emitted without also having a checker, because the list *is* the checkers.
ENCRYPTION_METADATA_FIELDS = tuple(ENCRYPTION_METADATA_VALUE_CHECKS)

#: The other half of the partition. Empty today - this module emits every
#: property the contract defines, including the two optional ones, because an
#: omitted ``key_rotation_generation`` is a rotation state nobody recorded
#: (Spec S23 makes key references a rebuild input) and an omitted ``tag`` is an
#: unauthenticated object. It is not empty *by omission*: the tests assert that
#: this table plus the table above covers the schema's property set exactly, so
#: a property added to the contract later lands in neither and fails on the day
#: it is added rather than arriving unchecked on somebody's object.
REFUSED_ENCRYPTION_FIELDS = {}


def _bounded(field, value):
    """Run ``manifest.py``'s bounded checker for a field, silently."""
    try:
        ENCRYPTION_METADATA_VALUE_CHECKS[field](value, field=field)
    except Exception:  # noqa: BLE001 - the text is discarded on purpose
        _refuse(field, "is outside the bound the manifest schema sets for it")


# --- the encrypted object -----------------------------------------------------


@dataclasses.dataclass(frozen=True)
class EncryptedObject:
    """Ciphertext plus the metadata that describes how to undo it.

    There is deliberately no field a plaintext key could be written into. The
    six metadata fields are exactly the schema's, every one of them is validated
    on construction by ``manifest.py``'s own checker, and ``repr`` prints
    neither the ciphertext nor the key reference - the first because it is the
    object, the second because a reference is still a pointer somebody can
    follow, and neither belongs in a log line written by accident.
    """

    ciphertext: bytes
    algorithm: str
    scheme_version: int
    key_ref: str
    key_rotation_generation: int
    nonce: str
    tag: str

    def __post_init__(self):
        if type(self.ciphertext) is bytearray:
            object.__setattr__(self, "ciphertext", bytes(self.ciphertext))
        if type(self.ciphertext) is not bytes:
            _refuse("ciphertext", "must be bytes")
        if len(self.ciphertext) > MAX_PAYLOAD_BYTES:
            _refuse("ciphertext",
                    f"is longer than the {MAX_PAYLOAD_BYTES}-byte bound this "
                    "module buffers in memory")
        for field in ENCRYPTION_METADATA_FIELDS:
            _bounded(field, getattr(self, field))
        for field in ("nonce", "tag"):
            if _b64_canonical(getattr(self, field)) is None:
                _refuse(field,
                        "is not the canonical base64 spelling of its own bytes. "
                        "Base64 slack bits let several strings decode to the "
                        "same value, and in a content-addressed mesh two "
                        "byte-different manifests for one object is a "
                        "deduplication hazard")

    def metadata(self):
        """Spec S21: algorithm, version and a key *reference* only.

        A fresh dict each call, in the declared field order. Never the key,
        never the ciphertext, never anything this module was handed that it did
        not validate.
        """
        return {field: getattr(self, field)
                for field in ENCRYPTION_METADATA_FIELDS}

    def replace(self, **fields):
        """A new object with some fields changed, re-validated from scratch.

        Rotation and re-encryption need this (Spec S21: rotation must not change
        canonical object identity semantics), and so do the tamper tests. The
        keyword set is closed and the refusal redacts the name, because a field
        name is as good a place to hide a credential as a value.
        """
        allowed = set(ENCRYPTION_METADATA_FIELDS) | {"ciphertext"}
        for name in fields:
            if name not in allowed:
                _refuse(name, "is not a field of an encrypted object")
        current = {name: getattr(self, name) for name in allowed}
        current.update(fields)
        return EncryptedObject(**current)

    def __repr__(self):
        # ``algorithm`` is a closed vocabulary and safe to name. The key
        # reference is not printed: it is available from ``metadata()`` to a
        # caller who asked for it, and absent from every accidental log line.
        return (f"EncryptedObject(algorithm={self.algorithm!r}, "
                f"scheme_version={self.scheme_version!r}, "
                f"ciphertext_bytes={len(self.ciphertext)})")


@dataclasses.dataclass(frozen=True)
class UploadPlan:
    """What may be handed to a storage adapter, and under what encryption state.

    Produced by ``prepare_upload``, which is where Spec S4's "CONFIDENTIAL
    leaves owned storage encrypted or not at all" is decided. It is also
    exported, and therefore constructible: a frozen dataclass in ``__all__``
    with no validation let a caller build
    ``UploadPlan(payload=b"PLAINTEXT", privacy_class="CONFIDENTIAL",
    encryption_state="CLIENT_SIDE_ENCRYPTED", encryption={})`` and hand it to an
    adapter - a plaintext CONFIDENTIAL object labelled as ciphertext, which is
    Spec S4's exact failure with the one check that exists to prevent it stepped
    around. The docstring said "produced only by ``prepare_upload``" and nothing
    made that true.

    So the rule is re-checked here rather than only at the factory. The type
    stays exported, because callers need it for ``isinstance``; what changes is
    that constructing one directly is no longer a way to skip Spec S4. This is a
    consistency check on a plan and not a second decision: it can refuse a plan,
    it cannot approve one ``prepare_upload`` would have refused.
    """

    payload: bytes
    privacy_class: str
    encryption_state: str
    encryption: dict = None

    #: The two states a plan may carry. A third would be a claim about the
    #: object nobody in this module can verify.
    ENCRYPTION_STATES = ("NONE", "CLIENT_SIDE_ENCRYPTED")

    def __post_init__(self):
        if type(self.payload) is bytearray:
            object.__setattr__(self, "payload", bytes(self.payload))
        if type(self.payload) is not bytes:
            _refuse("payload", "must be bytes")
        if self.privacy_class not in PRIVACY_CLASSES:
            _refuse("privacy_class",
                    f"is not one of {list(PRIVACY_CLASSES)}; an unrecognised "
                    "class fails closed rather than defaulting")
        if self.privacy_class in NEVER_UPLOADED:
            _refuse("privacy_class",
                    "is LOCAL_ONLY, which must never be uploaded to third-party "
                    "storage. Encrypting it does not change that: an encrypted "
                    "upload is still an upload (Spec S4)")
        if self.encryption_state not in self.ENCRYPTION_STATES:
            _refuse("encryption_state",
                    f"is not one of {list(self.ENCRYPTION_STATES)}")
        if self.encryption_state == "NONE":
            if self.encryption is not None:
                _refuse("encryption",
                        "is present on a plan that says the object is "
                        "plaintext; a plan cannot say at once that there is "
                        "nothing to decrypt and that a key opens it")
            if self.privacy_class in ENCRYPTION_REQUIRED_CLASSES:
                _refuse("encryption_state",
                        f"is NONE for a {self.privacy_class} object. Spec S4 "
                        "and policy.yaml "
                        "privacy.CONFIDENTIAL.client_encryption_required leave "
                        "no plaintext path out of owned storage for this class")
            return
        if not isinstance(self.encryption, dict):
            _refuse("encryption",
                    "is absent from a plan claiming the payload is ciphertext. "
                    "An unverifiable encryption claim is how a plaintext object "
                    "comes to be treated as ciphertext (Spec S4)")
        if set(self.encryption) != set(ENCRYPTION_METADATA_FIELDS):
            _refuse("encryption",
                    "is not the metadata of an encrypted object: the field set "
                    "is exactly the schema's, so a mapping that merely looks "
                    "the part is refused rather than forwarded")
        for field in ENCRYPTION_METADATA_FIELDS:
            _bounded(field, self.encryption[field])

    def __repr__(self):
        return (f"UploadPlan(privacy_class={self.privacy_class!r}, "
                f"encryption_state={self.encryption_state!r}, "
                f"payload_bytes={len(self.payload)})")


# --- provider handling --------------------------------------------------------


def _attr(obj, name):
    """``getattr`` that cannot itself blow up (Spec S14: degrade, don't crash)."""
    try:
        return getattr(obj, name, None)
    except Exception:  # noqa: BLE001
        return None


def _declares_double(obj):
    """Does this object declare itself a non-cryptographic stand-in?

    ``_attr`` wraps only the ``getattr``; the *truth test* used to happen
    outside it, and both halves of that were wrong. An attribute whose
    ``__bool__`` raises escaped as a raw exception carrying its own message into
    the traceback - the module's one credential-leak path - and an
    ``is_test_double`` *property* that raised was swallowed to ``None``, which
    is falsy, which skipped the gate and let a non-cryptographic double through
    as a real backend. That is the only gate in this module that failed *open*.

    An object that cannot say what it is is treated as a double. The cost of
    being wrong in that direction is a refusal; the cost of being wrong in the
    other direction is real data protected by a dict.
    """
    try:
        return bool(getattr(obj, "is_test_double", False))
    except Exception:  # noqa: BLE001 - an unreadable declaration is a refusal
        return True


def _test_double_gate(obj, allow_test_double, *, what):
    """Refuse a non-cryptographic stand-in unless three things all line up.

    The object must declare ``is_test_double``, carry the exact
    acknowledgement, *and* the call site must have passed
    ``allow_test_double=True``. One gate that can be satisfied by accident is
    not a gate; three that must agree cannot be tripped by a provider that
    merely looks the part.
    """
    if not _declares_double(obj):
        return
    if allow_test_double is not True:
        _unavailable(
            f"the {what} identifies itself as a non-cryptographic test double "
            "and the call site did not pass allow_test_double=True")
    if _attr(obj, "test_double_acknowledgement") != TEST_DOUBLE_ACKNOWLEDGEMENT:
        _unavailable(
            f"the {what} identifies itself as a test double but does not carry "
            "the acknowledgement that says what that means")


def _bounded_length(value, low, high):
    return type(value) is int and low <= value <= high


def _aead_of(key_provider, *, allow_test_double):
    """The injected AEAD primitive, or a refusal. Never a fallback."""
    if key_provider is None:
        _unavailable("no key provider was supplied")
    _test_double_gate(key_provider, allow_test_double, what="key provider")
    aead = _attr(key_provider, "aead")
    if aead is None:
        _unavailable("the key provider supplies no AEAD primitive")
    _test_double_gate(aead, allow_test_double, what="AEAD provider")
    for name in ("seal", "open"):
        if not callable(_attr(aead, name)):
            _unavailable(f"the AEAD provider has no callable {name!r}")
    if not _bounded_length(_attr(aead, "key_length"), min(ALLOWED_KEY_BYTES),
                           max(ALLOWED_KEY_BYTES)) or \
            _attr(aead, "key_length") not in ALLOWED_KEY_BYTES:
        _unavailable(
            "the AEAD provider declares a key length that is not one of the "
            f"standard sizes {ALLOWED_KEY_BYTES}")
    if not _bounded_length(_attr(aead, "nonce_length"), MIN_NONCE_BYTES,
                           MAX_NONCE_BYTES):
        _unavailable(
            "the AEAD provider declares a nonce length outside "
            f"{MIN_NONCE_BYTES}..{MAX_NONCE_BYTES} bytes, which is what the "
            "manifest's 32-character nonce field can represent")
    if not _bounded_length(_attr(aead, "tag_length"), MIN_TAG_BYTES,
                           MAX_TAG_BYTES):
        _unavailable(
            "the AEAD provider declares an authentication tag outside "
            f"{MIN_TAG_BYTES}..{MAX_TAG_BYTES} bytes, which is what the "
            "manifest's 32-character tag field can represent")
    _reconcile_shape(aead)
    return aead


def _reconcile_shape(aead):
    """The declared parameters must be the ones the declared *name* means.

    The bounds above are coarse and independent of each other; this is the check
    that the three of them together are the construction the provider says it
    is. Without it, ``metadata()`` - and therefore the manifest, and therefore
    Spec S23's rebuild input - attests an algorithm nobody performed.

    An algorithm with no entry in ``ALGORITHM_SHAPES`` is refused rather than
    waved through on the coarse bounds alone.
    """
    algorithm = _algorithm_of(aead)
    shape = ALGORITHM_SHAPES.get(algorithm)
    if shape is None:
        _unavailable(
            "the AEAD provider declares an algorithm this module has no "
            "parameter shape for, so the name it would write into the manifest "
            "cannot be reconciled with what it actually does")
    if (_attr(aead, "key_length"), _attr(aead, "nonce_length"),
            _attr(aead, "tag_length")) != shape:
        _unavailable(
            "the AEAD provider declares parameters that are not the ones its "
            "declared algorithm uses. The algorithm name goes into the object "
            "manifest, which Spec S23 makes a rebuild input, so metadata that "
            "attests a construction which was not performed is refused here "
            "rather than written down")


def _algorithm_of(aead):
    algorithm = _attr(aead, "algorithm")
    try:
        ENCRYPTION_METADATA_VALUE_CHECKS["algorithm"](algorithm,
                                                      field="algorithm")
    except Exception:  # noqa: BLE001 - the text is discarded on purpose
        _unavailable(
            "the AEAD provider declares an algorithm that is not in "
            "policy.yaml encryption.allowed_algorithms")
    return algorithm


def _key_material(key_provider, key_ref, aead):
    """The key bytes, or a refusal. Returned to one caller and never stored.

    Python cannot reliably zeroise a ``bytes`` object, so this module does the
    next best thing: the value is never assigned to an attribute, never placed
    in a container that outlives the call, and never formatted into a message.
    """
    lookup = _attr(key_provider, "key_for")
    if not callable(lookup):
        _unavailable("the key provider has no callable 'key_for'")
    try:
        key = lookup(key_ref)
    except Exception:  # noqa: BLE001 - a secret store's error text is not ours
        _unavailable("the key provider raised while resolving the key reference")
    if type(key) not in (bytes, bytearray):
        _unavailable(
            "the key provider returned something that is not key material")
    if len(key) != aead.key_length:
        _unavailable(
            "the key provider returned material of the wrong length for this "
            "construction")
    return bytes(key)


def _generation_of(key_provider, key_ref):
    lookup = _attr(key_provider, "key_rotation_generation")
    if not callable(lookup):
        return 0
    try:
        generation = lookup(key_ref)
    except Exception:  # noqa: BLE001
        _unavailable("the key provider raised while reporting key rotation state")
    if type(generation) is not int:
        _unavailable("the key provider reported a non-integer rotation generation")
    return generation


def _validated_key_ref(key_ref):
    """Spec S22, enforced with ``manifest.py``'s own rule rather than a copy."""
    _bounded("key_ref", key_ref)
    try:
        _manifest.assert_no_credential_material(key_ref, where="key_ref")
    except Exception:  # noqa: BLE001 - the checker quotes its input
        _refuse("key_ref",
                "has the shape of credential material rather than a pointer at "
                "a secret store")
    return key_ref


def _payload_bytes(payload, *, field="payload"):
    """``bytes`` or ``bytearray`` only; text is refused rather than encoded.

    Picking an encoding on the caller's behalf would make the ciphertext - and
    therefore what comes back out - depend on a guess made here. ``memoryview``
    is refused because it can be a non-contiguous or non-byte-typed view of
    something else.
    """
    if type(payload) not in (bytes, bytearray):
        _refuse(field,
                "must be bytes or bytearray; text is refused rather than "
                "encoded, because an encoding chosen here would be a guess that "
                "changes what comes back out")
    if len(payload) > MAX_PAYLOAD_BYTES:
        _refuse(field,
                f"is longer than the {MAX_PAYLOAD_BYTES}-byte bound this module "
                "buffers in memory; a larger object needs chunked encryption, "
                "which is a contract this module does not have")
    return bytes(payload)


def _associated_data(algorithm, key_ref, generation):
    """What the ciphertext is bound to, beyond itself.

    The key reference is in here on purpose: without it, re-pointing an object
    at a different key is a silent try-and-see rather than an authentication
    failure, and Spec S23 makes key references a disaster-recovery input that
    somebody will edit.
    """
    return _AAD_DOMAIN + json.dumps(
        {"algorithm": algorithm, "key_ref": key_ref,
         "key_rotation_generation": generation,
         "scheme_version": SCHEME_VERSION},
        sort_keys=True, separators=(",", ":")).encode("utf-8")


def _b64(raw):
    return base64.b64encode(raw).decode("ascii")


def _b64_canonical(value):
    """The bytes a base64 string spells, but only if it spells them canonically.

    Base64 leaves unused bits in the final character when the input length is
    not a multiple of three: a 16-byte tag has two, so four distinct strings
    decode to the same bytes and all four used to round trip. This mesh is
    content-addressed and its manifests are compared and deduplicated, so two
    byte-different manifests describing the identical object is a hazard on its
    own, before anything is decrypted. One spelling is admitted: the one this
    module emits.

    Returns ``None`` rather than raising, so each caller can refuse in its own
    vocabulary - ``_refuse`` at construction, ``_failed`` on the decrypt path
    where a distinguishable refusal would be an oracle.
    """
    if not isinstance(value, str):
        return None
    try:
        raw = base64.b64decode(value, validate=True)
    except Exception:  # noqa: BLE001
        return None
    if _b64(raw) != value:
        return None
    return raw


# --- the contract -------------------------------------------------------------


def encrypt_for_storage(payload, key_provider, key_ref, *,
                        allow_test_double=False):
    """Authenticate and encrypt ``payload`` with the provider's AEAD primitive.

    ``key_provider`` supplies both halves of what is needed and neither is
    chosen here: ``key_provider.aead`` is the AEAD primitive (with
    ``algorithm``, ``key_length``, ``nonce_length``, ``tag_length``, ``seal``
    and ``open``), and ``key_provider.key_for(key_ref)`` returns the key bytes.
    Supply nothing and the call fails closed.

    Returns an ``EncryptedObject``. Raises ``ValueError`` for a malformed
    argument and ``EncryptionUnavailable`` when there is no usable primitive or
    no usable key.
    """
    payload = _payload_bytes(payload)
    key_ref = _validated_key_ref(key_ref)
    aead = _aead_of(key_provider, allow_test_double=allow_test_double)
    algorithm = _algorithm_of(aead)
    generation = _generation_of(key_provider, key_ref)
    associated_data = _associated_data(algorithm, key_ref, generation)
    nonce = secrets.token_bytes(aead.nonce_length)
    key = _key_material(key_provider, key_ref, aead)
    try:
        sealed = aead.seal(key, nonce, payload, associated_data)
    except Exception:  # noqa: BLE001 - a backend's error text is not ours
        _unavailable("the AEAD provider raised while sealing the object")
    finally:
        del key
    if type(sealed) not in (bytes, bytearray) or len(sealed) < aead.tag_length:
        _unavailable(
            "the AEAD provider returned something that is not sealed bytes")
    sealed = bytes(sealed)
    return EncryptedObject(
        ciphertext=sealed[:len(sealed) - aead.tag_length],
        algorithm=algorithm,
        scheme_version=SCHEME_VERSION,
        key_ref=key_ref,
        key_rotation_generation=generation,
        nonce=_b64(nonce),
        tag=_b64(sealed[len(sealed) - aead.tag_length:]),
    )


def decrypt_from_storage(encrypted, key_provider, *, allow_test_double=False):
    """Authenticate and decrypt an ``EncryptedObject``, or refuse.

    There is no path through this function that returns bytes the injected AEAD
    did not authenticate - the qualification is in the module docstring: a
    primitive that lies is believed - and every refusal reached after an
    attacker-controlled field has been read raises ``DecryptionFailed`` with the
    same message, so the caller learns that it failed and not which part failed.
    The refusals raised before that point, by ``_aead_of``, are about the
    caller's own process rather than about this object.
    """
    if not isinstance(encrypted, EncryptedObject):
        _refuse("encrypted",
                "is not an EncryptedObject. A mapping that merely has the right "
                "keys is refused: it has not been through the metadata bounds, "
                "and accepting one would make those bounds optional")
    aead = _aead_of(key_provider, allow_test_double=allow_test_double)
    if _attr(aead, "algorithm") != encrypted.algorithm:
        _failed()
    if encrypted.scheme_version != SCHEME_VERSION:
        _failed()
    nonce = _b64_canonical(encrypted.nonce)
    tag = _b64_canonical(encrypted.tag)
    if nonce is None or tag is None:
        # Undecodable and non-canonical are the same refusal here. The
        # constructor already rejects both, so reaching this is an object built
        # around ``__post_init__``; it is still not told which half it got wrong.
        _failed()
    if len(nonce) != aead.nonce_length or len(tag) != aead.tag_length:
        _failed()
    associated_data = _associated_data(encrypted.algorithm, encrypted.key_ref,
                                       encrypted.key_rotation_generation)
    try:
        key = _key_material(key_provider, encrypted.key_ref, aead)
    except EncryptionUnavailable:
        # The key reference is attacker-controlled. A secret store that cannot
        # resolve it and a secret store that resolves it to the wrong key have
        # to be one refusal: a caller who can submit objects and read the
        # *exception type* would otherwise enumerate which references exist,
        # which is the namespace Spec S22/S23 treat as sensitive rebuild input.
        # Provider and AEAD-shape problems found by ``_aead_of`` above, before
        # any attacker-controlled field has been read, legitimately stay
        # ``EncryptionUnavailable``: they say nothing about this object.
        _failed()
    try:
        plaintext = aead.open(key, nonce, encrypted.ciphertext + tag,
                              associated_data)
    except Exception:  # noqa: BLE001 - every cause is one failure here
        _failed()
    finally:
        del key
    if type(plaintext) not in (bytes, bytearray):
        _failed()
    return bytes(plaintext)


def prepare_upload(record, *, payload=None, encrypted=None):
    """Decide what bytes may leave for a backend, and under what state.

    Spec S4, the only rule this function exists for: a CONFIDENTIAL object may
    leave owned storage only as ciphertext, and a LOCAL_ONLY object may not
    leave at all - encrypted or otherwise, because an encrypted upload is still
    an upload.

    ``record`` is a manifest-shaped mapping; only ``privacy_class`` is read, but
    the key set is closed against the manifest schema so that a key nobody
    anticipated is refused rather than silently ignored. This function chooses
    no backend: which provider receives the plan is Task 3's decision.
    """
    if not isinstance(record, dict):
        _refuse("record", "must be a mapping describing the object")
    for name in record:
        if _RECORD_FIELDS and name not in _RECORD_FIELDS:
            _refuse(name, "is not a field of an object manifest record")
    if "privacy_class" not in record:
        _refuse("privacy_class",
                "is absent, and an object whose privacy class nobody stated "
                "must not leave owned storage on a default (Spec S4)")
    privacy_class = record["privacy_class"]
    if not isinstance(privacy_class, str) or privacy_class not in PRIVACY_CLASSES:
        _refuse("privacy_class",
                f"is not one of {list(PRIVACY_CLASSES)}; an unrecognised class "
                "fails closed rather than defaulting, because either default "
                "would be a guess about privacy")
    if privacy_class in NEVER_UPLOADED:
        _refuse("privacy_class",
                "is LOCAL_ONLY, which must never be uploaded to third-party "
                "storage. Encrypting it does not change that: an encrypted "
                "upload is still an upload (Spec S4)")
    if payload is not None and encrypted is not None:
        _refuse("payload",
                "was supplied alongside ciphertext. Exactly one of the two is "
                "uploaded, and letting a caller pass both invites the plan to "
                "carry the plaintext of an object it claims is encrypted")
    if encrypted is None:
        if privacy_class in ENCRYPTION_REQUIRED_CLASSES:
            _refuse("encrypted",
                    f"is None for a {privacy_class} object. Spec S4 and "
                    "policy.yaml privacy.CONFIDENTIAL.client_encryption_required "
                    "require client-side encryption before upload, so there is "
                    "no plaintext path out of owned storage for this class")
        if payload is None:
            _refuse("payload",
                    "and 'encrypted' are both absent; there is nothing to upload")
        return UploadPlan(payload=_payload_bytes(payload),
                          privacy_class=privacy_class,
                          encryption_state="NONE", encryption=None)
    if not isinstance(encrypted, EncryptedObject):
        _refuse("encrypted",
                "is not an EncryptedObject. An object that merely claims to be "
                "encrypted is how a plaintext object comes to be treated as "
                "ciphertext (Spec S4)")
    return UploadPlan(payload=encrypted.ciphertext,
                      privacy_class=privacy_class,
                      encryption_state="CLIENT_SIDE_ENCRYPTED",
                      encryption=encrypted.metadata())


__all__ = [
    "AUTHORITY", "AUTHORITY_FLAGS", "CANONICAL_AUTHORITY", "ROUTED_BY",
    "CRYPTOGRAPHY_IMPLEMENTED_HERE", "AEAD_PROVIDER_REQUIRED",
    "PERMITTED_IMPORTS", "SCHEME_VERSION", "TEST_DOUBLE_ACKNOWLEDGEMENT",
    "ALLOWED_ALGORITHMS", "ALGORITHM_SHAPES",
    "ALGORITHMS_WITHOUT_A_KNOWN_SHAPE", "ALLOWED_KEY_BYTES", "MIN_NONCE_BYTES",
    "MAX_NONCE_BYTES", "MIN_TAG_BYTES", "MAX_TAG_BYTES", "MAX_PAYLOAD_BYTES",
    "NEVER_UPLOADED", "ENCRYPTION_REQUIRED_CLASSES",
    "ENCRYPTION_METADATA_VALUE_CHECKS", "ENCRYPTION_METADATA_FIELDS",
    "REFUSED_ENCRYPTION_FIELDS", "EncryptionUnavailable", "DecryptionFailed",
    "EncryptedObject", "UploadPlan", "encrypt_for_storage",
    "decrypt_from_storage", "prepare_upload",
]
