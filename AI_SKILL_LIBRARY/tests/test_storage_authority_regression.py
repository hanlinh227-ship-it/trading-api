"""Storage Mesh authority regression: the mesh must gain nothing.

The Federated Free Storage Mesh adds persistence. It must not, now or later,
add authority. ``GITHUB_BRAIN_V4`` stays the only Brain, ``task_router`` the
only routing authority, and Model Mesh the only model-selection authority.

Every assertion here is written so that a *future* edit granting storage some
authority fails, not merely the authority keys that happen to exist today. The
authority key list is therefore read from the policy documents on disk rather
than hard-coded: a newly added ``some_new_authority: true`` is discovered by
the walk and fails, where a fixed list would have let it through silently.
The same structural pattern is applied to the adversarial half of the suite -
the validator is asked to reject each authority key the files actually declare,
one at a time, so a new key is automatically a new rejection case.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

STORAGE_POLICY = "AI_SKILL_LIBRARY/v4/storage/policy.yaml"
STORAGE_PROVIDERS = "AI_SKILL_LIBRARY/v4/storage/providers.yaml"
LEARNING_POLICY = "AI_SKILL_LIBRARY/v4/learning/policy.yaml"
FABRIC_POLICY = "AI_SKILL_LIBRARY/v4/stable/universal_fabric.yaml"
CHECKPOINT = "AI_SKILL_LIBRARY/checkpoint.json"
ADAPTER_REGISTRY = "AI_SKILL_LIBRARY/v4/adapters/registry.yaml"
PROVIDER_SCHEMA = "AI_SKILL_LIBRARY/v4/schemas/storage_provider.schema.json"
MANIFEST_SCHEMA = "AI_SKILL_LIBRARY/v4/schemas/storage_object_manifest.schema.json"

# The checkpoint gains pointers and nothing else. These are the pointer keys the
# routed Brain may resolve to reach storage state; each must name a file that
# exists, and none of them may be, or become, an authority declaration.
CHECKPOINT_STORAGE_POINTERS = (
    "storage_mesh_policy_path",
    "storage_mesh_provider_registry_path",
    "storage_provider_schema_path",
    "storage_object_manifest_schema_path",
    "storage_mesh_validator_path",
)

# Keys that *name* the canonical authority rather than claim one. A document
# saying "github is canonical" is the invariant holding, not breaking.
NAMING_KEYS = {"canonical_authority", "brain_authority"}
NAMING_PATHS = {"canonical.authority"}
CANONICAL_NAMES = {"GITHUB_BRAIN_V4", "github", "task_router", "model_mesh"}

FILES_FOR_FIXTURE = (
    STORAGE_POLICY,
    STORAGE_PROVIDERS,
    LEARNING_POLICY,
    FABRIC_POLICY,
    CHECKPOINT,
    ADAPTER_REGISTRY,
    PROVIDER_SCHEMA,
    MANIFEST_SCHEMA,
    "AI_SKILL_LIBRARY/v4/storage/mesh_validator.py",
)


def load_yaml(rel: str, root: Path = ROOT) -> dict:
    return yaml.safe_load((root / rel).read_text(encoding="utf-8"))


def load_json(rel: str, root: Path = ROOT) -> dict:
    return json.loads((root / rel).read_text(encoding="utf-8"))


def walk(node, prefix: str = ""):
    """Yield (dotted_path, key, value) for every mapping entry, at any depth."""
    if isinstance(node, dict):
        for key, value in node.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            yield path, str(key), value
            yield from walk(value, path)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from walk(value, f"{prefix}[{index}]")


def authority_entries(node, prefix: str = ""):
    """Every entry whose key is ``authority`` or ends in ``_authority``."""
    for path, key, value in walk(node, prefix):
        if key == "authority" or key.endswith("_authority"):
            yield path, key, value


def claimed_authority(node, prefix: str = ""):
    """Authority entries that assert something other than 'not me'.

    A mapping or list under an authority key is a *container* of declarations
    (``authority: {storage_authority: false, ...}``), not a declaration itself;
    the walk descends into it, so each leaf is judged on its own.
    """
    offenders = []
    for path, key, value in authority_entries(node, prefix):
        if isinstance(value, (dict, list)):
            continue
        if key in NAMING_KEYS or path in NAMING_PATHS:
            if value not in CANONICAL_NAMES:
                offenders.append(f"{path}={value!r}")
            continue
        if value is not False:
            offenders.append(f"{path}={value!r}")
    return offenders


def storage_documents():
    for path in sorted((ROOT / "AI_SKILL_LIBRARY/v4/storage").glob("*.yaml")):
        yield path.relative_to(ROOT).as_posix(), yaml.safe_load(path.read_text(encoding="utf-8"))


def fabric_storage_block(root: Path = ROOT) -> dict:
    policy = load_yaml(FABRIC_POLICY, root)
    return policy["subordinate_subsystems"]["federated_free_storage_mesh"]


class StorageMeshHoldsNoAuthorityTests(unittest.TestCase):
    """The plan's sample assertions, plus the structural form of them."""

    def test_storage_mesh_cannot_become_router_or_brain(self):
        policy = load_yaml(STORAGE_POLICY)
        self.assertTrue(policy["authority"])  # the block is not empty
        self.assertFalse(any(policy["authority"].values()))

    def test_no_storage_document_claims_any_authority_at_any_depth(self):
        """Driven by the documents on disk, so a new key cannot slip through."""
        offenders = []
        for rel, doc in storage_documents():
            offenders += [f"{rel}: {item}" for item in claimed_authority(doc)]
        self.assertEqual(offenders, [])

    def test_the_authority_walk_actually_finds_the_declared_keys(self):
        """Guard the guard: a walk that found nothing would pass vacuously."""
        policy = load_yaml(STORAGE_POLICY)
        found = {key for _, key, _ in authority_entries(policy)}
        self.assertGreaterEqual(
            found,
            {"storage_authority", "routing_authority", "reasoning_authority",
             "model_selection_authority", "merge_authority", "trading_authority"},
        )

    def test_storage_names_the_canonical_brain_and_router(self):
        policy = load_yaml(STORAGE_POLICY)
        self.assertEqual(policy["canonical"]["authority"], "GITHUB_BRAIN_V4")
        self.assertEqual(policy["canonical"]["routed_by"], "task_router")
        self.assertEqual(policy["canonical"]["canonical_home"], "github")
        providers = load_yaml(STORAGE_PROVIDERS)
        self.assertEqual(providers["canonical_authority"], "GITHUB_BRAIN_V4")

    def test_no_storage_module_assigns_itself_an_authority(self):
        offenders = []
        for path in sorted((ROOT / "AI_SKILL_LIBRARY/v4/storage").rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("#") or "_authority" not in stripped:
                    continue
                if "True" in stripped:
                    offenders.append(f"{path.relative_to(ROOT).as_posix()}: {stripped}")
        self.assertEqual(offenders, [])


class LearningCannotSelectStorageProvidersTests(unittest.TestCase):
    def test_learning_cannot_select_storage_provider(self):
        policy = load_yaml(LEARNING_POLICY)
        self.assertIs(policy.get("storage_provider_selection_authority", False), False)

    def test_learning_declares_the_subordinate_storage_output_contract(self):
        """Explicit, not merely absent: an implicit default is not a contract."""
        policy = load_yaml(LEARNING_POLICY)
        self.assertIn("storage_provider_selection_authority", policy)
        self.assertIs(policy["storage_provider_selection_authority"], False)
        outputs = policy["storage_outputs"]
        self.assertIs(outputs["may_select_provider"], False)
        self.assertIs(outputs["may_override_placement_policy"], False)
        self.assertIs(outputs["may_bypass_privacy"], False)
        self.assertIs(outputs["may_bypass_retention"], False)
        self.assertIs(outputs["may_force_replication"], False)
        self.assertIs(outputs["may_widen_cloud_eligibility"], False)

    def test_learning_may_request_only_classes_the_storage_policy_defines(self):
        outputs = load_yaml(LEARNING_POLICY)["storage_outputs"]
        requested = outputs["may_request_storage_classes"]
        self.assertTrue(requested)
        defined = set(load_yaml(STORAGE_POLICY)["criticality"])
        self.assertLessEqual(set(requested), defined)

    def test_every_learning_storage_permission_except_class_requests_is_false(self):
        """Structural: a future ``may_pick_backend: true`` fails here."""
        outputs = load_yaml(LEARNING_POLICY)["storage_outputs"]
        offenders = [
            f"storage_outputs.{key}={value!r}"
            for key, value in outputs.items()
            if key != "may_request_storage_classes" and value is not False
        ]
        self.assertEqual(offenders, [])
        self.assertEqual(claimed_authority(outputs, "storage_outputs"), [])


class UniversalFabricKeepsStorageSubordinateTests(unittest.TestCase):
    def test_fabric_declares_storage_as_a_subordinate_subsystem(self):
        block = fabric_storage_block()
        self.assertEqual(block["role"], "subordinate_persistence_and_placement")
        self.assertEqual(block["canonical_authority"], "github")
        self.assertIs(block["second_portable_state_abstraction"], False)

    def test_fabric_storage_block_claims_no_authority(self):
        self.assertEqual(claimed_authority(fabric_storage_block(), "storage"), [])

    def test_fabric_storage_block_points_at_files_that_exist(self):
        block = fabric_storage_block()
        for key in ("policy", "providers", "provider_schema", "object_manifest_schema"):
            with self.subTest(pointer=key):
                self.assertTrue((ROOT / block[key]).is_file(), block[key])

    def test_fabric_keeps_the_brain_and_denies_learning_provider_selection(self):
        policy = load_yaml(FABRIC_POLICY)
        self.assertEqual(policy["authority"], "GITHUB_BRAIN_V4")
        block = fabric_storage_block()
        self.assertIs(block["learning_may_request_storage_classes"], True)
        self.assertIs(block["learning_storage_provider_selection_authority"], False)


class CheckpointAddsPointersOnlyTests(unittest.TestCase):
    def test_checkpoint_declares_every_storage_pointer_and_each_file_exists(self):
        checkpoint = load_json(CHECKPOINT)
        for key in CHECKPOINT_STORAGE_POINTERS:
            with self.subTest(pointer=key):
                self.assertIn(key, checkpoint)
                self.assertTrue((ROOT / checkpoint[key]).is_file(), checkpoint[key])

    def test_checkpoint_pointers_agree_with_the_fabric_policy(self):
        checkpoint = load_json(CHECKPOINT)
        block = fabric_storage_block()
        self.assertEqual(checkpoint["storage_mesh_policy_path"], block["policy"])
        self.assertEqual(checkpoint["storage_mesh_provider_registry_path"], block["providers"])
        self.assertEqual(checkpoint["storage_provider_schema_path"], block["provider_schema"])
        self.assertEqual(
            checkpoint["storage_object_manifest_schema_path"], block["object_manifest_schema"])

    def test_checkpoint_moves_no_authority(self):
        """Pointers only: the Brain, router and model-selection owners are untouched."""
        checkpoint = load_json(CHECKPOINT)
        self.assertEqual(checkpoint["checkpoint_id"], "GITHUB_BRAIN_V4")
        self.assertEqual(checkpoint["activation_key"], "GITHUB_BRAIN_V4")
        self.assertEqual(checkpoint["stable_router_path"], "AI_SKILL_LIBRARY/v4/stable/router.yaml")
        self.assertEqual(
            checkpoint["model_mesh_policy_path"], "AI_SKILL_LIBRARY/v4/model_mesh/policy.yaml")
        self.assertEqual(claimed_authority(checkpoint), [])
        storage_keys = [k for k in checkpoint if "storage" in k]
        self.assertEqual(sorted(storage_keys), sorted(CHECKPOINT_STORAGE_POINTERS))
        for key in storage_keys:
            with self.subTest(key=key):
                self.assertTrue(key.endswith("_path"))
                self.assertIsInstance(checkpoint[key], str)


class ValidatorRejectsStorageAuthorityClaimsTests(unittest.TestCase):
    """The validator must *reject* a claim, not merely decline to grant one."""

    def setUp(self):
        from AI_SKILL_LIBRARY.v4.tools.validate_universal_fabric import validate

        self.validate = validate
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for rel in FILES_FOR_FIXTURE:
            dest = self.tmp / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, dest)

    def write_yaml(self, rel: str, doc) -> None:
        (self.tmp / rel).write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    def write_json(self, rel: str, doc) -> None:
        (self.tmp / rel).write_text(json.dumps(doc, indent=2), encoding="utf-8")

    def test_the_unmodified_fixture_passes(self):
        """If this fails the fixture is wrong, not the repository."""
        self.assertEqual(self.validate(self.tmp), [])

    def test_every_storage_policy_authority_key_is_rejected_when_granted(self):
        """Driven from the policy on disk: a new key is a new rejection case."""
        original = load_yaml(STORAGE_POLICY)
        for key in original["authority"]:
            with self.subTest(authority=key):
                mutated = load_yaml(STORAGE_POLICY)
                mutated["authority"][key] = True
                self.write_yaml(STORAGE_POLICY, mutated)
                errors = self.validate(self.tmp)
                self.assertTrue(
                    any("storage" in e and key in e for e in errors),
                    f"granting {key} was not rejected: {errors}",
                )
        self.write_yaml(STORAGE_POLICY, original)

    def test_every_provider_registry_authority_flag_is_rejected_when_granted(self):
        original = load_yaml(STORAGE_PROVIDERS)
        for key in original["authority_flags"]:
            with self.subTest(authority=key):
                mutated = load_yaml(STORAGE_PROVIDERS)
                mutated["authority_flags"][key] = True
                self.write_yaml(STORAGE_PROVIDERS, mutated)
                self.assertTrue(
                    any(key in e for e in self.validate(self.tmp)),
                    f"granting providers.{key} was not rejected",
                )
        self.write_yaml(STORAGE_PROVIDERS, original)

    def test_provider_registry_claiming_authority_is_rejected(self):
        doc = load_yaml(STORAGE_PROVIDERS)
        doc["authority"] = True
        self.write_yaml(STORAGE_PROVIDERS, doc)
        self.assertIn("storage_provider_registry_must_not_be_authority", self.validate(self.tmp))

    def test_every_fabric_storage_authority_key_is_rejected_when_granted(self):
        block = fabric_storage_block()
        keys = [k for _, k, _ in authority_entries(block) if k != "canonical_authority"]
        self.assertTrue(keys)
        for key in keys:
            with self.subTest(authority=key):
                doc = load_yaml(FABRIC_POLICY)
                doc["subordinate_subsystems"]["federated_free_storage_mesh"][key] = True
                self.write_yaml(FABRIC_POLICY, doc)
                self.assertTrue(
                    any(key in e for e in self.validate(self.tmp)),
                    f"granting fabric storage {key} was not rejected",
                )

    def test_storage_claiming_a_non_github_canonical_authority_is_rejected(self):
        doc = load_yaml(STORAGE_POLICY)
        doc["canonical"]["authority"] = "FEDERATED_STORAGE_MESH"
        self.write_yaml(STORAGE_POLICY, doc)
        self.assertIn("storage_canonical_authority_must_be_github_brain_v4", self.validate(self.tmp))

    def test_storage_claiming_its_own_router_is_rejected(self):
        doc = load_yaml(STORAGE_POLICY)
        doc["canonical"]["routed_by"] = "storage_router"
        self.write_yaml(STORAGE_POLICY, doc)
        self.assertIn("storage_must_be_routed_by_task_router", self.validate(self.tmp))

    def test_learning_selecting_a_storage_provider_is_rejected(self):
        doc = load_yaml(LEARNING_POLICY)
        doc["storage_provider_selection_authority"] = True
        self.write_yaml(LEARNING_POLICY, doc)
        self.assertIn(
            "learning_storage_provider_selection_authority_forbidden", self.validate(self.tmp))

    def test_learning_storage_outputs_granting_any_permission_is_rejected(self):
        original = load_yaml(LEARNING_POLICY)
        for key, value in original["storage_outputs"].items():
            if value is not False:
                continue
            with self.subTest(permission=key):
                doc = load_yaml(LEARNING_POLICY)
                doc["storage_outputs"][key] = True
                self.write_yaml(LEARNING_POLICY, doc)
                self.assertTrue(
                    any(key in e for e in self.validate(self.tmp)),
                    f"granting learning storage_outputs.{key} was not rejected",
                )
        self.write_yaml(LEARNING_POLICY, original)

    def test_learning_requesting_an_undefined_storage_class_is_rejected(self):
        doc = load_yaml(LEARNING_POLICY)
        doc["storage_outputs"]["may_request_storage_classes"] = ["ANYTHING_GOES"]
        self.write_yaml(LEARNING_POLICY, doc)
        self.assertTrue(
            any("storage_class" in e for e in self.validate(self.tmp)), self.validate(self.tmp))

    def test_a_missing_checkpoint_storage_pointer_is_rejected(self):
        for key in CHECKPOINT_STORAGE_POINTERS:
            with self.subTest(pointer=key):
                doc = load_json(CHECKPOINT)
                doc.pop(key)
                self.write_json(CHECKPOINT, doc)
                self.assertIn(f"checkpoint_storage_pointer_missing:{key}", self.validate(self.tmp))

    def test_a_dangling_checkpoint_storage_pointer_is_rejected(self):
        doc = load_json(CHECKPOINT)
        doc["storage_mesh_policy_path"] = "AI_SKILL_LIBRARY/v4/storage/does_not_exist.yaml"
        self.write_json(CHECKPOINT, doc)
        self.assertTrue(
            any(e.startswith("checkpoint_storage_pointer_unresolved") for e in self.validate(self.tmp)))

    def test_a_missing_fabric_storage_block_is_rejected(self):
        doc = load_yaml(FABRIC_POLICY)
        doc["subordinate_subsystems"].pop("federated_free_storage_mesh")
        self.write_yaml(FABRIC_POLICY, doc)
        self.assertIn("universal_fabric_storage_subsystem_required", self.validate(self.tmp))


if __name__ == "__main__":
    unittest.main()
