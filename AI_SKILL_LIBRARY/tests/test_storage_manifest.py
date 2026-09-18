"""Task 2 - typed manifest model and privacy-safe object identity.

Task 1 checked in the *contracts*: ``storage_object_manifest.schema.json`` says
what a manifest record may look like, and ``mesh_validator.py`` says whether the
backends such a record names were actually admitted. Neither of them builds one.
Every manifest in the Task 1 tests is a dict literal typed out by hand, which is
fine for testing a schema and useless as a way for the rest of the mesh to
produce records: the next caller writes the dict by hand too, forgets
``authority_flags``, spells ``origin_class`` as ``kind``, and discovers it at
runtime - or does not discover it at all, because nothing downstream re-reads
the schema.

``manifest.py`` is the typed producer that closes that gap. The tests here are
about two properties and one habit.

1. **The model and the schema must not drift.** A model that emits a document
   the checked-in schema rejects is worse than no model, because it launders a
   hand-written mistake into a trusted-looking one. So the central test is not
   "does the dataclass have the right fields" - it is "does what this model
   produces validate against the schema on disk", asserted over several shapes,
   plus a field-set comparison in both directions so a schema property added
   later without a model field (or the reverse) fails here rather than in
   production.
2. **Secret material is refused by construction, not by review.** Two halves.
   Unknown keyword arguments are refused *structurally*: the model names the
   fields it accepts and everything else lands in ``**unknown`` and is rejected,
   so the seventh secret name nobody thought of is rejected on the same code
   path as the six the plan happened to list. Nested mappings are whitelisted
   the same way. On top of that - and only on top - values are scanned for the
   shapes real credentials actually have, because a leaked token rarely arrives
   under a key helpfully named ``secret``.
3. **Both directions are tested.** A model that only rejects is as broken as
   one that only accepts, so every rejection test has an acceptance test beside
   it showing the nearest legitimate document still passes.

Nothing here performs a placement (Task 3) or any cryptography (Task 6). The
one interaction with the validator is the honest one: a produced manifest is
handed to ``mesh_validator.validate_manifest_placement`` to show the two halves
meet, and the shipped registry says - correctly, today - that nothing is
placeable yet.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from AI_SKILL_LIBRARY.v4.storage import mesh_validator
from AI_SKILL_LIBRARY.v4.storage.manifest import (
    MANIFEST_VERSION,
    StorageObject,
    validate_object_name,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_SCHEMA_PATH = ROOT / "AI_SKILL_LIBRARY/v4/schemas/storage_object_manifest.schema.json"
MANIFEST_SCHEMA = json.loads(MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
SCHEMA_VALIDATOR = Draft202012Validator(MANIFEST_SCHEMA)

#: Set by the schema itself, never by the model.
CONSTANT_FIELDS = {"version", "authority", "authority_flags"}

AUTHORITY_FLAGS = (
    "storage_authority", "routing_authority", "reasoning_authority",
    "model_selection_authority", "admission_authority", "scheduling_authority",
    "merge_authority", "trading_authority",
)

#: The six names the plan lists. They are a *sample* of what must be refused,
#: not the definition of it - see the structural test below.
PLAN_SECRET_FIELD_NAMES = (
    "plaintext_key", "api_key", "authorization", "private_key", "seed_phrase",
    "token",
)


def schema_errors(document):
    return [f"{list(e.absolute_path)}: {e.message}"
            for e in SCHEMA_VALIDATOR.iter_errors(document)]


def public_object(content=b"abc", **overrides):
    """The plainest legitimate object the mesh can hold."""
    kwargs = dict(
        mime_type="application/octet-stream",
        privacy_class="PUBLIC",
        criticality="REPRODUCIBLE",
        retention_class="bounded",
        storage_tier="COLD",
        object_class="benchmark-bundle",
        source_provenance={"origin_class": "benchmark-bundle"},
    )
    kwargs.update(overrides)
    return StorageObject.from_bytes(content, **kwargs)


class ContentAddressedIdentityTests(unittest.TestCase):
    """Spec S7: the id is derived from the bytes and from nothing else."""

    def test_manifest_hashes_content_and_declares_no_authority(self):
        obj = public_object(b"abc")
        self.assertEqual(obj.content_sha256, hashlib.sha256(b"abc").hexdigest())
        manifest = obj.to_manifest()
        self.assertIs(manifest["authority"], False)
        self.assertEqual(manifest["version"], MANIFEST_VERSION)
        self.assertNotIn("plaintext_key", manifest)

    def test_object_id_is_the_digest_and_matches_the_schema_pattern(self):
        obj = public_object(b"abc")
        digest = hashlib.sha256(b"abc").hexdigest()
        self.assertEqual(obj.object_id, f"obj_{digest}")
        pattern = MANIFEST_SCHEMA["properties"]["object_id"]["pattern"]
        self.assertRegex(obj.object_id, pattern)
        self.assertEqual(len(obj.object_id),
                         MANIFEST_SCHEMA["properties"]["object_id"]["maxLength"])

    def test_object_id_is_independent_of_provider_tier_and_privacy(self):
        """Spec S7/S15: identity survives rebalance, re-tiering and replication."""
        here = public_object(b"same bytes", storage_tier="COLD",
                             primary_backend="local_owned_store")
        there = public_object(b"same bytes", storage_tier="HUMAN_BACKUP",
                              primary_backend="local_owned_store",
                              privacy_class="INTERNAL")
        self.assertEqual(here.object_id, there.object_id)
        self.assertEqual(here.size_bytes, len(b"same bytes"))

    def test_different_bytes_are_a_different_object(self):
        self.assertNotEqual(public_object(b"abc").object_id,
                            public_object(b"abd").object_id)

    def test_size_is_measured_not_asserted(self):
        obj = public_object(b"0123456789")
        self.assertEqual(obj.size_bytes, 10)
        with self.assertRaises(ValueError):
            public_object(b"abc", size_bytes=1)


class ImmutabilityTests(unittest.TestCase):
    def test_the_model_is_a_frozen_dataclass(self):
        obj = public_object()
        self.assertTrue(dataclasses.is_dataclass(obj))
        self.assertTrue(dataclasses.fields(obj))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            obj.privacy_class = "PUBLIC"

    def test_replica_backends_are_not_a_mutable_list_on_the_instance(self):
        obj = public_object(criticality="CRITICAL", reproducible=False,
                            primary_backend="local_owned_store",
                            replica_backends=["cloudflare_r2"])
        self.assertIsInstance(obj.replica_backends, tuple)

    def test_to_manifest_returns_a_fresh_document_each_time(self):
        obj = public_object()
        first = obj.to_manifest()
        first["replica_backends"].append("dropbox")
        first["privacy_class"] = "LOCAL_ONLY"
        self.assertEqual(obj.to_manifest()["replica_backends"], [])
        self.assertEqual(obj.to_manifest()["privacy_class"], "PUBLIC")

    def test_nested_mappings_are_copied_not_aliased(self):
        provenance = {"origin_class": "benchmark-bundle"}
        obj = public_object(source_provenance=provenance)
        provenance["origin_class"] = "mutated"
        self.assertEqual(obj.to_manifest()["source_provenance"]["origin_class"],
                         "benchmark-bundle")


class SchemaAgreementTests(unittest.TestCase):
    """The single most important test in the task, stated four ways."""

    def test_a_realistic_object_produces_a_manifest_the_schema_accepts(self):
        self.assertEqual(schema_errors(public_object().to_manifest()), [])

    def test_every_shape_the_model_can_emit_validates(self):
        cases = {
            "public-cold": public_object(),
            "local-only": public_object(privacy_class="LOCAL_ONLY",
                                        primary_backend="local_owned_store"),
            "internal-replicated": public_object(
                privacy_class="INTERNAL", criticality="CRITICAL",
                reproducible=False, primary_backend="local_owned_store",
                replica_backends=["cloudflare_r2"]),
            "confidential-ciphertext": public_object(
                privacy_class="CONFIDENTIAL", primary_backend="backblaze_b2",
                encryption_state="CLIENT_SIDE_ENCRYPTED",
                encryption_scheme_version=1,
                encryption={"algorithm": "aes-256-gcm", "scheme_version": 1,
                            "key_ref": "secretstore://mesh/object-dek"}),
            "metadata-supabase": public_object(
                b"x", storage_tier="METADATA", primary_backend="supabase"),
            "canonical-pointer": public_object(b"x", storage_tier="CANONICAL",
                                               primary_backend="local_owned_store"),
            "minimal-optional-fields": StorageObject.from_bytes(
                b"abc", privacy_class="PUBLIC", criticality="EPHEMERAL",
                storage_tier="HOT"),
            "fully-populated": public_object(
                last_accessed_at="2026-09-18T00:00:00Z",
                last_verified_at="2026-09-18T00:00:00Z",
                lifecycle_state="COMPRESSED",
                source_provenance={"origin_class": "benchmark-bundle",
                                   "producer_id": "eval-harness",
                                   "evidence_ref": "docs/superpowers/plans/x.md"},
                verification={"hash_verified": True, "verified_replica_count": 0,
                              "last_probe_at": "2026-09-18T00:00:00Z"}),
        }
        for name, obj in cases.items():
            with self.subTest(case=name):
                self.assertEqual(schema_errors(obj.to_manifest()), [])

    def test_the_model_field_set_does_not_drift_from_the_schema_properties(self):
        schema_properties = set(MANIFEST_SCHEMA["properties"])
        model_fields = {f.name for f in dataclasses.fields(StorageObject)}
        self.assertEqual(model_fields | CONSTANT_FIELDS, schema_properties,
                         "a schema property with no model field (or the reverse) "
                         "is drift; fix both sides together")
        self.assertEqual(model_fields & CONSTANT_FIELDS, set(),
                         "version/authority/authority_flags are constants the "
                         "model emits, never fields a caller can set")

    def test_every_required_schema_property_is_always_emitted(self):
        manifest = StorageObject.from_bytes(
            b"abc", privacy_class="PUBLIC", criticality="EPHEMERAL",
            storage_tier="HOT").to_manifest()
        for prop in MANIFEST_SCHEMA["required"]:
            with self.subTest(property=prop):
                self.assertIn(prop, manifest)

    def test_optional_fields_are_omitted_rather_than_emitted_as_null(self):
        manifest = StorageObject.from_bytes(
            b"abc", privacy_class="PUBLIC", criticality="EPHEMERAL",
            storage_tier="HOT").to_manifest()
        self.assertNotIn("mime_type", manifest)
        self.assertNotIn("encryption", manifest)
        self.assertEqual(schema_errors(manifest), [])


class AuthorityTests(unittest.TestCase):
    def test_authority_is_false_on_every_manifest_produced(self):
        for obj in (public_object(), public_object(privacy_class="LOCAL_ONLY",
                                                   primary_backend="local_owned_store")):
            manifest = obj.to_manifest()
            self.assertIs(manifest["authority"], False)
            self.assertEqual(sorted(manifest["authority_flags"]),
                             sorted(AUTHORITY_FLAGS))
            for flag in AUTHORITY_FLAGS:
                with self.subTest(flag=flag):
                    self.assertIs(manifest["authority_flags"][flag], False)

    def test_authority_cannot_be_asserted_by_a_caller(self):
        for field in ("authority", "authority_flags", "version"):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    public_object(**{field: True})


class UnknownFieldRejectionTests(unittest.TestCase):
    """Structural, not a denylist of six names."""

    def test_the_six_names_the_plan_lists_are_rejected(self):
        for name in PLAN_SECRET_FIELD_NAMES:
            with self.subTest(field=name):
                with self.assertRaises(ValueError):
                    public_object(**{name: "value"})

    def test_the_seventh_name_nobody_listed_is_rejected_on_the_same_path(self):
        """A denylist of six is bypassed by the seventh; this must not be one."""
        for name in ("client_secret", "aws_session_token", "cookie_jar",
                     "x_amz_signature", "kubeconfig", "totp_seed",
                     "harmless_looking_note", "zz_field_invented_in_2031"):
            with self.subTest(field=name):
                with self.assertRaises(ValueError):
                    public_object(**{name: "value"})

    def test_rejection_names_the_offending_field(self):
        with self.assertRaises(ValueError) as caught:
            public_object(bearer_assertion="x")
        self.assertIn("bearer_assertion", str(caught.exception))

    def test_nested_mappings_are_whitelisted_the_same_way(self):
        cases = [
            ("provenance", {"source_provenance": {"kind": "test"}}),
            ("provenance-secret", {"source_provenance": {
                "origin_class": "benchmark-bundle", "api_key": "x"}}),
            ("verification", {"verification": {"authorization": "Bearer x"}}),
        ]
        for name, kwargs in cases:
            with self.subTest(case=name):
                with self.assertRaises(ValueError):
                    public_object(**kwargs)

    def test_the_nearest_legitimate_nested_mapping_is_accepted(self):
        obj = public_object(source_provenance={"origin_class": "benchmark-bundle",
                                               "producer_id": "eval-harness"},
                            verification={"hash_verified": True})
        self.assertEqual(schema_errors(obj.to_manifest()), [])

    def test_encryption_metadata_has_no_slot_for_key_material(self):
        for bad in ({"algorithm": "aes-256-gcm", "scheme_version": 1,
                     "key_ref": "secretstore://mesh/dek", "key_material": "0" * 64},
                    {"algorithm": "aes-256-gcm", "scheme_version": 1,
                     "key_ref": "secretstore://mesh/dek", "dek": "0" * 64},
                    {"algorithm": "aes-256-gcm", "scheme_version": 1,
                     "key_ref": "secretstore://mesh/dek", "passphrase": "hunter2"}):
            with self.subTest(extra=sorted(set(bad) - {"algorithm", "scheme_version", "key_ref"})):
                with self.assertRaises(ValueError):
                    public_object(privacy_class="CONFIDENTIAL",
                                  primary_backend="backblaze_b2",
                                  encryption_state="CLIENT_SIDE_ENCRYPTED",
                                  encryption=bad)


class CredentialShapedValueTests(unittest.TestCase):
    """The value half: a token rarely arrives under a key named 'secret'."""

    def test_credential_shaped_values_are_refused_wherever_they_appear(self):
        cases = {
            "aws-key-id": {"object_class": "akiaiosfodnn7example"},
            "github-token": {"retention_class": "ghp_" + "a" * 36},
            "hex-key-material": {"object_class": "deadbeef" * 8},
            "provenance-token": {"source_provenance": {
                "origin_class": "benchmark-bundle",
                "producer_id": "ghp_" + "b" * 36}},
        }
        for name, kwargs in cases.items():
            with self.subTest(case=name):
                with self.assertRaises(ValueError):
                    public_object(**kwargs)

    def test_a_real_classifier_that_merely_looks_technical_is_accepted(self):
        obj = public_object(object_class="replay-bundle.v2",
                            retention_class="standard-90d")
        self.assertEqual(schema_errors(obj.to_manifest()), [])


class ObjectNameTests(unittest.TestCase):
    """A *name* here is a human-facing classifier label, never object identity.

    ``policy.yaml`` object_naming says ``content_addressed: true`` and
    ``human_readable_names_allowed: false``: the mesh's identity for an object is
    the digest in ``object_id``, and no manifest field is ever a filename or a
    storage key. ``validate_object_name`` therefore does not validate an
    identity - it guards the one place a human-chosen string may still enter a
    manifest, the small controlled-vocabulary classifiers (``object_class``,
    ``retention_class``, ``origin_class``, ``producer_id``). The distinction is
    load-bearing: an object_id is 68 characters of digest and must *fail* this
    check, because if a digest were an acceptable name, a name would be an
    acceptable id.
    """

    def test_object_name_rejects_sensitive_text(self):
        with self.assertRaises(ValueError):
            validate_object_name("backup-api_key-secret.txt")

    def test_names_carrying_secret_or_private_text_are_rejected(self):
        for name in ("backup-api_key-secret.txt", "my-password", "session_token",
                     "seed-phrase-backup", "privatekey", "oauth-refresh",
                     "user-1234567890-records", "deadbeefdeadbeef",
                     "ghp_" + "c" * 36, "akiaiosfodnn7example"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    validate_object_name(name)

    def test_path_like_and_free_text_names_are_rejected(self):
        for name in ("users/alice/tax-return-2025.pdf", "Alice Tax Return",
                     "notes for bob", "alice@example.com", "../../etc/passwd",
                     "", "   ", "a" * 41, "Benchmark-Bundle"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    validate_object_name(name)

    def test_an_object_id_is_not_an_acceptable_name(self):
        obj = public_object()
        with self.assertRaises(ValueError):
            validate_object_name(obj.object_id)

    def test_legitimate_classifier_labels_are_accepted(self):
        for name in ("benchmark-bundle", "replay", "checkpoint",
                     "evidence.compacted", "standard-90d", "bounded",
                     "eval-harness", "replay-bundle.v2"):
            with self.subTest(name=name):
                self.assertIsNone(validate_object_name(name))

    def test_non_strings_are_rejected(self):
        for value in (None, 7, b"benchmark-bundle", ["benchmark-bundle"]):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):
                    validate_object_name(value)

    def test_the_model_routes_its_classifiers_through_the_same_check(self):
        with self.assertRaises(ValueError):
            public_object(object_class="backup-api_key-secret.txt")


class PrivacyCoherenceTests(unittest.TestCase):
    """Spec S4, mirrored so the model cannot emit a document the schema refuses."""

    def test_local_only_cannot_name_an_external_backend(self):
        for kwargs in ({"primary_backend": "dropbox"},
                       {"primary_backend": "local_owned_store",
                        "replica_backends": ["google_drive"]}):
            with self.subTest(**kwargs):
                with self.assertRaises(ValueError):
                    public_object(privacy_class="LOCAL_ONLY", **kwargs)

    def test_local_only_on_owned_storage_is_accepted(self):
        obj = public_object(privacy_class="LOCAL_ONLY",
                            primary_backend="local_owned_store")
        self.assertEqual(schema_errors(obj.to_manifest()), [])

    def test_confidential_reaches_an_external_backend_only_as_ciphertext(self):
        with self.assertRaises(ValueError):
            public_object(privacy_class="CONFIDENTIAL",
                          primary_backend="backblaze_b2")

    def test_encryption_state_and_its_evidence_cannot_contradict_each_other(self):
        with self.assertRaises(ValueError):
            public_object(encryption_state="NONE",
                          encryption={"algorithm": "aes-256-gcm",
                                      "scheme_version": 1,
                                      "key_ref": "secretstore://mesh/dek"})
        with self.assertRaises(ValueError):
            public_object(encryption_state="CLIENT_SIDE_ENCRYPTED")
        with self.assertRaises(ValueError):
            public_object(encryption_state="NONE", encryption_scheme_version=1)

    def test_key_reference_must_point_away_from_the_ciphertext_provider(self):
        """Spec S22: allowed key locations are secret stores, not buckets."""
        for key_ref in ("https://backblaze_b2.example/bucket/dek",
                        "s3://bucket/dek", "0" * 64, "github://repo/keys.txt"):
            with self.subTest(key_ref=key_ref):
                with self.assertRaises(ValueError):
                    public_object(privacy_class="CONFIDENTIAL",
                                  primary_backend="backblaze_b2",
                                  encryption_state="CLIENT_SIDE_ENCRYPTED",
                                  encryption={"algorithm": "aes-256-gcm",
                                              "scheme_version": 1,
                                              "key_ref": key_ref})

    def test_an_allowed_key_location_is_accepted(self):
        for key_ref in ("env://MESH_OBJECT_DEK", "secretstore://mesh/object-dek",
                        "worker-secret://mesh/dek", "kms://mesh/dek"):
            with self.subTest(key_ref=key_ref):
                obj = public_object(privacy_class="CONFIDENTIAL",
                                    primary_backend="backblaze_b2",
                                    encryption_state="CLIENT_SIDE_ENCRYPTED",
                                    encryption={"algorithm": "aes-256-gcm",
                                                "scheme_version": 1,
                                                "key_ref": key_ref})
                self.assertEqual(schema_errors(obj.to_manifest()), [])

    def test_an_invented_algorithm_is_refused(self):
        with self.assertRaises(ValueError):
            public_object(privacy_class="CONFIDENTIAL",
                          primary_backend="backblaze_b2",
                          encryption_state="CLIENT_SIDE_ENCRYPTED",
                          encryption={"algorithm": "rot13-homebrew",
                                      "scheme_version": 1,
                                      "key_ref": "env://MESH_OBJECT_DEK"})

    def test_this_module_performs_no_cryptography(self):
        from AI_SKILL_LIBRARY.v4.storage import manifest as manifest_module

        self.assertIs(manifest_module.ENCRYPTION_IMPLEMENTED_HERE, False)
        for forbidden in ("encrypt", "decrypt", "derive_key", "wrap_key"):
            with self.subTest(symbol=forbidden):
                self.assertFalse(hasattr(manifest_module, forbidden))


class VocabularyAndTierTests(unittest.TestCase):
    def test_vocabularies_are_closed(self):
        for kwargs in ({"privacy_class": "SEMI_PUBLIC"},
                       {"criticality": "SORT_OF_IMPORTANT"},
                       {"storage_tier": "LUKEWARM"},
                       {"lifecycle_state": "PENDING"},
                       {"encryption_state": "MAYBE"},
                       {"primary_backend": "some_random_untrusted_host"},
                       {"replica_backends": ["some_random_untrusted_host"]}):
            with self.subTest(**kwargs):
                with self.assertRaises(ValueError):
                    public_object(**kwargs)

    def test_pointer_tiers_carry_no_bulk_object_data(self):
        oversized = b"x" * (mesh_validator.BULK_OBJECT_THRESHOLD_BYTES + 1)
        for tier in sorted(mesh_validator.NON_BULK_TIERS):
            with self.subTest(tier=tier):
                with self.assertRaises(ValueError):
                    public_object(oversized, storage_tier=tier,
                                  primary_backend="local_owned_store")

    def test_supabase_is_metadata_and_index_only(self):
        with self.assertRaises(ValueError):
            public_object(b"x", storage_tier="WARM", primary_backend="supabase")
        obj = public_object(b"x", storage_tier="METADATA",
                            primary_backend="supabase")
        self.assertEqual(schema_errors(obj.to_manifest()), [])

    def test_a_replica_may_not_be_the_primary_again(self):
        """Spec S9: a replica is an independent copy."""
        with self.assertRaises(ValueError):
            public_object(criticality="CRITICAL", reproducible=False,
                          primary_backend="local_owned_store",
                          replica_backends=["local_owned_store"])

    def test_reproducible_criticality_cannot_claim_to_be_irreproducible(self):
        with self.assertRaises(ValueError):
            public_object(criticality="REPRODUCIBLE", reproducible=False)

    def test_timestamps_must_be_rfc3339_instants(self):
        with self.assertRaises(ValueError):
            public_object(created_at="18 September 2026")

    def test_the_default_created_at_satisfies_the_schema_pattern(self):
        pattern = MANIFEST_SCHEMA["$defs"]["timestamp"]["pattern"]
        self.assertRegex(public_object().to_manifest()["created_at"],
                         re.compile(pattern))


class ValidatorHandoffTests(unittest.TestCase):
    """Passing the schema is necessary and not sufficient (Task 1's words)."""

    def test_a_produced_manifest_passes_the_schema_and_is_evaluated_by_the_validator(self):
        manifest = public_object(privacy_class="INTERNAL",
                                 primary_backend="cloudflare_r2").to_manifest()
        self.assertEqual(schema_errors(manifest), [],
                         "the model's output is a valid document")
        problems = mesh_validator.validate_manifest_placement(manifest)
        self.assertIsInstance(problems, list)
        self.assertTrue(problems,
                        "identity resolves, admission does not: nothing in the "
                        "shipped registry is placeable today")

    def test_the_model_does_not_decide_placement(self):
        """Task 3 owns placement. An unplaced object stays on owned storage."""
        obj = StorageObject.from_bytes(b"abc", privacy_class="PUBLIC",
                                       criticality="EPHEMERAL",
                                       storage_tier="HOT")
        self.assertEqual(obj.primary_backend, "local_owned_store")
        self.assertEqual(obj.replica_backends, ())

    def test_the_model_holds_no_authority_of_its_own(self):
        from AI_SKILL_LIBRARY.v4.storage import manifest as manifest_module

        self.assertIs(manifest_module.AUTHORITY, False)
        self.assertEqual(manifest_module.CANONICAL_AUTHORITY, "GITHUB_BRAIN_V4")


if __name__ == "__main__":
    unittest.main()
