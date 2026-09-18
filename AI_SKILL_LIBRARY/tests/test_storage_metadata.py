"""Task 4a - the metadata store boundary, and what it refuses to persist.

``metadata.py`` is the mesh's index. It is not the mesh's authority: Spec S18
and ``policy.yaml`` ``metadata_service`` both say so, and the practical
consequence is the one these tests are built around - when the index is
uncertain, nothing destructive may proceed. ``policy.yaml`` states it as
``lifecycle.destructive_action_on_uncertain_evidence: FAIL_CLOSED`` and
``metadata_service.on_unavailable.new_destructive_lifecycle_actions: BLOCKED``.

Four themes:

1. **Fail closed on every gap.** A missing required field, an unknown field, an
   unknown enum value, a wrong constant, a non-mapping, a store that says it is
   unhealthy, a store whose health probe raises - none of them produces a
   stored record and none of them produces a destructive-lifecycle permission.
   ``can_perform_destructive_lifecycle`` returns ``True`` for exactly one input
   shape and ``False`` for every other, including the duck-typed stub that
   cheerfully answers ``healthy() -> True`` without being a metadata store at
   all.

2. **Every string field is bounded, including the nested ones.** The headline
   test does not check that the substring ``"api_key"`` is absent - that is a
   check on field *names*, and it would miss two kilobytes of secret sitting in
   an allowed field that nobody bounded. Instead it walks every string-valued
   path of a fully-populated record, nested ones included, substitutes a 2KB
   credential into each in turn, and requires a refusal every time. The set of
   paths is computed from the record rather than typed out, so a field added
   later is covered the day it is added.

3. **No drift from the checked-in schema.** The record validator's field table
   is asserted equal to ``storage_object_manifest.schema.json``'s property set
   in both directions, and every record the validator admits is asserted valid
   against that schema on disk. A validator looser than the schema it guards is
   the bug class the manifest module already had to close once.

4. **The Supabase adapter creates nothing.** No project, no table, no
   credential, at import time or at any other time. It has no network client of
   its own; without an injected transport it is simply unhealthy, which is the
   honest state of a mesh whose connected Supabase account has no projects
   (Spec S25). The credential never lands on the instance, in a repr, or in a
   record.

Nothing here opens a connection, writes a file, reads an environment variable
or touches a provider account.
"""

from __future__ import annotations

import json
import types
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from AI_SKILL_LIBRARY.v4.storage import metadata
from AI_SKILL_LIBRARY.v4.storage.adapters import supabase_metadata
from AI_SKILL_LIBRARY.v4.storage.manifest import StorageObject

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_SCHEMA_PATH = ROOT / "AI_SKILL_LIBRARY/v4/schemas/storage_object_manifest.schema.json"
MANIFEST_SCHEMA = json.loads(MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
MANIFEST_VALIDATOR = Draft202012Validator(MANIFEST_SCHEMA)

AUTHORITY_FLAGS = (
    "storage_authority", "routing_authority", "reasoning_authority",
    "model_selection_authority", "admission_authority", "scheduling_authority",
    "merge_authority", "trading_authority",
)

#: Two kilobytes of the shape a real leaked credential has. Long enough that no
#: bounded field can hold it, and shaped so that a field which somehow admits it
#: is unambiguously a carrier rather than a classifier.
SMUGGLED_CREDENTIAL = "sk-" + ("A7bQ" * 512)

TIME = "2026-09-18T00:00:00Z"


def safe_manifest(content=b"storage-mesh-object", **overrides):
    """A fully-populated, legitimate manifest record.

    Every optional field is present on purpose: a record with the optional
    fields omitted cannot exercise the bounds on the optional fields, and those
    are precisely the ones a credential would be smuggled through.
    """
    kwargs = dict(
        privacy_class="CONFIDENTIAL",
        criticality="CRITICAL",
        storage_tier="HOT",
        object_class="benchmark-bundle",
        mime_type="application/octet-stream",
        retention_class="short-window",
        encryption_state="CLIENT_SIDE_ENCRYPTED",
        encryption_scheme_version=1,
        encryption={
            "algorithm": "aead-standard-library",
            "scheme_version": 1,
            "key_ref": "env://STORAGE_MESH_DEK",
            "key_rotation_generation": 0,
            "nonce": "YWJjZGVmZ2hpams",
            "tag": "bXl0YWdteXRhZw",
        },
        primary_backend="local_owned_store",
        replica_backends=("cloudflare_r2",),
        created_at=TIME,
        last_accessed_at=TIME,
        last_verified_at=TIME,
        lifecycle_state="RAW",
        source_provenance={
            "origin_class": "learning-fabric",
            "producer_id": "storage-mesh",
            "evidence_ref": "CHECKPOINTS/storage/probe.json",
        },
        verification={
            "hash_verified": True,
            "verified_replica_count": 1,
            "last_probe_at": TIME,
            "evidence_ref": "CHECKPOINTS/storage/verify.json",
        },
        reproducible=False,
    )
    kwargs.update(overrides)
    return StorageObject.from_bytes(content, **kwargs).to_manifest()


def string_paths(value, prefix=()):
    """Every path in a record whose value is a string.

    Computed rather than listed, so that the smuggling tests cover a field the
    day someone adds one instead of the day someone remembers to add it here.
    """
    if isinstance(value, str):
        yield prefix
    elif isinstance(value, dict):
        for key, nested in value.items():
            yield from string_paths(nested, prefix + (key,))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from string_paths(nested, prefix + (index,))


def set_path(record, path, new):
    """Return a deep copy of ``record`` with ``path`` replaced by ``new``."""
    copied = json.loads(json.dumps(record))
    target = copied
    for step in path[:-1]:
        target = target[step]
    target[path[-1]] = new
    return copied


class FakeMetadataStore(metadata.MetadataStore):
    """An in-memory store. No project, no table, no credential, no network.

    It subclasses the real ``MetadataStore`` on purpose: a hand-rolled double
    would let the tests pass while the validation that lives in the base class
    goes unexercised, and that validation is the whole point of the boundary.
    """

    def __init__(self, records=(), healthy=True, probe_raises=None):
        self._records = {}
        self._healthy = healthy
        self._probe_raises = probe_raises
        for record in records:
            self._records[record["object_id"]] = json.loads(json.dumps(record))

    def _probe_healthy(self):
        if self._probe_raises is not None:
            raise self._probe_raises
        return self._healthy

    def _put_record(self, object_id, record):
        self._records[object_id] = record

    def _get_record(self, object_id):
        return self._records.get(object_id)

    def _all_records(self):
        return list(self._records.values())


class AuthorityTests(unittest.TestCase):
    """The index is not an authority, and says so by name."""

    def test_modules_declare_no_authority(self):
        for module in (metadata, supabase_metadata):
            self.assertIs(module.AUTHORITY, False, module.__name__)
            for flag in AUTHORITY_FLAGS:
                self.assertIn(flag, module.AUTHORITY_FLAGS, module.__name__)

    def test_canonical_authority_is_github_and_supabase_is_not(self):
        self.assertEqual(metadata.CANONICAL_AUTHORITY, "GITHUB_BRAIN_V4")
        self.assertIs(supabase_metadata.IS_CANONICAL_AUTHORITY, False)

    def test_modules_perform_no_cryptography(self):
        for module in (metadata, supabase_metadata):
            self.assertIs(module.ENCRYPTION_IMPLEMENTED_HERE, False)
            for name in ("encrypt", "decrypt", "derive_key"):
                self.assertFalse(hasattr(module, name), f"{module.__name__}.{name}")

    def test_anchored_patterns_use_backslash_Z(self):
        """``$`` also matches before a trailing newline; ``\\Z`` does not.

        A validator looser than the schema it mirrors is how ``"a" * 64 + "\\n"``
        got accepted as a digest once already.
        """
        for module in (metadata, supabase_metadata):
            source = Path(module.__file__).read_text(encoding="utf-8")
            for line in source.splitlines():
                if "re.compile" in line or line.strip().startswith(("r\"", "r'")):
                    self.assertNotIn('$"', line, f"{module.__name__}: {line}")
                    self.assertNotIn("$'", line, f"{module.__name__}: {line}")


class RoundTripTests(unittest.TestCase):

    def test_put_get_list_round_trip(self):
        store = FakeMetadataStore()
        record = safe_manifest()
        self.assertIsNone(store.put_manifest(record))
        self.assertEqual(store.get_manifest(record["object_id"]), record)
        self.assertEqual(store.list_manifests(), [record])

    def test_get_manifest_returns_none_for_an_unknown_object(self):
        store = FakeMetadataStore()
        self.assertIsNone(store.get_manifest("obj_" + "a" * 64))

    def test_get_manifest_refuses_an_id_that_is_not_an_object_id(self):
        store = FakeMetadataStore(records=[safe_manifest()])
        for bad in ("", "users/alice/tax-return.pdf", "obj_" + "a" * 63,
                    "obj_" + "A" * 64, "a" * 64, None, 17, "obj_" + "a" * 64 + "\n"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    store.get_manifest(bad)

    def test_stored_records_are_copies_not_the_callers_handle(self):
        store = FakeMetadataStore()
        record = safe_manifest()
        store.put_manifest(record)
        record["privacy_class"] = "PUBLIC"
        record["encryption"]["key_ref"] = "env://SOMETHING_ELSE"
        stored = store.get_manifest(record["object_id"])
        self.assertEqual(stored["privacy_class"], "CONFIDENTIAL")
        self.assertEqual(stored["encryption"]["key_ref"], "env://STORAGE_MESH_DEK")

    def test_returned_records_cannot_mutate_the_store(self):
        store = FakeMetadataStore(records=[safe_manifest()])
        got = store.list_manifests()[0]
        got["criticality"] = "EPHEMERAL"
        self.assertEqual(store.list_manifests()[0]["criticality"], "CRITICAL")

    def test_list_manifests_is_deterministic_by_object_id(self):
        records = [safe_manifest(content=bytes([n])) for n in range(6)]
        forward = FakeMetadataStore(records=records).list_manifests()
        backward = FakeMetadataStore(records=list(reversed(records))).list_manifests()
        self.assertEqual(forward, backward)
        self.assertEqual([r["object_id"] for r in forward],
                         sorted(r["object_id"] for r in records))

    def test_put_is_idempotent_on_the_same_content(self):
        store = FakeMetadataStore()
        record = safe_manifest()
        store.put_manifest(record)
        store.put_manifest(record)
        self.assertEqual(len(store.list_manifests()), 1)


class FailClosedTests(unittest.TestCase):

    def test_put_refuses_a_non_mapping(self):
        store = FakeMetadataStore()
        for bad in (None, "obj", 17, [safe_manifest()], object()):
            with self.subTest(bad=type(bad).__name__):
                with self.assertRaises(ValueError):
                    store.put_manifest(bad)

    def test_put_refuses_an_unknown_field(self):
        store = FakeMetadataStore()
        for name in ("api_key", "plaintext_key", "notes", "filename",
                     "supabase_service_role_key", "anything_at_all"):
            with self.subTest(field=name):
                record = safe_manifest()
                record[name] = "x"
                with self.assertRaises(ValueError):
                    store.put_manifest(record)

    def test_put_refuses_an_omitted_required_field(self):
        store = FakeMetadataStore()
        for name in MANIFEST_SCHEMA["required"]:
            with self.subTest(field=name):
                record = safe_manifest()
                record.pop(name)
                with self.assertRaises(ValueError):
                    store.put_manifest(record)

    def test_put_refuses_a_record_claiming_authority(self):
        store = FakeMetadataStore()
        record = safe_manifest()
        record["authority"] = True
        with self.assertRaises(ValueError):
            store.put_manifest(record)
        for flag in AUTHORITY_FLAGS:
            with self.subTest(flag=flag):
                record = safe_manifest()
                record["authority_flags"][flag] = True
                with self.assertRaises(ValueError):
                    store.put_manifest(record)
                record = safe_manifest()
                record["authority_flags"].pop(flag)
                with self.assertRaises(ValueError):
                    store.put_manifest(record)

    def test_put_refuses_an_unknown_enum_value(self):
        store = FakeMetadataStore()
        cases = {
            "privacy_class": "SEMI_PUBLIC",
            "criticality": "SORT_OF_IMPORTANT",
            "storage_tier": "LUKEWARM",
            "lifecycle_state": "PENDING",
            "encryption_state": "MAYBE",
            "primary_backend": "some_random_untrusted_host",
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                record = safe_manifest()
                record[field] = value
                with self.assertRaises(ValueError):
                    store.put_manifest(record)

    def test_put_refuses_a_wrong_version_constant(self):
        store = FakeMetadataStore()
        for version in (0, 2, "1", None, True):
            with self.subTest(version=version):
                record = safe_manifest()
                record["version"] = version
                with self.assertRaises(ValueError):
                    store.put_manifest(record)

    def test_put_refuses_a_digest_that_is_not_the_object_id(self):
        store = FakeMetadataStore()
        record = safe_manifest()
        record["content_sha256"] = "b" * 64
        with self.assertRaises(ValueError):
            store.put_manifest(record)

    def test_put_refuses_a_replica_list_that_is_a_string(self):
        store = FakeMetadataStore()
        record = safe_manifest()
        record["replica_backends"] = "cloudflare_r2"
        with self.assertRaises(ValueError):
            store.put_manifest(record)

    def test_put_refuses_duplicate_and_overlong_replica_lists(self):
        store = FakeMetadataStore()
        record = safe_manifest()
        record["replica_backends"] = ["cloudflare_r2", "cloudflare_r2"]
        with self.assertRaises(ValueError):
            store.put_manifest(record)
        record = safe_manifest()
        record["replica_backends"] = ["cloudflare_r2"] * 9
        with self.assertRaises(ValueError):
            store.put_manifest(record)

    def test_put_refuses_a_local_only_object_on_an_external_backend(self):
        """Privacy outranks everything, in the index as much as in placement."""
        store = FakeMetadataStore()
        record = safe_manifest(privacy_class="LOCAL_ONLY",
                               encryption_state="NONE", encryption=None,
                               encryption_scheme_version=None,
                               replica_backends=())
        # Edited after construction on purpose: StorageObject refuses to build
        # this record at all, which is the point - the index must refuse it too,
        # because a row from a provider scan never went through StorageObject.
        record["replica_backends"] = ["cloudflare_r2"]
        with self.assertRaises(ValueError):
            store.put_manifest(record)

    def test_put_refuses_confidential_plaintext_on_an_external_backend(self):
        store = FakeMetadataStore()
        record = safe_manifest()
        record["encryption_state"] = "NONE"
        record.pop("encryption")
        record.pop("encryption_scheme_version")
        record["primary_backend"] = "cloudflare_r2"
        with self.assertRaises(ValueError):
            store.put_manifest(record)

    def test_put_is_blocked_when_the_store_is_unhealthy(self):
        store = FakeMetadataStore(healthy=False)
        with self.assertRaises(metadata.MetadataStoreUnavailable):
            store.put_manifest(safe_manifest())
        store._healthy = True
        self.assertEqual(store.list_manifests(), [],
                         "a blocked write must not have landed anyway")

    def test_reading_back_a_corrupted_row_fails_closed(self):
        """A metadata table is a shared surface; a row may not be ours."""
        store = FakeMetadataStore()
        store._records["obj_" + "a" * 64] = {"object_id": "obj_" + "a" * 64,
                                             "api_key": SMUGGLED_CREDENTIAL}
        with self.assertRaises(ValueError):
            store.get_manifest("obj_" + "a" * 64)
        with self.assertRaises(ValueError):
            store.list_manifests()

    def test_the_largest_legitimate_record_is_far_under_the_byte_bound(self):
        """The whole-record byte bound is belt and braces, and is meant to be
        unreachable: every field is individually bounded, so the largest record
        the validator can admit is a fraction of ``MAX_RECORD_BYTES``. If this
        assertion ever narrows, a field has grown a way to hold bulk."""
        store = FakeMetadataStore()
        record = safe_manifest(privacy_class="PUBLIC", encryption_state="NONE",
                               encryption=None, encryption_scheme_version=None)
        record["replica_backends"] = ["cloudflare_r2", "backblaze_b2",
                                      "oracle_object_storage", "huggingface_hub",
                                      "google_drive", "onedrive", "dropbox"]
        store.put_manifest(record)
        largest = max(len(json.dumps(r)) for r in store.list_manifests())
        self.assertLess(largest * 2, metadata.MAX_RECORD_BYTES)


class DestructiveLifecycleTests(unittest.TestCase):
    """``destructive_action_on_uncertain_evidence: FAIL_CLOSED`` (policy.yaml)."""

    def test_destructive_actions_block_when_metadata_unhealthy(self):
        store = FakeMetadataStore(healthy=False)
        self.assertIs(metadata.can_perform_destructive_lifecycle(store), False)

    def test_destructive_actions_are_permitted_only_on_a_healthy_store(self):
        self.assertIs(
            metadata.can_perform_destructive_lifecycle(FakeMetadataStore()), True)

    def test_an_unreachable_store_is_not_a_healthy_one(self):
        for error in (RuntimeError("connection refused"), TimeoutError(),
                      OSError(), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                store = FakeMetadataStore(probe_raises=error)
                self.assertIs(store.healthy(), False)
                self.assertIs(metadata.can_perform_destructive_lifecycle(store),
                              False)

    def test_a_non_store_never_gets_a_destructive_permission(self):
        """Duck typing is not evidence: an object that answers ``healthy()``
        is not thereby a metadata store."""
        stub = types.SimpleNamespace(healthy=lambda: True)
        for candidate in (None, stub, object(), True, "healthy", {}, []):
            with self.subTest(candidate=type(candidate).__name__):
                self.assertIs(
                    metadata.can_perform_destructive_lifecycle(candidate), False)

    def test_a_truthy_non_boolean_health_answer_is_not_health(self):
        class Vague(FakeMetadataStore):
            def _probe_healthy(self):
                return 1

        self.assertIs(Vague().healthy(), False)
        self.assertIs(metadata.can_perform_destructive_lifecycle(Vague()), False)

    def test_healthy_always_returns_a_real_boolean(self):
        for store in (FakeMetadataStore(), FakeMetadataStore(healthy=False),
                      FakeMetadataStore(probe_raises=RuntimeError())):
            self.assertIsInstance(store.healthy(), bool)


class BoundedFieldTests(unittest.TestCase):
    """The hole that has already got past this project twice."""

    def test_every_string_field_refuses_a_two_kilobyte_credential(self):
        store = FakeMetadataStore()
        record = safe_manifest()
        paths = list(string_paths(record))
        self.assertGreaterEqual(len(paths), 18, "fixture is not fully populated")
        for path in paths:
            with self.subTest(path=".".join(str(step) for step in path)):
                smuggled = set_path(record, path, SMUGGLED_CREDENTIAL)
                with self.assertRaises(ValueError):
                    store.put_manifest(smuggled)
                self.assertEqual(store.list_manifests(), [])

    def test_every_string_field_refuses_a_two_kilobyte_benign_blob(self):
        """It is not the credential shape doing the work - it is the bound."""
        store = FakeMetadataStore()
        record = safe_manifest()
        for path in string_paths(record):
            with self.subTest(path=".".join(str(step) for step in path)):
                smuggled = set_path(record, path, "a" * 2048)
                with self.assertRaises(ValueError):
                    store.put_manifest(smuggled)

    def test_every_string_field_is_bounded_well_under_a_kilobyte(self):
        store = FakeMetadataStore()
        record = safe_manifest()
        for path in string_paths(record):
            with self.subTest(path=".".join(str(step) for step in path)):
                for length in (256, 512, 1024):
                    with self.assertRaises(ValueError):
                        store.put_manifest(set_path(record, path, "a" * length))

    def test_nested_containers_are_refused_outright(self):
        store = FakeMetadataStore()
        for field in ("encryption", "source_provenance", "verification"):
            with self.subTest(field=field):
                record = safe_manifest()
                record[field] = {"algorithm": {"nested": SMUGGLED_CREDENTIAL}}
                with self.assertRaises(ValueError):
                    store.put_manifest(record)

    def test_nested_mappings_refuse_unknown_fields(self):
        store = FakeMetadataStore()
        for field in ("encryption", "source_provenance", "verification"):
            with self.subTest(field=field):
                record = safe_manifest()
                record[field]["service_role_key"] = "x"
                with self.assertRaises(ValueError):
                    store.put_manifest(record)

    def test_a_plaintext_key_has_no_field_to_live_in(self):
        store = FakeMetadataStore()
        record = safe_manifest()
        record["encryption"]["key_ref"] = "a" * 64
        with self.assertRaises(ValueError):
            store.put_manifest(record)
        record = safe_manifest()
        record["encryption"]["key_ref"] = "https://bucket.example.com/dek.bin"
        with self.assertRaises(ValueError):
            store.put_manifest(record)


class SchemaAgreementTests(unittest.TestCase):

    def test_the_field_table_matches_the_checked_in_schema(self):
        self.assertEqual(set(metadata.RECORD_FIELDS),
                         set(MANIFEST_SCHEMA["properties"]))

    def test_every_admitted_record_validates_against_the_schema_on_disk(self):
        for record in (safe_manifest(),
                       safe_manifest(privacy_class="PUBLIC",
                                     criticality="REPRODUCIBLE",
                                     reproducible=True,
                                     encryption_state="NONE", encryption=None,
                                     encryption_scheme_version=None)):
            admitted = metadata.validate_metadata_record(record)
            MANIFEST_VALIDATOR.validate(admitted)

    def test_the_validator_is_not_looser_than_the_schema(self):
        """Anything the validator admits, the schema must admit too."""
        store = FakeMetadataStore()
        record = safe_manifest()
        for path in string_paths(record):
            candidate = set_path(record, path, "a" * 41)
            try:
                admitted = metadata.validate_metadata_record(candidate)
            except ValueError:
                continue
            MANIFEST_VALIDATOR.validate(admitted)

    def test_validate_returns_a_fresh_dict(self):
        record = safe_manifest()
        admitted = metadata.validate_metadata_record(record)
        self.assertIsNot(admitted, record)
        self.assertIsNot(admitted["encryption"], record["encryption"])
        self.assertEqual(admitted, record)


class SupabaseAdapterTests(unittest.TestCase):
    """Spec S25: the connected account has no projects, and none is created."""

    URL = "https://abcdefghijklmnopqrst.supabase.co"

    def credential(self):
        self.credential_calls += 1
        return "injected-at-runtime-never-stored"

    def setUp(self):
        self.credential_calls = 0

    def store(self, **kwargs):
        kwargs.setdefault("project_url", self.URL)
        kwargs.setdefault("credential_provider", self.credential)
        return supabase_metadata.SupabaseMetadataStore(**kwargs)

    def test_the_adapter_creates_no_external_resource(self):
        self.assertIs(supabase_metadata.CREATES_EXTERNAL_RESOURCES, False)
        self.assertIs(supabase_metadata.PROVISIONING_AUTHORIZED, False)
        self.assertIs(supabase_metadata.PROJECT_EXISTS_VERIFIED, False)

    def test_the_table_contract_is_documentation_and_is_never_executed(self):
        contract = supabase_metadata.TABLE_CONTRACT
        self.assertIn("storage_objects", contract)
        source = Path(supabase_metadata.__file__).read_text(encoding="utf-8")
        for forbidden in ("import psycopg", "import supabase", "create_client",
                          "cursor(", "execute("):
            self.assertNotIn(forbidden, source, forbidden)
        for name in ("create_table", "provision", "ensure_table", "migrate"):
            self.assertFalse(hasattr(supabase_metadata.SupabaseMetadataStore, name),
                             name)

    def test_construction_calls_no_credential_provider_and_no_transport(self):
        calls = []
        self.store(transport=lambda *a, **k: calls.append(a))
        self.assertEqual(self.credential_calls, 0)
        self.assertEqual(calls, [])

    def test_without_a_transport_the_store_is_unhealthy_and_blocks(self):
        store = self.store()
        self.assertIs(store.healthy(), False)
        self.assertIs(metadata.can_perform_destructive_lifecycle(store), False)
        with self.assertRaises(metadata.MetadataStoreUnavailable):
            store.put_manifest(safe_manifest())
        with self.assertRaises(metadata.MetadataStoreUnavailable):
            store.list_manifests()
        with self.assertRaises(metadata.MetadataStoreUnavailable):
            store.get_manifest("obj_" + "a" * 64)

    def test_the_credential_never_lands_on_the_instance_or_in_a_repr(self):
        store = self.store()
        blob = json.dumps({k: repr(v) for k, v in vars(store).items()})
        self.assertNotIn("injected-at-runtime-never-stored", blob)
        self.assertNotIn("injected-at-runtime-never-stored", repr(store))
        self.assertNotIn("injected-at-runtime-never-stored", str(store))
        self.assertEqual(self.credential_calls, 0)

    def test_the_project_url_is_bounded_and_refuses_embedded_credentials(self):
        for bad in ("", "http://abc.supabase.co", "https://" + "a" * 300 + ".supabase.co",
                    "https://user:hunter2@abc.supabase.co",
                    "https://abc.supabase.co/rest/v1/storage_objects?apikey=x",
                    "abc.supabase.co", None, 17,
                    "https://abcdefghijklmnopqrst.supabase.co\n"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    self.store(project_url=bad)

    def test_a_credential_provider_is_required_and_must_be_callable(self):
        for bad in (None, "a-literal-key", 17, object()):
            with self.subTest(bad=type(bad).__name__):
                with self.assertRaises(ValueError):
                    self.store(credential_provider=bad)

    def test_supabase_is_metadata_and_index_only(self):
        self.assertEqual(supabase_metadata.ROLE, "metadata_and_object_index_only")
        self.assertIs(supabase_metadata.BULK_OBJECT_BACKEND_ALLOWED, False)
        self.assertLessEqual(supabase_metadata.MAX_ROW_BYTES,
                             metadata.MAX_RECORD_BYTES)

    def test_an_injected_transport_is_the_only_way_out(self):
        """Nothing leaves the process until a transport is injected, and then
        exactly the validated record leaves - with the credential handed over
        as a call argument rather than buried in the payload a transport logs."""
        sent = []

        def transport(operation, payload, *, project_url, credential):
            sent.append((operation, json.loads(json.dumps(payload)), credential))
            if operation == "health":
                return True
            if operation == "select_all":
                return [payload for op, payload, _ in sent if op == "upsert"]
            return None

        store = self.store(transport=transport)
        self.assertIs(store.healthy(), True)
        record = safe_manifest()
        store.put_manifest(record)
        self.assertEqual(store.list_manifests(), [record])

        operations = [operation for operation, _, _ in sent]
        self.assertIn("upsert", operations)
        self.assertTrue(set(operations) <= set(supabase_metadata.OPERATIONS))
        upsert = [payload for op, payload, _ in sent if op == "upsert"][0]
        self.assertEqual(upsert[supabase_metadata.MANIFEST_COLUMN], record)
        self.assertEqual(upsert["object_id"], record["object_id"])

        # The credential is fetched per call and appears only as the call
        # argument - never in a payload, and never on the instance.
        self.assertEqual(self.credential_calls, len(sent))
        self.assertEqual({credential for _, _, credential in sent},
                         {"injected-at-runtime-never-stored"})
        payloads = json.dumps([(op, payload) for op, payload, _ in sent])
        self.assertNotIn("injected-at-runtime-never-stored", payloads)
        self.assertNotIn("injected-at-runtime-never-stored",
                         json.dumps({k: repr(v) for k, v in vars(store).items()}))

    def test_a_transport_that_raises_makes_the_store_unhealthy_not_loud(self):
        def transport(operation, payload, *, project_url, credential):
            raise RuntimeError("supabase project is paused")

        store = self.store(transport=transport)
        self.assertIs(store.healthy(), False)
        self.assertIs(metadata.can_perform_destructive_lifecycle(store), False)

    def test_a_row_the_transport_returns_is_validated_before_it_is_believed(self):
        poisoned = {"object_id": "obj_" + "a" * 64, "api_key": SMUGGLED_CREDENTIAL}
        row = {"object_id": poisoned["object_id"],
               supabase_metadata.MANIFEST_COLUMN: poisoned}

        def transport(operation, payload, *, project_url, credential):
            if operation == "health":
                return True
            if operation == "select_all":
                return [row]
            return row

        store = self.store(transport=transport)
        with self.assertRaises(ValueError):
            store.list_manifests()
        with self.assertRaises(ValueError):
            store.get_manifest("obj_" + "a" * 64)


class RecordIdentityTests(unittest.TestCase):
    """A read answers about the object that was asked for, or it does not answer.

    ``get_manifest`` validated the row it got back as *a* record and returned
    it without ever checking it was *the* record. That is a fail-open on
    exactly the decision ``can_perform_destructive_lifecycle`` exists to gate:
    a caller reading a record to decide whether an object may be evicted was
    handed another object's criticality.
    """

    def test_get_manifest_refuses_a_row_for_a_different_object(self):
        critical = safe_manifest(content=b"critical-object")
        other = safe_manifest(content=b"some-other-object",
                              criticality="EPHEMERAL", reproducible=True)
        self.assertEqual(critical["criticality"], "CRITICAL")
        self.assertIs(critical["reproducible"], False)

        class Swapped(FakeMetadataStore):
            def _get_record(self, object_id):
                return json.loads(json.dumps(other))

        store = Swapped(records=[critical])
        with self.assertRaises(metadata.MetadataStoreError):
            store.get_manifest(critical["object_id"])

    def test_the_swap_is_refused_through_the_real_adapter_too(self):
        """It reproduces through the base class, so it is not an adapter bug -
        but the adapter is where a real transport would hand it over."""
        critical = safe_manifest(content=b"critical-object")
        other = safe_manifest(content=b"some-other-object",
                              criticality="EPHEMERAL", reproducible=True)

        def transport(operation, payload, *, project_url, credential):
            if operation == "health":
                return True
            if operation == "select":
                return {"object_id": other["object_id"], "manifest": other}
            return None

        store = supabase_metadata.SupabaseMetadataStore(
            project_url="https://abcdefghijklmnopqrst.supabase.co",
            credential_provider=lambda: "injected", transport=transport)
        with self.assertRaises(metadata.MetadataStoreError):
            store.get_manifest(critical["object_id"])

    def test_the_right_row_still_comes_back(self):
        record = safe_manifest()
        store = FakeMetadataStore(records=[record])
        self.assertEqual(store.get_manifest(record["object_id"]), record)

    def test_list_manifests_refuses_a_duplicated_object_id(self):
        """Two rows for one object is an index that disagrees with itself. It
        surfaced only later, as a confusing ordering error from the exporter."""
        record = safe_manifest()

        class Doubled(FakeMetadataStore):
            def _all_records(self):
                return [json.loads(json.dumps(record)),
                        json.loads(json.dumps(record))]

        with self.assertRaises(metadata.MetadataStoreError):
            Doubled().list_manifests()


class DestructiveGateIsUnconditionalTests(unittest.TestCase):

    def test_a_store_whose_healthy_raises_does_not_escape_the_gate(self):
        """``healthy`` is overridable. A subclass that raises out of it used to
        propagate straight through the destructive-action gate."""

        class Loud(FakeMetadataStore):
            def healthy(self):
                raise RuntimeError("supabase project is paused")

        self.assertIs(metadata.can_perform_destructive_lifecycle(Loud()), False)

    def test_a_store_whose_healthy_answers_vaguely_is_not_healthy(self):
        class Vague(FakeMetadataStore):
            def healthy(self):
                return "yes"

        self.assertIs(metadata.can_perform_destructive_lifecycle(Vague()), False)


class SupabaseRoundTripSymmetryTests(unittest.TestCase):
    """The adapter wrote ``record`` and the contract documents ``manifest``."""

    URL = "https://abcdefghijklmnopqrst.supabase.co"

    def test_the_payload_key_is_the_documented_column(self):
        sent = []

        def transport(operation, payload, *, project_url, credential):
            sent.append((operation, json.loads(json.dumps(payload))))
            return True if operation == "health" else None

        store = supabase_metadata.SupabaseMetadataStore(
            project_url=self.URL, credential_provider=lambda: "injected",
            transport=transport)
        record = safe_manifest()
        store.put_manifest(record)
        upsert = [payload for op, payload in sent if op == "upsert"][0]
        self.assertIn("manifest", supabase_metadata.TABLE_CONTRACT)
        self.assertEqual(set(upsert), {"object_id", "manifest"})
        self.assertEqual(upsert["manifest"], record)

    def test_what_the_adapter_writes_is_what_the_adapter_reads_back(self):
        """A table standing in for a real one: whatever ``upsert`` stores is
        what ``select`` hands back. An asymmetric adapter round-trips only
        against a transport written to match its bug."""
        table = {}

        def transport(operation, payload, *, project_url, credential):
            if operation == "health":
                return True
            if operation == "upsert":
                table[payload["object_id"]] = json.loads(json.dumps(payload))
                return None
            if operation == "select":
                return table.get(payload["object_id"])
            if operation == "select_all":
                return list(table.values())
            return None

        store = supabase_metadata.SupabaseMetadataStore(
            project_url=self.URL, credential_provider=lambda: "injected",
            transport=transport)
        record = safe_manifest()
        store.put_manifest(record)
        self.assertEqual(store.get_manifest(record["object_id"]), record)
        self.assertEqual(store.list_manifests(), [record])


if __name__ == "__main__":
    unittest.main()
