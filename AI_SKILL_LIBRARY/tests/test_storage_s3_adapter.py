"""Task 5a - the S3-compatible object adapter, and what it refuses to store.

Tasks 1-4 built a mesh that has never held a byte. ``manifest.py`` says what an
object *is*, ``placement.py`` says where it may go, ``metadata.py`` remembers
that it went there - and none of them can put it there. This module is the edge
where bytes cross out of the process, and the whole of it is written on the
assumption that everything on the far side is hostile or broken.

Five themes, each one the answer to a specific way an object adapter goes
wrong.

1. **No network, ever, anywhere in this file.** There is no S3 client here and
   none in the module under test: the transport is a callable injected at
   runtime, and without one the store is simply unusable. The tests prove that
   twice over - once by asserting the module imports no networking machinery,
   and once by replacing ``socket.socket`` with something that raises and then
   driving every public method through a fake.

2. **Identity is recomputed, never accepted.** ``put`` refuses to store bytes
   under an ``object_id`` that is not their digest, ``get`` re-hashes what came
   back before returning it, and a receipt built from a ``head`` is marked as
   the provider's *claim* rather than as evidence. A content-addressed store
   that believes the address it was handed is not content-addressed; it is a
   key-value store with a longer key.

3. **The credential never lands anywhere.** It is fetched from a zero-argument
   provider at the moment of a call, handed to the transport as a keyword, and
   never placed on the instance, in the request payload, in a receipt, in a
   repr or in an exception message. The sweep below pushes a credential-shaped
   needle through every input the adapter accepts and requires that no output
   of any kind contains it - including the text of the refusal.

4. **Every accepted field is bounded, and completeness is structural.** The
   metadata a caller may attach to an object is a projection of
   ``storage_object_manifest.schema.json``, and every property of that schema is
   either in ``OBJECT_METADATA_VALUE_CHECKS`` with a bounded checker or in
   ``REFUSED_METADATA_FIELDS`` with a reason. The test that asserts this drives
   the field list *from the schema on disk*, so a property added to the contract
   later lands in neither set and fails the test the day it is added. This lane
   has shipped "an allowed field whose value nothing bounds" three times; a
   hand-written list of fields is how that keeps happening.

5. **Privacy outranks the transport.** A LOCAL_ONLY object is refused on an
   external backend and a CONFIDENTIAL object is refused unencrypted, at the
   last possible moment before the bytes leave. Those decisions belong to
   Task 3 and are made there; re-checking them here is not a second placement
   authority, it is the door refusing to open on a decision that was already
   wrong.

Nothing here opens a connection, writes a file, reads an environment variable
or touches a provider account.
"""

from __future__ import annotations

import ast
import json
import socket
import traceback
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from AI_SKILL_LIBRARY.v4.storage import manifest as manifest_module
from AI_SKILL_LIBRARY.v4.storage.adapters import s3_object

from AI_SKILL_LIBRARY.tests.test_storage_metadata import (
    AUTHORITY_FLAGS,
    SMUGGLED_CREDENTIAL,
    TIME,
    safe_manifest,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_SCHEMA_PATH = ROOT / "AI_SKILL_LIBRARY/v4/schemas/storage_object_manifest.schema.json"
MANIFEST_SCHEMA = json.loads(MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
MANIFEST_VALIDATOR = Draft202012Validator(MANIFEST_SCHEMA)

PAYLOAD = b"federated-free-storage-mesh-object"
OBJECT_ID = manifest_module.StorageObject.from_bytes(
    PAYLOAD,
    privacy_class="PUBLIC",
    criticality="REPRODUCIBLE",
    storage_tier="HOT",
    primary_backend="cloudflare_r2",
).object_id

ENDPOINT = "https://object-storage.example.invalid"
BUCKET = "mesh-objects"


def credential():
    """What a runtime secret store would hand back. Never a module constant."""
    return "injected-credential-value"


def object_metadata(**overrides):
    """A legitimate, fully-populated set of object metadata.

    Every field the adapter accepts is present on purpose: a call with the
    optional fields omitted cannot exercise the bounds on the optional fields,
    and those are exactly the ones a credential would ride in on.
    """
    attached = {
        "version": 1,
        "content_sha256": OBJECT_ID[len("obj_"):],
        "size_bytes": len(PAYLOAD),
        "privacy_class": "PUBLIC",
        "criticality": "REPRODUCIBLE",
        "storage_tier": "HOT",
        "lifecycle_state": "RAW",
        "encryption_state": "NONE",
        "mime_type": "application/octet-stream",
        "object_class": "benchmark-bundle",
        "retention_class": "short-window",
        "created_at": TIME,
        "reproducible": True,
    }
    attached.update(overrides)
    return {key: value for key, value in attached.items() if value is not _ABSENT}


_ABSENT = object()


class FakeS3Transport:
    """An in-memory S3-compatible endpoint. No socket, no client, no account.

    It records every call it receives, so the tests can assert on what the
    adapter *sent* as well as on what it returned - the credential handling is
    only checkable from the outbound side.
    """

    def __init__(self, *, objects=None, raise_on=(), returns=None,
                 head_override=_ABSENT, corrupt_get=False):
        self.objects = dict(objects or {})
        self.raise_on = set(raise_on)
        self.returns = dict(returns or {})
        self.head_override = head_override
        self.corrupt_get = corrupt_get
        self.calls = []
        self.deleted = []

    def __call__(self, operation, payload, *, endpoint, bucket, credential):
        self.calls.append({
            "operation": operation,
            "payload": payload,
            "endpoint": endpoint,
            "bucket": bucket,
            "credential": credential,
        })
        if operation in self.raise_on:
            raise RuntimeError(f"fake transport refuses {operation}")
        if operation in self.returns:
            return self.returns[operation]
        if operation == "put":
            self.objects[payload["key"]] = (bytes(payload["body"]),
                                            dict(payload["metadata"]))
            return True
        if operation == "get":
            stored = self.objects.get(payload["key"])
            if stored is None:
                return None
            return b"tampered-in-flight" if self.corrupt_get else stored[0]
        if operation == "head":
            if self.head_override is not _ABSENT:
                return self.head_override
            stored = self.objects.get(payload["key"])
            if stored is None:
                return None
            return {
                "size_bytes": len(stored[0]),
                "content_sha256": s3_object.content_digest(stored[0]),
                "metadata": dict(stored[1]),
            }
        if operation == "delete":
            self.deleted.append(payload["key"])
            self.objects.pop(payload["key"], None)
            return True
        raise AssertionError(f"the adapter asked for {operation!r}")


def store(transport=_ABSENT, **overrides):
    kwargs = {
        "backend_id": "cloudflare_r2",
        "endpoint": ENDPOINT,
        "bucket": BUCKET,
        "credential_provider": credential,
        "transport": FakeS3Transport() if transport is _ABSENT else transport,
        "clock": lambda: TIME,
    }
    kwargs.update(overrides)
    return s3_object.ObjectStore(**kwargs)


def refusal_text(callable_, *args, **kwargs):
    """Run something expected to refuse, and return everything it would print.

    The whole formatted traceback, chained causes included. ``str(exc)`` alone
    is not the test: ``raise Scrubbed(...) from original`` produces a clean
    message and still prints the original - credential and all - to any log
    that renders the traceback, which is every log.
    """
    try:
        callable_(*args, **kwargs)
    except BaseException as exc:  # noqa: BLE001 - the text is the subject
        return "".join(traceback.format_exception(type(exc), exc,
                                                  exc.__traceback__))
    return ""


class AuthorityTests(unittest.TestCase):
    """An adapter is a door, not a decision (Spec S2)."""

    def test_no_authority_of_any_kind(self):
        self.assertIs(s3_object.AUTHORITY, False)
        self.assertIs(s3_object.ObjectStore.AUTHORITY, False)
        for flag in AUTHORITY_FLAGS:
            self.assertIs(s3_object.AUTHORITY_FLAGS[flag], False, flag)
        self.assertEqual(set(s3_object.AUTHORITY_FLAGS), set(AUTHORITY_FLAGS))

    def test_github_remains_canonical(self):
        self.assertEqual(s3_object.CANONICAL_AUTHORITY, "GITHUB_BRAIN_V4")

    def test_no_cryptography_is_implemented_here(self):
        self.assertIs(s3_object.ENCRYPTION_IMPLEMENTED_HERE, False)
        for name in ("encrypt", "decrypt", "derive_key", "generate_key",
                     "wrap_key", "seal"):
            self.assertFalse(hasattr(s3_object, name),
                             f"{name} has no business in an object adapter")

    def test_nothing_external_is_created(self):
        self.assertIs(s3_object.CREATES_EXTERNAL_RESOURCES, False)
        self.assertIs(s3_object.PROVISIONING_AUTHORIZED, False)
        for name in ("create_bucket", "ensure_bucket", "provision",
                     "create_account", "put_bucket_policy"):
            self.assertFalse(hasattr(s3_object.ObjectStore, name),
                             f"{name} would create external state")


class NoNetworkTests(unittest.TestCase):
    """The transport is injected. There is no other way out of this process."""

    def test_the_module_imports_no_networking_machinery(self):
        # Parsed rather than grepped: a substring search over the source reads
        # the prose as well as the code, and "this module does not import
        # urllib" would fail its own test. The import statements are the fact.
        tree = ast.parse(
            (ROOT / "AI_SKILL_LIBRARY/v4/storage/adapters/s3_object.py"
             ).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        banned = {"socket", "ssl", "http", "http.client", "urllib",
                  "urllib.request", "urllib3", "requests", "boto3", "botocore",
                  "httpx", "aiohttp", "asyncio", "subprocess", "os"}
        for name in sorted(imported):
            root = name.split(".")[0]
            self.assertNotIn(name, banned, f"{name} can dial out")
            self.assertNotIn(root, banned, f"{name} can dial out")

    def test_no_hard_coded_provider_endpoint_or_credential(self):
        source = (ROOT / "AI_SKILL_LIBRARY/v4/storage/adapters/s3_object.py"
                  ).read_text(encoding="utf-8").lower()
        for banned in ("r2.cloudflarestorage.com", "backblazeb2.com",
                       "oraclecloud.com", "amazonaws.com", "access_key_id=",
                       "secret_access_key="):
            self.assertNotIn(banned, source,
                             f"{banned} is a provider binding, not an adapter")

    def test_construction_performs_no_call_at_all(self):
        transport = FakeS3Transport()
        store(transport)
        self.assertEqual(transport.calls, [])

    def test_every_method_works_with_sockets_disabled(self):
        # The strongest available proof that nothing here dials out: make a
        # socket unconstructable and then drive the whole surface.
        transport = FakeS3Transport()
        subject = store(transport)
        real_socket = socket.socket

        def refuse(*args, **kwargs):
            raise AssertionError("the adapter tried to open a socket")

        socket.socket = refuse
        try:
            subject.put(OBJECT_ID, PAYLOAD, object_metadata())
            self.assertEqual(subject.get(OBJECT_ID), PAYLOAD)
            self.assertIsNotNone(subject.head(OBJECT_ID))
            self.assertIsNone(subject.delete(OBJECT_ID))
        finally:
            socket.socket = real_socket

    def test_without_a_transport_every_operation_fails_closed(self):
        subject = store(transport=None)
        for call in (lambda: subject.put(OBJECT_ID, PAYLOAD, object_metadata()),
                     lambda: subject.get(OBJECT_ID),
                     lambda: subject.head(OBJECT_ID),
                     lambda: subject.delete(OBJECT_ID)):
            with self.assertRaises(s3_object.ObjectStoreUnavailable):
                call()


class ConstructionBoundsTests(unittest.TestCase):
    """Every string the constructor accepts is bounded by a pattern and a length."""

    def test_backend_must_be_an_s3_compatible_registry_row(self):
        for backend in ("supabase", "local_owned_store", "huggingface_hub",
                        "google_drive", "not_a_row", "", "A" * 300, None, 1,
                        True, b"cloudflare_r2"):
            with self.subTest(backend=repr(backend)[:24]):
                with self.assertRaises(ValueError):
                    store(backend_id=backend)

    def test_the_three_s3_registry_rows_are_accepted(self):
        for backend in ("cloudflare_r2", "backblaze_b2", "oracle_object_storage"):
            with self.subTest(backend=backend):
                self.assertEqual(store(backend_id=backend).backend_id, backend)

    def test_endpoint_is_bounded_and_carries_no_credential(self):
        for endpoint in (
                "http://object-storage.example.invalid",          # not https
                "https://user:key@object-storage.example.invalid",  # userinfo
                "https://object-storage.example.invalid/bucket",   # path
                "https://object-storage.example.invalid?apikey=x",  # query
                "https://" + "a" * 200 + ".example.invalid",        # unbounded
                "https://object-storage.example.invalid\n",        # trailing NL
                "", None, 1, True, b"https://x.invalid"):
            with self.subTest(endpoint=repr(endpoint)[:32]):
                with self.assertRaises(ValueError):
                    store(endpoint=endpoint)

    def test_endpoint_length_bound_is_enforced(self):
        self.assertLessEqual(s3_object.MAX_ENDPOINT, 128)
        over = "https://" + "a" * (s3_object.MAX_ENDPOINT) + ".example.invalid"
        with self.assertRaises(ValueError):
            store(endpoint=over)

    def test_bucket_is_bounded(self):
        for bucket in ("", "ab", "A" * 300, "Mesh-Objects", "mesh objects",
                       "mesh/objects", "0123456789abcdef0123456789abcdef",
                       None, 1, True, b"mesh-objects", "mesh-objects\n"):
            with self.subTest(bucket=repr(bucket)[:32]):
                with self.assertRaises(ValueError):
                    store(bucket=bucket)

    def test_key_prefix_is_bounded(self):
        self.assertEqual(store(key_prefix="objects/").key_prefix, "objects/")
        for prefix in ("objects", "/objects/", "A" * 300, "../", "obj ects/",
                       "objects/\n", None, 1, True, b"objects/"):
            with self.subTest(prefix=repr(prefix)[:32]):
                with self.assertRaises(ValueError):
                    store(key_prefix=prefix)

    def test_a_literal_credential_is_refused_as_a_provider(self):
        for provider in (SMUGGLED_CREDENTIAL, "", None, 1, True,
                         b"credential", ["credential"]):
            with self.subTest(provider=repr(provider)[:24]):
                with self.assertRaises(ValueError):
                    store(credential_provider=provider)

    def test_transport_must_be_callable_or_absent(self):
        for transport in ("transport", 1, True, [], {}):
            with self.subTest(transport=repr(transport)[:24]):
                with self.assertRaises(ValueError):
                    store(transport=transport)

    def test_clock_must_be_callable_or_absent(self):
        for clock in ("2026-09-18T00:00:00Z", 1, True, []):
            with self.subTest(clock=repr(clock)[:24]):
                with self.assertRaises(ValueError):
                    store(clock=clock)


class IdentityTests(unittest.TestCase):
    """Identity is the content. It is recomputed and never accepted."""

    def test_put_refuses_an_object_id_that_is_not_the_digest(self):
        transport = FakeS3Transport()
        subject = store(transport)
        other = manifest_module.StorageObject.from_bytes(
            b"a different object", privacy_class="PUBLIC",
            criticality="REPRODUCIBLE", storage_tier="HOT",
            primary_backend="cloudflare_r2").object_id
        with self.assertRaises(ValueError):
            subject.put(other, PAYLOAD, object_metadata())
        self.assertEqual(transport.calls, [],
                         "the bytes left before the address was checked")

    def test_put_refuses_a_malformed_object_id(self):
        subject = store()
        for object_id in ("obj_" + "z" * 64, "obj_" + "a" * 63, "",
                          "obj_" + "a" * 64 + "\n", OBJECT_ID.upper(),
                          None, 1, True, b"obj_" + b"a" * 64,
                          SMUGGLED_CREDENTIAL):
            with self.subTest(object_id=repr(object_id)[:24]):
                with self.assertRaises(ValueError):
                    subject.put(object_id, PAYLOAD, object_metadata())

    def test_put_refuses_a_payload_that_is_not_bytes(self):
        subject = store()
        for payload in ("text", None, 1, True, [], {}, memoryview(PAYLOAD),
                        SMUGGLED_CREDENTIAL):
            with self.subTest(payload=repr(payload)[:24]):
                with self.assertRaises(ValueError):
                    subject.put(OBJECT_ID, payload, object_metadata())

    def test_a_bytearray_payload_is_accepted_and_copied(self):
        transport = FakeS3Transport()
        subject = store(transport)
        mutable = bytearray(PAYLOAD)
        receipt = subject.put(OBJECT_ID, mutable, object_metadata())
        mutable.extend(b"mutated after the receipt")
        self.assertEqual(receipt.size_bytes, len(PAYLOAD))
        self.assertEqual(transport.objects[f"{OBJECT_ID}"][0], PAYLOAD)

    def test_put_refuses_an_object_over_the_size_bound(self):
        self.assertGreater(s3_object.MAX_OBJECT_BYTES, 0)
        subject = store(max_object_bytes=len(PAYLOAD) - 1)
        with self.assertRaises(ValueError):
            subject.put(OBJECT_ID, PAYLOAD, object_metadata())
        for bound in (-1, 0, 10 ** 30, "1", True, 1.5, []):
            with self.subTest(bound=repr(bound)[:16]):
                with self.assertRaises(ValueError):
                    store(max_object_bytes=bound)

    def test_get_rehashes_what_came_back(self):
        transport = FakeS3Transport(corrupt_get=True)
        subject = store(transport)
        subject.put(OBJECT_ID, PAYLOAD, object_metadata())
        with self.assertRaises(s3_object.ObjectIntegrityError):
            subject.get(OBJECT_ID)

    def test_get_of_an_absent_object_is_not_an_empty_object(self):
        subject = store()
        with self.assertRaises(s3_object.ObjectNotFound):
            subject.get(OBJECT_ID)

    def test_get_of_an_unreachable_store_is_not_an_absent_object(self):
        subject = store(FakeS3Transport(raise_on=("get",)))
        with self.assertRaises(s3_object.ObjectStoreUnavailable):
            subject.get(OBJECT_ID)

    def test_head_returns_none_for_an_absent_object(self):
        self.assertIsNone(store().head(OBJECT_ID))

    def test_head_raises_rather_than_reporting_absence_when_unreachable(self):
        subject = store(FakeS3Transport(raise_on=("head",)))
        with self.assertRaises(s3_object.ObjectStoreUnavailable):
            subject.head(OBJECT_ID)

    def test_a_head_receipt_is_a_claim_and_a_put_receipt_is_evidence(self):
        transport = FakeS3Transport()
        subject = store(transport)
        put_receipt = subject.put(OBJECT_ID, PAYLOAD, object_metadata())
        head_receipt = subject.head(OBJECT_ID)
        self.assertEqual(put_receipt.digest_source, "computed")
        self.assertEqual(head_receipt.digest_source, "provider_asserted")
        self.assertIs(put_receipt.verified, True)
        self.assertIs(head_receipt.verified, False)

    def test_a_head_that_asserts_nothing_produces_an_unverifiable_receipt(self):
        transport = FakeS3Transport(head_override={"size_bytes": len(PAYLOAD)})
        receipt = store(transport).head(OBJECT_ID)
        self.assertIsNone(receipt.content_sha256)
        self.assertEqual(receipt.digest_source, "unknown")

    def test_a_head_row_with_an_unknown_field_is_refused(self):
        transport = FakeS3Transport(head_override={"x-amz-meta-key": "value"})
        with self.assertRaises(s3_object.ObjectStoreError):
            store(transport).head(OBJECT_ID)

    def test_a_transport_that_does_not_acknowledge_is_a_failure(self):
        for answer in (None, False, "ok", 1, 0, {}, []):
            with self.subTest(answer=repr(answer)[:16]):
                transport = FakeS3Transport(returns={"put": answer})
                with self.assertRaises(s3_object.ObjectStoreError):
                    store(transport).put(OBJECT_ID, PAYLOAD, object_metadata())

    def test_a_transport_returning_the_wrong_shape_is_a_failure(self):
        for answer in ("payload", 1, True, {}, [], object()):
            with self.subTest(answer=repr(answer)[:16]):
                transport = FakeS3Transport(returns={"get": answer})
                with self.assertRaises(s3_object.ObjectStoreError):
                    store(transport).get(OBJECT_ID)

    def test_the_storage_key_is_the_content_address_and_nothing_else(self):
        transport = FakeS3Transport()
        subject = store(transport, key_prefix="objects/")
        subject.put(OBJECT_ID, PAYLOAD, object_metadata())
        self.assertEqual(list(transport.objects), [f"objects/{OBJECT_ID}"])


class MetadataBoundsTests(unittest.TestCase):
    """Every field the adapter attaches is bounded, and the set is closed."""

    def test_a_legitimate_metadata_set_is_accepted(self):
        transport = FakeS3Transport()
        receipt = store(transport).put(OBJECT_ID, PAYLOAD, object_metadata())
        self.assertEqual(receipt.object_id, OBJECT_ID)
        self.assertEqual(receipt.backend_id, "cloudflare_r2")

    def test_metadata_must_be_a_mapping(self):
        subject = store()
        for value in ("metadata", None, 1, True, [], (), b"{}", object()):
            with self.subTest(value=repr(value)[:24]):
                with self.assertRaises(ValueError):
                    subject.put(OBJECT_ID, PAYLOAD, value)

    def test_an_unknown_metadata_field_is_refused(self):
        subject = store()
        for field in ("api_key", "plaintext_key", "authorization", "x",
                      "objectid", "note"):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    subject.put(OBJECT_ID, PAYLOAD,
                                object_metadata(**{field: "value"}))

    def test_a_refused_schema_field_is_refused_by_name(self):
        subject = store()
        source = safe_manifest()
        for field in sorted(s3_object.REFUSED_METADATA_FIELDS):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    subject.put(OBJECT_ID, PAYLOAD,
                                object_metadata(**{field: source[field]}))

    def test_encryption_material_can_never_be_attached_to_the_ciphertext(self):
        # Spec S22: keys are separated from the ciphertext provider, and the
        # object's own tags are the one place they must never be.
        for field in ("encryption",):
            self.assertIn(field, s3_object.REFUSED_METADATA_FIELDS)

    def test_a_null_metadata_value_is_refused(self):
        subject = store()
        for field in sorted(s3_object.OBJECT_METADATA_VALUE_CHECKS):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    subject.put(OBJECT_ID, PAYLOAD,
                                object_metadata(**{field: None}))

    def test_metadata_must_agree_with_the_payload(self):
        subject = store()
        with self.assertRaises(ValueError):
            subject.put(OBJECT_ID, PAYLOAD, object_metadata(size_bytes=1))
        with self.assertRaises(ValueError):
            subject.put(OBJECT_ID, PAYLOAD,
                        object_metadata(content_sha256="a" * 64))

    def test_the_whole_metadata_block_is_bounded(self):
        self.assertLessEqual(s3_object.MAX_METADATA_BYTES, 2048)
        largest = len(json.dumps(object_metadata(), sort_keys=True))
        self.assertLess(largest, s3_object.MAX_METADATA_BYTES,
                        "the cap must be unreachable by a well-formed set, "
                        "which is the point of having it")


class SchemaDrivenCompletenessTests(unittest.TestCase):
    """The structural guard: the field list comes from the schema on disk.

    A hand-written list closes the fields somebody thought of. This walks
    ``storage_object_manifest.schema.json`` itself, so a property added to the
    contract later is in neither table and fails here the day it is added -
    which is the only form of this fix that has ever held.
    """

    def test_every_schema_property_has_a_declared_value_check_or_a_refusal(self):
        declared = set(s3_object.OBJECT_METADATA_VALUE_CHECKS)
        refused = set(s3_object.REFUSED_METADATA_FIELDS)
        self.assertEqual(declared | refused, set(MANIFEST_SCHEMA["properties"]))
        self.assertEqual(declared & refused, set())

    def test_every_refusal_states_a_reason(self):
        for field, reason in s3_object.REFUSED_METADATA_FIELDS.items():
            with self.subTest(field=field):
                self.assertIsInstance(reason, str)
                self.assertGreater(len(reason), 20)

    def test_the_adapter_is_never_looser_than_the_manifest_schema(self):
        # For every accepted field, a value the checked-in schema rejects must
        # not be attachable to an object. Generic hostile values on purpose:
        # the point is the sweep, not the cleverness of any one input.
        hostile = (SMUGGLED_CREDENTIAL, "A" * 300, "", None, -1, 10 ** 30,
                   True, 1.5, 2, [], {}, [SMUGGLED_CREDENTIAL],
                   {"leak": SMUGGLED_CREDENTIAL}, "unexpected", b"PUBLIC",
                   bytearray(b"HOT"))
        subject = store()
        for field in sorted(s3_object.OBJECT_METADATA_VALUE_CHECKS):
            for value in hostile:
                record = dict(safe_manifest())
                record[field] = value
                if MANIFEST_VALIDATOR.is_valid(record):
                    continue
                with self.subTest(field=field, value=repr(value)[:24]):
                    with self.assertRaises(ValueError):
                        subject.put(OBJECT_ID, PAYLOAD,
                                    object_metadata(**{field: value}))

    def test_no_hostile_metadata_value_ever_escapes_as_an_unexpected_error(self):
        # Spec S14: refuse, do not crash. Every refusal is a ValueError the
        # caller is documented to expect - never an AttributeError, a TypeError
        # or a KeyError from somewhere deep inside.
        hostile = (SMUGGLED_CREDENTIAL, None, -1, True, b"PUBLIC",
                   bytearray(b"HOT"), 1.5, [SMUGGLED_CREDENTIAL],
                   {"leak": SMUGGLED_CREDENTIAL}, object(), (), set())
        subject = store()
        for field in sorted(MANIFEST_SCHEMA["properties"]):
            for value in hostile:
                with self.subTest(field=field, value=repr(value)[:24]):
                    try:
                        subject.put(OBJECT_ID, PAYLOAD,
                                    object_metadata(**{field: value}))
                    except (ValueError, s3_object.ObjectStoreError):
                        pass


class PrivacyTests(unittest.TestCase):
    """Privacy outranks the transport (Spec S4/S5)."""

    def test_a_local_only_object_never_leaves_owned_storage(self):
        subject = store()
        with self.assertRaises(ValueError):
            subject.put(OBJECT_ID, PAYLOAD,
                        object_metadata(privacy_class="LOCAL_ONLY"))

    def test_a_confidential_object_is_refused_unencrypted(self):
        subject = store()
        with self.assertRaises(ValueError):
            subject.put(OBJECT_ID, PAYLOAD,
                        object_metadata(privacy_class="CONFIDENTIAL",
                                        encryption_state="NONE"))

    def test_a_confidential_object_encrypted_elsewhere_is_accepted(self):
        # The encryption itself is Task 6's. This adapter checks the state and
        # performs no cryptography of its own.
        transport = FakeS3Transport()
        receipt = store(transport).put(
            OBJECT_ID, PAYLOAD,
            object_metadata(privacy_class="CONFIDENTIAL",
                            encryption_state="CLIENT_SIDE_ENCRYPTED",
                            encryption_scheme_version=1))
        self.assertEqual(receipt.object_id, OBJECT_ID)

    def test_nothing_is_sent_before_privacy_is_checked(self):
        transport = FakeS3Transport()
        subject = store(transport)
        with self.assertRaises(ValueError):
            subject.put(OBJECT_ID, PAYLOAD,
                        object_metadata(privacy_class="LOCAL_ONLY"))
        self.assertEqual(transport.calls, [])


class CredentialTests(unittest.TestCase):
    """The needle sweep: a credential fed in anywhere comes out nowhere."""

    def test_the_credential_is_never_an_attribute(self):
        subject = store()
        blob = json.dumps({key: repr(value)
                           for key, value in vars(subject).items()})
        self.assertNotIn("injected-credential-value", blob)

    def test_the_credential_is_never_fetched_at_construction(self):
        calls = []

        def counting():
            calls.append(1)
            return "injected-credential-value"

        store(credential_provider=counting)
        self.assertEqual(calls, [])

    def test_the_credential_reaches_the_transport_and_nothing_else(self):
        transport = FakeS3Transport()
        subject = store(transport)
        subject.put(OBJECT_ID, PAYLOAD, object_metadata())
        subject.get(OBJECT_ID)
        subject.head(OBJECT_ID)
        subject.delete(OBJECT_ID)
        self.assertTrue(transport.calls)
        for call in transport.calls:
            with self.subTest(operation=call["operation"]):
                self.assertEqual(call["credential"], "injected-credential-value")
                sent = json.dumps(call["payload"], default=repr)
                self.assertNotIn("injected-credential-value", sent,
                                 "the credential is in the request body, which "
                                 "is the thing a transport logs")

    def test_the_repr_carries_no_input_of_any_kind(self):
        transport = FakeS3Transport()
        subject = store(transport)
        text = repr(subject)
        self.assertNotIn("injected-credential-value", text)
        self.assertNotIn(SMUGGLED_CREDENTIAL, text)
        self.assertLess(len(text), 200)

    def test_a_needle_in_any_constructor_field_reaches_no_output(self):
        fields = ("backend_id", "endpoint", "bucket", "key_prefix")
        for field in fields:
            with self.subTest(field=field):
                text = refusal_text(store, **{field: SMUGGLED_CREDENTIAL})
                self.assertNotIn(SMUGGLED_CREDENTIAL, text)
                self.assertNotIn("sk-A7bQ", text)

    def test_a_needle_in_any_metadata_field_reaches_no_refusal_text(self):
        subject = store()
        for field in sorted(MANIFEST_SCHEMA["properties"]):
            with self.subTest(field=field):
                text = refusal_text(
                    subject.put, OBJECT_ID, PAYLOAD,
                    object_metadata(**{field: SMUGGLED_CREDENTIAL}))
                self.assertNotIn(SMUGGLED_CREDENTIAL, text)
                self.assertNotIn("sk-A7bQ", text)

    def test_a_needle_as_a_metadata_key_reaches_no_refusal_text(self):
        # The sweep above puts the needle in the *values*. A caller who builds
        # metadata from a mapping they did not write puts it in the keys, and
        # an "unknown field 'X'" message that quotes X is the same leak with
        # the arguments the other way round.
        subject = store()
        for key in (SMUGGLED_CREDENTIAL, "Bearer " + "A" * 40,
                    "AKIAIOSFODNN7EXAMPLE"):
            with self.subTest(key=key[:12]):
                text = refusal_text(subject.put, OBJECT_ID, PAYLOAD,
                                    object_metadata(**{key: "value"}))
                self.assertNotIn(key, text)
                self.assertNotIn("sk-A7bQ", text)
                self.assertNotIn("AKIA", text)

    def test_a_needle_as_an_object_id_or_payload_reaches_no_refusal_text(self):
        subject = store()
        text = refusal_text(subject.put, SMUGGLED_CREDENTIAL, PAYLOAD,
                            object_metadata())
        self.assertNotIn("sk-A7bQ", text)
        text = refusal_text(subject.get, SMUGGLED_CREDENTIAL)
        self.assertNotIn("sk-A7bQ", text)
        text = refusal_text(subject.head, SMUGGLED_CREDENTIAL)
        self.assertNotIn("sk-A7bQ", text)
        text = refusal_text(subject.delete, SMUGGLED_CREDENTIAL)
        self.assertNotIn("sk-A7bQ", text)

    def test_a_needle_as_payload_content_never_reaches_a_receipt(self):
        secret_bytes = SMUGGLED_CREDENTIAL.encode("utf-8")
        object_id = "obj_" + s3_object.content_digest(secret_bytes)
        transport = FakeS3Transport()
        receipt = store(transport).put(
            object_id, secret_bytes,
            object_metadata(content_sha256=object_id[len("obj_"):],
                            size_bytes=len(secret_bytes)))
        self.assertNotIn("sk-A7bQ", repr(receipt))
        self.assertNotIn("sk-A7bQ", json.dumps(receipt.as_dict(), default=repr))

    def test_a_transport_error_is_not_echoed_verbatim(self):
        # A transport's own exception can carry a signed URL or a header.
        def leaking(operation, payload, *, endpoint, bucket, credential):
            raise RuntimeError(f"HTTP 403 for {credential} {SMUGGLED_CREDENTIAL}")

        subject = store(leaking)
        for text in (refusal_text(subject.put, OBJECT_ID, PAYLOAD,
                                  object_metadata()),
                     refusal_text(subject.get, OBJECT_ID),
                     refusal_text(subject.head, OBJECT_ID),
                     refusal_text(subject.delete, OBJECT_ID)):
            self.assertNotIn("sk-A7bQ", text)
            self.assertNotIn("injected-credential-value", text)


class ReceiptTests(unittest.TestCase):
    """A receipt is a record of what this process observed."""

    def test_a_receipt_is_immutable(self):
        receipt = store().put(OBJECT_ID, PAYLOAD, object_metadata())
        with self.assertRaises(Exception):
            receipt.content_sha256 = "a" * 64

    def test_a_receipt_carries_the_digest_this_process_computed(self):
        receipt = store().put(OBJECT_ID, PAYLOAD, object_metadata())
        self.assertEqual(receipt.content_sha256,
                         s3_object.content_digest(PAYLOAD))
        self.assertEqual(receipt.object_id,
                         "obj_" + s3_object.content_digest(PAYLOAD))
        self.assertEqual(receipt.size_bytes, len(PAYLOAD))
        self.assertEqual(receipt.observed_at, TIME)

    def test_a_receipt_never_carries_the_payload(self):
        receipt = store().put(OBJECT_ID, PAYLOAD, object_metadata())
        blob = json.dumps(receipt.as_dict(), default=repr)
        self.assertNotIn("federated-free-storage-mesh-object", blob)

    def test_content_digest_refuses_what_is_not_bytes(self):
        for value in ("text", None, 1, True, [], memoryview(PAYLOAD)):
            with self.subTest(value=repr(value)[:24]):
                with self.assertRaises(ValueError):
                    s3_object.content_digest(value)


def receipt_fields(**overrides):
    """A legitimate ``ObjectReceipt`` field set, for the redaction sweeps below."""
    fields = {
        "object_id": OBJECT_ID,
        "backend_id": "cloudflare_r2",
        "content_sha256": OBJECT_ID[len("obj_"):],
        "size_bytes": len(PAYLOAD),
        "observed_at": TIME,
        "digest_source": "computed",
        "verified": True,
    }
    fields.update(overrides)
    return fields


class HeadAnswerRedactionTests(unittest.TestCase):
    """A head answer's *keys* come from the far side of the transport.

    The value sweep has always been here; the key sweep was the blind spot.
    ``head`` is the one place this module took a provider-supplied string and
    interpolated it into a refusal, which is the same leak as quoting a value
    with the arguments the other way round.
    """

    def test_a_head_answer_key_is_never_echoed(self):
        for key in (SMUGGLED_CREDENTIAL, "Bearer " + "A" * 40,
                    "AKIAIOSFODNN7EXAMPLE", "x-amz-meta-" + "Q" * 200):
            with self.subTest(key=key[:12]):
                transport = FakeS3Transport(head_override={key: "value"})
                text = refusal_text(store(transport).head, OBJECT_ID)
                self.assertTrue(text, "an unrecognised head key must be refused")
                self.assertNotIn(key, text)
                self.assertNotIn("sk-A7bQ", text)
                self.assertNotIn("AKIA", text)
                self.assertNotIn("Q" * 64, text)

    def test_a_head_answer_key_and_value_together_are_never_echoed(self):
        # The reviewer's exact reproduction: the needle as the key, bulk as the
        # value, checked against the whole formatted traceback rather than str.
        transport = FakeS3Transport(
            head_override={SMUGGLED_CREDENTIAL: "Q" * 2048})
        subject = store(transport)
        with self.assertRaises(s3_object.ObjectStoreError) as caught:
            subject.head(OBJECT_ID)
        exc = caught.exception
        blob = str(exc) + repr(exc) + "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__))
        self.assertNotIn("sk-A7bQ", blob)
        self.assertNotIn("Q" * 64, blob)

    def test_a_head_answer_with_non_string_keys_is_refused_not_crashed(self):
        # A mixture of key types made the old ``sorted`` raise TypeError out of
        # the adapter, which is a crash rather than a refusal (Spec S14).
        for override in ({1: "value"}, {1: "a", "zzz": "b"},
                         {(1, 2): "value", "size_bytes": 1},
                         {None: "value"}):
            with self.subTest(override=repr(override)[:32]):
                transport = FakeS3Transport(head_override=override)
                with self.assertRaises(s3_object.ObjectStoreError):
                    store(transport).head(OBJECT_ID)

    def test_the_count_of_unrecognised_fields_is_still_reported(self):
        transport = FakeS3Transport(head_override={"alpha_key": "a",
                                                   "beta_key": "b"})
        text = refusal_text(store(transport).head, OBJECT_ID)
        self.assertIn("2", text)

    def test_a_transport_answer_type_name_is_not_echoed(self):
        # The class name of a transport-controlled object is chosen by whoever
        # controls the transport, and it was interpolated verbatim.
        smuggled = type("sk_A7bQ" + "A7bQ" * 100, (), {})

        for method in ("get", "head"):
            with self.subTest(method=method):
                transport = FakeS3Transport(returns={method: smuggled()})
                text = refusal_text(getattr(store(transport), method), OBJECT_ID)
                self.assertTrue(text)
                self.assertNotIn("sk_A7bQ", text)
                self.assertNotIn("A7bQA7bQ", text)


class ReceiptFieldRedactionTests(unittest.TestCase):
    """``ObjectReceipt`` is public, and its own refusals must not quote input.

    ``__post_init__`` delegated two of its checks to ``manifest.py``, whose
    checkers quote what they were given - which is exactly why ``_bounded``
    swallows them everywhere else in this module.
    """

    def test_a_backend_id_refusal_quotes_nothing(self):
        for value in (SMUGGLED_CREDENTIAL, "Q" * 2048, "AKIAIOSFODNN7EXAMPLE",
                      None, 1, True, b"cloudflare_r2", object()):
            with self.subTest(value=repr(value)[:24]):
                text = refusal_text(s3_object.ObjectReceipt,
                                    **receipt_fields(backend_id=value))
                self.assertTrue(text, "an unregistered backend must be refused")
                self.assertNotIn("sk-A7bQ", text)
                self.assertNotIn("Q" * 64, text)
                self.assertNotIn("AKIA", text)

    def test_an_observed_at_refusal_quotes_nothing(self):
        for value in (SMUGGLED_CREDENTIAL, "Q" * 2048, "AKIAIOSFODNN7EXAMPLE",
                      None, 1, True, b"2026-09-18T00:00:00Z", object()):
            with self.subTest(value=repr(value)[:24]):
                text = refusal_text(s3_object.ObjectReceipt,
                                    **receipt_fields(observed_at=value))
                self.assertTrue(text, "a malformed instant must be refused")
                self.assertNotIn("sk-A7bQ", text)
                self.assertNotIn("Q" * 64, text)
                self.assertNotIn("AKIA", text)

    def test_every_receipt_field_refusal_is_redaction_safe(self):
        for field in sorted(receipt_fields()):
            for value in (SMUGGLED_CREDENTIAL, "Q" * 2048):
                with self.subTest(field=field, value=value[:8]):
                    text = refusal_text(s3_object.ObjectReceipt,
                                        **receipt_fields(**{field: value}))
                    self.assertNotIn("sk-A7bQ", text)
                    self.assertNotIn("Q" * 64, text)

    def test_the_injected_clocks_answer_is_never_echoed(self):
        for value in (SMUGGLED_CREDENTIAL, "Q" * 2048, None, 1, object()):
            with self.subTest(value=repr(value)[:24]):
                subject = store(clock=lambda _v=value: _v)
                text = refusal_text(subject.put, OBJECT_ID, PAYLOAD,
                                    object_metadata())
                self.assertTrue(text, "a clock that is not an instant is refused")
                self.assertNotIn("sk-A7bQ", text)
                self.assertNotIn("Q" * 64, text)

    def test_a_clock_that_raises_is_still_refused_without_a_chain(self):
        def explode():
            raise RuntimeError(f"clock failure {SMUGGLED_CREDENTIAL}")

        text = refusal_text(store(clock=explode).put, OBJECT_ID, PAYLOAD,
                            object_metadata())
        self.assertNotIn("sk-A7bQ", text)


class MimeTypeContentTests(unittest.TestCase):
    """``mime_type`` is free text, and length alone is not a content bound.

    Every other free-text classifier in this lane goes through
    ``validate_object_name``, which applies the bare-hex rule and the
    credential-shape rule. A mime type went through neither, and a ``/`` is all
    it takes to split a 256-bit key into two halves that each pass on their own.
    """

    def test_a_hex_run_is_refused_in_either_mime_part(self):
        half = "deadbeef" * 7 + "deadbe"
        subject = store()
        for value in (f"{half}/{half}", f"{half}/octet-stream",
                      f"application/{half}"):
            with self.subTest(value=value[:24]):
                with self.assertRaises(ValueError):
                    subject.put(OBJECT_ID, PAYLOAD,
                                object_metadata(mime_type=value))

    def test_nothing_is_sent_when_the_mime_type_is_refused(self):
        half = "deadbeef" * 7 + "deadbe"
        transport = FakeS3Transport()
        subject = store(transport)
        with self.assertRaises(ValueError):
            subject.put(OBJECT_ID, PAYLOAD,
                        object_metadata(mime_type=f"{half}/{half}"))
        self.assertEqual(transport.calls, [],
                         "key material reached the ciphertext provider's own "
                         "object tags, which is the one place Spec S22 says it "
                         "must never be written")

    def test_a_credential_shaped_mime_type_is_refused(self):
        subject = store()
        for value in ("application/" + "sk-" + "A" * 40,
                      "application/AKIAIOSFODNN7EXAMPLE"):
            with self.subTest(value=value[:24]):
                with self.assertRaises(ValueError):
                    subject.put(OBJECT_ID, PAYLOAD,
                                object_metadata(mime_type=value))

    def test_a_mime_type_refusal_quotes_nothing(self):
        half = "deadbeef" * 7 + "deadbe"
        text = refusal_text(store().put, OBJECT_ID, PAYLOAD,
                            object_metadata(mime_type=f"{half}/{half}"))
        self.assertNotIn(half, text)
        self.assertNotIn("deadbeefdeadbeef", text)

    def test_ordinary_mime_types_are_still_accepted(self):
        subject = store()
        for value in ("application/octet-stream", "text/plain",
                      "application/json", "image/png",
                      "application/vnd.api+json"):
            with self.subTest(value=value):
                receipt = subject.put(OBJECT_ID, PAYLOAD,
                                      object_metadata(mime_type=value))
                self.assertEqual(receipt.object_id, OBJECT_ID)


class AbsentProviderAssertionTests(unittest.TestCase):
    """An absent assertion is unknown, and unknown is not zero."""

    def test_an_absent_size_stays_absent_rather_than_becoming_empty(self):
        transport = FakeS3Transport(
            head_override={"content_sha256": OBJECT_ID[len("obj_"):]})
        receipt = store(transport).head(OBJECT_ID)
        self.assertIsNone(receipt.size_bytes,
                          "'the provider said nothing' is not 'the object is "
                          "empty'; the content_sha256 two lines above is "
                          "handled exactly this way")

    def test_an_absent_size_is_not_agreement_with_a_real_object(self):
        from AI_SKILL_LIBRARY.v4.storage import replication as replication_module
        transport = FakeS3Transport(
            head_override={"content_sha256": OBJECT_ID[len("obj_"):]})
        receipt = store(transport).head(OBJECT_ID)
        self.assertIs(replication_module.verify_copy(PAYLOAD, receipt), False)

    def test_a_genuinely_empty_object_still_reports_zero(self):
        empty = b""
        empty_id = "obj_" + s3_object.content_digest(empty)
        transport = FakeS3Transport(head_override={"size_bytes": 0,
                                                   "content_sha256":
                                                       s3_object.content_digest(empty)})
        receipt = store(transport).head(empty_id)
        self.assertEqual(receipt.size_bytes, 0)



if __name__ == "__main__":
    unittest.main()
