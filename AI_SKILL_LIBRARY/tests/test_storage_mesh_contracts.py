"""Contract tests for the Federated Free Storage Mesh (Task 1).

The mesh is a subordinate persistence/placement subsystem. Nothing here
executes a placement or touches a provider; these tests police the *shape* of
the contracts, because shape is the only part of a policy that survives the
next author.

Three things are checked, in order of how expensive they are to get wrong:

1. Authority and cost. Eight authority flags are false in the policy and
   pinned `const: false` in both schemas, and the zero-cost guard reads the
   way Spec §11 states it. A flag that is merely absent is a flag a future
   document can set.
2. Privacy as structure. `LOCAL_ONLY` cannot name an external backend and
   `CONFIDENTIAL` cannot reach an external backend unencrypted - not by
   convention, but because the schema rejects the document. A comment saying
   "don't do this" is not a control.
3. Credential exclusion by typing. Every string in the manifest schema is
   bounded by pattern and maxLength, every array by maxItems, every object by
   `additionalProperties: false`. An unbounded string is a slot that will hold
   an API key as happily as it holds a mime type; the convention is the one
   already worked through in experience_ledger.schema.json.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
STORAGE = ROOT / "AI_SKILL_LIBRARY/v4/storage"
SCHEMAS = ROOT / "AI_SKILL_LIBRARY/v4/schemas"
POLICY_PATH = STORAGE / "policy.yaml"
PROVIDERS_PATH = STORAGE / "providers.yaml"
MANIFEST_SCHEMA_PATH = SCHEMAS / "storage_object_manifest.schema.json"
PROVIDER_SCHEMA_PATH = SCHEMAS / "storage_provider.schema.json"
SHARED_STATE_PATH = ROOT / "AI_SKILL_LIBRARY/v4/runtime/shared_state.yaml"
FABRIC_PATH = ROOT / "AI_SKILL_LIBRARY/v4/stable/universal_fabric.yaml"

AUTHORITY_FLAGS = (
    "storage_authority",
    "routing_authority",
    "reasoning_authority",
    "model_selection_authority",
    "admission_authority",
    "scheduling_authority",
    "merge_authority",
    "trading_authority",
)

PRIVACY_CLASSES = ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "LOCAL_ONLY"]
CRITICALITY_CLASSES = ["CRITICAL", "IMPORTANT", "REPRODUCIBLE", "EPHEMERAL"]
STORAGE_TIERS = ["CANONICAL", "HOT", "WARM", "COLD", "HUMAN_BACKUP", "METADATA"]

#: Shapes of real credential material, borrowed from the lane's existing
#: security regression. About values, because a leaked token rarely arrives
#: under a key helpfully named "secret".
CREDENTIAL_PATTERNS = [
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("OpenAI-style key", re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
    ("bearer header", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{20,}=*")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("basic-auth URL", re.compile(r"https?://[^/\s:@]+:[^/\s@]+@")),
]

SENSITIVE_KEY_NAMES = {
    "key", "secret", "secrets", "api_key", "apikey", "token", "access_token",
    "refresh_token", "bearer", "password", "passphrase", "seed", "seed_phrase",
    "mnemonic", "private_key", "privatekey", "credential", "credentials",
    "session_token", "client_secret", "signing_key", "key_material",
    "encryption_key", "data_key", "account_id", "reasoning", "hidden_reasoning",
    "raw_payload", "prompt",
}


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def walk_subschemas(node, trail="#"):
    """Yield (trail, subschema) for every schema-shaped mapping in a schema."""
    if isinstance(node, dict):
        yield trail, node
        for keyword in ("properties", "$defs", "definitions", "patternProperties"):
            for name, child in (node.get(keyword) or {}).items():
                yield from walk_subschemas(child, f"{trail}/{keyword}/{name}")
        for keyword in ("items", "contains", "if", "then", "else", "not",
                        "additionalProperties", "propertyNames"):
            child = node.get(keyword)
            if isinstance(child, dict):
                yield from walk_subschemas(child, f"{trail}/{keyword}")
        for keyword in ("allOf", "anyOf", "oneOf", "prefixItems"):
            for index, child in enumerate(node.get(keyword) or []):
                yield from walk_subschemas(child, f"{trail}/{keyword}/{index}")


def declares_type(subschema, name):
    declared = subschema.get("type")
    return declared == name or (isinstance(declared, list) and name in declared)


def sensitive_key_paths(value, trail=""):
    found = []
    if isinstance(value, dict):
        for key, nested in value.items():
            here = f"{trail}.{key}" if trail else str(key)
            if str(key).strip().lower() in SENSITIVE_KEY_NAMES:
                found.append(here)
            found.extend(sensitive_key_paths(nested, here))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found.extend(sensitive_key_paths(item, f"{trail}[{index}]"))
    return found


def valid_manifest(**overrides):
    base = {
        "version": 1,
        "authority": False,
        "authority_flags": {flag: False for flag in AUTHORITY_FLAGS},
        "object_id": "obj_" + "a" * 64,
        "content_sha256": "b" * 64,
        "size_bytes": 1024,
        "mime_type": "application/json",
        "privacy_class": "PUBLIC",
        "criticality": "REPRODUCIBLE",
        "retention_class": "standard-90d",
        "storage_tier": "WARM",
        "encryption_state": "NONE",
        "primary_backend": "backblaze_b2",
        "replica_backends": [],
        "created_at": "2026-09-18T00:00:00Z",
        "last_accessed_at": "2026-09-18T00:00:00Z",
        "last_verified_at": "2026-09-18T00:00:00Z",
        "lifecycle_state": "RAW",
        "source_provenance": {"origin_class": "benchmark-bundle"},
        "reproducible": True,
    }
    base.update(overrides)
    return base


def valid_provider(**overrides):
    base = {
        "provider_id": "backblaze_b2",
        "adapter_type": "s3_compatible",
        "external": True,
        "free_status": "UNVERIFIED",
        "free_status_evidence": {"evidence_class": "none"},
        "quota_total": None,
        "quota_used": None,
        "hard_stop_verified": False,
        "paid_spillover_possible": "unknown",
        "privacy_classes_allowed": ["PUBLIC"],
        "encryption_required_classes": ["CONFIDENTIAL"],
        "health": "QUARANTINED",
        "autonomous_write_allowed": False,
        "bulk_object_backend_allowed": True,
        "tiers_allowed": ["WARM", "COLD"],
        "authority": False,
        "authority_flags": {flag: False for flag in AUTHORITY_FLAGS},
    }
    base.update(overrides)
    return base


class PolicyAuthorityAndCostTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_yaml(POLICY_PATH)

    def test_storage_policy_is_subordinate_and_free_only(self):
        policy = self.policy
        self.assertIs(policy["authority"]["storage_authority"], False)
        self.assertIs(policy["authority"]["routing_authority"], False)
        self.assertIs(policy["authority"]["trading_authority"], False)
        self.assertIs(policy["cost"]["paid_storage_allowed"], False)
        self.assertIs(policy["cost"]["overage_allowed"], False)

    def test_every_named_authority_is_denied_by_name(self):
        self.assertEqual(sorted(self.policy["authority"]), sorted(AUTHORITY_FLAGS))
        for flag in AUTHORITY_FLAGS:
            with self.subTest(flag=flag):
                self.assertIs(self.policy["authority"][flag], False)

    def test_zero_cost_guard_states_are_exact(self):
        cost = self.policy["cost"]
        self.assertEqual(cost["unknown_cost_state"], "QUARANTINE")
        self.assertEqual(cost["billable_spillover_unverified"], "NO_AUTONOMOUS_WRITE")
        self.assertEqual(cost["free_expiry_unknown"], "NO_AUTONOMOUS_WRITE")

    def test_canonical_authority_and_the_one_portable_state_contract(self):
        canonical = self.policy["canonical"]
        self.assertEqual(canonical["authority"], "GITHUB_BRAIN_V4")
        self.assertEqual(
            canonical["portable_state_contract"],
            "AI_SKILL_LIBRARY/v4/runtime/shared_state.yaml",
        )
        self.assertEqual(canonical["routed_by"], "task_router")

    def test_local_only_provider_eligibility_is_empty(self):
        self.assertIs(
            self.policy["privacy"]["LOCAL_ONLY"]["external_backends_allowed"], False)

    def test_privacy_classes_are_exactly_the_four(self):
        self.assertEqual(sorted(self.policy["privacy"]), sorted(PRIVACY_CLASSES))

    def test_confidential_requires_client_side_encryption(self):
        confidential = self.policy["privacy"]["CONFIDENTIAL"]
        self.assertIs(confidential["client_encryption_required"], True)
        self.assertEqual(confidential["external_backends_allowed"],
                         "encrypted_verified_only")

    def test_criticality_and_tier_vocabularies_are_exact(self):
        self.assertEqual(sorted(self.policy["criticality"]), sorted(CRITICALITY_CLASSES))
        self.assertEqual(sorted(self.policy["tiers"]), sorted(STORAGE_TIERS))

    def test_placement_order_is_the_spec_order(self):
        self.assertEqual(
            self.policy["placement_order"],
            [
                "privacy", "integrity_criticality", "free_only_eligibility",
                "provider_health", "quota_headroom", "object_size",
                "access_frequency", "retention_class", "latency", "backend_choice",
            ],
        )

    def test_supabase_is_metadata_only_and_not_authority(self):
        supabase = self.policy["metadata_service"]
        self.assertEqual(supabase["provider_id"], "supabase")
        self.assertIs(supabase["authority"], False)
        self.assertIs(supabase["bulk_object_backend_allowed"], False)
        self.assertEqual(supabase["tiers_allowed"], ["METADATA"])
        self.assertIs(supabase["project_creation_requires_explicit_approval"], True)

    def test_policy_declares_no_crypto_implementation_here(self):
        encryption = self.policy["encryption"]
        self.assertIs(encryption["implemented_here"], False)
        self.assertIs(encryption["key_material_in_repository"], False)
        self.assertIs(encryption["key_material_in_metadata"], False)


class PolicyMatchesPythonEnumsTests(unittest.TestCase):
    def test_package_enums_do_not_drift_from_the_policy(self):
        from AI_SKILL_LIBRARY.v4 import storage

        policy = load_yaml(POLICY_PATH)
        self.assertEqual(sorted(storage.PRIVACY_CLASSES), sorted(policy["privacy"]))
        self.assertEqual(sorted(storage.CRITICALITY_CLASSES), sorted(policy["criticality"]))
        self.assertEqual(sorted(storage.STORAGE_TIERS), sorted(policy["tiers"]))
        self.assertEqual(sorted(storage.AUTHORITY_FLAGS), sorted(policy["authority"]))

    def test_package_declares_no_authority_of_its_own(self):
        from AI_SKILL_LIBRARY.v4 import storage

        self.assertIs(storage.AUTHORITY, False)
        self.assertEqual(storage.CANONICAL_AUTHORITY, "GITHUB_BRAIN_V4")
        self.assertEqual(storage.ROUTED_BY, "task_router")


class SchemaShapeTests(unittest.TestCase):
    """Credential exclusion is a property of the shape, not of the writer."""

    def setUp(self):
        self.schemas = {
            "manifest": load_json(MANIFEST_SCHEMA_PATH),
            "provider": load_json(PROVIDER_SCHEMA_PATH),
        }

    def test_both_schemas_are_valid_draft_2020_12(self):
        for name, schema in self.schemas.items():
            with self.subTest(schema=name):
                Draft202012Validator.check_schema(schema)

    def test_every_string_is_bounded_by_pattern_and_max_length(self):
        offenders = []
        for name, schema in self.schemas.items():
            for trail, node in walk_subschemas(schema):
                if not declares_type(node, "string"):
                    continue
                if "enum" in node or "const" in node:
                    continue
                if "maxLength" not in node:
                    offenders.append(f"{name}{trail}: no maxLength")
                if "pattern" not in node:
                    offenders.append(f"{name}{trail}: no pattern")
        self.assertEqual(offenders, [])

    def test_every_array_is_bounded_by_max_items(self):
        offenders = []
        for name, schema in self.schemas.items():
            for trail, node in walk_subschemas(schema):
                if declares_type(node, "array") and "maxItems" not in node:
                    offenders.append(f"{name}{trail}: no maxItems")
        self.assertEqual(offenders, [])

    def test_every_object_closes_its_field_set(self):
        offenders = []
        for name, schema in self.schemas.items():
            for trail, node in walk_subschemas(schema):
                if not declares_type(node, "object"):
                    continue
                if node.get("additionalProperties") is not False:
                    offenders.append(f"{name}{trail}: additionalProperties not false")
        self.assertEqual(offenders, [])

    def test_both_schemas_pin_all_eight_authority_flags_false(self):
        for name, schema in self.schemas.items():
            flags = schema["$defs"]["authority_flags"]
            with self.subTest(schema=name):
                self.assertEqual(sorted(flags["required"]), sorted(AUTHORITY_FLAGS))
                for flag in AUTHORITY_FLAGS:
                    self.assertEqual(flags["properties"][flag], {"const": False},
                                     f"{name}:{flag}")

    def test_manifest_enums_are_exactly_the_canonical_vocabularies(self):
        manifest = self.schemas["manifest"]
        props = manifest["properties"]
        self.assertEqual(props["privacy_class"]["enum"], PRIVACY_CLASSES)
        self.assertEqual(props["criticality"]["enum"], CRITICALITY_CLASSES)
        self.assertEqual(props["storage_tier"]["enum"], STORAGE_TIERS)


class ManifestPrivacyStructureTests(unittest.TestCase):
    def setUp(self):
        self.validator = Draft202012Validator(load_json(MANIFEST_SCHEMA_PATH))

    def assertAccepted(self, doc):
        errors = sorted(self.validator.iter_errors(doc), key=str)
        self.assertEqual([e.message for e in errors], [])

    def assertRejected(self, doc):
        self.assertTrue(list(self.validator.iter_errors(doc)))

    def test_a_well_formed_public_manifest_is_accepted(self):
        self.assertAccepted(valid_manifest())

    def test_local_only_cannot_name_an_external_primary_backend(self):
        self.assertRejected(valid_manifest(
            privacy_class="LOCAL_ONLY", primary_backend="cloudflare_r2"))

    def test_local_only_cannot_name_an_external_replica(self):
        self.assertRejected(valid_manifest(
            privacy_class="LOCAL_ONLY",
            primary_backend="local_owned_store",
            replica_backends=["backblaze_b2"]))

    def test_local_only_on_a_local_backend_is_accepted(self):
        self.assertAccepted(valid_manifest(
            privacy_class="LOCAL_ONLY",
            storage_tier="HOT",
            primary_backend="local_owned_store",
            replica_backends=[]))

    def test_confidential_unencrypted_on_an_external_backend_is_rejected(self):
        self.assertRejected(valid_manifest(
            privacy_class="CONFIDENTIAL",
            primary_backend="backblaze_b2",
            encryption_state="NONE"))

    def test_confidential_external_needs_encryption_metadata_not_just_a_flag(self):
        self.assertRejected(valid_manifest(
            privacy_class="CONFIDENTIAL",
            primary_backend="backblaze_b2",
            encryption_state="CLIENT_SIDE_ENCRYPTED"))

    def test_confidential_client_side_encrypted_with_key_reference_is_accepted(self):
        self.assertAccepted(valid_manifest(
            privacy_class="CONFIDENTIAL",
            primary_backend="backblaze_b2",
            encryption_state="CLIENT_SIDE_ENCRYPTED",
            encryption={
                "algorithm": "aead-standard-library",
                "scheme_version": 1,
                "key_ref": "secretstore://brain/storage-mesh/dek-2026-09",
                "nonce": "PDcgVqXQ0m7hRk9s",
                "tag": "9a2f1c0bd4e7a6538f10c2bb",
            }))

    def test_confidential_stored_locally_needs_no_external_encryption(self):
        self.assertAccepted(valid_manifest(
            privacy_class="CONFIDENTIAL",
            storage_tier="HOT",
            primary_backend="local_owned_store"))


class ManifestCredentialExclusionTests(unittest.TestCase):
    def setUp(self):
        self.validator = Draft202012Validator(load_json(MANIFEST_SCHEMA_PATH))

    def assertRejected(self, doc):
        self.assertTrue(list(self.validator.iter_errors(doc)))

    def test_an_unknown_field_is_rejected_rather_than_stored(self):
        self.assertRejected(valid_manifest(api_key="sk-" + "a" * 40))

    def test_encryption_metadata_cannot_carry_key_material(self):
        self.assertRejected(valid_manifest(
            privacy_class="CONFIDENTIAL",
            primary_backend="backblaze_b2",
            encryption_state="CLIENT_SIDE_ENCRYPTED",
            encryption={
                "algorithm": "aead-standard-library",
                "scheme_version": 1,
                "key_ref": "secretstore://brain/dek",
                "key": "3f1a" * 16,
            }))

    def test_a_key_reference_cannot_be_an_inline_secret(self):
        self.assertRejected(valid_manifest(
            privacy_class="CONFIDENTIAL",
            primary_backend="backblaze_b2",
            encryption_state="CLIENT_SIDE_ENCRYPTED",
            encryption={
                "algorithm": "aead-standard-library",
                "scheme_version": 1,
                "key_ref": "3f1a2b3c4d5e6f708192a3b4c5d6e7f8",
            }))

    def test_a_key_reference_cannot_point_at_the_ciphertext_provider(self):
        self.assertRejected(valid_manifest(
            privacy_class="CONFIDENTIAL",
            primary_backend="backblaze_b2",
            encryption_state="CLIENT_SIDE_ENCRYPTED",
            encryption={
                "algorithm": "aead-standard-library",
                "scheme_version": 1,
                "key_ref": "s3://brain-objects/keys/dek-2026-09",
            }))

    def test_nonce_and_tag_are_too_short_to_hold_a_256_bit_key(self):
        schema = load_json(MANIFEST_SCHEMA_PATH)
        encryption = schema["$defs"]["encryption_metadata"]["properties"]
        for field in ("nonce", "tag"):
            with self.subTest(field=field):
                self.assertLessEqual(encryption[field]["maxLength"], 32)

    def test_object_id_cannot_carry_prose_or_a_path(self):
        self.assertRejected(valid_manifest(object_id="users/alice/tax-return-2025.pdf"))

    def test_provenance_is_a_classifier_not_a_free_text_note(self):
        self.assertRejected(valid_manifest(
            source_provenance={"origin_class": "Exported from Alice's inbox on request"}))

    def test_authority_cannot_be_asserted_true(self):
        self.assertRejected(valid_manifest(authority=True))
        self.assertRejected(valid_manifest(
            authority_flags={**{f: False for f in AUTHORITY_FLAGS},
                             "storage_authority": True}))


class ProviderAdmissionStructureTests(unittest.TestCase):
    def setUp(self):
        self.validator = Draft202012Validator(load_json(PROVIDER_SCHEMA_PATH))

    def assertAccepted(self, doc):
        errors = [e.message for e in sorted(self.validator.iter_errors(doc), key=str)]
        self.assertEqual(errors, [])

    def assertRejected(self, doc):
        self.assertTrue(list(self.validator.iter_errors(doc)))

    def test_an_unverified_provider_record_is_accepted_as_quarantined(self):
        self.assertAccepted(valid_provider())

    def test_an_unverified_provider_cannot_be_healthy(self):
        self.assertRejected(valid_provider(health="HEALTHY"))

    def test_an_unverified_provider_cannot_take_autonomous_writes(self):
        self.assertRejected(valid_provider(autonomous_write_allowed=True))

    def test_free_status_cannot_be_verified_from_provider_documentation(self):
        self.assertRejected(valid_provider(
            free_status="VERIFIED_FREE",
            free_status_evidence={"evidence_class": "provider_documentation"},
            health="HEALTHY",
            hard_stop_verified=True,
            paid_spillover_possible=False,
            autonomous_write_allowed=True))

    def test_runtime_account_evidence_can_verify_free_status(self):
        self.assertAccepted(valid_provider(
            free_status="VERIFIED_FREE",
            free_status_evidence={
                "evidence_class": "runtime_account_evidence",
                "verified_at": "2026-09-18T00:00:00Z",
                "evidence_ref": "CHECKPOINTS/evidence/storage_b2_quota.json",
            },
            quota_total=10737418240,
            quota_used=0,
            health="HEALTHY",
            hard_stop_verified=True,
            paid_spillover_possible=False,
            autonomous_write_allowed=True,
            # An autonomous writer is a writer, and a HEALTHY claim now needs a
            # probe behind it. Both were previously absent from this fixture,
            # which is how the review found rows that were writable in name
            # while nothing had been observed about them.
            write_enabled=True,
            last_probe_at="2026-09-18T00:00:00Z"))

    def test_unverified_hard_stop_blocks_autonomous_writes(self):
        self.assertRejected(valid_provider(
            free_status="VERIFIED_FREE",
            free_status_evidence={
                "evidence_class": "runtime_account_evidence",
                "verified_at": "2026-09-18T00:00:00Z",
                "evidence_ref": "CHECKPOINTS/evidence/storage_b2_quota.json",
            },
            health="HEALTHY",
            hard_stop_verified=False,
            paid_spillover_possible=False,
            autonomous_write_allowed=True))

    def test_possible_paid_spillover_blocks_autonomous_writes(self):
        self.assertRejected(valid_provider(
            free_status="VERIFIED_FREE",
            free_status_evidence={
                "evidence_class": "runtime_account_evidence",
                "verified_at": "2026-09-18T00:00:00Z",
                "evidence_ref": "CHECKPOINTS/evidence/storage_b2_quota.json",
            },
            health="HEALTHY",
            hard_stop_verified=True,
            paid_spillover_possible=True,
            autonomous_write_allowed=True))

    def test_an_external_provider_can_never_be_admitted_for_local_only(self):
        self.assertRejected(valid_provider(
            privacy_classes_allowed=["PUBLIC", "LOCAL_ONLY"]))

    def test_an_external_provider_must_require_encryption_for_confidential(self):
        self.assertRejected(valid_provider(
            privacy_classes_allowed=["PUBLIC", "CONFIDENTIAL"],
            encryption_required_classes=[]))

    def test_supabase_cannot_be_declared_a_bulk_object_backend(self):
        self.assertRejected(valid_provider(
            provider_id="supabase",
            adapter_type="supabase_metadata",
            bulk_object_backend_allowed=True,
            tiers_allowed=["METADATA"]))

    def test_supabase_cannot_be_given_object_tiers(self):
        self.assertRejected(valid_provider(
            provider_id="supabase",
            adapter_type="supabase_metadata",
            bulk_object_backend_allowed=False,
            tiers_allowed=["METADATA", "COLD"]))

    def test_an_external_provider_id_cannot_impersonate_a_local_store(self):
        self.assertRejected(valid_provider(provider_id="local_owned_store"))

    def test_a_local_store_is_not_an_external_free_tier(self):
        self.assertRejected(valid_provider(
            provider_id="local_owned_store",
            adapter_type="local_filesystem",
            external=True))

    def test_a_local_store_record_is_accepted(self):
        self.assertAccepted(valid_provider(
            provider_id="local_owned_store",
            adapter_type="local_filesystem",
            external=False,
            free_status="NOT_APPLICABLE",
            free_status_evidence={"evidence_class": "not_applicable"},
            hard_stop_verified=True,
            paid_spillover_possible=False,
            privacy_classes_allowed=PRIVACY_CLASSES,
            encryption_required_classes=[],
            health="HEALTHY",
            autonomous_write_allowed=True,
            write_enabled=True,
            last_probe_at="2026-09-18T00:00:00Z",
            tiers_allowed=["HOT"]))

    def test_a_local_store_cannot_claim_health_without_a_probe(self):
        """The same discipline the external rows get, applied to our own disk."""
        self.assertRejected(valid_provider(
            provider_id="local_owned_store",
            adapter_type="local_filesystem",
            external=False,
            free_status="NOT_APPLICABLE",
            free_status_evidence={"evidence_class": "not_applicable"},
            hard_stop_verified=True,
            paid_spillover_possible=False,
            privacy_classes_allowed=PRIVACY_CLASSES,
            encryption_required_classes=[],
            health="HEALTHY",
            autonomous_write_allowed=True,
            write_enabled=True,
            last_probe_at=None,
            tiers_allowed=["HOT"]))

    def test_a_local_store_cannot_be_given_an_invented_quota(self):
        """Mutant from review: the registry test skipped non-external rows."""
        self.assertRejected(valid_provider(
            provider_id="local_owned_store",
            adapter_type="local_filesystem",
            external=False,
            free_status="NOT_APPLICABLE",
            free_status_evidence={"evidence_class": "not_applicable"},
            quota_total=107374182400,
            hard_stop_verified=True,
            paid_spillover_possible=False,
            privacy_classes_allowed=PRIVACY_CLASSES,
            encryption_required_classes=[],
            health="QUARANTINED",
            autonomous_write_allowed=False,
            tiers_allowed=["HOT"]))


class ProviderRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = load_yaml(PROVIDERS_PATH)
        self.providers = self.registry["providers"]
        self.validator = Draft202012Validator(load_json(PROVIDER_SCHEMA_PATH))

    def test_every_registered_provider_validates(self):
        offenders = []
        for provider in self.providers:
            for error in self.validator.iter_errors(provider):
                offenders.append(f"{provider.get('provider_id')}: {error.message}")
        self.assertEqual(offenders, [])

    def test_the_registry_itself_holds_no_authority(self):
        self.assertIs(self.registry["authority"], False)
        for flag in AUTHORITY_FLAGS:
            with self.subTest(flag=flag):
                self.assertIs(self.registry["authority_flags"][flag], False)
        self.assertIs(self.registry["registry_membership_is_admission"], False)

    def test_no_external_provider_is_admitted_or_verified_without_evidence(self):
        """Honest default: nothing here has been verified, so nothing may write."""
        for provider in self.providers:
            if not provider["external"]:
                continue
            with self.subTest(provider=provider["provider_id"]):
                self.assertEqual(provider["free_status"], "UNVERIFIED")
                self.assertEqual(provider["health"], "QUARANTINED")
                self.assertIs(provider["autonomous_write_allowed"], False)
                self.assertIs(provider["hard_stop_verified"], False)

    def test_no_quota_number_is_invented(self):
        for provider in self.providers:
            if not provider["external"]:
                continue
            with self.subTest(provider=provider["provider_id"]):
                self.assertIsNone(provider["quota_total"])
                self.assertIsNone(provider["quota_used"])

    def test_supabase_is_registered_as_metadata_only(self):
        supabase = next(p for p in self.providers if p["provider_id"] == "supabase")
        self.assertEqual(supabase["adapter_type"], "supabase_metadata")
        self.assertIs(supabase["bulk_object_backend_allowed"], False)
        self.assertEqual(supabase["tiers_allowed"], ["METADATA"])

    def test_a_local_store_exists_so_local_only_has_a_home(self):
        local = [p for p in self.providers if not p["external"]]
        self.assertTrue(local)
        for provider in local:
            with self.subTest(provider=provider["provider_id"]):
                self.assertIn("LOCAL_ONLY", provider["privacy_classes_allowed"])


class NoSecretsInContractsTests(unittest.TestCase):
    def artifacts(self):
        return [POLICY_PATH, PROVIDERS_PATH, MANIFEST_SCHEMA_PATH,
                PROVIDER_SCHEMA_PATH, STORAGE / "__init__.py",
                STORAGE / "mesh_validator.py"]

    def test_no_contract_file_contains_credential_shaped_text(self):
        offenders = []
        for path in self.artifacts():
            text = path.read_text(encoding="utf-8", errors="replace")
            for label, pattern in CREDENTIAL_PATTERNS:
                if pattern.search(text):
                    offenders.append(f"{path.name}: {label}")
        self.assertEqual(offenders, [])

    def test_the_provider_registry_carries_no_sensitive_key_names(self):
        self.assertEqual(sensitive_key_paths(load_yaml(PROVIDERS_PATH)), [])

    def test_the_patterns_actually_match_something(self):
        """A regression that can never fire is not a regression."""
        samples = {
            "private key block": "-----BEGIN RSA PRIVATE KEY-----",
            "AWS access key id": "AKIAIOSFODNN7EXAMPLE",
            "GitHub token": "ghp_" + "A" * 36,
            "Slack token": "xoxb-0123456789-abcdefghij",
            "OpenAI-style key": "sk-" + "A" * 40,
            "bearer header": "Bearer " + "A" * 32,
            "JWT": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K",
            "basic-auth URL": "https://user:pass@example.invalid/x",
        }
        for label, pattern in CREDENTIAL_PATTERNS:
            with self.subTest(pattern=label):
                self.assertTrue(pattern.search(samples[label]))


class SubordinationWiringTests(unittest.TestCase):
    def setUp(self):
        self.shared_state = load_yaml(SHARED_STATE_PATH)
        self.fabric = load_yaml(FABRIC_PATH)

    def test_the_existing_object_store_interface_survives_unchanged(self):
        object_store = self.shared_state["interfaces"]["ObjectStore"]
        self.assertIs(object_store["required"], False)
        self.assertEqual(object_store["first_backend"], "optional_r2")
        self.assertEqual(object_store["binding"], "BRAIN_OBJECTS")
        self.assertEqual(object_store["on_unavailable"], "inline_bounded_metadata_only")
        self.assertEqual(object_store["future_backends"], ["s3_compatible"])

    def test_the_mesh_hangs_off_object_store_as_a_subordinate(self):
        mesh = self.shared_state["interfaces"]["ObjectStore"]["federated_storage_mesh"]
        self.assertIs(mesh["authority"], False)
        self.assertIs(mesh["storage_authority"], False)
        self.assertEqual(mesh["extends_interface"], "ObjectStore")
        self.assertIs(mesh["second_portable_state_abstraction"], False)
        self.assertEqual(mesh["policy"], "AI_SKILL_LIBRARY/v4/storage/policy.yaml")
        self.assertEqual(mesh["providers"], "AI_SKILL_LIBRARY/v4/storage/providers.yaml")
        self.assertIs(mesh["metadata_service_authority"], False)
        self.assertEqual(mesh["backend_resolver"],
                         "AI_SKILL_LIBRARY/v4/storage/mesh_validator.py")
        self.assertIs(mesh["backend_resolver_authority"], False)

    def test_there_is_still_exactly_one_portable_state_abstraction(self):
        """A second ObjectStore-shaped interface would be the second abstraction."""
        interfaces = self.shared_state["interfaces"]
        self.assertEqual(
            sorted(interfaces),
            ["LeaseLock", "MetadataStore", "ObjectStore", "StateKV",
             "TaskQueue", "VectorIndex"])

    def test_the_fabric_registers_the_mesh_as_subordinate(self):
        mesh = self.fabric["subordinate_subsystems"]["federated_free_storage_mesh"]
        self.assertEqual(mesh["canonical_authority"], "github")
        self.assertEqual(mesh["extends"], "AI_SKILL_LIBRARY/v4/runtime/shared_state.yaml#interfaces.ObjectStore")
        for flag in AUTHORITY_FLAGS:
            with self.subTest(flag=flag):
                self.assertIs(mesh[flag], False)
        self.assertIs(mesh["paid_storage_allowed"], False)
        self.assertIs(mesh["overage_allowed"], False)
        self.assertIs(mesh["secrets_allowed"], False)

    def test_the_fabric_authority_chain_is_untouched(self):
        self.assertEqual(self.fabric["authority"], "GITHUB_BRAIN_V4")
        self.assertIs(self.fabric["adapter_authority"], False)
        self.assertIs(self.fabric["shared_state"]["secrets_allowed"], False)

    def test_the_universal_fabric_validator_still_passes(self):
        from AI_SKILL_LIBRARY.v4.tools.validate_universal_fabric import validate

        self.assertEqual(validate(ROOT), [])


# ---------------------------------------------------------------------------
# Provider/manifest linkage (independent review: BLOCKER 1, 2, 3).
#
# The provider schema is real admission control. Until now the manifest schema -
# the surface that decides where an actual byte lands - never consulted it, so a
# manifest could name a backend that was never admitted, or one that is not in
# the registry at all. Two halves close that: the schema enumerates the registry
# keys it will accept (a fact checked into the repository), and a validator
# resolves each named backend to its registry row and applies the admission,
# privacy, tier and capacity state that a JSON Schema cannot see.
# ---------------------------------------------------------------------------

#: Spec S6: CANONICAL and METADATA carry no bulk object data. One number, so the
#: manifest schema, the provider schema and the validator cannot drift.
BULK_THRESHOLD_BYTES = 1048576

REGISTERED_BACKEND_IDS = [
    "local_owned_store", "cloudflare_r2", "backblaze_b2", "oracle_object_storage",
    "huggingface_hub", "google_drive", "onedrive", "dropbox", "supabase",
]


def admitted_provider(**overrides):
    """A provider row that has actually been admitted.

    Nothing in providers.yaml looks like this and nothing should: no account has
    been probed. It exists so every tightening below can be shown to still
    accept a provider that *is* legitimately writable, which is the half of a
    security control that is easy to forget to test.
    """
    base = valid_provider(
        free_status="VERIFIED_RECURRING_FREE",
        free_status_evidence={
            "evidence_class": "runtime_account_evidence",
            "verified_at": "2026-09-18T00:00:00Z",
            "evidence_ref": "CHECKPOINTS/evidence/storage_b2_quota.json",
        },
        free_expiry_at=None,
        quota_total=10737418240,
        quota_used=1073741824,
        quota_reserved=0,
        hard_stop_verified=True,
        paid_spillover_possible=False,
        privacy_classes_allowed=["PUBLIC", "INTERNAL"],
        encryption_required_classes=["CONFIDENTIAL"],
        health="HEALTHY",
        autonomous_write_allowed=True,
        read_enabled=True,
        write_enabled=True,
        bulk_object_backend_allowed=True,
        tiers_allowed=["WARM", "COLD"],
        last_probe_at="2026-09-18T00:00:00Z",
    )
    base.update(overrides)
    return base


def admitted_registry(*rows):
    """A registry fixture whose rows are admitted, for positive-direction tests."""
    return list(rows) if rows else [admitted_provider()]


class BackendIdentityResolutionTests(unittest.TestCase):
    """BLOCKER 1: a manifest may not name a backend nobody admitted."""

    def setUp(self):
        self.schema = load_json(MANIFEST_SCHEMA_PATH)
        self.validator = Draft202012Validator(self.schema)

    def assertRejected(self, doc):
        self.assertTrue(list(self.validator.iter_errors(doc)))

    def test_the_schema_accepts_exactly_the_checked_in_registry_keys(self):
        """The enum is only honest if it is the registry, so assert it is."""
        registry_ids = [p["provider_id"] for p in load_yaml(PROVIDERS_PATH)["providers"]]
        self.assertEqual(
            sorted(self.schema["$defs"]["backend_id"]["enum"]), sorted(registry_ids))
        self.assertEqual(sorted(registry_ids), sorted(REGISTERED_BACKEND_IDS))

    def test_a_manifest_cannot_name_a_backend_outside_the_registry(self):
        self.assertRejected(valid_manifest(
            privacy_class="INTERNAL", primary_backend="some_random_untrusted_host"))

    def test_a_replica_cannot_name_a_backend_outside_the_registry(self):
        self.assertRejected(valid_manifest(
            replica_backends=["some_random_untrusted_host"]))

    def test_internal_on_an_unadmitted_registry_row_is_rejected_by_the_validator(self):
        """The case the reviewer reproduced: INTERNAL + a QUARANTINED row."""
        from AI_SKILL_LIBRARY.v4.storage import mesh_validator

        problems = mesh_validator.validate_manifest_placement(
            valid_manifest(privacy_class="INTERNAL", primary_backend="cloudflare_r2"))
        self.assertTrue(problems)

    def test_public_on_an_unadmitted_registry_row_is_rejected_by_the_validator(self):
        from AI_SKILL_LIBRARY.v4.storage import mesh_validator

        problems = mesh_validator.validate_manifest_placement(
            valid_manifest(privacy_class="PUBLIC", primary_backend="backblaze_b2"))
        self.assertTrue(problems)

    def test_the_validator_rejects_an_unresolvable_backend_id(self):
        from AI_SKILL_LIBRARY.v4.storage import mesh_validator

        problems = mesh_validator.validate_manifest_placement(
            valid_manifest(primary_backend="some_random_untrusted_host"),
            providers=admitted_registry())
        self.assertTrue(any("registry" in p for p in problems))

    def test_the_validator_rejects_an_unresolvable_replica(self):
        from AI_SKILL_LIBRARY.v4.storage import mesh_validator

        problems = mesh_validator.validate_manifest_placement(
            valid_manifest(replica_backends=["some_random_untrusted_host"]),
            providers=admitted_registry())
        self.assertTrue(any("registry" in p for p in problems))

    def test_a_backend_that_does_not_admit_the_privacy_class_is_rejected(self):
        from AI_SKILL_LIBRARY.v4.storage import mesh_validator

        problems = mesh_validator.validate_manifest_placement(
            valid_manifest(privacy_class="CONFIDENTIAL",
                           encryption_state="CLIENT_SIDE_ENCRYPTED",
                           encryption={
                               "algorithm": "aes-256-gcm",
                               "scheme_version": 1,
                               "key_ref": "secretstore://brain/storage-mesh/dek",
                           }),
            providers=admitted_registry())
        self.assertTrue(any("privacy" in p for p in problems))

    def test_a_backend_that_does_not_serve_the_tier_is_rejected(self):
        from AI_SKILL_LIBRARY.v4.storage import mesh_validator

        problems = mesh_validator.validate_manifest_placement(
            valid_manifest(storage_tier="HOT"), providers=admitted_registry())
        self.assertTrue(any("tier" in p for p in problems))

    def test_a_realistic_manifest_on_an_admitted_backend_is_accepted(self):
        """The other direction: the gate must not be a wall."""
        from AI_SKILL_LIBRARY.v4.storage import mesh_validator

        self.assertEqual(
            mesh_validator.validate_manifest_placement(
                valid_manifest(), providers=admitted_registry()),
            [])


class TierSizeAndMetadataConfinementTests(unittest.TestCase):
    """BLOCKER 2: bulk/tier rules belong in the manifest, not only in prose."""

    def setUp(self):
        self.manifest = Draft202012Validator(load_json(MANIFEST_SCHEMA_PATH))
        self.provider = Draft202012Validator(load_json(PROVIDER_SCHEMA_PATH))

    def assertManifestRejected(self, doc):
        self.assertTrue(list(self.manifest.iter_errors(doc)))

    def assertManifestAccepted(self, doc):
        self.assertEqual([e.message for e in self.manifest.iter_errors(doc)], [])

    def test_canonical_tier_cannot_carry_bulk_object_data(self):
        self.assertManifestRejected(valid_manifest(
            storage_tier="CANONICAL", size_bytes=1099511627776))

    def test_metadata_tier_cannot_carry_bulk_object_data(self):
        self.assertManifestRejected(valid_manifest(
            storage_tier="METADATA", primary_backend="supabase",
            size_bytes=1099511627776))

    def test_supabase_as_primary_cannot_hold_a_hot_hundred_gigabyte_object(self):
        self.assertManifestRejected(valid_manifest(
            primary_backend="supabase", storage_tier="HOT",
            size_bytes=100000000000))

    def test_supabase_as_a_replica_on_a_cold_object_is_rejected(self):
        self.assertManifestRejected(valid_manifest(
            storage_tier="COLD", replica_backends=["supabase"]))

    def test_a_bounded_metadata_object_on_supabase_is_still_accepted(self):
        self.assertManifestAccepted(valid_manifest(
            primary_backend="supabase", storage_tier="METADATA", size_bytes=4096))

    def test_a_normal_bulk_object_on_a_bulk_backend_is_still_accepted(self):
        self.assertManifestAccepted(valid_manifest(
            storage_tier="WARM", primary_backend="backblaze_b2",
            size_bytes=5368709120))

    def test_supabase_cannot_relabel_its_adapter_type_to_escape_confinement(self):
        """The reviewer's opt-in label: identity must pin the adapter."""
        self.assertTrue(list(self.provider.iter_errors(valid_provider(
            provider_id="supabase",
            adapter_type="s3_compatible",
            bulk_object_backend_allowed=True,
            tiers_allowed=["HOT"]))))

    def test_the_validator_refuses_bulk_bytes_on_a_metadata_role_backend(self):
        from AI_SKILL_LIBRARY.v4.storage import mesh_validator

        metadata_row = admitted_provider(
            provider_id="supabase", adapter_type="supabase_metadata",
            bulk_object_backend_allowed=False, tiers_allowed=["METADATA"],
            preferred_tiers=["METADATA"], object_size_limits={"max_object_bytes": None})
        problems = mesh_validator.validate_manifest_placement(
            valid_manifest(primary_backend="supabase", storage_tier="METADATA",
                           size_bytes=100000000000),
            providers=[metadata_row])
        self.assertTrue(any("bulk" in p for p in problems))


class ProviderWriteAdmissionTests(unittest.TestCase):
    """BLOCKER 3: a provider may not be writable with unknowable capacity."""

    def setUp(self):
        self.validator = Draft202012Validator(load_json(PROVIDER_SCHEMA_PATH))

    def assertRejected(self, doc):
        self.assertTrue(list(self.validator.iter_errors(doc)))

    def assertAccepted(self, doc):
        self.assertEqual([e.message for e in self.validator.iter_errors(doc)], [])

    def test_an_unknowable_quota_blocks_autonomous_writes(self):
        self.assertRejected(admitted_provider(quota_total=None, quota_used=None))

    def test_an_autonomous_writer_must_also_be_write_enabled(self):
        self.assertRejected(admitted_provider(write_enabled=False))

    def test_a_quarantined_row_cannot_be_write_enabled(self):
        self.assertRejected(valid_provider(write_enabled=True))

    def test_a_non_writable_health_state_blocks_writes(self):
        for state in ("NEAR_FULL", "READ_ONLY", "OFFLINE"):
            with self.subTest(health=state):
                self.assertRejected(admitted_provider(health=state))

    def test_a_writable_health_state_is_still_accepted(self):
        for state in ("FREE", "HEALTHY", "PRESSURED"):
            with self.subTest(health=state):
                self.assertAccepted(admitted_provider(health=state))

    def test_quota_used_cannot_exceed_quota_total(self):
        from AI_SKILL_LIBRARY.v4.storage import mesh_validator

        problems = mesh_validator.validate_provider_row(
            admitted_provider(quota_total=100, quota_used=999999))
        self.assertTrue(any("quota" in p for p in problems))

    def test_a_free_tier_that_already_expired_blocks_writes(self):
        from AI_SKILL_LIBRARY.v4.storage import mesh_validator

        problems = mesh_validator.validate_provider_row(
            admitted_provider(free_status="VERIFIED_FREE",
                              free_expiry_at="2026-01-01T00:00:00Z"),
            now="2026-09-18T00:00:00Z")
        self.assertTrue(any("expir" in p for p in problems))

    def test_a_free_tier_that_has_not_expired_still_permits_writes(self):
        from AI_SKILL_LIBRARY.v4.storage import mesh_validator

        self.assertEqual(
            mesh_validator.validate_provider_row(
                admitted_provider(free_status="VERIFIED_FREE",
                                  free_expiry_at="2027-01-01T00:00:00Z"),
                now="2026-09-18T00:00:00Z"),
            [])

    def test_an_admitted_provider_row_passes_both_schema_and_validator(self):
        from AI_SKILL_LIBRARY.v4.storage import mesh_validator

        row = admitted_provider()
        self.assertAccepted(row)
        self.assertEqual(mesh_validator.validate_provider_row(
            row, now="2026-09-18T00:00:00Z"), [])

    def test_the_validator_agrees_with_the_shipped_registry(self):
        """Every shipped row must be internally coherent, quarantined or not."""
        from AI_SKILL_LIBRARY.v4.storage import mesh_validator

        offenders = []
        for row in load_yaml(PROVIDERS_PATH)["providers"]:
            for problem in mesh_validator.validate_provider_row(row):
                offenders.append(f"{row['provider_id']}: {problem}")
        self.assertEqual(offenders, [])


class MeshValidatorIsPureTests(unittest.TestCase):
    """A read-only validator that could write is not a read-only validator."""

    def test_the_validator_module_performs_no_write_or_network_call(self):
        import ast

        source = (STORAGE / "mesh_validator.py").read_text(encoding="utf-8")
        forbidden = {
            "open", "write_text", "write_bytes", "mkdir", "unlink", "rmtree",
            "urlopen", "request", "post", "put", "system", "popen", "run",
        }
        offenders = []
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name in forbidden:
                offenders.append(name)
        self.assertEqual(offenders, [])

    def test_the_validator_declares_no_authority(self):
        from AI_SKILL_LIBRARY.v4.storage import mesh_validator

        self.assertIs(mesh_validator.AUTHORITY, False)


# ---------------------------------------------------------------------------
# Classifier and evidence fields (independent review: SHOULD-FIX 4 and 5).
#
# Every classifier in both schemas was a class_token: lower-case, punctuation-
# limited, maxLength 64. That is exactly the shape of a 64-character hex private
# key, and encryption.algorithm - the sharpest case, because it sits inside the
# encryption block next to key_ref - was one of them. evidence_ref meanwhile
# admitted 222 characters including ? # & = % @, which is the shape of a
# presigned URL or a token callback rather than the shape of a pointer into the
# evidence path.
# ---------------------------------------------------------------------------

#: A 64-character lower-case hex string: the shape of a raw private key, and
#: the exact value the reviewer got accepted as an object_class. It is not a
#: key, it is a shape - no key material belongs in a test file either.
RAW_HEX_SHAPED_TOKEN = "4c0883a69f1b4e4c8f8d5a6e2c9b7d1f3a0e6c4b8d2f7a1e9c3b5d0f8a2e6c1b"

#: A presigned-URL shape and a token-callback shape. Again shapes, not secrets.
PRESIGNED_URL_SHAPE = (
    "https://bucket.example.invalid/o?X-Amz-Credential=EXAMPLE%2F20260918"
    "&X-Amz-Signature=0123456789abcdef"
)
TOKEN_CALLBACK_SHAPE = "https://example.invalid/cb?token=ghp_" + "a" * 36


def credential_shaped_values(document, trail="$"):
    """Run the credential patterns over a *document*, not only over a file.

    The suite's credential scan only ever read the five static contract files.
    A manifest or provider row that a validator has just accepted is the place a
    token would actually arrive, and nothing was looking there.
    """
    found = []
    if isinstance(document, dict):
        for key, value in document.items():
            found.extend(credential_shaped_values(value, f"{trail}.{key}"))
    elif isinstance(document, (list, tuple)):
        for index, value in enumerate(document):
            found.extend(credential_shaped_values(value, f"{trail}[{index}]"))
    elif isinstance(document, str):
        for label, pattern in CREDENTIAL_PATTERNS:
            if pattern.search(document):
                found.append(f"{trail}: {label}")
    return found


class ClassifierFieldsCannotHoldKeyMaterialTests(unittest.TestCase):
    """SHOULD-FIX 5: a classifier that fits a private key is a key slot."""

    def setUp(self):
        self.manifest_schema = load_json(MANIFEST_SCHEMA_PATH)
        self.provider_schema = load_json(PROVIDER_SCHEMA_PATH)
        self.manifest = Draft202012Validator(self.manifest_schema)
        self.provider = Draft202012Validator(self.provider_schema)

    def assertManifestRejected(self, doc):
        self.assertTrue(list(self.manifest.iter_errors(doc)))

    def assertManifestAccepted(self, doc):
        self.assertEqual([e.message for e in self.manifest.iter_errors(doc)], [])

    def assertProviderRejected(self, doc):
        self.assertTrue(list(self.provider.iter_errors(doc)))

    def assertProviderAccepted(self, doc):
        self.assertEqual([e.message for e in self.provider.iter_errors(doc)], [])

    def test_manifest_classifiers_reject_a_raw_hex_key_shape(self):
        for field in ("object_class", "retention_class"):
            with self.subTest(field=field):
                self.assertManifestRejected(
                    valid_manifest(**{field: RAW_HEX_SHAPED_TOKEN}))

    def test_provenance_classifiers_reject_a_raw_hex_key_shape(self):
        for field in ("origin_class", "producer_id"):
            with self.subTest(field=field):
                self.assertManifestRejected(valid_manifest(
                    source_provenance={"origin_class": "benchmark-bundle",
                                       **{field: RAW_HEX_SHAPED_TOKEN}}))

    def test_the_encryption_algorithm_is_a_closed_vocabulary(self):
        algorithm = self.manifest_schema["$defs"]["encryption_metadata"]["properties"]["algorithm"]
        self.assertIn("enum", algorithm,
                      "algorithm sits next to key_ref; it must not be free-form")
        self.assertNotIn("$ref", algorithm)

    def test_the_algorithm_vocabulary_is_the_one_the_policy_names(self):
        """A vocabulary the schema invents privately is not a controlled one."""
        algorithm = self.manifest_schema["$defs"]["encryption_metadata"]["properties"]["algorithm"]
        policy = load_yaml(POLICY_PATH)
        self.assertEqual(sorted(algorithm["enum"]),
                         sorted(policy["encryption"]["allowed_algorithms"]))

    def test_the_encryption_algorithm_cannot_hold_a_raw_hex_key_shape(self):
        self.assertManifestRejected(valid_manifest(
            privacy_class="CONFIDENTIAL",
            primary_backend="backblaze_b2",
            encryption_state="CLIENT_SIDE_ENCRYPTED",
            encryption={
                "algorithm": RAW_HEX_SHAPED_TOKEN,
                "scheme_version": 1,
                "key_ref": "secretstore://brain/storage-mesh/dek-2026-09",
            }))

    def test_provider_classifiers_reject_a_raw_hex_key_shape(self):
        for field in ("retention_policy_class", "quota_reset_semantics"):
            with self.subTest(field=field):
                self.assertProviderRejected(
                    valid_provider(**{field: RAW_HEX_SHAPED_TOKEN}))
        self.assertProviderRejected(valid_provider(free_status_evidence={
            "evidence_class": "none", "observed_by": RAW_HEX_SHAPED_TOKEN}))

    def test_acceptable_use_class_is_a_closed_vocabulary(self):
        field = self.provider_schema["properties"]["acceptable_use_class"]
        self.assertIn("enum", field)
        policy = load_yaml(POLICY_PATH)
        self.assertEqual(sorted(field["enum"]),
                         sorted(policy["provider_roles"]["acceptable_use_classes"]))

    def test_there_is_no_free_note_field_on_a_provider_row(self):
        """A 'notes' field in a lane whose thesis is 'no free text'."""
        self.assertNotIn("notes_class", self.provider_schema["properties"])

    def test_no_classifier_can_hold_a_base64_or_hex_shaped_key(self):
        token = self.manifest_schema["$defs"]["class_token"]
        self.assertLessEqual(
            token["maxLength"], 43,
            "44 characters is base64 of a 256-bit key; 64 is its hex form")

    def test_real_classifier_values_still_validate(self):
        """The other direction: these fields must still hold real classifiers."""
        self.assertManifestAccepted(valid_manifest(
            object_class="benchmark-bundle",
            retention_class="standard-90d",
            source_provenance={"origin_class": "evidence.compacted",
                               "producer_id": "brain-v4-compactor",
                               "evidence_ref": "CHECKPOINTS/evidence/storage.json"}))
        for row in load_yaml(PROVIDERS_PATH)["providers"]:
            with self.subTest(provider=row["provider_id"]):
                self.assertProviderAccepted(row)

    def test_every_allowed_algorithm_still_validates_in_a_manifest(self):
        for algorithm in load_yaml(POLICY_PATH)["encryption"]["allowed_algorithms"]:
            with self.subTest(algorithm=algorithm):
                self.assertManifestAccepted(valid_manifest(
                    privacy_class="CONFIDENTIAL",
                    primary_backend="backblaze_b2",
                    encryption_state="CLIENT_SIDE_ENCRYPTED",
                    encryption={
                        "algorithm": algorithm,
                        "scheme_version": 1,
                        "key_ref": "secretstore://brain/storage-mesh/dek-2026-09",
                        "nonce": "PDcgVqXQ0m7hRk9s",
                        "tag": "9a2f1c0bd4e7a6538f10c2bb",
                    }))


class EvidenceRefIsAPointerNotAUrlWithCredentialsTests(unittest.TestCase):
    """SHOULD-FIX 4: 222 characters including ? # & = % @ is a presigned URL."""

    def setUp(self):
        self.manifest = Draft202012Validator(load_json(MANIFEST_SCHEMA_PATH))
        self.provider = Draft202012Validator(load_json(PROVIDER_SCHEMA_PATH))

    def test_a_presigned_url_is_not_an_evidence_reference(self):
        self.assertTrue(list(self.manifest.iter_errors(valid_manifest(
            source_provenance={"origin_class": "replay",
                               "evidence_ref": PRESIGNED_URL_SHAPE}))))

    def test_a_token_callback_is_not_an_evidence_reference(self):
        self.assertTrue(list(self.manifest.iter_errors(valid_manifest(
            verification={"hash_verified": True,
                          "evidence_ref": TOKEN_CALLBACK_SHAPE}))))

    def test_a_provider_evidence_reference_rejects_the_same_shapes(self):
        for shape in (PRESIGNED_URL_SHAPE, TOKEN_CALLBACK_SHAPE):
            with self.subTest(shape=shape[:32]):
                self.assertTrue(list(self.provider.iter_errors(valid_provider(
                    free_status_evidence={"evidence_class": "none",
                                          "evidence_ref": shape}))))

    def test_a_basic_auth_url_is_not_an_evidence_reference(self):
        self.assertTrue(list(self.manifest.iter_errors(valid_manifest(
            source_provenance={"origin_class": "replay",
                               "evidence_ref": "https://u:p@example.invalid/x.json"}))))

    def test_real_evidence_references_still_validate(self):
        for reference in (
            "CHECKPOINTS/evidence/storage_b2_quota.json",
            "AI_SKILL_LIBRARY/v4/storage/policy.yaml",
            "https://example.invalid/evidence/storage-probe.json",
            "git+https://example.invalid/repo/evidence.json",
        ):
            with self.subTest(reference=reference):
                self.assertEqual(
                    [e.message for e in self.manifest.iter_errors(valid_manifest(
                        source_provenance={"origin_class": "replay",
                                           "evidence_ref": reference}))],
                    [])


class CredentialScanReachesValidatedDocumentsTests(unittest.TestCase):
    """SHOULD-FIX 4, second half: the scan only ever read five static files."""

    def test_the_document_scan_catches_a_token_a_file_scan_would_miss(self):
        """A regression that can never fire is not a regression."""
        self.assertTrue(credential_shaped_values(
            {"source_provenance": {"evidence_ref": TOKEN_CALLBACK_SHAPE}}))
        self.assertTrue(credential_shaped_values({"x": "AKIAIOSFODNN7EXAMPLE"}))

    def test_a_manifest_the_schema_accepts_is_also_credential_clean(self):
        validator = Draft202012Validator(load_json(MANIFEST_SCHEMA_PATH))
        documents = [
            valid_manifest(),
            valid_manifest(primary_backend="supabase", storage_tier="METADATA"),
            valid_manifest(privacy_class="LOCAL_ONLY", storage_tier="HOT",
                           primary_backend="local_owned_store"),
            valid_manifest(privacy_class="CONFIDENTIAL",
                           primary_backend="backblaze_b2",
                           encryption_state="CLIENT_SIDE_ENCRYPTED",
                           encryption={
                               "algorithm": "aes-256-gcm",
                               "scheme_version": 1,
                               "key_ref": "secretstore://brain/storage-mesh/dek",
                           }),
        ]
        for document in documents:
            with self.subTest(backend=document["primary_backend"]):
                self.assertEqual(
                    [e.message for e in validator.iter_errors(document)], [])
                self.assertEqual(credential_shaped_values(document), [])

    def test_every_registry_row_is_scanned_as_a_document(self):
        offenders = []
        for row in load_yaml(PROVIDERS_PATH)["providers"]:
            offenders.extend(
                f"{row['provider_id']}: {hit}" for hit in credential_shaped_values(row))
        self.assertEqual(offenders, [])

    def test_the_whole_policy_document_is_scanned_as_a_document(self):
        self.assertEqual(credential_shaped_values(load_yaml(POLICY_PATH)), [])


# ---------------------------------------------------------------------------
# Reachability, surviving mutants and portability
# (independent review: SHOULD-FIX 6 and 7, NIT 9 and 10).
#
# A guard that inspects $defs proves a definition exists, not that anything
# reaches it. authority and authority_flags were required in the manifest and
# optional in the provider record, so every shipped registry row carried no
# authority_flags at all and the guard passed anyway.
# ---------------------------------------------------------------------------


class AuthorityIsReachableNotMerelyDefinedTests(unittest.TestCase):
    """SHOULD-FIX 6: the guard read $defs and never asked who reaches it."""

    def setUp(self):
        self.schemas = {
            "manifest": load_json(MANIFEST_SCHEMA_PATH),
            "provider": load_json(PROVIDER_SCHEMA_PATH),
        }

    def test_both_schemas_require_authority_and_authority_flags(self):
        for name, schema in self.schemas.items():
            with self.subTest(schema=name):
                self.assertIn("authority", schema["required"])
                self.assertIn("authority_flags", schema["required"])

    def test_the_authority_defs_are_actually_referenced_by_a_property(self):
        """Reachability, not existence: a $def nothing points at is decoration."""
        for name, schema in self.schemas.items():
            with self.subTest(schema=name):
                self.assertEqual(schema["properties"]["authority_flags"],
                                 {"$ref": "#/$defs/authority_flags"})

    def test_a_provider_row_without_authority_flags_is_rejected(self):
        validator = Draft202012Validator(load_json(PROVIDER_SCHEMA_PATH))
        row = valid_provider()
        row.pop("authority_flags", None)
        row.pop("authority", None)
        self.assertTrue(list(validator.iter_errors(row)))

    def test_a_provider_row_cannot_assert_an_authority(self):
        validator = Draft202012Validator(load_json(PROVIDER_SCHEMA_PATH))
        self.assertTrue(list(validator.iter_errors(valid_provider(authority=True))))
        self.assertTrue(list(validator.iter_errors(valid_provider(
            authority_flags={**{f: False for f in AUTHORITY_FLAGS},
                             "admission_authority": True}))))

    def test_every_shipped_registry_row_denies_every_authority_by_name(self):
        for row in load_yaml(PROVIDERS_PATH)["providers"]:
            with self.subTest(provider=row["provider_id"]):
                self.assertIs(row["authority"], False)
                self.assertEqual(sorted(row["authority_flags"]), sorted(AUTHORITY_FLAGS))
                for flag in AUTHORITY_FLAGS:
                    self.assertIs(row["authority_flags"][flag], False, flag)


class SurvivingMutantTests(unittest.TestCase):
    """SHOULD-FIX 7: two mutants the suite did not kill."""

    def test_no_quota_number_is_invented_on_any_row_including_local(self):
        """The original test skipped non-external rows, so the mutant lived."""
        for row in load_yaml(PROVIDERS_PATH)["providers"]:
            with self.subTest(provider=row["provider_id"]):
                self.assertIsNone(row["quota_total"])
                self.assertIsNone(row["quota_used"])
                self.assertIsNone(row.get("quota_reserved"))

    def test_no_registry_row_claims_health_it_has_not_probed(self):
        for row in load_yaml(PROVIDERS_PATH)["providers"]:
            with self.subTest(provider=row["provider_id"]):
                if row.get("last_probe_at") is None:
                    self.assertEqual(row["health"], "QUARANTINED")

    def test_no_registry_row_is_writable_while_nothing_is_verified(self):
        for row in load_yaml(PROVIDERS_PATH)["providers"]:
            with self.subTest(provider=row["provider_id"]):
                self.assertIs(row["autonomous_write_allowed"], False)
                self.assertIs(row["write_enabled"], False)

    def test_every_acceptable_use_class_is_one_the_policy_names(self):
        allowed = load_yaml(POLICY_PATH)["provider_roles"]["acceptable_use_classes"]
        for row in load_yaml(PROVIDERS_PATH)["providers"]:
            with self.subTest(provider=row["provider_id"]):
                self.assertIn(row["acceptable_use_class"], allowed)


class PortableRegexTests(unittest.TestCase):
    """NIT 9: a load-bearing rule should not rest on a lookahead."""

    def test_no_schema_pattern_uses_a_lookahead_or_lookbehind(self):
        offenders = []
        for name, path in (("manifest", MANIFEST_SCHEMA_PATH),
                           ("provider", PROVIDER_SCHEMA_PATH)):
            for trail, node in walk_subschemas(load_json(path)):
                pattern = node.get("pattern")
                if isinstance(pattern, str) and ("(?=" in pattern or "(?!" in pattern
                                                 or "(?<" in pattern):
                    offenders.append(f"{name}{trail}: {pattern}")
        self.assertEqual(offenders, [])

    def test_the_reserved_local_namespace_is_still_enforced(self):
        """Removing the lookahead must not remove the rule it carried."""
        validator = Draft202012Validator(load_json(PROVIDER_SCHEMA_PATH))
        self.assertTrue(list(validator.iter_errors(valid_provider(
            provider_id="local_r2", adapter_type="s3_compatible"))))
        self.assertEqual(
            [e.message for e in validator.iter_errors(valid_provider(
                provider_id="cloudflare_r2"))], [])


class EncryptionStateAndMetadataAgreeTests(unittest.TestCase):
    """NIT 10: a flag and its evidence must not be able to contradict."""

    def setUp(self):
        self.validator = Draft202012Validator(load_json(MANIFEST_SCHEMA_PATH))

    def assertRejected(self, doc):
        self.assertTrue(list(self.validator.iter_errors(doc)))

    def assertAccepted(self, doc):
        self.assertEqual([e.message for e in self.validator.iter_errors(doc)], [])

    def test_encryption_state_none_cannot_carry_an_encryption_block(self):
        self.assertRejected(valid_manifest(
            encryption_state="NONE",
            encryption={
                "algorithm": "aes-256-gcm",
                "scheme_version": 1,
                "key_ref": "secretstore://brain/storage-mesh/dek",
            }))

    def test_client_side_encrypted_without_a_block_is_rejected_for_any_class(self):
        for privacy_class in ("PUBLIC", "INTERNAL"):
            with self.subTest(privacy_class=privacy_class):
                self.assertRejected(valid_manifest(
                    privacy_class=privacy_class,
                    encryption_state="CLIENT_SIDE_ENCRYPTED"))

    def test_a_consistent_encrypted_internal_object_is_still_accepted(self):
        self.assertAccepted(valid_manifest(
            privacy_class="INTERNAL",
            encryption_state="CLIENT_SIDE_ENCRYPTED",
            encryption_scheme_version=1,
            encryption={
                "algorithm": "chacha20-poly1305",
                "scheme_version": 1,
                "key_ref": "worker-secret://brain/storage-mesh/dek-2026-09",
                "nonce": "PDcgVqXQ0m7hRk9s",
                "tag": "9a2f1c0bd4e7a6538f10c2bb",
            }))

    def test_a_consistent_unencrypted_object_is_still_accepted(self):
        self.assertAccepted(valid_manifest(encryption_state="NONE"))


class SchemaGreenIsNotPlacementGreenTests(unittest.TestCase):
    """The two halves are a split, not a gap - so it is asserted, not implied.

    INTERNAL on cloudflare_r2 is the reviewer's case, and the schema still
    accepts it: cloudflare_r2 *is* a registry row, and whether that row has been
    admitted is runtime state a JSON Schema cannot read. Leaving that as a quiet
    asymmetry is how the next author concludes that schema-green means safe to
    place, so the asymmetry is written down as a test with both halves in it.
    """

    def test_a_registered_but_unadmitted_backend_passes_the_schema_and_fails_placement(self):
        from AI_SKILL_LIBRARY.v4.storage import mesh_validator

        validator = Draft202012Validator(load_json(MANIFEST_SCHEMA_PATH))
        document = valid_manifest(privacy_class="INTERNAL",
                                  primary_backend="cloudflare_r2")
        self.assertEqual([e.message for e in validator.iter_errors(document)], [],
                         "identity resolves: cloudflare_r2 is a registry row")
        self.assertTrue(mesh_validator.validate_manifest_placement(document),
                        "admission does not: the row is UNVERIFIED/QUARANTINED")

    def test_both_schemas_say_that_passing_them_is_not_admission(self):
        for name, path in (("manifest", MANIFEST_SCHEMA_PATH),
                           ("provider", PROVIDER_SCHEMA_PATH)):
            with self.subTest(schema=name):
                self.assertIn("mesh_validator.py", load_json(path)["description"])

    def test_the_policy_names_the_resolver_and_denies_it_authority(self):
        identity = load_yaml(POLICY_PATH)["backend_identity"]
        self.assertIs(identity["manifest_backend_must_resolve_to_registry_row"], True)
        self.assertEqual(identity["resolver"],
                         "AI_SKILL_LIBRARY/v4/storage/mesh_validator.py")
        self.assertIs(identity["resolver_authority"], False)
        self.assertIs(identity["resolver_is_read_only"], True)
        self.assertEqual(identity["unresolvable_backend"], "REJECT")
        self.assertEqual(identity["unadmitted_backend"], "REJECT")

    def test_nothing_in_the_shipped_registry_is_placeable_today(self):
        """Honest end state of Task 1: contracts exist, nothing is activated."""
        from AI_SKILL_LIBRARY.v4.storage import mesh_validator

        for backend in REGISTERED_BACKEND_IDS:
            with self.subTest(backend=backend):
                self.assertTrue(mesh_validator.validate_manifest_placement(
                    valid_manifest(primary_backend=backend)))


if __name__ == "__main__":
    unittest.main()
