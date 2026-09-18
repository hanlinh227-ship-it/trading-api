"""Provider registry tests for the Federated Free Storage Mesh (Task 8).

``test_storage_mesh_contracts.py`` polices the *shape* of the two schemas and
the honesty of the registry as a whole. This file is about the eight rows Task 8
names - R2, B2, Oracle, Hugging Face, Drive, OneDrive, Dropbox and the Supabase
metadata service - and about the one mistake that would make the mesh expensive
rather than merely wrong.

**Unknown quota is not an entitlement.** The plan states the rule as
``free_quota.verified is False`` implies ``autonomous_write_allowed is False``.
The checked-in record has no ``free_quota`` object - the provider schema closes
its field set and spells the same facts as ``free_status``,
``free_status_evidence.evidence_class``, ``quota_total``, ``quota_used`` and
``hard_stop_verified`` - so :func:`free_quota` derives that view from the fields
that exist rather than a field being invented here to make an assertion pass.
Every row is tested, twice: once as shipped, and once mutated to claim the
entitlement, because "the file happens to say false today" is a fact about the
file and not a control. The mutation has to be refused by the schema on disk.

**Documentation evidence is not account evidence.** A provider's pricing page is
a claim about a product; the mesh needs a fact about this account. So no quota
number is copied out of a vendor page into ``quota_total``, and the registry is
asserted to carry no ``runtime_account_evidence`` at all - nobody has probed
these accounts, and a row saying otherwise would be fabricated runtime state.

**Roles are the spec's roles.** Hugging Face is AI artifacts (Spec S17), Drive,
OneDrive and Dropbox are human backup surfaces and never canonical runtime
object stores (Spec S6 tiers, ``policy.yaml`` ``tiers.HUMAN_BACKUP``), Supabase
is the metadata index. Those are checked against the adapter modules' own
declared constants, so a registry row and the adapter that would drive it cannot
drift apart.

**The bound check is driven from the schema on disk.** Every field of every
shipped row is resolved to its subschema and a string field with no ``pattern``
plus ``maxLength`` (or no closed vocabulary) is a finding - so a property added
to the contract later without a bound fails here the day it is added rather than
the day somebody stores a token in it.

Nothing here opens a connection, creates an account, a bucket, a project or a
folder, or reads a credential. It reads two checked-in documents.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from AI_SKILL_LIBRARY.v4.storage import AUTHORITY_FLAGS
from AI_SKILL_LIBRARY.v4.storage import mesh_validator
from AI_SKILL_LIBRARY.v4.storage.adapters import human_backup, huggingface_artifact
from AI_SKILL_LIBRARY.v4.storage.adapters import s3_object, supabase_metadata

ROOT = Path(__file__).resolve().parents[2]
STORAGE = ROOT / "AI_SKILL_LIBRARY/v4/storage"
PROVIDERS_PATH = STORAGE / "providers.yaml"
PROVIDER_SCHEMA_PATH = ROOT / "AI_SKILL_LIBRARY/v4/schemas/storage_provider.schema.json"

#: The two ``free_status`` values only runtime account evidence can produce.
VERIFIED_FREE_STATUSES = mesh_validator.VERIFIED_FREE_STATUSES

#: The eight backends Task 8 registers, with the role Spec S17 gives each one.
#: ``supabase_metadata`` is the adapter type rather than a second provider id:
#: ``storage_object_manifest.schema.json`` pins the metadata service to the
#: identity ``supabase`` and confines anything naming it to the METADATA tier, so
#: renaming the row would move the confinement off the identity the manifest
#: side keys on. The row is therefore asserted by adapter type below, which is
#: the thing an adapter actually resolves.
EXPECTED_ROLES = {
    "cloudflare_r2": {
        "adapter_type": "s3_compatible",
        "tiers_allowed": ["HOT", "WARM"],
        "preferred_tiers": ["HOT"],
        "acceptable_use_class": "object-storage",
        "bulk_object_backend_allowed": True,
    },
    "backblaze_b2": {
        "adapter_type": "s3_compatible",
        "tiers_allowed": ["WARM", "COLD"],
        "preferred_tiers": ["WARM", "COLD"],
        "acceptable_use_class": "object-storage",
        "bulk_object_backend_allowed": True,
    },
    "oracle_object_storage": {
        "adapter_type": "s3_compatible",
        "tiers_allowed": ["WARM", "COLD"],
        "preferred_tiers": ["WARM", "COLD"],
        "acceptable_use_class": "object-storage",
        "bulk_object_backend_allowed": True,
    },
    "huggingface_hub": {
        "adapter_type": "huggingface_hub",
        "tiers_allowed": ["COLD"],
        "preferred_tiers": ["COLD"],
        "acceptable_use_class": "ai-artifacts-only",
        "bulk_object_backend_allowed": True,
    },
    "google_drive": {
        "adapter_type": "google_drive_api",
        "tiers_allowed": ["HUMAN_BACKUP"],
        "preferred_tiers": ["HUMAN_BACKUP"],
        "acceptable_use_class": "human-backup-only",
        "bulk_object_backend_allowed": True,
    },
    "onedrive": {
        "adapter_type": "microsoft_graph_api",
        "tiers_allowed": ["HUMAN_BACKUP"],
        "preferred_tiers": ["HUMAN_BACKUP"],
        "acceptable_use_class": "human-backup-only",
        "bulk_object_backend_allowed": True,
    },
    "dropbox": {
        "adapter_type": "dropbox_api",
        "tiers_allowed": ["HUMAN_BACKUP"],
        "preferred_tiers": ["HUMAN_BACKUP"],
        "acceptable_use_class": "human-backup-only",
        "bulk_object_backend_allowed": True,
    },
    "supabase": {
        "adapter_type": "supabase_metadata",
        "tiers_allowed": ["METADATA"],
        "preferred_tiers": ["METADATA"],
        "acceptable_use_class": "metadata-index-only",
        "bulk_object_backend_allowed": False,
    },
}

#: Marketing figures from the three object-storage vendors' public free-tier
#: pages, as bytes. They appear here *only* so that the registry can be checked
#: not to contain them: a number from a web page is documentation evidence, and
#: writing it into quota_total would turn a claim about a product into a
#: statement about this account.
MARKETING_QUOTA_BYTES = {
    "cloudflare_r2 10 GB": 10 * 1000 ** 3,
    "cloudflare_r2 10 GiB": 10 * 1024 ** 3,
    "backblaze_b2 10 GB": 10 * 1000 ** 3,
    "oracle 20 GB": 20 * 1000 ** 3,
    "oracle 20 GiB": 20 * 1024 ** 3,
    "google_drive 15 GB": 15 * 1000 ** 3,
    "google_drive 15 GiB": 15 * 1024 ** 3,
    "onedrive 5 GB": 5 * 1000 ** 3,
    "dropbox 2 GB": 2 * 1000 ** 3,
    "supabase 500 MB": 500 * 1000 ** 2,
    "huggingface 1 TB": 1000 ** 4,
}


def load_registry():
    return yaml.safe_load(PROVIDERS_PATH.read_text(encoding="utf-8"))


def load_providers():
    return list(load_registry()["providers"])


def free_quota(row):
    """The ``free_quota`` view the plan names, derived from the fields on disk.

    ``verified`` is true only when every part of "this account has a free
    allowance and we have seen it" is answered by runtime account evidence: a
    VERIFIED_* status, produced by ``runtime_account_evidence`` rather than a
    vendor page, with a ceiling and a current consumption that were actually
    read, and an observed hard stop. Any missing part leaves it unknown, and
    unknown is the state this whole file exists to keep away from a write.
    """
    evidence = row.get("free_status_evidence") or {}
    total = row.get("quota_total")
    used = row.get("quota_used")
    verified = (
        row.get("free_status") in VERIFIED_FREE_STATUSES
        and evidence.get("evidence_class") == "runtime_account_evidence"
        and isinstance(total, int) and not isinstance(total, bool)
        and isinstance(used, int) and not isinstance(used, bool)
        and row.get("hard_stop_verified") is True
    )
    return {"verified": verified, "total": total, "used": used,
            "evidence_class": evidence.get("evidence_class")}


def resolve(schema, node):
    """Follow a local ``$ref`` one hop, which is all this schema ever uses."""
    ref = node.get("$ref") if isinstance(node, dict) else None
    if not ref:
        return node
    assert ref.startswith("#/$defs/"), ref
    return schema["$defs"][ref.split("/")[-1]]


def string_is_bounded(subschema):
    """A string slot is bounded when it cannot hold something it should not.

    Either a closed vocabulary - an ``enum`` or a ``const``, where the accepted
    values are written out - or a ``pattern`` *and* a ``maxLength``. A pattern
    with no length bound still admits a megabyte of matching text, and a length
    bound with no pattern admits a 200-character API key.
    """
    if "enum" in subschema or "const" in subschema:
        return True
    for branch in ("oneOf", "anyOf", "allOf"):
        members = subschema.get(branch)
        if members and all(
                "type" in m and m["type"] == "null" or string_is_bounded(m)
                for m in members):
            return True
    return "pattern" in subschema and "maxLength" in subschema


class RegistryMembershipTests(unittest.TestCase):
    def setUp(self):
        self.providers = load_providers()
        self.by_id = {row["provider_id"]: row for row in self.providers}

    def test_all_initial_provider_ids_present(self):
        required = {"cloudflare_r2", "backblaze_b2", "oracle_object_storage",
                    "huggingface_hub", "google_drive", "onedrive", "dropbox"}
        self.assertTrue(required.issubset(set(self.by_id)))

    def test_the_metadata_service_is_present_by_adapter_type(self):
        """``supabase_metadata`` is an adapter type, not a second identity."""
        rows = [r for r in self.providers
                if r["adapter_type"] == "supabase_metadata"]
        self.assertEqual([r["provider_id"] for r in rows], ["supabase"])
        self.assertEqual(rows[0]["provider_id"], supabase_metadata.PROVIDER_ID)

    def test_the_external_rows_are_exactly_the_eight_task_8_registers(self):
        external = {r["provider_id"] for r in self.providers if r["external"]}
        self.assertEqual(external, set(EXPECTED_ROLES))

    def test_a_local_row_still_exists_so_local_only_has_a_home(self):
        local = [r for r in self.providers if not r["external"]]
        self.assertTrue(local)
        for row in local:
            with self.subTest(provider=row["provider_id"]):
                self.assertIn("LOCAL_ONLY", row["privacy_classes_allowed"])

    def test_no_provider_id_is_repeated(self):
        ids = [row["provider_id"] for row in self.providers]
        self.assertEqual(sorted(ids), sorted(set(ids)))


class UnknownQuotaIsNeverAnEntitlementTests(unittest.TestCase):
    """The non-negotiable, stated three ways and checked on every row."""

    def setUp(self):
        self.providers = load_providers()
        import json
        self.validator = Draft202012Validator(
            json.loads(PROVIDER_SCHEMA_PATH.read_text(encoding="utf-8")))

    def test_unverified_free_quota_forbids_autonomous_writes_on_every_row(self):
        for row in self.providers:
            with self.subTest(provider=row["provider_id"]):
                if free_quota(row)["verified"] is False:
                    self.assertIs(row["autonomous_write_allowed"], False)

    def test_unverified_free_quota_forbids_plain_writes_on_every_row(self):
        """An autonomous writer is a writer, and so is a manual one."""
        for row in self.providers:
            with self.subTest(provider=row["provider_id"]):
                if free_quota(row)["verified"] is False:
                    self.assertIs(row.get("write_enabled", False), False)

    def test_every_shipped_row_has_an_unverified_free_quota(self):
        """Nothing has been probed, so nothing is verified. Said out loud."""
        for row in self.providers:
            with self.subTest(provider=row["provider_id"]):
                self.assertIs(free_quota(row)["verified"], False)

    def test_claiming_the_entitlement_is_refused_by_the_schema_on_every_row(self):
        """The control, not the current value of a field.

        Each shipped row is mutated into the row a careless edit would produce -
        an autonomous writer - and the schema on disk has to refuse it. A row
        that passed here would be one where "unknown quota" and "may write" are
        merely not written together today.
        """
        for row in self.providers:
            with self.subTest(provider=row["provider_id"]):
                mutant = dict(row)
                mutant["autonomous_write_allowed"] = True
                mutant["write_enabled"] = True
                errors = list(self.validator.iter_errors(mutant))
                self.assertTrue(errors, "the schema accepted an unverified "
                                        "autonomous writer")

    def test_a_verified_free_status_without_a_read_quota_still_cannot_write(self):
        """The row a plausible half-done verification produces."""
        mutant = dict(next(r for r in load_providers()
                           if r["provider_id"] == "oracle_object_storage"))
        mutant.update({
            "free_status": "VERIFIED_RECURRING_FREE",
            "free_status_evidence": {
                "evidence_class": "runtime_account_evidence",
                "verified_at": "2026-09-18T00:00:00Z",
                "evidence_ref": "CHECKPOINTS/evidence/storage-probe.json",
            },
            "hard_stop_verified": True,
            "paid_spillover_possible": False,
            "health": "HEALTHY",
            "last_probe_at": "2026-09-18T00:00:00Z",
            "autonomous_write_allowed": True,
            "write_enabled": True,
        })
        self.assertIs(free_quota(mutant)["verified"], False)
        self.assertTrue(list(self.validator.iter_errors(mutant)))
        self.assertTrue(mesh_validator.validate_provider_row(mutant))

    def test_the_mutation_fixture_is_otherwise_valid(self):
        """Fixture check: the refusals above are about the quota, not the shape.

        The same row with the writes withdrawn must validate, or every assertion
        in this class could be passing on an unrelated error.
        """
        mutant = dict(next(r for r in load_providers()
                           if r["provider_id"] == "oracle_object_storage"))
        mutant.update({
            "free_status": "VERIFIED_RECURRING_FREE",
            "free_status_evidence": {
                "evidence_class": "runtime_account_evidence",
                "verified_at": "2026-09-18T00:00:00Z",
                "evidence_ref": "CHECKPOINTS/evidence/storage-probe.json",
            },
            "hard_stop_verified": True,
            "paid_spillover_possible": False,
            "health": "HEALTHY",
            "last_probe_at": "2026-09-18T00:00:00Z",
            "autonomous_write_allowed": False,
            "write_enabled": False,
        })
        self.assertEqual([e.message for e in self.validator.iter_errors(mutant)], [])

    def test_the_shipped_registry_passes_the_registry_validator(self):
        self.assertEqual(mesh_validator.validate_registry(load_providers()), [])


class DocumentationIsNotAccountEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.registry = load_registry()
        self.providers = self.registry["providers"]

    def test_no_row_claims_runtime_account_evidence(self):
        for row in self.providers:
            with self.subTest(provider=row["provider_id"]):
                self.assertNotEqual(
                    row["free_status_evidence"]["evidence_class"],
                    "runtime_account_evidence")

    def test_no_marketing_quota_number_appears_anywhere_in_the_registry(self):
        text = PROVIDERS_PATH.read_text(encoding="utf-8")
        numbers = re.findall(r"\b[0-9]{6,}\b", text)
        offenders = [(label, value) for label, value in MARKETING_QUOTA_BYTES.items()
                     if str(value) in numbers]
        self.assertEqual(offenders, [])

    def test_no_external_row_states_a_quota_at_all(self):
        for row in self.providers:
            if not row["external"]:
                continue
            with self.subTest(provider=row["provider_id"]):
                self.assertIsNone(row["quota_total"])
                self.assertIsNone(row["quota_used"])
                self.assertIsNone(row.get("quota_reserved"))

    def test_no_external_row_states_a_rate_limit_it_has_not_observed(self):
        for row in self.providers:
            if not row["external"]:
                continue
            with self.subTest(provider=row["provider_id"]):
                limits = row.get("rate_limits")
                self.assertIsInstance(limits, dict)
                self.assertIs(limits["verified"], False)
                self.assertIsNone(limits["requests_per_minute"])
                self.assertIsNone(limits["bytes_per_day"])

    def test_no_external_row_states_an_object_size_limit_it_has_not_observed(self):
        for row in self.providers:
            if not row["external"]:
                continue
            with self.subTest(provider=row["provider_id"]):
                limits = row.get("object_size_limits")
                self.assertIsInstance(limits, dict)
                for field, value in limits.items():
                    self.assertIsNone(value, field)

    def test_the_registry_says_out_loud_which_evidence_it_holds(self):
        self.assertIs(
            self.registry["documentation_evidence_is_not_account_evidence"], True)
        self.assertIs(self.registry["marketing_quota_numbers_recorded"], False)
        self.assertIs(self.registry["accounts_created_here"], False)
        self.assertIs(self.registry["registry_membership_is_admission"], False)
        self.assertIs(self.registry["registry_membership_is_activation"], False)

    def test_no_external_row_is_admitted_for_any_privacy_class(self):
        for row in self.providers:
            if not row["external"]:
                continue
            with self.subTest(provider=row["provider_id"]):
                self.assertEqual(row["privacy_classes_allowed"], [])
                self.assertIn("CONFIDENTIAL", row["encryption_required_classes"])

    def test_no_external_row_claims_a_probe_or_an_expiry_date(self):
        for row in self.providers:
            if not row["external"]:
                continue
            with self.subTest(provider=row["provider_id"]):
                self.assertIsNone(row["last_probe_at"])
                self.assertIsNone(row["free_expiry_at"])
                self.assertEqual(row["health"], "QUARANTINED")
                self.assertEqual(row["paid_spillover_possible"], "unknown")


class ProviderRoleTests(unittest.TestCase):
    def setUp(self):
        self.by_id = {row["provider_id"]: row for row in load_providers()}

    def test_every_row_carries_the_role_spec_s17_gives_it(self):
        for provider_id, expected in EXPECTED_ROLES.items():
            with self.subTest(provider=provider_id):
                row = self.by_id[provider_id]
                for field, value in expected.items():
                    self.assertEqual(row[field], value, field)

    def test_no_registry_row_may_serve_the_canonical_tier(self):
        """CANONICAL is GitHub's, and GitHub is not a storage provider row."""
        for row in self.by_id.values():
            with self.subTest(provider=row["provider_id"]):
                self.assertNotIn("CANONICAL", row["tiers_allowed"])
                self.assertNotIn("CANONICAL", row.get("preferred_tiers") or [])

    def test_a_human_backup_row_serves_only_the_human_backup_tier(self):
        for provider_id in ("google_drive", "onedrive", "dropbox"):
            with self.subTest(provider=provider_id):
                row = self.by_id[provider_id]
                self.assertEqual(row["tiers_allowed"], ["HUMAN_BACKUP"])
                self.assertEqual(row["acceptable_use_class"], "human-backup-only")

    def test_the_human_backup_rows_are_exactly_the_adapter_s_adapter_types(self):
        declared = {self.by_id[p]["adapter_type"]
                    for p in ("google_drive", "onedrive", "dropbox")}
        self.assertEqual(declared, set(human_backup.ADAPTER_TYPES))

    def test_the_hugging_face_row_is_the_artifact_adapter_s_row(self):
        row = self.by_id["huggingface_hub"]
        self.assertEqual(row["adapter_type"], huggingface_artifact.ADAPTER_TYPE)
        self.assertEqual(row["acceptable_use_class"],
                         huggingface_artifact.ACCEPTABLE_USE_CLASS)
        self.assertEqual(tuple(row["tiers_allowed"]),
                         huggingface_artifact.TIERS_ALLOWED)

    def test_the_three_s3_rows_are_the_s3_adapter_s_rows(self):
        for provider_id in ("cloudflare_r2", "backblaze_b2", "oracle_object_storage"):
            with self.subTest(provider=provider_id):
                self.assertEqual(self.by_id[provider_id]["adapter_type"],
                                 s3_object.ADAPTER_TYPE)

    def test_the_metadata_row_is_not_a_bulk_backend(self):
        row = self.by_id["supabase"]
        self.assertIs(row["bulk_object_backend_allowed"], False)
        self.assertIs(supabase_metadata.BULK_OBJECT_BACKEND_ALLOWED, False)
        self.assertIsNone(row["object_size_limits"]["max_object_bytes"])

    def test_the_acceptable_use_classes_are_the_policy_vocabulary(self):
        policy = yaml.safe_load((STORAGE / "policy.yaml").read_text(encoding="utf-8"))
        allowed = set(policy["provider_roles"]["acceptable_use_classes"])
        for row in self.by_id.values():
            with self.subTest(provider=row["provider_id"]):
                self.assertIn(row["acceptable_use_class"], allowed)


class NoRowIsAnAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.registry = load_registry()

    def test_the_registry_document_holds_no_authority(self):
        self.assertIs(self.registry["authority"], False)
        for flag in AUTHORITY_FLAGS:
            with self.subTest(flag=flag):
                self.assertIs(self.registry["authority_flags"][flag], False)

    def test_every_row_denies_all_eight_authorities_by_name(self):
        for row in self.registry["providers"]:
            with self.subTest(provider=row["provider_id"]):
                self.assertIs(row["authority"], False)
                self.assertEqual(set(row["authority_flags"]), set(AUTHORITY_FLAGS))
                for flag, held in row["authority_flags"].items():
                    self.assertIs(held, False, flag)

    def test_the_canonical_authority_is_still_github(self):
        self.assertEqual(self.registry["canonical_authority"], "GITHUB_BRAIN_V4")


class RegistryFieldsAreBoundedTests(unittest.TestCase):
    """The structural guard, driven from the schema and the registry on disk.

    Not a hand-written list of field names: every field of every shipped row is
    looked up in ``storage_provider.schema.json``, so a field nobody bounded and
    a field nobody declared are both findings, and a property added later
    arrives already covered.
    """

    def setUp(self):
        import json
        self.schema = json.loads(PROVIDER_SCHEMA_PATH.read_text(encoding="utf-8"))
        self.properties = self.schema["properties"]
        self.providers = load_providers()

    def test_every_field_used_by_a_row_is_declared_by_the_schema(self):
        offenders = []
        for row in self.providers:
            for field in row:
                if field not in self.properties:
                    offenders.append(f"{row['provider_id']}.{field}")
        self.assertEqual(offenders, [])

    def test_every_required_field_is_present_on_every_row(self):
        required = set(self.schema["required"])
        for row in self.providers:
            with self.subTest(provider=row["provider_id"]):
                self.assertEqual(sorted(required - set(row)), [])

    def test_every_string_field_a_row_uses_is_bounded_by_the_schema(self):
        offenders = []
        for row in self.providers:
            for field, value in row.items():
                if not isinstance(value, str):
                    continue
                subschema = resolve(self.schema, self.properties[field])
                if not string_is_bounded(subschema):
                    offenders.append(f"{row['provider_id']}.{field}")
        self.assertEqual(offenders, [])

    def test_every_nested_string_a_row_uses_is_bounded_too(self):
        """``free_status_evidence``, ``object_size_limits``, ``rate_limits``."""
        offenders = []
        for row in self.providers:
            for field, value in row.items():
                if not isinstance(value, dict):
                    continue
                parent = resolve(self.schema, self.properties[field])
                nested_properties = parent.get("properties") or {}
                self.assertIs(parent.get("additionalProperties"), False, field)
                for name, nested in value.items():
                    if name not in nested_properties:
                        offenders.append(f"{row['provider_id']}.{field}.{name}")
                    elif isinstance(nested, str) and not string_is_bounded(
                            resolve(self.schema, nested_properties[name])):
                        offenders.append(f"{row['provider_id']}.{field}.{name}")
        self.assertEqual(offenders, [])

    def test_the_bound_check_can_actually_fail(self):
        """A guard that cannot fire is not a guard."""
        self.assertFalse(string_is_bounded({"type": "string"}))
        self.assertFalse(string_is_bounded({"type": "string", "maxLength": 64}))
        self.assertFalse(string_is_bounded({"type": "string", "pattern": "^a"}))
        self.assertTrue(string_is_bounded(
            {"type": "string", "pattern": "^a", "maxLength": 64}))
        self.assertTrue(string_is_bounded({"enum": ["a", "b"]}))

    def test_the_registry_names_no_endpoint_account_or_credential(self):
        """A registry row says which backends exist, not how to reach one."""
        text = PROVIDERS_PATH.read_text(encoding="utf-8")
        body = "\n".join(line for line in text.splitlines()
                         if not line.lstrip().startswith("#"))
        for needle in ("://", "@", "=", "Bearer", "api_key", "token"):
            with self.subTest(needle=needle):
                self.assertNotIn(needle, body)

    def test_every_row_validates_against_the_schema(self):
        import json
        validator = Draft202012Validator(
            json.loads(PROVIDER_SCHEMA_PATH.read_text(encoding="utf-8")))
        offenders = []
        for row in self.providers:
            for error in validator.iter_errors(row):
                offenders.append(f"{row['provider_id']}: {error.message}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
