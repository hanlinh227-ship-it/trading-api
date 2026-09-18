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
            autonomous_write_allowed=True))

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
                PROVIDER_SCHEMA_PATH, STORAGE / "__init__.py"]

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


if __name__ == "__main__":
    unittest.main()
