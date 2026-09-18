"""Task 6 - the client-side encryption contract (Spec S4, S21, S22, S23).

Three things this suite is built to prove, because each one is a specific way
this task goes wrong.

1. **No cryptography is invented here, and none is hard-imported either.**
   ``cryptography`` imports in the development container but is *not* a declared
   dependency: ``AI_SKILL_LIBRARY/requirements.txt`` is two lines, ``PyYAML``
   and ``jsonschema``, and every CI workflow installs exactly that. A module
   that says ``import cryptography`` at the top is green on a laptop and red in
   CI. So the AEAD primitive is *injected*, the module imports with no crypto
   library present at all, and every operation fails closed when nobody supplies
   one. ``ImportsWithoutACryptoLibraryTests`` proves the import in a subprocess
   with ``cryptography``, ``nacl`` and ``Crypto`` blocked at the meta path.

2. **The stand-in used by these tests is not a cipher.** It is a vault: it
   escrows the plaintext in an in-memory dict and hands back an opaque token.
   It performs no transformation of any kind - no XOR, no keystream, no
   homemade MAC - because a "good enough" construction in a test file is a
   construction somebody ships. It also refuses to run unless it is explicitly
   acknowledged as a test double on *both* sides: the double itself demands the
   acknowledgement string, and ``encryption.py`` refuses a provider that
   identifies as a test double unless the caller passes ``allow_test_double``.
   A real AEAD is exercised too, in a class that skips cleanly when
   ``cryptography`` is absent, so the suite is green either way.

3. **A credential-shaped needle fed through every input reaches no output.**
   Not only ``str(exc)``: Task 5 found a leak that ``str(exc)`` hid and
   ``traceback.format_exc()`` printed, under "During handling of the above
   exception", because a refusal raised inside an ``except`` carries the
   original as ``__context__``. Every leak assertion here checks the formatted
   traceback as well as ``str``, ``repr`` and the serialised metadata.

The structural guard follows Tasks 4 and 5: the field list is not typed out
here, it is *derived* from ``ENCRYPTION_METADATA_VALUE_CHECKS``, and the test
that checks it complete drives the property set from
``storage_object_manifest.schema.json`` on disk. A field added to the contract
later lands in neither the accepted table nor the refused one and fails on the
day it is added.
"""

from __future__ import annotations

import ast
import base64
import hmac
import json
import os
import secrets
import subprocess
import sys
import traceback
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from AI_SKILL_LIBRARY.v4.storage import manifest as manifest_module
from AI_SKILL_LIBRARY.v4.storage import encryption

from AI_SKILL_LIBRARY.tests.test_storage_metadata import (
    AUTHORITY_FLAGS,
    SMUGGLED_CREDENTIAL,
)

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "AI_SKILL_LIBRARY/v4/storage/encryption.py"
MANIFEST_SCHEMA_PATH = ROOT / "AI_SKILL_LIBRARY/v4/schemas/storage_object_manifest.schema.json"
MANIFEST_SCHEMA = json.loads(MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
MANIFEST_VALIDATOR = Draft202012Validator(MANIFEST_SCHEMA)
ENCRYPTION_SCHEMA = MANIFEST_SCHEMA["$defs"]["encryption_metadata"]

PLAINTEXT = b"federated-free-storage-mesh-confidential-object"
KEY_REF = "secretstore://mesh/object-dek/current"

#: A second needle, shaped like a credential but short enough to survive the
#: length bounds a long one trips on its own. The point of a needle is to test
#: the *redaction*, not the length check that happens to precede it.
SHORT_NEEDLE = "sk-" + ("A7bQ" * 9)


# --- the non-cryptographic test double ---------------------------------------


_UNSET = object()


class NotCryptographyError(RuntimeError):
    """Raised when the vault double is used without acknowledgement."""


class VaultTestDouble:
    """**NOT A CIPHER. NOT CRYPTOGRAPHY. NEVER FOR REAL DATA.**

    This class provides *zero* confidentiality. ``seal`` does not transform the
    plaintext at all: it stores it in a Python dict under a random token and
    returns the token. ``open`` looks the token up. It is a stand-in for the
    *shape* of an AEAD - a key, a nonce, associated data, a tag, and a refusal
    when any of them is wrong - and for nothing else.

    It is written this way on purpose. A test file that XORs bytes together, or
    hashes a key with a nonce and calls the result a keystream, has invented
    cryptography; the fact that it lives under ``tests/`` is not a control,
    because the next person to need an AEAD copies the nearest thing that
    looks like one. There is nothing here to copy.

    It refuses to exist unless the caller passes the acknowledgement string, and
    ``encryption.py`` refuses it a second time unless the call site passes
    ``allow_test_double=True``. Two independent gates, because one that can be
    satisfied by accident is not a gate.
    """

    is_test_double = True
    test_double_acknowledgement = encryption.TEST_DOUBLE_ACKNOWLEDGEMENT

    def __init__(self, acknowledgement=None, *, algorithm="aead-standard-library",
                 key_length=32, nonce_length=12, tag_length=16):
        if acknowledgement != encryption.TEST_DOUBLE_ACKNOWLEDGEMENT:
            raise NotCryptographyError(
                "VaultTestDouble provides no confidentiality and refuses to be "
                "constructed without the test-double acknowledgement")
        self.algorithm = algorithm
        self.key_length = key_length
        self.nonce_length = nonce_length
        self.tag_length = tag_length
        self._vault = {}

    def seal(self, key, nonce, plaintext, associated_data):
        token = secrets.token_bytes(len(plaintext) + self.tag_length)
        self._vault[bytes(token)] = (bytes(key), bytes(nonce), bytes(plaintext),
                                     bytes(associated_data))
        return token

    def open(self, key, nonce, ciphertext, associated_data):
        record = self._vault.get(bytes(ciphertext))
        if record is None:
            raise NotCryptographyError("no such sealed object")
        stored_key, stored_nonce, plaintext, stored_aad = record
        if not hmac.compare_digest(stored_key, bytes(key)):
            raise NotCryptographyError("key mismatch")
        if not hmac.compare_digest(stored_nonce, bytes(nonce)):
            raise NotCryptographyError("nonce mismatch")
        if not hmac.compare_digest(stored_aad, bytes(associated_data)):
            raise NotCryptographyError("associated data mismatch")
        return plaintext


class KeyProviderDouble:
    """A key provider backed by the vault double.

    ``key_for`` returns bytes and nothing else. The key never leaves this
    object except as the return value of that call, and no test asserts on its
    value beyond its length.
    """

    is_test_double = True
    test_double_acknowledgement = encryption.TEST_DOUBLE_ACKNOWLEDGEMENT

    def __init__(self, aead=None, *, key=_UNSET, generation=0, raises=None):
        self.aead = aead if aead is not None else VaultTestDouble(
            encryption.TEST_DOUBLE_ACKNOWLEDGEMENT)
        self._key = secrets.token_bytes(32) if key is _UNSET else key
        self._generation = generation
        self._raises = raises

    def key_for(self, key_ref):
        if self._raises is not None:
            raise self._raises
        return self._key

    def key_rotation_generation(self, key_ref):
        return self._generation


def provider(**kwargs):
    return KeyProviderDouble(**kwargs)


def seal(payload=PLAINTEXT, key_provider=None, key_ref=KEY_REF):
    key_provider = key_provider if key_provider is not None else provider()
    return encryption.encrypt_for_storage(
        payload, key_provider, key_ref, allow_test_double=True), key_provider


def formatted_traceback(callable_, *args, **kwargs):
    """The full formatted traceback of whatever escapes, or ``""``.

    ``str(exc)`` is not enough. A refusal raised inside an ``except`` block
    carries the exception it was raised from as ``__context__``; ``str`` hides
    it and every traceback prints it.
    """
    try:
        callable_(*args, **kwargs)
    except BaseException as exc:  # noqa: BLE001 - the text is the subject
        return "".join(traceback.format_exception(type(exc), exc,
                                                  exc.__traceback__))
    return ""


def tamper(raw):
    """Flip the last byte of a byte string."""
    return raw[:-1] + bytes([raw[-1] ^ 0x01])


class AuthorityTests(unittest.TestCase):
    """This module encrypts. It decides nothing (Spec S2)."""

    def test_no_authority_of_any_kind(self):
        self.assertIs(encryption.AUTHORITY, False)
        for flag in AUTHORITY_FLAGS:
            self.assertIs(encryption.AUTHORITY_FLAGS[flag], False, flag)
        self.assertEqual(set(encryption.AUTHORITY_FLAGS), set(AUTHORITY_FLAGS))

    def test_github_remains_canonical(self):
        self.assertEqual(encryption.CANONICAL_AUTHORITY, "GITHUB_BRAIN_V4")

    def test_no_cryptographic_primitive_is_implemented_here(self):
        self.assertIs(encryption.CRYPTOGRAPHY_IMPLEMENTED_HERE, False)
        self.assertIs(encryption.AEAD_PROVIDER_REQUIRED, True)

    def test_this_module_makes_no_placement_decision(self):
        for name in ("choose_backend", "place", "select_provider", "rebalance"):
            self.assertFalse(hasattr(encryption, name), name)


class ImportsWithoutACryptoLibraryTests(unittest.TestCase):
    """The dependency gate, asserted rather than assumed.

    ``cryptography`` is not in ``AI_SKILL_LIBRARY/requirements.txt`` and CI
    installs exactly that file, so a hard import here is a red pipeline. These
    tests are the standing guard against somebody adding one back.
    """

    def test_requirements_still_do_not_declare_a_crypto_library(self):
        text = (ROOT / "AI_SKILL_LIBRARY/requirements.txt").read_text(
            encoding="utf-8").lower()
        for name in ("cryptography", "pynacl", "pycryptodome", "nacl"):
            self.assertNotIn(name, text, name)

    def test_the_module_imports_only_the_standard_library_and_this_lane(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])
        self.assertLessEqual(imported, encryption.PERMITTED_IMPORTS)
        for name in ("cryptography", "nacl", "Crypto", "cryptodome"):
            self.assertNotIn(name, imported, name)

    def test_the_module_imports_with_every_crypto_library_blocked(self):
        program = (
            "import sys\n"
            "class Block:\n"
            "    blocked = ('cryptography', 'nacl', 'Crypto', 'Cryptodome')\n"
            "    def find_module(self, name, path=None):\n"
            "        return self.find_spec(name, path)\n"
            "    def find_spec(self, name, path=None, target=None):\n"
            "        if name.split('.')[0] in self.blocked:\n"
            "            raise ImportError('blocked for this test: ' + name)\n"
            "        return None\n"
            "sys.meta_path.insert(0, Block())\n"
            "from AI_SKILL_LIBRARY.v4.storage import encryption\n"
            "print(encryption.AUTHORITY, encryption.CRYPTOGRAPHY_IMPLEMENTED_HERE)\n"
        )
        result = subprocess.run([sys.executable, "-c", program], cwd=str(ROOT),
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "False False")


class TestDoubleGateTests(unittest.TestCase):
    """A non-cryptographic stand-in must be impossible to use by accident."""

    def test_the_double_refuses_to_be_constructed_without_acknowledgement(self):
        with self.assertRaises(NotCryptographyError):
            VaultTestDouble()
        with self.assertRaises(NotCryptographyError):
            VaultTestDouble("sure, whatever")

    def test_the_acknowledgement_says_what_it_acknowledges(self):
        text = encryption.TEST_DOUBLE_ACKNOWLEDGEMENT
        self.assertIsInstance(text, str)
        self.assertIn("NOT CRYPTOGRAPHY", text.upper())
        self.assertGreater(len(text), 40)

    def test_encrypt_refuses_a_test_double_unless_the_caller_opts_in(self):
        with self.assertRaises(encryption.EncryptionUnavailable):
            encryption.encrypt_for_storage(PLAINTEXT, provider(), KEY_REF)

    def test_decrypt_refuses_a_test_double_unless_the_caller_opts_in(self):
        encrypted, keys = seal()
        with self.assertRaises(encryption.EncryptionUnavailable):
            encryption.decrypt_from_storage(encrypted, keys)

    def test_a_provider_claiming_to_be_a_double_without_the_string_is_refused(self):
        class Liar(KeyProviderDouble):
            test_double_acknowledgement = "trust me"

        with self.assertRaises(encryption.EncryptionUnavailable):
            encryption.encrypt_for_storage(PLAINTEXT, Liar(), KEY_REF,
                                           allow_test_double=True)


class RoundTripTests(unittest.TestCase):
    def test_round_trip_returns_the_original_bytes(self):
        encrypted, keys = seal()
        self.assertEqual(
            encryption.decrypt_from_storage(encrypted, keys,
                                            allow_test_double=True),
            PLAINTEXT)

    def test_empty_payload_round_trips(self):
        encrypted, keys = seal(payload=b"")
        self.assertEqual(
            encryption.decrypt_from_storage(encrypted, keys,
                                            allow_test_double=True),
            b"")

    def test_bytearray_payload_is_accepted(self):
        encrypted, keys = seal(payload=bytearray(PLAINTEXT))
        self.assertEqual(
            encryption.decrypt_from_storage(encrypted, keys,
                                            allow_test_double=True),
            PLAINTEXT)

    def test_two_encryptions_of_the_same_payload_use_different_nonces(self):
        keys = provider()
        first, _ = seal(key_provider=keys)
        second, _ = seal(key_provider=keys)
        self.assertNotEqual(first.metadata()["nonce"],
                            second.metadata()["nonce"])

    def test_the_ciphertext_is_not_the_plaintext(self):
        encrypted, _ = seal()
        self.assertNotIn(PLAINTEXT, encrypted.ciphertext)


class MetadataTests(unittest.TestCase):
    """Spec S21: algorithm, version and a key *reference* only."""

    def test_metadata_never_contains_key_bytes(self):
        needle = b"secret-key-material-0123456789ab"
        encrypted, _ = seal(key_provider=provider(key=needle))
        blob = json.dumps(encrypted.metadata()).lower()
        self.assertNotIn("secret-key-material", blob)
        self.assertNotIn(base64.b64encode(needle).decode().lower(), blob)
        self.assertNotIn(needle.hex(), blob)

    def test_metadata_carries_the_key_reference(self):
        encrypted, _ = seal()
        self.assertEqual(encrypted.metadata()["key_ref"], KEY_REF)

    def test_metadata_fields_are_exactly_the_declared_table(self):
        encrypted, _ = seal()
        self.assertEqual(set(encrypted.metadata()),
                         set(encryption.ENCRYPTION_METADATA_FIELDS))

    def test_metadata_validates_against_the_schema_on_disk(self):
        encrypted, _ = seal()
        Draft202012Validator(ENCRYPTION_SCHEMA).validate(encrypted.metadata())

    def test_metadata_is_a_copy_the_caller_cannot_mutate_back_in(self):
        encrypted, _ = seal()
        first = encrypted.metadata()
        first["key_ref"] = "env://somewhere-else"
        self.assertEqual(encrypted.metadata()["key_ref"], KEY_REF)

    def test_metadata_holds_no_field_a_key_could_be_written_into(self):
        encrypted, _ = seal()
        for name in ("key", "key_material", "dek", "kek", "passphrase",
                     "secret", "plaintext_key", "wrapped_key"):
            self.assertNotIn(name, encrypted.metadata(), name)

    def test_the_encrypted_object_never_exposes_the_key(self):
        needle = b"secret-key-material-0123456789ab"
        encrypted, _ = seal(key_provider=provider(key=needle))
        for name in dir(encrypted):
            if name.startswith("__"):
                continue
            value = getattr(encrypted, name, None)
            if isinstance(value, (bytes, bytearray)):
                self.assertNotIn(needle, bytes(value), name)

    def test_a_manifest_record_accepts_this_metadata(self):
        encrypted, _ = seal()
        record = manifest_module.StorageObject.from_bytes(
            encrypted.ciphertext,
            privacy_class="CONFIDENTIAL",
            criticality="IMPORTANT",
            storage_tier="WARM",
            encryption_state="CLIENT_SIDE_ENCRYPTED",
            encryption_scheme_version=encrypted.metadata()["scheme_version"],
            encryption=encrypted.metadata(),
        ).to_manifest()
        MANIFEST_VALIDATOR.validate(record)


class StructuralGuardTests(unittest.TestCase):
    """The field list is derived, and completeness is driven by the schema.

    This class of hole has got past this project four times: a field is
    whitelisted by name and then validated by nothing. The remedy Tasks 4 and 5
    established is a checker table that the field tuple is *derived from*, and a
    test that walks the schema on disk so a property added later has nowhere to
    hide.
    """

    def test_the_field_tuple_is_derived_from_the_checker_table(self):
        self.assertEqual(encryption.ENCRYPTION_METADATA_FIELDS,
                         tuple(encryption.ENCRYPTION_METADATA_VALUE_CHECKS))

    def test_every_schema_property_is_accepted_or_refused_with_a_reason(self):
        declared = set(encryption.ENCRYPTION_METADATA_VALUE_CHECKS)
        refused = set(encryption.REFUSED_ENCRYPTION_FIELDS)
        self.assertEqual(declared | refused, set(ENCRYPTION_SCHEMA["properties"]))
        self.assertEqual(declared & refused, set())

    def test_every_refusal_states_a_reason(self):
        for field, reason in encryption.REFUSED_ENCRYPTION_FIELDS.items():
            with self.subTest(field=field):
                self.assertIsInstance(reason, str)
                self.assertGreater(len(reason), 20)

    def test_the_checkers_are_the_manifest_module_s_own(self):
        # Not a fifth copy. The same callable object, so the two cannot drift.
        for field, check in encryption.ENCRYPTION_METADATA_VALUE_CHECKS.items():
            with self.subTest(field=field):
                self.assertIs(check, manifest_module._ENCRYPTION_FIELD_CHECKS[field])

    def test_every_emitted_string_field_is_bounded_by_pattern_and_length(self):
        encrypted, _ = seal()
        for field, value in encrypted.metadata().items():
            if not isinstance(value, str):
                continue
            with self.subTest(field=field):
                spec = ENCRYPTION_SCHEMA["properties"][field]
                self.assertTrue("pattern" in spec or "enum" in spec, field)
                if "pattern" in spec:
                    self.assertIn("maxLength", spec)
                    self.assertLessEqual(len(value), spec["maxLength"])

    def test_no_anchored_regex_in_the_module_uses_a_dollar_anchor(self):
        # ``$`` also matches before a trailing newline in Python; ``\Z`` does
        # not. A validator looser than the schema it mirrors is the bug class.
        source = MODULE_PATH.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value.startswith("^"):
                    self.assertFalse(node.value.endswith("$"), node.value)


class FailClosedTests(unittest.TestCase):
    """No provider, no key, no algorithm, no operation."""

    def test_no_provider_at_all_refuses(self):
        with self.assertRaises(encryption.EncryptionUnavailable):
            encryption.encrypt_for_storage(PLAINTEXT, None, KEY_REF,
                                           allow_test_double=True)

    def test_a_provider_without_an_aead_refuses(self):
        keys = provider()
        keys.aead = None
        with self.assertRaises(encryption.EncryptionUnavailable):
            encryption.encrypt_for_storage(PLAINTEXT, keys, KEY_REF,
                                           allow_test_double=True)

    def test_an_aead_missing_seal_or_open_refuses(self):
        for missing in ("seal", "open"):
            with self.subTest(missing=missing):
                aead = VaultTestDouble(encryption.TEST_DOUBLE_ACKNOWLEDGEMENT)
                setattr(aead, missing, None)
                with self.assertRaises(encryption.EncryptionUnavailable):
                    encryption.encrypt_for_storage(
                        PLAINTEXT, provider(aead=aead), KEY_REF,
                        allow_test_double=True)

    def test_an_unknown_algorithm_refuses(self):
        for algorithm in ("rot13", "aes-128-cbc", "", None, 7, "AES-256-GCM"):
            with self.subTest(algorithm=algorithm):
                aead = VaultTestDouble(encryption.TEST_DOUBLE_ACKNOWLEDGEMENT,
                                       algorithm=algorithm)
                with self.assertRaises((ValueError,
                                        encryption.EncryptionUnavailable)):
                    encryption.encrypt_for_storage(
                        PLAINTEXT, provider(aead=aead), KEY_REF,
                        allow_test_double=True)

    def test_every_policy_algorithm_is_accepted(self):
        for algorithm in encryption.ALLOWED_ALGORITHMS:
            with self.subTest(algorithm=algorithm):
                aead = VaultTestDouble(encryption.TEST_DOUBLE_ACKNOWLEDGEMENT,
                                       algorithm=algorithm)
                encrypted, keys = seal(key_provider=provider(aead=aead))
                self.assertEqual(encrypted.metadata()["algorithm"], algorithm)

    def test_a_key_provider_returning_none_or_nothing_refuses(self):
        for key in (None, b""):
            with self.subTest(key=repr(key)):
                with self.assertRaises(encryption.EncryptionUnavailable):
                    encryption.encrypt_for_storage(
                        PLAINTEXT, provider(key=key), KEY_REF,
                        allow_test_double=True)

    def test_a_key_of_the_wrong_length_refuses(self):
        for length in (0, 1, 8, 15, 31, 33, 64, 4096):
            with self.subTest(length=length):
                with self.assertRaises(encryption.EncryptionUnavailable):
                    encryption.encrypt_for_storage(
                        PLAINTEXT, provider(key=b"k" * length), KEY_REF,
                        allow_test_double=True)

    def test_a_key_of_the_wrong_type_refuses(self):
        for key in (None, "k" * 32, 32, [1] * 32, {"k": 1}, memoryview(b"k" * 32),
                    True, 1.5, object()):
            with self.subTest(key=type(key).__name__):
                with self.assertRaises(encryption.EncryptionUnavailable):
                    encryption.encrypt_for_storage(
                        PLAINTEXT, provider(key=key), KEY_REF,
                        allow_test_double=True)

    def test_a_key_provider_that_raises_refuses(self):
        keys = provider(raises=RuntimeError("secret store is down"))
        with self.assertRaises(encryption.EncryptionUnavailable):
            encryption.encrypt_for_storage(PLAINTEXT, keys, KEY_REF,
                                           allow_test_double=True)

    def test_a_key_provider_without_key_for_refuses(self):
        class NoLookup:
            is_test_double = True
            test_double_acknowledgement = encryption.TEST_DOUBLE_ACKNOWLEDGEMENT
            aead = VaultTestDouble(encryption.TEST_DOUBLE_ACKNOWLEDGEMENT)

        with self.assertRaises(encryption.EncryptionUnavailable):
            encryption.encrypt_for_storage(PLAINTEXT, NoLookup(), KEY_REF,
                                           allow_test_double=True)

    def test_a_text_payload_is_refused_rather_than_encoded(self):
        with self.assertRaises(ValueError):
            encryption.encrypt_for_storage("text", provider(), KEY_REF,
                                           allow_test_double=True)

    def test_a_payload_over_the_bound_is_refused(self):
        oversized = bytearray(encryption.MAX_PAYLOAD_BYTES + 1)
        with self.assertRaises(ValueError):
            encryption.encrypt_for_storage(oversized, provider(), KEY_REF,
                                           allow_test_double=True)

    def test_a_nonce_or_tag_length_outside_the_metadata_bound_refuses(self):
        for kwargs in ({"nonce_length": 0}, {"nonce_length": 4},
                       {"nonce_length": 32}, {"nonce_length": 64},
                       {"tag_length": 0}, {"tag_length": 4}, {"tag_length": 32},
                       {"nonce_length": "12"}, {"tag_length": None},
                       {"key_length": 7}, {"key_length": 0},
                       {"key_length": 4096}, {"key_length": "32"}):
            with self.subTest(**kwargs):
                aead = VaultTestDouble(encryption.TEST_DOUBLE_ACKNOWLEDGEMENT,
                                       **kwargs)
                with self.assertRaises(encryption.EncryptionUnavailable):
                    encryption.encrypt_for_storage(
                        PLAINTEXT, provider(aead=aead), KEY_REF,
                        allow_test_double=True)


class KeyReferenceTests(unittest.TestCase):
    """Spec S22: the reference points at a secret store, never at a bucket."""

    def test_allowed_schemes_are_accepted(self):
        for ref in ("env://MESH_OBJECT_DEK",
                    "secretstore://mesh/object-dek/current",
                    "worker-secret://mesh-worker/dek",
                    "kms://project/keyring/mesh-dek"):
            with self.subTest(ref=ref):
                encrypted, _ = seal(key_ref=ref)
                self.assertEqual(encrypted.metadata()["key_ref"], ref)

    def test_an_object_storage_location_is_refused(self):
        for ref in ("https://bucket.r2.cloudflarestorage.com/mesh/dek",
                    "s3://mesh-objects/dek.bin",
                    "gs://mesh/dek",
                    "file:///etc/mesh/dek",
                    "AI_SKILL_LIBRARY/v4/storage/dek.bin",
                    "supabase://public.storage_keys/1",
                    "dropbox://backup/dek"):
            with self.subTest(ref=ref):
                with self.assertRaises(ValueError):
                    encryption.encrypt_for_storage(PLAINTEXT, provider(), ref,
                                                   allow_test_double=True)

    def test_a_bare_key_as_the_reference_is_refused(self):
        for ref in ("0" * 64, base64.b64encode(b"k" * 32).decode(),
                    SHORT_NEEDLE, SMUGGLED_CREDENTIAL):
            with self.subTest(ref=ref[:16]):
                with self.assertRaises(ValueError):
                    encryption.encrypt_for_storage(PLAINTEXT, provider(), ref,
                                                   allow_test_double=True)

    def test_a_credential_shaped_reference_inside_an_allowed_scheme_is_refused(self):
        with self.assertRaises(ValueError):
            encryption.encrypt_for_storage(
                PLAINTEXT, provider(), "secretstore://" + SHORT_NEEDLE,
                allow_test_double=True)

    def test_an_over_long_reference_is_refused(self):
        with self.assertRaises(ValueError):
            encryption.encrypt_for_storage(PLAINTEXT, provider(),
                                           "env://" + "A" * 400,
                                           allow_test_double=True)

    def test_a_reference_of_the_wrong_type_is_refused(self):
        for ref in (None, 1, b"env://X", ["env://X"], {"env": "X"}, True,
                    object()):
            with self.subTest(ref=type(ref).__name__):
                with self.assertRaises(ValueError):
                    encryption.encrypt_for_storage(PLAINTEXT, provider(), ref,
                                                   allow_test_double=True)

    def test_the_key_reference_rule_is_the_manifest_module_s_own(self):
        self.assertIs(encryption.ENCRYPTION_METADATA_VALUE_CHECKS["key_ref"],
                      manifest_module._ENCRYPTION_FIELD_CHECKS["key_ref"])


class TamperTests(unittest.TestCase):
    """Decryption of tampered data must never return plaintext."""

    def refuses(self, encrypted, keys):
        with self.assertRaises(encryption.DecryptionFailed):
            encryption.decrypt_from_storage(encrypted, keys,
                                            allow_test_double=True)

    def test_tampered_ciphertext_refuses(self):
        encrypted, keys = seal()
        self.refuses(encrypted.replace(ciphertext=tamper(encrypted.ciphertext)),
                     keys)

    def test_truncated_ciphertext_refuses(self):
        encrypted, keys = seal()
        self.refuses(encrypted.replace(ciphertext=encrypted.ciphertext[:-1]),
                     keys)

    def test_empty_ciphertext_refuses(self):
        encrypted, keys = seal()
        self.refuses(encrypted.replace(ciphertext=b""), keys)

    def test_tampered_tag_refuses(self):
        encrypted, keys = seal()
        tag = encrypted.metadata()["tag"]
        flipped = base64.b64encode(tamper(base64.b64decode(tag))).decode()
        self.refuses(encrypted.replace(tag=flipped), keys)

    def test_tampered_nonce_refuses(self):
        encrypted, keys = seal()
        nonce = encrypted.metadata()["nonce"]
        flipped = base64.b64encode(tamper(base64.b64decode(nonce))).decode()
        self.refuses(encrypted.replace(nonce=flipped), keys)

    def test_tampered_key_reference_refuses(self):
        # The key reference is bound as associated data, so re-pointing the
        # ciphertext at a different key is an authentication failure and not a
        # silent decrypt-with-whatever-is-there.
        encrypted, keys = seal()
        self.refuses(encrypted.replace(key_ref="env://SOMETHING_ELSE"), keys)

    def test_tampered_rotation_generation_refuses(self):
        encrypted, keys = seal()
        self.refuses(encrypted.replace(key_rotation_generation=9), keys)

    def test_wrong_key_refuses(self):
        aead = VaultTestDouble(encryption.TEST_DOUBLE_ACKNOWLEDGEMENT)
        encrypted, _ = seal(key_provider=provider(aead=aead))
        self.refuses(encrypted,
                     provider(aead=aead, key=secrets.token_bytes(32)))

    def test_every_refusal_reads_the_same(self):
        # No oracle: a caller must not be able to tell *which* part failed.
        encrypted, keys = seal()
        messages = set()
        for mutated in (encrypted.replace(ciphertext=tamper(encrypted.ciphertext)),
                        encrypted.replace(ciphertext=encrypted.ciphertext[:-1]),
                        encrypted.replace(key_ref="env://SOMETHING_ELSE")):
            try:
                encryption.decrypt_from_storage(mutated, keys,
                                                allow_test_double=True)
            except encryption.DecryptionFailed as exc:
                messages.add(str(exc))
        self.assertEqual(len(messages), 1, messages)

    def test_a_decrypt_of_a_non_encrypted_object_refuses(self):
        keys = provider()
        for candidate in (None, {}, PLAINTEXT, "ciphertext", 1, [],
                          {"ciphertext": b"x", "key_ref": KEY_REF}, object()):
            with self.subTest(candidate=type(candidate).__name__):
                with self.assertRaises((ValueError,
                                        encryption.DecryptionFailed,
                                        encryption.EncryptionUnavailable)):
                    encryption.decrypt_from_storage(candidate, keys,
                                                    allow_test_double=True)

    def test_an_unknown_scheme_version_refuses(self):
        encrypted, keys = seal()
        for version in (2, 4096, 0):
            with self.subTest(version=version):
                with self.assertRaises((ValueError,
                                        encryption.DecryptionFailed)):
                    encryption.decrypt_from_storage(
                        encrypted.replace(scheme_version=version), keys,
                        allow_test_double=True)

    def test_an_algorithm_the_provider_does_not_serve_refuses(self):
        encrypted, keys = seal()
        mutated = encrypted.replace(algorithm="chacha20-poly1305")
        with self.assertRaises((ValueError, encryption.DecryptionFailed,
                                encryption.EncryptionUnavailable)):
            encryption.decrypt_from_storage(mutated, keys,
                                            allow_test_double=True)


class NoLeakTests(unittest.TestCase):
    """A credential-shaped needle through every input reaches no output."""

    def assertNoNeedle(self, text, needle=SMUGGLED_CREDENTIAL):
        self.assertNotIn(needle, text)
        self.assertNotIn(needle[:40], text)

    def test_a_needle_in_the_payload_never_surfaces(self):
        encrypted, keys = seal(payload=SMUGGLED_CREDENTIAL.encode())
        self.assertNoNeedle(repr(encrypted))
        self.assertNoNeedle(str(encrypted))
        self.assertNoNeedle(json.dumps(encrypted.metadata()))

    def test_a_needle_in_the_key_reference_never_surfaces(self):
        text = formatted_traceback(encryption.encrypt_for_storage, PLAINTEXT,
                                   provider(), SMUGGLED_CREDENTIAL,
                                   allow_test_double=True)
        self.assertTrue(text)
        self.assertNoNeedle(text)

    def test_a_short_needle_in_the_key_reference_never_surfaces(self):
        text = formatted_traceback(encryption.encrypt_for_storage, PLAINTEXT,
                                   provider(), "secretstore://" + SHORT_NEEDLE,
                                   allow_test_double=True)
        self.assertTrue(text)
        self.assertNoNeedle(text, SHORT_NEEDLE)

    def test_needle_key_bytes_never_surface(self):
        needle = SMUGGLED_CREDENTIAL[:31].encode()
        text = formatted_traceback(encryption.encrypt_for_storage, PLAINTEXT,
                                   provider(key=needle), KEY_REF,
                                   allow_test_double=True)
        self.assertTrue(text)
        self.assertNoNeedle(text, needle.decode())

    def test_a_correct_length_needle_key_never_surfaces(self):
        needle = (SMUGGLED_CREDENTIAL[:32]).encode()
        encrypted, keys = seal(key_provider=provider(key=needle))
        self.assertNoNeedle(repr(encrypted), needle.decode())
        self.assertNoNeedle(json.dumps(encrypted.metadata()), needle.decode())
        self.assertNoNeedle(
            formatted_traceback(encryption.decrypt_from_storage,
                                encrypted.replace(ciphertext=b"x"), keys,
                                allow_test_double=True),
            needle.decode())

    def test_a_needle_in_a_provider_error_never_surfaces(self):
        keys = provider(raises=RuntimeError(SMUGGLED_CREDENTIAL))
        text = formatted_traceback(encryption.encrypt_for_storage, PLAINTEXT,
                                   keys, KEY_REF, allow_test_double=True)
        self.assertTrue(text)
        self.assertNoNeedle(text)

    def test_a_needle_in_a_provider_error_type_name_never_surfaces(self):
        error = type("Err" + SHORT_NEEDLE.replace("-", "_"), (RuntimeError,), {})
        keys = provider(raises=error("boom"))
        text = formatted_traceback(encryption.encrypt_for_storage, PLAINTEXT,
                                   keys, KEY_REF, allow_test_double=True)
        self.assertTrue(text)
        self.assertNoNeedle(text, SHORT_NEEDLE.replace("-", "_"))

    def test_a_needle_in_an_aead_error_never_surfaces(self):
        aead = VaultTestDouble(encryption.TEST_DOUBLE_ACKNOWLEDGEMENT)

        def exploding(*args, **kwargs):
            raise RuntimeError(SMUGGLED_CREDENTIAL)

        aead.seal = exploding
        text = formatted_traceback(encryption.encrypt_for_storage, PLAINTEXT,
                                   provider(aead=aead), KEY_REF,
                                   allow_test_double=True)
        self.assertTrue(text)
        self.assertNoNeedle(text)

    def test_a_needle_in_a_metadata_value_never_surfaces(self):
        encrypted, keys = seal()
        for field in encryption.ENCRYPTION_METADATA_FIELDS:
            with self.subTest(field=field):
                text = formatted_traceback(
                    encrypted.replace, **{field: SMUGGLED_CREDENTIAL})
                self.assertTrue(text)
                self.assertNoNeedle(text)

    def test_a_needle_in_a_metadata_key_never_surfaces(self):
        encrypted, _ = seal()
        text = formatted_traceback(encrypted.replace,
                                   **{"k" + SHORT_NEEDLE.replace("-", "_"): 1})
        self.assertTrue(text)
        self.assertNoNeedle(text, SHORT_NEEDLE.replace("-", "_"))

    def test_a_needle_in_a_prepare_upload_record_never_surfaces(self):
        for record in ({"privacy_class": SMUGGLED_CREDENTIAL},
                       {"privacy_class": "CONFIDENTIAL",
                        SMUGGLED_CREDENTIAL: 1}):
            with self.subTest(record=sorted(record)[0][:12]):
                text = formatted_traceback(encryption.prepare_upload, record,
                                           payload=PLAINTEXT)
                self.assertTrue(text)
                self.assertNoNeedle(text)

    def test_a_needle_in_a_decrypt_argument_never_surfaces(self):
        text = formatted_traceback(encryption.decrypt_from_storage,
                                   SMUGGLED_CREDENTIAL, provider(),
                                   allow_test_double=True)
        self.assertTrue(text)
        self.assertNoNeedle(text)


class PrepareUploadTests(unittest.TestCase):
    """Spec S4: CONFIDENTIAL leaves owned storage encrypted or not at all."""

    def confidential(self, **overrides):
        record = {"privacy_class": "CONFIDENTIAL", "criticality": "IMPORTANT"}
        record.update(overrides)
        return record

    def test_confidential_requires_encryption(self):
        with self.assertRaises(ValueError):
            encryption.prepare_upload(self.confidential(), encrypted=None,
                                      payload=PLAINTEXT)

    def test_confidential_with_no_encrypted_argument_at_all_refuses(self):
        with self.assertRaises(ValueError):
            encryption.prepare_upload(self.confidential(), payload=PLAINTEXT)

    def test_confidential_with_ciphertext_is_accepted(self):
        encrypted, _ = seal()
        plan = encryption.prepare_upload(self.confidential(),
                                         encrypted=encrypted)
        self.assertEqual(plan.payload, encrypted.ciphertext)
        self.assertEqual(plan.encryption_state, "CLIENT_SIDE_ENCRYPTED")
        self.assertEqual(plan.encryption, encrypted.metadata())

    def test_local_only_never_leaves(self):
        with self.assertRaises(ValueError):
            encryption.prepare_upload({"privacy_class": "LOCAL_ONLY"},
                                      payload=PLAINTEXT)

    def test_local_only_is_refused_even_when_encrypted(self):
        encrypted, _ = seal()
        with self.assertRaises(ValueError):
            encryption.prepare_upload({"privacy_class": "LOCAL_ONLY"},
                                      encrypted=encrypted)

    def test_public_and_internal_may_upload_plaintext(self):
        for privacy_class in ("PUBLIC", "INTERNAL"):
            with self.subTest(privacy_class=privacy_class):
                plan = encryption.prepare_upload(
                    {"privacy_class": privacy_class}, payload=PLAINTEXT)
                self.assertEqual(plan.payload, PLAINTEXT)
                self.assertEqual(plan.encryption_state, "NONE")
                self.assertIsNone(plan.encryption)

    def test_public_may_also_be_encrypted(self):
        encrypted, _ = seal()
        plan = encryption.prepare_upload({"privacy_class": "PUBLIC"},
                                         encrypted=encrypted)
        self.assertEqual(plan.encryption_state, "CLIENT_SIDE_ENCRYPTED")

    def test_both_payload_and_ciphertext_is_refused(self):
        encrypted, _ = seal()
        with self.assertRaises(ValueError):
            encryption.prepare_upload({"privacy_class": "PUBLIC"},
                                      payload=PLAINTEXT, encrypted=encrypted)

    def test_neither_payload_nor_ciphertext_is_refused(self):
        with self.assertRaises(ValueError):
            encryption.prepare_upload({"privacy_class": "PUBLIC"})

    def test_an_unknown_privacy_class_refuses(self):
        for privacy_class in ("SECRET", "public", "", None, 1, True, [], {}):
            with self.subTest(privacy_class=privacy_class):
                with self.assertRaises(ValueError):
                    encryption.prepare_upload(
                        {"privacy_class": privacy_class}, payload=PLAINTEXT)

    def test_a_record_that_is_not_a_mapping_refuses(self):
        for record in (None, "CONFIDENTIAL", 1, [], (), b"CONFIDENTIAL", object()):
            with self.subTest(record=type(record).__name__):
                with self.assertRaises(ValueError):
                    encryption.prepare_upload(record, payload=PLAINTEXT)

    def test_an_encrypted_argument_that_is_not_an_encrypted_object_refuses(self):
        for candidate in ("ciphertext", b"ciphertext", 1, [], object(),
                          {"ciphertext": b"x"}):
            with self.subTest(candidate=type(candidate).__name__):
                with self.assertRaises(ValueError):
                    encryption.prepare_upload(self.confidential(),
                                              encrypted=candidate)

    def test_the_plan_never_carries_a_key(self):
        needle = b"secret-key-material-0123456789ab"
        encrypted, _ = seal(key_provider=provider(key=needle))
        plan = encryption.prepare_upload(self.confidential(),
                                         encrypted=encrypted)
        self.assertNotIn(b"secret-key-material", plan.payload)
        self.assertNotIn("secret-key-material", json.dumps(plan.encryption))
        self.assertNotIn("secret-key-material", repr(plan))


class DegradeDoNotCrashTests(unittest.TestCase):
    """Spec S14. Hostile types refuse; they do not escape as a TypeError.

    ``bytes`` is a ``collections.abc.Sequence``, which is how a bytes object
    walks through a "is this a sequence of records" check, so byte strings are
    in the sweep on purpose.
    """

    HOSTILE = (None, "", "x", b"", b"x", bytearray(b"x"), 0, 1, -1, 1.5, True,
               False, [], (), {}, set(), [PLAINTEXT], {"a": 1}, object(),
               10 ** 30, memoryview(b"x"), SMUGGLED_CREDENTIAL)

    ALLOWED = (ValueError, encryption.EncryptionUnavailable,
               encryption.DecryptionFailed)

    def test_encrypt_refuses_every_hostile_argument(self):
        for value in self.HOSTILE:
            for call in (
                lambda v: encryption.encrypt_for_storage(
                    v, provider(), KEY_REF, allow_test_double=True),
                lambda v: encryption.encrypt_for_storage(
                    PLAINTEXT, v, KEY_REF, allow_test_double=True),
                lambda v: encryption.encrypt_for_storage(
                    PLAINTEXT, provider(), v, allow_test_double=True),
            ):
                with self.subTest(value=repr(value)[:24]):
                    try:
                        call(value)
                    except self.ALLOWED:
                        pass

    def test_decrypt_refuses_every_hostile_argument(self):
        encrypted, keys = seal()
        for value in self.HOSTILE:
            with self.subTest(value=repr(value)[:24]):
                try:
                    encryption.decrypt_from_storage(value, keys,
                                                    allow_test_double=True)
                except self.ALLOWED:
                    pass
                try:
                    encryption.decrypt_from_storage(encrypted, value,
                                                    allow_test_double=True)
                except self.ALLOWED:
                    pass

    def test_prepare_upload_refuses_every_hostile_argument(self):
        for value in self.HOSTILE:
            with self.subTest(value=repr(value)[:24]):
                try:
                    encryption.prepare_upload(value, payload=PLAINTEXT)
                except self.ALLOWED:
                    pass
                try:
                    encryption.prepare_upload({"privacy_class": "PUBLIC"},
                                              payload=value)
                except self.ALLOWED:
                    pass
                try:
                    encryption.prepare_upload({"privacy_class": "CONFIDENTIAL"},
                                              encrypted=value)
                except self.ALLOWED:
                    pass


def _probe_for_a_real_aead():  # pragma: no cover - availability, not behaviour
    """Try to obtain a real AEAD, without assuming the attempt is survivable.

    ``BaseException`` and not ``Exception``: in this container the import does
    not raise ``ImportError``. ``cryptography`` is installed but its Rust
    bindings cannot find ``_cffi_backend``, so the import panics out of pyo3 and
    surfaces as ``pyo3_runtime.PanicException`` - a ``BaseException``, which an
    ``except Exception`` guard walks straight past. That is the case for
    injection in one line: "cryptography imports here" was not even true.

    The panic is written to file descriptor 2 by Rust rather than through
    ``sys.stderr``, so it is silenced at the descriptor and not with
    ``redirect_stderr``.
    """
    saved = os.dup(2)
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, 2)
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        return AESGCM
    except BaseException:  # noqa: BLE001
        return None
    finally:
        os.dup2(saved, 2)
        os.close(saved)
        os.close(devnull)


_AESGCM = _probe_for_a_real_aead()


class RealAeadAdapter:
    """A thin adapter over ``cryptography``'s AES-GCM.

    Not a test double: it declares nothing about being one, and it must work
    through the same injection path a production backend would use. It is also
    the whole shape a reviewer has to add to make this module do real work -
    roughly twenty lines and one line in ``requirements.txt``.
    """

    algorithm = "aes-256-gcm"
    key_length = 32
    nonce_length = 12
    tag_length = 16

    def seal(self, key, nonce, plaintext, associated_data):
        return _AESGCM(bytes(key)).encrypt(bytes(nonce), bytes(plaintext),
                                           bytes(associated_data))

    def open(self, key, nonce, ciphertext, associated_data):
        return _AESGCM(bytes(key)).decrypt(bytes(nonce), bytes(ciphertext),
                                           bytes(associated_data))


class RealKeyProvider:
    def __init__(self, key=None):
        self.aead = RealAeadAdapter()
        self._key = key if key is not None else secrets.token_bytes(32)

    def key_for(self, key_ref):
        return self._key

    def key_rotation_generation(self, key_ref):
        return 0


@unittest.skipUnless(_AESGCM is not None,
                     "cryptography is not installed; it is not a declared "
                     "dependency of this repository and CI does not install it")
class RealAeadTests(unittest.TestCase):
    """The same contract, driven by a real AEAD when one happens to be here."""

    def test_round_trip(self):
        keys = RealKeyProvider()
        encrypted = encryption.encrypt_for_storage(PLAINTEXT, keys, KEY_REF)
        self.assertNotIn(PLAINTEXT, encrypted.ciphertext)
        self.assertEqual(encryption.decrypt_from_storage(encrypted, keys),
                         PLAINTEXT)

    def test_no_opt_in_is_needed_for_a_real_backend(self):
        keys = RealKeyProvider()
        encryption.encrypt_for_storage(PLAINTEXT, keys, KEY_REF)

    def test_tampered_ciphertext_refuses(self):
        keys = RealKeyProvider()
        encrypted = encryption.encrypt_for_storage(PLAINTEXT, keys, KEY_REF)
        with self.assertRaises(encryption.DecryptionFailed):
            encryption.decrypt_from_storage(
                encrypted.replace(ciphertext=tamper(encrypted.ciphertext)), keys)

    def test_tampered_tag_refuses(self):
        keys = RealKeyProvider()
        encrypted = encryption.encrypt_for_storage(PLAINTEXT, keys, KEY_REF)
        tag = base64.b64decode(encrypted.metadata()["tag"])
        with self.assertRaises(encryption.DecryptionFailed):
            encryption.decrypt_from_storage(
                encrypted.replace(tag=base64.b64encode(tamper(tag)).decode()),
                keys)

    def test_tampered_nonce_refuses(self):
        keys = RealKeyProvider()
        encrypted = encryption.encrypt_for_storage(PLAINTEXT, keys, KEY_REF)
        nonce = base64.b64decode(encrypted.metadata()["nonce"])
        with self.assertRaises(encryption.DecryptionFailed):
            encryption.decrypt_from_storage(
                encrypted.replace(nonce=base64.b64encode(tamper(nonce)).decode()),
                keys)

    def test_tampered_key_reference_refuses(self):
        keys = RealKeyProvider()
        encrypted = encryption.encrypt_for_storage(PLAINTEXT, keys, KEY_REF)
        with self.assertRaises(encryption.DecryptionFailed):
            encryption.decrypt_from_storage(
                encrypted.replace(key_ref="env://SOMETHING_ELSE"), keys)

    def test_wrong_key_refuses(self):
        keys = RealKeyProvider()
        encrypted = encryption.encrypt_for_storage(PLAINTEXT, keys, KEY_REF)
        with self.assertRaises(encryption.DecryptionFailed):
            encryption.decrypt_from_storage(encrypted,
                                            RealKeyProvider(secrets.token_bytes(32)))

    def test_metadata_validates_against_the_schema_on_disk(self):
        keys = RealKeyProvider()
        encrypted = encryption.encrypt_for_storage(PLAINTEXT, keys, KEY_REF)
        Draft202012Validator(ENCRYPTION_SCHEMA).validate(encrypted.metadata())

    def test_a_needle_key_never_surfaces_through_a_real_backend(self):
        keys = RealKeyProvider(SMUGGLED_CREDENTIAL[:32].encode())
        encrypted = encryption.encrypt_for_storage(PLAINTEXT, keys, KEY_REF)
        self.assertNotIn(SMUGGLED_CREDENTIAL[:32], repr(encrypted))
        self.assertNotIn(SMUGGLED_CREDENTIAL[:32],
                         json.dumps(encrypted.metadata()))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
