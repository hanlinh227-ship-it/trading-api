"""Task 4b - the bounded GitHub recovery snapshot, and the rebuild from it.

Spec S18 says the metadata service must not become a single point of failure,
and names what GitHub keeps instead: the policy, the provider registry, a
*bounded* manifest snapshot or pointer set, the schema version, the known
critical-object index, and the last successful export reference. Spec S23 says
a full mesh rebuild must be possible from those plus provider-side object
metadata and content hashes.

"Bounded" is the load-bearing word and it is tested as three separate bounds:

* a cap on entries (``MAX_SNAPSHOT_ENTRIES``),
* a cap on the serialised snapshot (``MAX_SNAPSHOT_BYTES``),
* a cap on every individual string in it (``MAX_SNAPSHOT_STRING``).

The third is the one that matters most and it is why this file does not settle
for the plan's sketch of ``assert "api_key" not in blob``. That is a substring
check on field *names*: it passes happily while two kilobytes of secret sit in
an allowed field that nobody bounded. What is asserted here instead is that the
snapshot is a *projection* - an entry may carry only the fields on a checked-in
whitelist, every other field of the record is dropped whatever it holds, and
every string that survives is short enough that it cannot be a credential.

The rebuild is tested for the same disposition: it admits an object only when a
provider-side content hash matches the snapshot pointer, it refuses to
reconstruct a record that would violate privacy (a LOCAL_ONLY object seen on an
external provider is a loss to report, not a record to write), and objects it
cannot verify are listed explicitly rather than quietly dropped - Spec S23
step 9, "mark unrecoverable objects explicitly".

Nothing here contacts a provider, a metadata service or a network.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path


from AI_SKILL_LIBRARY.v4.storage import metadata, recovery
from AI_SKILL_LIBRARY.v4.storage.manifest import assert_no_credential_material

from AI_SKILL_LIBRARY.tests.test_storage_metadata import (
    AUTHORITY_FLAGS,
    FakeMetadataStore,
    MANIFEST_VALIDATOR,
    SMUGGLED_CREDENTIAL,
    TIME,
    safe_manifest,
    set_path,
    string_paths,
)

ROOT = Path(__file__).resolve().parents[2]
RECOVERY_MANIFEST_PATH = ROOT / "AI_SKILL_LIBRARY/v4/storage/recovery_manifest.json"


def observed(record, backend_id=None, **overrides):
    """One provider-side observation of an object: what a scan can actually see."""
    row = {
        "backend_id": backend_id or record["primary_backend"],
        "object_id": record["object_id"],
        "content_sha256": record["content_sha256"],
        "size_bytes": record["size_bytes"],
        "observed_at": TIME,
    }
    row.update(overrides)
    return row


def snapshot_of(records):
    return recovery.export_recovery_snapshot(
        FakeMetadataStore(records=records), generated_at=TIME)


def all_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, nested in value.items():
            yield key
            yield from all_strings(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from all_strings(nested)


class AuthorityTests(unittest.TestCase):

    def test_the_module_declares_no_authority(self):
        self.assertIs(recovery.AUTHORITY, False)
        for flag in AUTHORITY_FLAGS:
            self.assertIn(flag, recovery.AUTHORITY_FLAGS)
        self.assertEqual(recovery.CANONICAL_AUTHORITY, "GITHUB_BRAIN_V4")

    def test_the_module_performs_no_cryptography(self):
        self.assertIs(recovery.ENCRYPTION_IMPLEMENTED_HERE, False)
        for name in ("encrypt", "decrypt", "derive_key"):
            self.assertFalse(hasattr(recovery, name), name)

    def test_a_snapshot_denies_the_eight_authorities_by_name(self):
        snapshot = snapshot_of([safe_manifest()])
        self.assertIs(snapshot["authority"], False)
        self.assertEqual(set(snapshot["authority_flags"]), set(AUTHORITY_FLAGS))
        self.assertEqual(set(snapshot["authority_flags"].values()), {False})

    def test_anchored_patterns_use_backslash_Z(self):
        source = Path(recovery.__file__).read_text(encoding="utf-8")
        for line in source.splitlines():
            if "re.compile" in line:
                self.assertNotIn('$"', line, line)
                self.assertNotIn("$'", line, line)


class SnapshotShapeTests(unittest.TestCase):

    def test_export_is_deterministic(self):
        records = [safe_manifest(content=bytes([n])) for n in range(5)]
        first = snapshot_of(records)
        second = snapshot_of(list(reversed(records)))
        self.assertEqual(json.dumps(first, sort_keys=True),
                         json.dumps(second, sort_keys=True))

    def test_entries_are_ordered_and_counted_honestly(self):
        records = [safe_manifest(content=bytes([n])) for n in range(5)]
        snapshot = snapshot_of(records)
        self.assertEqual(snapshot["entry_count"], 5)
        self.assertIs(snapshot["truncated"], False)
        self.assertEqual(snapshot["omitted_entries"], 0)
        self.assertEqual(len(snapshot["entries"]), 5)

    def test_the_critical_object_index_names_exactly_the_critical_objects(self):
        critical = [safe_manifest(content=b"c1"), safe_manifest(content=b"c2")]
        others = [safe_manifest(content=b"r1", criticality="REPRODUCIBLE",
                                reproducible=True),
                  safe_manifest(content=b"e1", criticality="EPHEMERAL")]
        snapshot = snapshot_of(critical + others)
        self.assertEqual(sorted(snapshot["critical_object_index"]),
                         sorted(r["object_id"] for r in critical))
        entry_ids = {entry["object_id"] for entry in snapshot["entries"]}
        self.assertTrue(set(snapshot["critical_object_index"]) <= entry_ids)

    def test_the_snapshot_points_at_the_canonical_documents(self):
        snapshot = snapshot_of([])
        for pointer in snapshot["pointers"].values():
            self.assertTrue((ROOT / pointer).exists(), pointer)

    def test_export_blocks_when_the_metadata_store_is_unhealthy(self):
        store = FakeMetadataStore(records=[safe_manifest()], healthy=False)
        with self.assertRaises(metadata.MetadataStoreUnavailable):
            recovery.export_recovery_snapshot(store)

    def test_export_refuses_a_non_store(self):
        for bad in (None, object(), [safe_manifest()], {}):
            with self.subTest(bad=type(bad).__name__):
                with self.assertRaises(ValueError):
                    recovery.export_recovery_snapshot(bad)

    def test_export_refuses_to_summarise_a_corrupted_row(self):
        store = FakeMetadataStore()
        store._records["obj_" + "a" * 64] = {"object_id": "obj_" + "a" * 64,
                                             "api_key": SMUGGLED_CREDENTIAL}
        with self.assertRaises(ValueError):
            recovery.export_recovery_snapshot(store)


class SnapshotCarriesNoSecretsTests(unittest.TestCase):

    def test_recovery_snapshot_contains_no_secret_material(self):
        """The plan's check, kept because it is cheap - and then the real ones."""
        snapshot = snapshot_of([safe_manifest()])
        blob = json.dumps(snapshot).lower()
        self.assertNotIn("api_key", blob)
        self.assertNotIn("private_key", blob)

    def test_an_entry_carries_only_whitelisted_fields(self):
        """The projection is the control. A field not on the list is dropped
        whatever it holds, so a field added to the manifest later cannot reach
        GitHub by default."""
        snapshot = snapshot_of([safe_manifest()])
        entry = snapshot["entries"][0]
        self.assertEqual(set(entry) - set(recovery.ENTRY_FIELDS), set())
        for dropped in ("source_provenance", "verification", "last_accessed_at",
                        "object_class", "mime_type", "retention_class"):
            self.assertNotIn(dropped, entry, dropped)

    def test_the_ciphertext_parameters_never_reach_github(self):
        snapshot = snapshot_of([safe_manifest()])
        entry = snapshot["entries"][0]
        self.assertEqual(set(entry["encryption"]),
                         set(recovery.SNAPSHOT_ENCRYPTION_FIELDS))
        self.assertNotIn("nonce", entry["encryption"])
        self.assertNotIn("tag", entry["encryption"])
        blob = json.dumps(snapshot)
        self.assertNotIn("YWJjZGVmZ2hpams", blob)
        self.assertNotIn("bXl0YWdteXRhZw", blob)

    def test_the_key_reference_is_a_pointer_at_the_secret_store(self):
        """Spec S22/S23: a reference into the authorized secret system is a
        recovery input; key *material* is not, and there is no field for it."""
        entry = snapshot_of([safe_manifest()])["entries"][0]
        self.assertTrue(entry["encryption"]["key_ref"].startswith(
            ("env://", "secretstore://", "worker-secret://", "kms://")))

    def test_every_string_in_a_snapshot_is_bounded(self):
        """A 2KB secret does not need a field called ``api_key``; it needs an
        unbounded field. There is none."""
        snapshot = snapshot_of([safe_manifest(content=bytes([n]))
                                for n in range(20)])
        for text in all_strings(snapshot):
            self.assertLessEqual(len(text), recovery.MAX_SNAPSHOT_STRING, text[:40])
            assert_no_credential_material(text, where="snapshot")

    def test_a_smuggled_credential_never_survives_into_a_snapshot(self):
        record = safe_manifest()
        for path in string_paths(record):
            with self.subTest(path=".".join(str(step) for step in path)):
                poisoned = set_path(record, path, SMUGGLED_CREDENTIAL)
                try:
                    snapshot = snapshot_of([poisoned])
                except (ValueError, metadata.MetadataStoreUnavailable):
                    continue
                self.assertNotIn(SMUGGLED_CREDENTIAL, json.dumps(snapshot))
                for text in all_strings(snapshot):
                    self.assertLessEqual(len(text), recovery.MAX_SNAPSHOT_STRING)

    def test_the_cleanliness_check_catches_a_hand_edited_snapshot(self):
        snapshot = snapshot_of([safe_manifest()])
        recovery.assert_snapshot_is_clean(snapshot)
        poisoned = json.loads(json.dumps(snapshot))
        poisoned["entries"][0]["object_id"] = SMUGGLED_CREDENTIAL
        with self.assertRaises(ValueError):
            recovery.assert_snapshot_is_clean(poisoned)
        poisoned = json.loads(json.dumps(snapshot))
        poisoned["entries"][0]["note"] = "-----BEGIN RSA PRIVATE KEY-----"
        with self.assertRaises(ValueError):
            recovery.assert_snapshot_is_clean(poisoned)

    def test_the_per_string_bound_is_enforced_in_its_own_right(self):
        """Exercised directly, and deliberately so.

        Every string a snapshot carries is also pattern-checked, so with the
        projection in place nothing valid can get near this bound - a mutation
        that deletes it survives the rest of this file. That is exactly why it
        is asserted here rather than left as a comment: it is the last line of
        defence, the one that still holds if a future field is added to
        ``ENTRY_FIELDS`` with a weak pattern, and an untested last line of
        defence is the one that quietly stops existing.
        """
        recovery._walk_values("a" * recovery.MAX_SNAPSHOT_STRING, where="probe")
        with self.assertRaises(ValueError):
            recovery._walk_values("a" * (recovery.MAX_SNAPSHOT_STRING + 1),
                                  where="probe")
        with self.assertRaises(ValueError):
            recovery._walk_values({"k": ["ok", SMUGGLED_CREDENTIAL]}, where="probe")
        with self.assertRaises(ValueError):
            recovery._walk_values({"a" * 400: "ok"}, where="probe")
        with self.assertRaises(ValueError):
            recovery._walk_values(1.5, where="probe")

    def test_a_snapshot_cannot_promote_the_index_to_canonical(self):
        """The checkpoint is read during a bootstrap, before anything else is
        loaded. A hand edit here is the cheapest place to declare Supabase
        canonical, so the shape is checked rather than merely carried."""
        snapshot = snapshot_of([safe_manifest()])
        for mutate in (
                lambda s: s["metadata_service"].update(authority=True),
                lambda s: s["metadata_service"].update(role="canonical"),
                lambda s: s["metadata_service"].update(project_exists_verified=True),
                lambda s: s["metadata_service"].pop("authority"),
                lambda s: s.update(canonical_authority="SUPABASE"),
        ):
            with self.subTest(mutate=mutate):
                broken = json.loads(json.dumps(snapshot))
                mutate(broken)
                with self.assertRaises(ValueError):
                    recovery.assert_snapshot_is_clean(broken)

    def test_a_pointer_cannot_redirect_a_rebuild_somewhere_else(self):
        snapshot = snapshot_of([])
        for value in ("https://evil.example.com/policy.yaml",
                      "/etc/passwd", "../../elsewhere/policy.yaml",
                      "AI_SKILL_LIBRARY/v4/storage/policy.yaml\n", "", 17):
            with self.subTest(value=value):
                broken = json.loads(json.dumps(snapshot))
                broken["pointers"]["storage_policy"] = value
                with self.assertRaises(ValueError):
                    recovery.assert_snapshot_is_clean(broken)

    def test_declared_caps_must_be_the_caps_the_code_enforces(self):
        snapshot = snapshot_of([])
        broken = json.loads(json.dumps(snapshot))
        broken["caps"]["max_string"] = 100000
        with self.assertRaises(ValueError):
            recovery.assert_snapshot_is_clean(broken)

    def test_a_snapshot_never_carries_object_content(self):
        snapshot = snapshot_of([safe_manifest(content=b"x" * 4096)])
        self.assertNotIn("x" * 64, json.dumps(snapshot))


class SnapshotIsBoundedTests(unittest.TestCase):

    def test_entries_are_capped_and_the_truncation_is_declared(self):
        cap = recovery.MAX_SNAPSHOT_ENTRIES
        records = [safe_manifest(content=str(n).encode(),
                                 criticality="REPRODUCIBLE", reproducible=True)
                   for n in range(cap + 40)]
        snapshot = snapshot_of(records)
        self.assertEqual(len(snapshot["entries"]), cap)
        self.assertIs(snapshot["truncated"], True)
        self.assertEqual(snapshot["omitted_entries"], 40)
        self.assertEqual(snapshot["entry_count"], cap + 40)

    def test_critical_objects_are_kept_before_anything_else(self):
        cap = recovery.MAX_SNAPSHOT_ENTRIES
        filler = [safe_manifest(content=("f%d" % n).encode(),
                                criticality="REPRODUCIBLE", reproducible=True)
                  for n in range(cap)]
        critical = [safe_manifest(content=("c%d" % n).encode()) for n in range(5)]
        snapshot = snapshot_of(filler + critical)
        kept = {entry["object_id"] for entry in snapshot["entries"]}
        for record in critical:
            self.assertIn(record["object_id"], kept, "a CRITICAL object was dropped")
        self.assertEqual(sorted(snapshot["critical_object_index"]),
                         sorted(r["object_id"] for r in critical))

    def test_more_critical_objects_than_the_cap_fails_closed(self):
        cap = recovery.MAX_SNAPSHOT_ENTRIES
        records = [safe_manifest(content=("c%d" % n).encode())
                   for n in range(cap + 1)]
        with self.assertRaises(ValueError):
            snapshot_of(records)

    def test_the_serialised_snapshot_stays_under_the_byte_cap(self):
        cap = recovery.MAX_SNAPSHOT_ENTRIES
        records = [safe_manifest(content=str(n).encode()) for n in range(cap)]
        snapshot = snapshot_of(records)
        self.assertLessEqual(len(json.dumps(snapshot)), recovery.MAX_SNAPSHOT_BYTES)

    def test_the_caps_are_stated_and_stay_small(self):
        self.assertEqual(recovery.MAX_SNAPSHOT_ENTRIES, 256)
        self.assertEqual(recovery.MAX_SNAPSHOT_BYTES, 262144)
        self.assertLessEqual(recovery.MAX_SNAPSHOT_STRING, 256)


class RebuildTests(unittest.TestCase):

    def test_manifest_rebuilds_from_provider_metadata_plus_github_state(self):
        record = safe_manifest()
        snapshot = snapshot_of([record])
        rebuilt = recovery.rebuild_manifest([observed(record)], snapshot)
        self.assertEqual(len(rebuilt), 1)
        self.assertEqual(rebuilt[0]["object_id"], record["object_id"])
        self.assertEqual(rebuilt[0]["content_sha256"], record["content_sha256"])
        self.assertEqual(rebuilt[0]["privacy_class"], record["privacy_class"])
        self.assertEqual(rebuilt[0]["criticality"], record["criticality"])

    def test_rebuilt_records_are_valid_manifests_a_store_will_accept(self):
        records = [safe_manifest(content=b"a"),
                   safe_manifest(content=b"b", privacy_class="PUBLIC",
                                 criticality="REPRODUCIBLE", reproducible=True,
                                 encryption_state="NONE", encryption=None,
                                 encryption_scheme_version=None,
                                 primary_backend="cloudflare_r2",
                                 replica_backends=())]
        snapshot = snapshot_of(records)
        rebuilt = recovery.rebuild_manifest([observed(r) for r in records], snapshot)
        self.assertEqual(len(rebuilt), 2)
        store = FakeMetadataStore()
        for entry in rebuilt:
            MANIFEST_VALIDATOR.validate(entry)
            store.put_manifest(entry)
        self.assertEqual(len(store.list_manifests()), 2)

    def test_a_content_hash_mismatch_is_never_admitted(self):
        record = safe_manifest()
        snapshot = snapshot_of([record])
        wrong = observed(record, content_sha256="b" * 64)
        self.assertEqual(recovery.rebuild_manifest([wrong], snapshot), [])
        report = recovery.rebuild_report([wrong], snapshot)
        self.assertEqual(report["rebuilt"], [])
        self.assertIn(record["object_id"], report["unverified"])

    def test_a_size_mismatch_is_never_admitted(self):
        record = safe_manifest()
        snapshot = snapshot_of([record])
        wrong = observed(record, size_bytes=record["size_bytes"] + 1)
        self.assertEqual(recovery.rebuild_manifest([wrong], snapshot), [])

    def test_an_object_absent_from_the_snapshot_is_not_invented(self):
        record = safe_manifest()
        other = safe_manifest(content=b"not-in-the-snapshot")
        snapshot = snapshot_of([record])
        rebuilt = recovery.rebuild_manifest([observed(other)], snapshot)
        self.assertEqual(rebuilt, [])
        report = recovery.rebuild_report([observed(other)], snapshot)
        self.assertIn(other["object_id"], report["unknown"])

    def test_an_object_no_provider_still_holds_is_marked_unrecoverable(self):
        """Spec S23 step 9: mark unrecoverable objects explicitly. Not
        fabricating success is the whole requirement."""
        record = safe_manifest()
        snapshot = snapshot_of([record])
        report = recovery.rebuild_report([], snapshot)
        self.assertEqual(report["rebuilt"], [])
        self.assertEqual(report["unrecoverable"], [record["object_id"]])

    def test_privacy_survives_the_rebuild(self):
        """A LOCAL_ONLY object seen on an external provider is a loss to
        report, not a manifest row to write."""
        record = safe_manifest(privacy_class="LOCAL_ONLY", encryption_state="NONE",
                               encryption=None, encryption_scheme_version=None,
                               primary_backend="local_owned_store",
                               replica_backends=())
        snapshot = snapshot_of([record])
        rows = [observed(record, backend_id="cloudflare_r2")]
        self.assertEqual(recovery.rebuild_manifest(rows, snapshot), [])
        report = recovery.rebuild_report(rows, snapshot)
        self.assertIn(record["object_id"], report["unrecoverable"])

    def test_replicas_are_recomputed_from_what_providers_actually_hold(self):
        record = safe_manifest(privacy_class="PUBLIC", encryption_state="NONE",
                               encryption=None, encryption_scheme_version=None,
                               criticality="IMPORTANT",
                               primary_backend="cloudflare_r2",
                               replica_backends=("backblaze_b2",))
        snapshot = snapshot_of([record])
        rows = [observed(record, backend_id="backblaze_b2"),
                observed(record, backend_id="oracle_object_storage")]
        rebuilt = recovery.rebuild_manifest(rows, snapshot)[0]
        self.assertEqual(
            sorted([rebuilt["primary_backend"]] + rebuilt["replica_backends"]),
            ["backblaze_b2", "oracle_object_storage"])
        self.assertNotIn("cloudflare_r2", rebuilt["replica_backends"])

    def test_rebuild_is_deterministic(self):
        records = [safe_manifest(content=str(n).encode()) for n in range(6)]
        snapshot = snapshot_of(records)
        rows = [observed(r) for r in records]
        first = recovery.rebuild_manifest(rows, snapshot)
        second = recovery.rebuild_manifest(list(reversed(rows)), snapshot)
        self.assertEqual(first, second)
        self.assertEqual([r["object_id"] for r in first],
                         sorted(r["object_id"] for r in records))

    def test_rebuild_of_nothing_is_nothing(self):
        self.assertEqual(recovery.rebuild_manifest([], snapshot_of([])), [])

    def test_rebuild_refuses_a_malformed_snapshot(self):
        good = snapshot_of([safe_manifest()])
        for mutate in (
                lambda s: s.pop("entries"),
                lambda s: s.update(version=2),
                lambda s: s.update(authority=True),
                lambda s: s.update(smuggled=SMUGGLED_CREDENTIAL),
                lambda s: s["entries"][0].update(note=SMUGGLED_CREDENTIAL),
                lambda s: s["entries"][0].update(object_id="not-an-object-id"),
        ):
            with self.subTest(mutate=mutate.__name__):
                broken = json.loads(json.dumps(good))
                mutate(broken)
                with self.assertRaises(ValueError):
                    recovery.rebuild_manifest([], broken)
        for bad in (None, [], "snapshot", 17):
            with self.subTest(bad=type(bad).__name__):
                with self.assertRaises(ValueError):
                    recovery.rebuild_manifest([], bad)

    def test_rebuild_refuses_a_malformed_provider_record(self):
        record = safe_manifest()
        snapshot = snapshot_of([record])
        for bad in (None, "row", 17, []):
            with self.subTest(bad=type(bad).__name__):
                with self.assertRaises(ValueError):
                    recovery.rebuild_manifest([bad], snapshot)
        for field in ("backend_id", "object_id", "content_sha256", "size_bytes"):
            with self.subTest(missing=field):
                row = observed(record)
                row.pop(field)
                with self.assertRaises(ValueError):
                    recovery.rebuild_manifest([row], snapshot)
        for field, value in (("etag", "x"), ("notes", "x"), ("api_key", "x"),
                             ("url", "https://example.com/o")):
            with self.subTest(unknown=field):
                row = observed(record)
                row[field] = value
                with self.assertRaises(ValueError):
                    recovery.rebuild_manifest([row], snapshot)
        with self.subTest(case="unregistered backend"):
            with self.assertRaises(ValueError):
                recovery.rebuild_manifest(
                    [observed(record, backend_id="some_random_untrusted_host")],
                    snapshot)

    def test_every_provider_record_string_field_refuses_a_credential(self):
        record = safe_manifest()
        snapshot = snapshot_of([record])
        row = observed(record)
        for path in string_paths(row):
            with self.subTest(path=".".join(str(step) for step in path)):
                with self.assertRaises(ValueError):
                    recovery.rebuild_manifest(
                        [set_path(row, path, SMUGGLED_CREDENTIAL)], snapshot)
                with self.assertRaises(ValueError):
                    recovery.rebuild_manifest(
                        [set_path(row, path, "a" * 2048)], snapshot)

    def test_rebuild_does_not_carry_forward_a_stale_verification(self):
        """The old verification predates the loss that forced the rebuild;
        re-asserting it would be fabricating evidence."""
        record = safe_manifest()
        rebuilt = recovery.rebuild_manifest([observed(record)],
                                            snapshot_of([record]))[0]
        self.assertNotIn("verification", rebuilt)
        self.assertNotIn("last_verified_at", rebuilt)


class CheckedInRecoveryManifestTests(unittest.TestCase):

    def setUp(self):
        self.document = json.loads(
            RECOVERY_MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_it_parses_and_is_the_shape_the_exporter_emits(self):
        empty = recovery.export_recovery_snapshot(FakeMetadataStore(),
                                                  generated_at=TIME)
        self.assertEqual(set(self.document), set(empty))
        self.assertEqual(self.document["version"], recovery.SNAPSHOT_VERSION)

    def test_it_is_clean_and_bounded(self):
        recovery.assert_snapshot_is_clean(self.document)
        self.assertLessEqual(len(RECOVERY_MANIFEST_PATH.read_bytes()),
                             recovery.MAX_SNAPSHOT_BYTES)
        self.assertLessEqual(len(self.document["entries"]),
                             recovery.MAX_SNAPSHOT_ENTRIES)

    def test_it_is_honest_about_a_mesh_nobody_has_probed(self):
        """Spec S25: the connected Supabase account has no projects. An empty
        index is the true state; a populated one would be a fabrication."""
        self.assertEqual(self.document["entries"], [])
        self.assertEqual(self.document["critical_object_index"], [])
        self.assertEqual(self.document["entry_count"], 0)
        self.assertIs(self.document["truncated"], False)

    def test_it_holds_no_authority(self):
        self.assertIs(self.document["authority"], False)
        self.assertEqual(set(self.document["authority_flags"]),
                         set(AUTHORITY_FLAGS))
        self.assertEqual(set(self.document["authority_flags"].values()), {False})
        self.assertEqual(self.document["canonical_authority"], "GITHUB_BRAIN_V4")

    def test_its_pointers_resolve(self):
        for pointer in self.document["pointers"].values():
            self.assertTrue((ROOT / pointer).exists(), pointer)


if __name__ == "__main__":
    unittest.main()
