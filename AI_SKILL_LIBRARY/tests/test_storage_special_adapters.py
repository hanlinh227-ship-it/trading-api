"""The two special adapters of Task 8: human backup, and Hugging Face artifacts.

Both are edges out of the process, and both are edges the S3 adapter's rules do
not fit, so each has one extra thing to prove.

**A human-backup target is not a storage backend.** Drive, OneDrive and Dropbox
are where a person goes to find a recovery export when everything else is gone
(Spec S6 HUMAN_BACKUP, ``policy.yaml`` ``tiers.HUMAN_BACKUP``
``canonical_runtime_object_store: false``). So the adapter offers
``export_backup``/``list_backups``/``fetch_backup`` and not ``put``/``get`` -
there is no generic object-store surface to reach for, it is not an
``ObjectStore``, and a descriptor naming any tier other than HUMAN_BACKUP is
refused. A backup surface that can be addressed like a primary eventually is
one.

**The Hugging Face adapter accepts declared AI artifact classes and nothing
else.** Spec S17 admits models, datasets and benchmark corpora and says in as
many words that the Hub is not a generic log dump; ``ARTIFACT_CLASSES`` is that
sentence made into a closed vocabulary, and an artifact class the list does not
name is refused rather than warned about.

Everything else is the discipline the lane already converged on, asserted rather
than assumed:

* nothing is created - no folder, no repo, no project - at import, at
  construction or at any other time, and there is no method that could;
* no network, no SDK, no endpoint and no credential in either file; the
  credential arrives through a zero-argument provider called at request time and
  is never a parameter and never an attribute;
* a credential-shaped needle is fed through *every* input, keys included, and
  must appear in no ``str``, no ``repr`` and no ``traceback.format_exc()``;
* the accepted/refused descriptor partition is driven from the manifest schema
  on disk, and the accepted checkers are the identical callables from
  ``metadata.py``/``s3_object.py`` - asserted with ``is``, because a second copy
  of "what a bounded classifier looks like" is a copy that will drift and the
  looser one is the one an attacker gets to use.

Every test here uses a fake transport. Nothing opens a connection.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import traceback
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.storage import AUTHORITY_FLAGS, CANONICAL_AUTHORITY
from AI_SKILL_LIBRARY.v4.storage import manifest as _manifest
from AI_SKILL_LIBRARY.v4.storage import metadata as _metadata
from AI_SKILL_LIBRARY.v4.storage.adapters import human_backup, huggingface_artifact
from AI_SKILL_LIBRARY.v4.storage.adapters import s3_object

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_SCHEMA_PATH = ROOT / "AI_SKILL_LIBRARY/v4/schemas/storage_object_manifest.schema.json"

PAYLOAD = b"a bounded recovery export"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()
OBJECT_ID = f"obj_{DIGEST}"

#: Credential-shaped needles. Two shapes, because one pattern's blind spot is
#: the other's match, and both carry upper-case characters so that a refusal
#: naming a *key* has to redact them rather than merely quote them.
NEEDLES = ("AKIAIOSFODNN7EXAMPLE", "ghp_" + "A" * 36)


class FakeTransport:
    """Records what it was asked to do and answers from a script.

    It performs no I/O of any kind: it is a list with a call signature. The
    credential is captured separately from the payload, because the payload is
    the part a real transport logs and the assertion that matters is that the
    secret is not in it.
    """

    def __init__(self, answers=None, raises=None):
        self.calls = []
        self.answers = answers or {}
        self.raises = raises

    def __call__(self, operation, payload, **context):
        self.credential = context.pop("credential", None)
        self.calls.append((operation, payload, context))
        if self.raises is not None:
            raise self.raises
        if operation in self.answers:
            return self.answers[operation]
        return True


def provider():
    """A credential provider that never yields a real secret in a test."""
    return lambda: "not-a-real-credential"


def backup_target(**overrides):
    kwargs = {
        "backend_id": "google_drive",
        "folder": "brain-backup/",
        "credential_provider": provider(),
        "transport": FakeTransport(),
    }
    kwargs.update(overrides)
    return human_backup.HumanBackupTarget(**kwargs)


def backup_descriptor(**overrides):
    base = {
        "version": 1,
        "content_sha256": DIGEST,
        "size_bytes": len(PAYLOAD),
        "privacy_class": "PUBLIC",
        "criticality": "IMPORTANT",
        "storage_tier": "HUMAN_BACKUP",
        "lifecycle_state": "ARCHIVED",
        "encryption_state": "NONE",
        "mime_type": "application/zip",
        "object_class": "recovery-export",
        "retention_class": "standard-90d",
        "created_at": "2026-09-18T00:00:00Z",
        "reproducible": False,
    }
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not _ABSENT}


def artifact_store(**overrides):
    kwargs = {
        "repo_id": "brain-mesh/eval-corpus",
        "repo_type": "dataset",
        "credential_provider": provider(),
        "transport": FakeTransport(),
    }
    kwargs.update(overrides)
    return huggingface_artifact.HuggingFaceArtifactStore(**kwargs)


def artifact_descriptor(**overrides):
    base = {
        "version": 1,
        "content_sha256": DIGEST,
        "size_bytes": len(PAYLOAD),
        "privacy_class": "PUBLIC",
        "criticality": "REPRODUCIBLE",
        "storage_tier": "COLD",
        "lifecycle_state": "ARCHIVED",
        "encryption_state": "NONE",
        "mime_type": "application/json",
        "object_class": "benchmark-corpus",
        "retention_class": "standard-90d",
        "created_at": "2026-09-18T00:00:00Z",
        "reproducible": True,
    }
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not _ABSENT}


class _Absent:
    def __repr__(self):  # pragma: no cover - debugging aid
        return "<absent>"


#: Sentinel for "leave this field out", so a fixture can express absence
#: without a second builder.
_ABSENT = _Absent()


class AdapterHonestyTests(unittest.TestCase):
    """Facts both modules must state, checked on both rather than on one."""

    MODULES = (human_backup, huggingface_artifact)

    def test_neither_adapter_holds_any_authority(self):
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                self.assertIs(module.AUTHORITY, False)
                self.assertEqual(set(module.AUTHORITY_FLAGS), set(AUTHORITY_FLAGS))
                for flag, held in module.AUTHORITY_FLAGS.items():
                    self.assertIs(held, False, flag)
                self.assertEqual(module.CANONICAL_AUTHORITY, CANONICAL_AUTHORITY)
                self.assertEqual(module.ROUTED_BY, "task_router")

    def test_neither_adapter_class_claims_authority_either(self):
        for cls in (human_backup.HumanBackupTarget,
                    huggingface_artifact.HuggingFaceArtifactStore):
            with self.subTest(cls=cls.__name__):
                self.assertIs(cls.AUTHORITY, False)
                self.assertIs(cls.ENCRYPTION_IMPLEMENTED_HERE, False)

    def test_neither_adapter_creates_anything_or_is_authorized_to(self):
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                self.assertIs(module.CREATES_EXTERNAL_RESOURCES, False)
                self.assertIs(module.PROVISIONING_AUTHORIZED, False)

    def test_neither_adapter_implements_cryptography(self):
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                self.assertIs(module.ENCRYPTION_IMPLEMENTED_HERE, False)
                for name in ("encrypt", "decrypt", "derive_key", "seal", "unseal"):
                    self.assertFalse(hasattr(module, name), name)

    def test_no_provisioning_method_exists_to_call_by_accident(self):
        forbidden = ("create", "provision", "ensure", "mkdir", "migrate",
                     "init_repo", "create_folder", "create_repo", "setup")
        for cls in (human_backup.HumanBackupTarget,
                    huggingface_artifact.HuggingFaceArtifactStore):
            for name in dir(cls):
                if name.startswith("__"):
                    continue
                with self.subTest(cls=cls.__name__, name=name):
                    self.assertFalse(
                        any(name.startswith(prefix) for prefix in forbidden))

    def test_neither_module_imports_a_network_client_or_an_sdk(self):
        forbidden = {
            "boto3", "botocore", "requests", "httpx", "urllib", "urllib3",
            "http", "socket", "ssl", "ftplib", "smtplib", "huggingface_hub",
            "datasets", "transformers", "google", "googleapiclient", "dropbox",
            "msal", "azure", "subprocess", "os",
        }
        for module in self.MODULES:
            tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                for name in names:
                    with self.subTest(module=module.__name__, imported=name):
                        self.assertNotIn(name.split(".")[0], forbidden)

    def test_neither_module_hard_codes_an_endpoint_or_a_credential(self):
        for module in self.MODULES:
            text = Path(module.__file__).read_text(encoding="utf-8")
            body = "\n".join(
                line for line in text.splitlines()
                if not line.lstrip().startswith("#"))
            with self.subTest(module=module.__name__):
                self.assertNotIn("https://", body)
                self.assertNotIn("Bearer ", body)
                self.assertNotIn(".amazonaws.com", body)
                self.assertNotIn("huggingface.co", body)

    def test_the_credential_is_never_a_parameter(self):
        for cls in (human_backup.HumanBackupTarget,
                    huggingface_artifact.HuggingFaceArtifactStore):
            parameters = set(inspect.signature(cls.__init__).parameters)
            with self.subTest(cls=cls.__name__):
                self.assertIn("credential_provider", parameters)
                for name in ("credential", "token", "api_key", "secret",
                             "password", "key"):
                    self.assertNotIn(name, parameters)

    def test_a_literal_credential_is_refused_where_a_provider_is_required(self):
        with self.assertRaises(ValueError):
            backup_target(credential_provider="a-literal-secret")
        with self.assertRaises(ValueError):
            artifact_store(credential_provider="a-literal-secret")

    def test_construction_asks_the_transport_for_nothing(self):
        for build in (backup_target, artifact_store):
            transport = FakeTransport()
            with self.subTest(build=build.__name__):
                build(transport=transport)
                self.assertEqual(transport.calls, [])

    def test_without_a_transport_every_operation_fails_closed(self):
        target = backup_target(transport=None)
        with self.assertRaises(human_backup.HumanBackupUnavailable):
            target.export_backup(OBJECT_ID, PAYLOAD, backup_descriptor())
        with self.assertRaises(human_backup.HumanBackupUnavailable):
            target.list_backups()
        with self.assertRaises(human_backup.HumanBackupUnavailable):
            target.fetch_backup(OBJECT_ID)

        store = artifact_store(transport=None)
        with self.assertRaises(huggingface_artifact.ArtifactStoreUnavailable):
            store.upload_artifact(OBJECT_ID, PAYLOAD, artifact_descriptor())
        with self.assertRaises(huggingface_artifact.ArtifactStoreUnavailable):
            store.list_artifacts()
        with self.assertRaises(huggingface_artifact.ArtifactStoreUnavailable):
            store.fetch_artifact(OBJECT_ID)

    def test_the_operation_vocabularies_are_closed(self):
        self.assertEqual(human_backup.OPERATIONS,
                         ("export_backup", "list_backups", "fetch_backup"))
        self.assertEqual(huggingface_artifact.OPERATIONS,
                         ("upload_artifact", "list_artifacts", "fetch_artifact"))


class HumanBackupIsNotCanonicalStorageTests(unittest.TestCase):
    def test_the_module_says_it_is_not_a_canonical_runtime_object_store(self):
        self.assertIs(human_backup.CANONICAL_PRIMARY_ALLOWED, False)
        self.assertIs(human_backup.CANONICAL_RUNTIME_OBJECT_STORE, False)
        self.assertIs(human_backup.GENERIC_OBJECT_STORE, False)
        self.assertEqual(human_backup.TIER, "HUMAN_BACKUP")
        self.assertEqual(human_backup.ACCEPTABLE_USE_CLASS, "human-backup-only")

    def test_it_is_not_an_object_store_by_inheritance_either(self):
        self.assertFalse(issubclass(human_backup.HumanBackupTarget,
                                    s3_object.ObjectStore))

    def test_there_is_no_generic_object_store_surface_to_reach_for(self):
        for name in ("put", "get", "head", "delete", "write", "read",
                     "upload", "download"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(human_backup.HumanBackupTarget, name))

    def test_the_declared_operations_are_explicitly_backup_and_export(self):
        for name in ("export_backup", "list_backups", "fetch_backup"):
            with self.subTest(name=name):
                self.assertTrue(callable(
                    getattr(human_backup.HumanBackupTarget, name)))

    def test_a_descriptor_naming_any_other_tier_is_refused(self):
        target = backup_target()
        for tier in ("CANONICAL", "HOT", "WARM", "COLD", "METADATA"):
            with self.subTest(tier=tier):
                with self.assertRaises(ValueError):
                    target.export_backup(
                        OBJECT_ID, PAYLOAD,
                        backup_descriptor(storage_tier=tier))

    def test_a_descriptor_with_no_tier_at_all_is_refused(self):
        with self.assertRaises(ValueError):
            backup_target().export_backup(
                OBJECT_ID, PAYLOAD, backup_descriptor(storage_tier=_ABSENT))

    def test_a_backend_that_is_not_a_human_backup_surface_is_refused(self):
        for backend_id in ("cloudflare_r2", "backblaze_b2", "huggingface_hub",
                           "supabase", "local_owned_store"):
            with self.subTest(backend_id=backend_id):
                with self.assertRaises(ValueError):
                    backup_target(backend_id=backend_id)

    def test_the_three_human_backup_backends_are_accepted(self):
        for backend_id in ("google_drive", "onedrive", "dropbox"):
            with self.subTest(backend_id=backend_id):
                self.assertEqual(backup_target(backend_id=backend_id).backend_id,
                                 backend_id)

    def test_a_backend_outside_the_registry_is_refused(self):
        with self.assertRaises(ValueError):
            backup_target(backend_id="some_random_untrusted_host")

    def test_an_export_round_trips_through_the_transport(self):
        transport = FakeTransport()
        target = backup_target(transport=transport)
        receipt = target.export_backup(OBJECT_ID, PAYLOAD, backup_descriptor())
        self.assertEqual(receipt.object_id, OBJECT_ID)
        self.assertEqual(receipt.content_sha256, DIGEST)
        self.assertEqual(receipt.digest_source, "computed")
        self.assertIs(receipt.verified, True)
        operation, payload, context = transport.calls[0]
        self.assertEqual(operation, "export_backup")
        self.assertEqual(payload["body"], PAYLOAD)
        self.assertEqual(context["folder"], "brain-backup/")

    def test_the_receipt_is_the_lane_s_receipt_type(self):
        receipt = backup_target().export_backup(OBJECT_ID, PAYLOAD,
                                                backup_descriptor())
        self.assertIs(type(receipt), s3_object.ObjectReceipt)

    def test_an_export_under_the_wrong_address_is_refused(self):
        with self.assertRaises(ValueError):
            backup_target().export_backup(
                f"obj_{'0' * 64}", PAYLOAD, backup_descriptor())

    def test_a_fetch_rehashes_what_came_back(self):
        transport = FakeTransport(answers={"fetch_backup": b"different bytes"})
        with self.assertRaises(human_backup.BackupIntegrityError):
            backup_target(transport=transport).fetch_backup(OBJECT_ID)

    def test_a_fetch_that_finds_nothing_raises_rather_than_returning_empty(self):
        transport = FakeTransport(answers={"fetch_backup": None})
        with self.assertRaises(human_backup.BackupNotFound):
            backup_target(transport=transport).fetch_backup(OBJECT_ID)

    def test_a_good_fetch_returns_the_bytes(self):
        transport = FakeTransport(answers={"fetch_backup": PAYLOAD})
        self.assertEqual(backup_target(transport=transport).fetch_backup(OBJECT_ID),
                         PAYLOAD)

    def test_listing_refuses_a_string_or_bytes_answer(self):
        """``bytes`` is a ``Sequence``; a listing is a list of ids."""
        for answer in (b"obj_" + b"a" * 64, "obj_" + "a" * 64, (1, 2)):
            with self.subTest(answer=type(answer).__name__):
                transport = FakeTransport(answers={"list_backups": answer})
                with self.assertRaises(human_backup.HumanBackupError):
                    backup_target(transport=transport).list_backups()

    def test_listing_refuses_a_member_that_is_not_an_object_id(self):
        transport = FakeTransport(answers={"list_backups": ["brain-backup/notes.txt"]})
        with self.assertRaises(human_backup.HumanBackupError):
            backup_target(transport=transport).list_backups()

    def test_a_good_listing_comes_back_as_object_ids(self):
        transport = FakeTransport(
            answers={"list_backups": [f"brain-backup/{OBJECT_ID}"]})
        self.assertEqual(backup_target(transport=transport).list_backups(),
                         (OBJECT_ID,))

    def test_the_folder_is_a_bounded_filing_convenience_not_a_name(self):
        for folder in ("", "/absolute/", "Backups/", "a" * 80 + "/",
                       "users/alice/tax-return-2025.pdf"):
            with self.subTest(folder=folder):
                with self.assertRaises(ValueError):
                    backup_target(folder=folder)

    def test_the_folder_bound_is_the_lane_s_prefix_bound(self):
        self.assertEqual(human_backup.MAX_FOLDER, s3_object.MAX_KEY_PREFIX)

    def test_an_export_over_the_bound_is_refused(self):
        oversize = b"x" * (human_backup.MAX_EXPORT_BYTES + 1)
        digest = hashlib.sha256(oversize).hexdigest()
        with self.assertRaises(ValueError):
            backup_target().export_backup(
                f"obj_{digest}", oversize,
                backup_descriptor(content_sha256=digest,
                                  size_bytes=len(oversize)))

    def test_the_export_bound_is_smaller_than_the_bulk_object_ceiling(self):
        """A human recovery export is something a person can restore from."""
        self.assertLess(human_backup.MAX_EXPORT_BYTES, s3_object.MAX_OBJECT_BYTES)

    def test_a_caller_may_narrow_the_export_ceiling_and_never_widen_it(self):
        self.assertEqual(backup_target(max_export_bytes=1024).max_export_bytes,
                         1024)
        with self.assertRaises(ValueError):
            backup_target(max_export_bytes=human_backup.MAX_EXPORT_BYTES + 1)

    def test_privacy_still_outranks_the_transport(self):
        target = backup_target()
        with self.assertRaises(ValueError):
            target.export_backup(OBJECT_ID, PAYLOAD,
                                 backup_descriptor(privacy_class="LOCAL_ONLY"))
        with self.assertRaises(ValueError):
            target.export_backup(
                OBJECT_ID, PAYLOAD,
                backup_descriptor(privacy_class="CONFIDENTIAL"))

    def test_confidential_ciphertext_with_its_scheme_version_is_accepted(self):
        receipt = backup_target().export_backup(
            OBJECT_ID, PAYLOAD,
            backup_descriptor(privacy_class="CONFIDENTIAL",
                              encryption_state="CLIENT_SIDE_ENCRYPTED",
                              encryption_scheme_version=1))
        self.assertEqual(receipt.object_id, OBJECT_ID)

    def test_a_descriptor_missing_its_privacy_class_is_refused(self):
        with self.assertRaises(ValueError):
            backup_target().export_backup(
                OBJECT_ID, PAYLOAD, backup_descriptor(privacy_class=_ABSENT))


class HuggingFaceAcceptsOnlyDeclaredArtifactsTests(unittest.TestCase):
    def test_the_artifact_classes_are_a_closed_declared_vocabulary(self):
        self.assertIsInstance(huggingface_artifact.ARTIFACT_CLASSES, tuple)
        self.assertTrue(huggingface_artifact.ARTIFACT_CLASSES)
        for artifact_class in huggingface_artifact.ARTIFACT_CLASSES:
            with self.subTest(artifact_class=artifact_class):
                _manifest.validate_object_name(artifact_class)

    def test_no_catch_all_class_smuggles_everything_back_in(self):
        for catch_all in ("artifact", "ai-artifact", "any", "other", "misc",
                          "data", "file", "object", "blob"):
            with self.subTest(catch_all=catch_all):
                self.assertNotIn(catch_all, huggingface_artifact.ARTIFACT_CLASSES)

    def test_every_declared_artifact_class_is_accepted(self):
        for artifact_class in huggingface_artifact.ARTIFACT_CLASSES:
            with self.subTest(artifact_class=artifact_class):
                receipt = artifact_store().upload_artifact(
                    OBJECT_ID, PAYLOAD,
                    artifact_descriptor(object_class=artifact_class))
                self.assertEqual(receipt.object_id, OBJECT_ID)

    def test_anything_else_is_refused(self):
        for artifact_class in ("log-dump", "raw-telemetry", "replay-bundle",
                               "chat-history", "backup", "recovery-export",
                               "evidence.compacted"):
            with self.subTest(artifact_class=artifact_class):
                with self.assertRaises(ValueError):
                    artifact_store().upload_artifact(
                        OBJECT_ID, PAYLOAD,
                        artifact_descriptor(object_class=artifact_class))

    def test_an_artifact_with_no_declared_class_is_refused(self):
        with self.assertRaises(ValueError):
            artifact_store().upload_artifact(
                OBJECT_ID, PAYLOAD, artifact_descriptor(object_class=_ABSENT))

    def test_the_class_check_still_runs_the_lane_s_classifier_bound_first(self):
        """The override is stricter than the borrowed checker, never looser."""
        for bad in ("A" * 8, "a" * 80, "0123456789abcdef0123", 7, None):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    artifact_store().upload_artifact(
                        OBJECT_ID, PAYLOAD, artifact_descriptor(object_class=bad))

    def test_the_hub_serves_the_cold_tier_only(self):
        self.assertEqual(huggingface_artifact.TIERS_ALLOWED, ("COLD",))
        for tier in ("CANONICAL", "HOT", "WARM", "HUMAN_BACKUP", "METADATA"):
            with self.subTest(tier=tier):
                with self.assertRaises(ValueError):
                    artifact_store().upload_artifact(
                        OBJECT_ID, PAYLOAD, artifact_descriptor(storage_tier=tier))

    def test_only_the_hugging_face_registry_row_may_be_driven_through_it(self):
        for backend_id in ("google_drive", "cloudflare_r2", "supabase",
                           "local_owned_store", "some_random_untrusted_host"):
            with self.subTest(backend_id=backend_id):
                with self.assertRaises(ValueError):
                    artifact_store(backend_id=backend_id)

    def test_the_repo_id_is_a_bounded_namespace_and_name(self):
        for repo_id in ("", "no-namespace", "/leading", "trailing/",
                        "Namespace/Name", "a/" + "b" * 80,
                        "user:secret@host/name", "a/b/c"):
            with self.subTest(repo_id=repo_id):
                with self.assertRaises(ValueError):
                    artifact_store(repo_id=repo_id)

    def test_the_repo_type_is_a_closed_vocabulary(self):
        self.assertEqual(huggingface_artifact.REPO_TYPES, ("model", "dataset"))
        for repo_type in ("space", "anything", "", None, 1):
            with self.subTest(repo_type=repo_type):
                with self.assertRaises(ValueError):
                    artifact_store(repo_type=repo_type)

    def test_an_upload_round_trips_through_the_transport(self):
        transport = FakeTransport()
        receipt = artifact_store(transport=transport).upload_artifact(
            OBJECT_ID, PAYLOAD, artifact_descriptor())
        self.assertEqual(receipt.content_sha256, DIGEST)
        operation, payload, context = transport.calls[0]
        self.assertEqual(operation, "upload_artifact")
        self.assertEqual(payload["body"], PAYLOAD)
        self.assertEqual(context["repo_id"], "brain-mesh/eval-corpus")
        self.assertEqual(context["repo_type"], "dataset")

    def test_a_fetch_rehashes_what_came_back(self):
        transport = FakeTransport(answers={"fetch_artifact": b"different bytes"})
        with self.assertRaises(huggingface_artifact.ArtifactIntegrityError):
            artifact_store(transport=transport).fetch_artifact(OBJECT_ID)

    def test_a_fetch_that_finds_nothing_raises(self):
        transport = FakeTransport(answers={"fetch_artifact": None})
        with self.assertRaises(huggingface_artifact.ArtifactNotFound):
            artifact_store(transport=transport).fetch_artifact(OBJECT_ID)

    def test_listing_refuses_a_string_or_bytes_answer(self):
        for answer in (b"obj_" + b"a" * 64, "obj_" + "a" * 64, {"a": 1}):
            with self.subTest(answer=type(answer).__name__):
                transport = FakeTransport(answers={"list_artifacts": answer})
                with self.assertRaises(huggingface_artifact.ArtifactStoreError):
                    artifact_store(transport=transport).list_artifacts()

    def test_privacy_still_outranks_the_transport(self):
        store = artifact_store()
        with self.assertRaises(ValueError):
            store.upload_artifact(OBJECT_ID, PAYLOAD,
                                  artifact_descriptor(privacy_class="LOCAL_ONLY"))
        with self.assertRaises(ValueError):
            store.upload_artifact(OBJECT_ID, PAYLOAD,
                                  artifact_descriptor(privacy_class="CONFIDENTIAL"))

    def test_an_upload_under_the_wrong_address_is_refused(self):
        with self.assertRaises(ValueError):
            artifact_store().upload_artifact(f"obj_{'0' * 64}", PAYLOAD,
                                             artifact_descriptor())


class DescriptorFieldPartitionTests(unittest.TestCase):
    """The structural guard, driven from the manifest schema on disk.

    Every property of ``storage_object_manifest.schema.json`` is in exactly one
    of the two tables, so a property added to the contract later is in neither
    and fails here the day it is added - which is the only way this lane has
    found to stop shipping "an allowed field whose value nothing bounds".
    """

    CASES = (
        (human_backup, "BACKUP_DESCRIPTOR_VALUE_CHECKS",
         "REFUSED_DESCRIPTOR_FIELDS", "BACKUP_DESCRIPTOR_FIELDS"),
        (huggingface_artifact, "ARTIFACT_DESCRIPTOR_VALUE_CHECKS",
         "REFUSED_DESCRIPTOR_FIELDS", "ARTIFACT_DESCRIPTOR_FIELDS"),
    )

    def setUp(self):
        schema = json.loads(MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
        self.schema_properties = set(schema["properties"])

    def test_the_partition_covers_the_schema_exactly(self):
        for module, accepted_name, refused_name, _ in self.CASES:
            accepted = set(getattr(module, accepted_name))
            refused = set(getattr(module, refused_name))
            with self.subTest(module=module.__name__):
                self.assertEqual(accepted & refused, set())
                self.assertEqual(accepted | refused, self.schema_properties)

    def test_the_field_tuple_is_derived_from_the_checker_table(self):
        for module, accepted_name, _, fields_name in self.CASES:
            with self.subTest(module=module.__name__):
                self.assertEqual(getattr(module, fields_name),
                                 tuple(getattr(module, accepted_name)))

    def test_every_refusal_carries_a_written_reason(self):
        for module, _, refused_name, _ in self.CASES:
            for field, reason in getattr(module, refused_name).items():
                with self.subTest(module=module.__name__, field=field):
                    self.assertIsInstance(reason, str)
                    self.assertGreater(len(reason), 40)

    def test_every_accepted_checker_is_the_lane_s_own_callable(self):
        """Bound, not copied - and asserted with ``is`` so a copy fails.

        Every field except a *declared* override must be the identical callable
        ``metadata.py`` already holds, reached directly or through the S3
        adapter's table. A seventh hand-written copy of "what a bounded
        classifier looks like" fails here rather than drifting quietly looser.
        """
        for module, accepted_name, _, _ in self.CASES:
            for field, check in getattr(module, accepted_name).items():
                if field in module.DESCRIPTOR_CHECK_OVERRIDES:
                    continue
                with self.subTest(module=module.__name__, field=field):
                    self.assertIn(check, (
                        s3_object.OBJECT_METADATA_VALUE_CHECKS.get(field),
                        _metadata._RECORD_FIELD_CHECKS.get(field)))
                    self.assertIs(check,
                                  s3_object.OBJECT_METADATA_VALUE_CHECKS[field])

    def test_the_declared_overrides_are_the_actual_overrides(self):
        """An override that is not declared is a copy nobody noticed."""
        for module, accepted_name, _, _ in self.CASES:
            actual = {field for field, check
                      in getattr(module, accepted_name).items()
                      if check is not
                      s3_object.OBJECT_METADATA_VALUE_CHECKS.get(field)}
            with self.subTest(module=module.__name__):
                self.assertEqual(actual, set(module.DESCRIPTOR_CHECK_OVERRIDES))
        self.assertEqual(human_backup.DESCRIPTOR_CHECK_OVERRIDES, ())
        self.assertEqual(huggingface_artifact.DESCRIPTOR_CHECK_OVERRIDES,
                         ("object_class",))

    def test_an_override_runs_the_borrowed_checker_before_its_own_rule(self):
        """Stricter, never looser: the borrowed bound still refuses first."""
        check = huggingface_artifact.ARTIFACT_DESCRIPTOR_VALUE_CHECKS["object_class"]
        borrowed = s3_object.OBJECT_METADATA_VALUE_CHECKS["object_class"]
        for bad in ("A" * 8, "a" * 80, "users/alice/tax-return.pdf"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    borrowed(bad, field="object_class")
                with self.assertRaises(ValueError):
                    check(bad, field="object_class")

    def test_a_refused_field_is_refused_at_the_boundary(self):
        for field in human_backup.REFUSED_DESCRIPTOR_FIELDS:
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    backup_target().export_backup(
                        OBJECT_ID, PAYLOAD, backup_descriptor(**{field: "x"}))
        for field in huggingface_artifact.REFUSED_DESCRIPTOR_FIELDS:
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    artifact_store().upload_artifact(
                        OBJECT_ID, PAYLOAD, artifact_descriptor(**{field: "x"}))

    def test_an_undeclared_field_is_refused_rather_than_ignored(self):
        for build, send, descriptor in (
                (backup_target, "export_backup", backup_descriptor),
                (artifact_store, "upload_artifact", artifact_descriptor)):
            for field in ("api_key", "plaintext_key", "nobody_thought_of_this"):
                with self.subTest(send=send, field=field):
                    with self.assertRaises(ValueError):
                        getattr(build(), send)(
                            OBJECT_ID, PAYLOAD, descriptor(**{field: "x"}))

    def test_an_out_of_bound_value_is_refused_on_every_accepted_field(self):
        """One over-long value per accepted field, driven from the table."""
        for build, send, descriptor, table in (
                (backup_target, "export_backup", backup_descriptor,
                 human_backup.BACKUP_DESCRIPTOR_VALUE_CHECKS),
                (artifact_store, "upload_artifact", artifact_descriptor,
                 huggingface_artifact.ARTIFACT_DESCRIPTOR_VALUE_CHECKS)):
            for field in table:
                with self.subTest(send=send, field=field):
                    with self.assertRaises(ValueError):
                        getattr(build(), send)(
                            OBJECT_ID, PAYLOAD, descriptor(**{field: "z" * 300}))

    def test_a_null_value_is_omitted_rather_than_emitted(self):
        with self.assertRaises(ValueError):
            backup_target().export_backup(
                OBJECT_ID, PAYLOAD, backup_descriptor(object_class=None))

    def test_a_descriptor_that_disagrees_with_the_bytes_is_refused(self):
        with self.assertRaises(ValueError):
            backup_target().export_backup(
                OBJECT_ID, PAYLOAD, backup_descriptor(size_bytes=1))
        with self.assertRaises(ValueError):
            artifact_store().upload_artifact(
                OBJECT_ID, PAYLOAD, artifact_descriptor(content_sha256="c" * 64))

    def test_a_descriptor_that_is_not_a_mapping_is_refused(self):
        for value in ("descriptor", b"descriptor", [("privacy_class", "PUBLIC")]):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(ValueError):
                    backup_target().export_backup(OBJECT_ID, PAYLOAD, value)

    def test_a_non_string_descriptor_key_is_refused(self):
        with self.assertRaises(ValueError):
            backup_target().export_backup(OBJECT_ID, PAYLOAD,
                                          {1: "PUBLIC", **backup_descriptor()})

    def test_the_descriptor_block_is_bounded_as_a_whole(self):
        self.assertEqual(human_backup.MAX_DESCRIPTOR_BYTES,
                         s3_object.MAX_METADATA_BYTES)
        self.assertEqual(huggingface_artifact.MAX_DESCRIPTOR_BYTES,
                         s3_object.MAX_METADATA_BYTES)


class NoCredentialSurvivesAnyInputTests(unittest.TestCase):
    """A credential-shaped needle through every input, keys included.

    ``str``, ``repr`` and ``traceback.format_exc()`` - the third because a
    refusal raised from inside an ``except`` carries the caught exception as
    ``__context__``, which ``str(exc)`` hides and every traceback prints under
    "During handling of the above exception". ``from None`` is what actually
    keeps the value out of a log, and only the traceback assertion can tell.
    """

    def assert_clean(self, needle, call):
        try:
            call()
        except BaseException as exc:  # noqa: BLE001 - the point of the test
            rendered = traceback.format_exc()
            self.assertNotIn(needle, str(exc))
            self.assertNotIn(needle, repr(exc))
            self.assertNotIn(needle, rendered)
        else:
            self.fail("the input was accepted rather than refused")

    def test_a_needle_in_a_constructor_argument_never_surfaces(self):
        for needle in NEEDLES:
            for kwargs in ({"backend_id": needle}, {"folder": needle},
                           {"max_export_bytes": needle}):
                with self.subTest(needle=needle, argument=sorted(kwargs)[0]):
                    self.assert_clean(needle, lambda k=kwargs: backup_target(**k))
            for kwargs in ({"repo_id": needle}, {"repo_type": needle},
                           {"path_prefix": needle}):
                with self.subTest(needle=needle, argument=sorted(kwargs)[0]):
                    self.assert_clean(needle, lambda k=kwargs: artifact_store(**k))

    def test_a_needle_as_an_object_id_never_surfaces(self):
        for needle in NEEDLES:
            with self.subTest(needle=needle):
                self.assert_clean(needle, lambda n=needle: backup_target(
                    ).export_backup(n, PAYLOAD, backup_descriptor()))
                self.assert_clean(needle, lambda n=needle: artifact_store(
                    ).upload_artifact(n, PAYLOAD, artifact_descriptor()))
                self.assert_clean(needle,
                                  lambda n=needle: backup_target().fetch_backup(n))
                self.assert_clean(
                    needle, lambda n=needle: artifact_store().fetch_artifact(n))

    def test_a_needle_in_any_descriptor_value_never_surfaces(self):
        for needle in NEEDLES:
            for field in human_backup.BACKUP_DESCRIPTOR_VALUE_CHECKS:
                with self.subTest(needle=needle, field=field):
                    self.assert_clean(needle, lambda f=field, n=needle:
                                      backup_target().export_backup(
                                          OBJECT_ID, PAYLOAD,
                                          backup_descriptor(**{f: n})))
            for field in huggingface_artifact.ARTIFACT_DESCRIPTOR_VALUE_CHECKS:
                with self.subTest(needle=needle, field=field):
                    self.assert_clean(needle, lambda f=field, n=needle:
                                      artifact_store().upload_artifact(
                                          OBJECT_ID, PAYLOAD,
                                          artifact_descriptor(**{f: n})))

    def test_a_needle_in_a_descriptor_key_never_surfaces(self):
        for needle in NEEDLES:
            with self.subTest(needle=needle):
                self.assert_clean(needle, lambda n=needle: backup_target(
                    ).export_backup(OBJECT_ID, PAYLOAD,
                                    {**backup_descriptor(), n: "x"}))
                self.assert_clean(needle, lambda n=needle: artifact_store(
                    ).upload_artifact(OBJECT_ID, PAYLOAD,
                                      {**artifact_descriptor(), n: "x"}))

    def test_a_needle_in_a_refused_field_key_never_surfaces(self):
        """A refused field is named by the table, but its value is not."""
        for needle in NEEDLES:
            with self.subTest(needle=needle):
                self.assert_clean(needle, lambda n=needle: backup_target(
                    ).export_backup(OBJECT_ID, PAYLOAD,
                                    backup_descriptor(encryption=n)))

    def test_a_needle_from_the_transport_never_surfaces(self):
        for needle in NEEDLES:
            with self.subTest(needle=needle):
                transport = FakeTransport(raises=RuntimeError(needle))
                self.assert_clean(needle, lambda t=transport: backup_target(
                    transport=t).export_backup(OBJECT_ID, PAYLOAD,
                                               backup_descriptor()))
                transport = FakeTransport(raises=RuntimeError(needle))
                self.assert_clean(needle, lambda t=transport: artifact_store(
                    transport=t).upload_artifact(OBJECT_ID, PAYLOAD,
                                                 artifact_descriptor()))

    def test_a_needle_from_the_credential_provider_never_surfaces(self):
        def angry():
            raise RuntimeError(NEEDLES[0])

        self.assert_clean(NEEDLES[0], lambda: backup_target(
            credential_provider=angry).export_backup(OBJECT_ID, PAYLOAD,
                                                     backup_descriptor()))
        self.assert_clean(NEEDLES[0], lambda: artifact_store(
            credential_provider=angry).upload_artifact(OBJECT_ID, PAYLOAD,
                                                       artifact_descriptor()))

    def test_a_needle_from_the_clock_never_surfaces(self):
        for needle in NEEDLES:
            with self.subTest(needle=needle):
                self.assert_clean(needle, lambda n=needle: backup_target(
                    clock=lambda: n).export_backup(OBJECT_ID, PAYLOAD,
                                                   backup_descriptor()))
                self.assert_clean(needle, lambda n=needle: artifact_store(
                    clock=lambda: n).upload_artifact(OBJECT_ID, PAYLOAD,
                                                     artifact_descriptor()))

    def test_the_credential_is_never_stored_logged_or_put_in_a_payload(self):
        needle = NEEDLES[1]
        transport = FakeTransport()
        target = backup_target(transport=transport,
                               credential_provider=lambda: needle)
        target.export_backup(OBJECT_ID, PAYLOAD, backup_descriptor())
        self.assertNotIn(needle, repr(target))
        for attribute in vars(target).values():
            self.assertNotIn(needle, repr(attribute))
        operation, payload, context = transport.calls[0]
        self.assertNotIn(needle, repr(payload))
        self.assertNotIn(needle, repr(context))
        self.assertEqual(transport.credential, needle)

    def test_the_artifact_store_holds_no_credential_either(self):
        needle = NEEDLES[1]
        transport = FakeTransport()
        store = artifact_store(transport=transport,
                               credential_provider=lambda: needle)
        store.upload_artifact(OBJECT_ID, PAYLOAD, artifact_descriptor())
        self.assertNotIn(needle, repr(store))
        for attribute in vars(store).values():
            self.assertNotIn(needle, repr(attribute))
        operation, payload, context = transport.calls[0]
        self.assertNotIn(needle, repr(payload))
        self.assertNotIn(needle, repr(context))

    def test_the_needles_are_real_credential_shapes(self):
        """A regression that can never fire is not a regression."""
        for needle in NEEDLES:
            with self.subTest(needle=needle):
                with self.assertRaises(ValueError):
                    _manifest.assert_no_credential_material(needle, where="test")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
