"""Task 3 - the restore drill that a manifest check cannot impersonate.

``DISASTER_RECOVERY_READY`` is the gate a schema check is most tempting to
satisfy. A manifest parses, a backup contract validates, and the gate goes
green while nobody has ever reconstructed a byte. The closure rule says the
opposite in one line: no schema/manifest-only check may set the gate, and a
drill that restores an empty directory, or restores into a location that
already held the answer, is a failed drill dressed as a pass.

So these tests do not assert that the drill *reports* the four facts. They
assert the facts are *observed*:

* the primary is gone from the filesystem before the restore starts, and the
  drill's own reading of that is checked against the filesystem;
* the restore destination is observed empty, and the restored bytes therefore
  cannot have been sitting there already;
* the restored content hashes to the backup's recorded digest and parses back
  to the recorded revision;
* the production cleanliness gate and the production restore verifier are the
  ones that ran - a tampered snapshot fails the drill, which it could not do
  if the drill had its own looser copy of those checks.

And the negative cases: a corrupt backup, a missing backup and an empty backup
object each produce ``ready=false`` rather than an exception that a caller
could mistake for a pass.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.storage import metadata as storage_metadata
from AI_SKILL_LIBRARY.v4.storage import recovery as storage_recovery
from AI_SKILL_LIBRARY.v4.survival import recovery as survival_recovery
from AI_SKILL_LIBRARY.v4.tools import storage_restore_drill as drill

ROOT = Path(__file__).resolve().parents[2]

#: The exact field set the closure plan names for this evidence document.
CONTRACT_FIELDS = (
    "gate",
    "ready",
    "source_sha",
    "backup_identity",
    "restored_identity",
    "integrity_verified",
    "primary_removed_before_restore",
    "restore_destination_was_empty",
    "proofs",
)

SHA = "0123456789abcdef0123456789abcdef01234567"


def workspace(case):
    """A temporary directory, cleaned up by the test, outside the repository."""
    tmp = tempfile.TemporaryDirectory(prefix="restore-drill-test-")
    case.addCleanup(tmp.cleanup)
    return Path(tmp.name)


def run(case, **kwargs):
    kwargs.setdefault("source_sha", SHA)
    return drill.run_drill(workspace=workspace(case), **kwargs)


def strings(node, trail=""):
    if isinstance(node, str):
        yield trail, node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from strings(value, f"{trail}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from strings(value, f"{trail}[{index}]")


class AuthorityTests(unittest.TestCase):

    def test_the_tool_declares_no_authority(self):
        self.assertIs(drill.AUTHORITY, False)
        self.assertEqual(set(drill.AUTHORITY_FLAGS.values()), {False})
        for flag in ("routing_authority", "reasoning_authority",
                     "model_selection_authority", "merge_authority",
                     "deployment_authority", "evidence_authority",
                     "trading_authority"):
            self.assertIn(flag, drill.AUTHORITY_FLAGS, flag)

    def test_the_tool_invents_no_cryptography(self):
        for name in ("encrypt", "decrypt", "derive_key"):
            self.assertFalse(hasattr(drill, name), name)
        source = Path(drill.__file__).read_text(encoding="utf-8")
        self.assertIn("hashlib.sha256", source)

    def test_anchored_patterns_use_backslash_Z(self):
        source = Path(drill.__file__).read_text(encoding="utf-8")
        for line in source.splitlines():
            if "re.compile" in line:
                self.assertNotIn('$"', line, line)
                self.assertNotIn("$'", line, line)

    def test_the_gate_is_the_one_the_plan_names(self):
        self.assertEqual(drill.GATE, "DISASTER_RECOVERY_READY")


class StructuralGuardTests(unittest.TestCase):
    """The field list is derived from the checker table, not written twice."""

    def test_the_field_tuple_is_derived_from_the_check_table(self):
        self.assertEqual(drill.EVIDENCE_FIELDS, tuple(drill.FIELD_CHECKS))

    def test_the_check_table_matches_the_data_contract_in_both_directions(self):
        self.assertEqual(set(drill.EVIDENCE_FIELDS), set(CONTRACT_FIELDS))

    def test_every_string_field_is_bounded_by_pattern_and_length(self):
        for field in drill.FIELD_PATTERNS:
            self.assertIn(field, drill.FIELD_CHECKS, field)
            self.assertIn(field, drill.FIELD_MAX_LENGTHS, field)
            self.assertTrue(drill.FIELD_PATTERNS[field].pattern.endswith("\\Z"),
                            field)

    def test_a_field_with_no_checker_cannot_be_an_allowed_field(self):
        evidence = drill.run_drill(workspace=workspace(self), source_sha=SHA)
        document = drill.evidence_from(evidence)
        document["extra_field"] = "anything"
        with self.assertRaises(drill.EvidenceRejected):
            drill.assert_evidence_is_clean(document)

    def test_a_missing_field_is_refused(self):
        document = drill.evidence_from(run(self))
        for field in CONTRACT_FIELDS:
            partial = {k: v for k, v in document.items() if k != field}
            with self.assertRaises(drill.EvidenceRejected, msg=field):
                drill.assert_evidence_is_clean(partial)

    def test_an_unbounded_string_is_refused(self):
        document = drill.evidence_from(run(self))
        document["source_sha"] = "a" * 500
        with self.assertRaises(drill.EvidenceRejected):
            drill.assert_evidence_is_clean(document)

    def test_a_proof_outside_the_vocabulary_is_refused(self):
        document = drill.evidence_from(run(self))
        document["proofs"] = ["restored from /home/user/secret?token=abc123=pass"]
        with self.assertRaises(drill.EvidenceRejected):
            drill.assert_evidence_is_clean(document)

    def test_ready_true_with_a_failing_proof_is_refused(self):
        document = drill.evidence_from(run(self))
        document["proofs"] = [
            p.replace("=pass", "=fail") if p.startswith("restored_state_non_empty")
            else p for p in document["proofs"]]
        with self.assertRaises(drill.EvidenceRejected):
            drill.assert_evidence_is_clean(document)

    def test_ready_true_without_an_observed_removal_is_refused(self):
        document = drill.evidence_from(run(self))
        document["primary_removed_before_restore"] = False
        with self.assertRaises(drill.EvidenceRejected):
            drill.assert_evidence_is_clean(document)

    def test_ready_true_with_mismatched_identities_is_refused(self):
        document = drill.evidence_from(run(self))
        document["restored_identity"] = "unavailable"
        with self.assertRaises(drill.EvidenceRejected):
            drill.assert_evidence_is_clean(document)


class RealRestoreTests(unittest.TestCase):

    def setUp(self):
        self.work = workspace(self)
        self.result = drill.run_drill(workspace=self.work, source_sha=SHA)
        self.document = drill.evidence_from(self.result)

    def test_the_drill_is_ready_and_says_why(self):
        self.assertIs(self.document["ready"], True, self.document["proofs"])
        self.assertIs(self.document["integrity_verified"], True)
        self.assertEqual(self.document["gate"], "DISASTER_RECOVERY_READY")
        self.assertEqual(self.document["source_sha"], SHA)
        drill.assert_evidence_is_clean(self.document)

    def test_every_required_proof_is_present_and_passed(self):
        self.assertEqual(
            sorted(self.document["proofs"]),
            sorted(f"{name}=pass" for name in drill.REQUIRED_PROOFS))

    def test_the_sample_state_is_the_one_the_plan_names(self):
        self.assertEqual(drill.SAMPLE_STATE, {
            "project_id": "e2e-closure-test",
            "revision": 7,
            "payload": {"marker": "restore-me"},
        })

    def test_the_primary_really_was_removed_before_the_restore(self):
        self.assertIs(self.document["primary_removed_before_restore"], True)
        self.assertFalse(self.result["primary_root"].exists())
        # Observed, not asserted: the reading the drill recorded is the one the
        # filesystem gives now.
        self.assertEqual(
            self.document["primary_removed_before_restore"],
            not self.result["primary_root"].exists())

    def test_the_destination_was_observed_empty_before_the_restore(self):
        self.assertIs(self.document["restore_destination_was_empty"], True)
        self.assertEqual(self.result["destination_listing_before_restore"], [])

    def test_the_restored_bytes_are_byte_identical_to_the_protected_state(self):
        restored = self.result["restored_path"].read_bytes()
        self.assertTrue(restored)
        self.assertEqual(restored, drill.sample_state_bytes())
        self.assertEqual(json.loads(restored.decode("utf-8")), drill.SAMPLE_STATE)

    def test_the_restored_revision_matches_the_recorded_revision(self):
        self.assertEqual(self.result["recorded_revision"], 7)
        self.assertEqual(self.result["restored_revision"], 7)

    def test_the_identities_name_the_exact_artifact_and_agree(self):
        digest = hashlib.sha256(drill.sample_state_bytes()).hexdigest()
        expected = f"obj_{digest}@sha256:{digest}"
        self.assertEqual(self.document["backup_identity"], expected)
        self.assertEqual(self.document["restored_identity"], expected)

    def test_the_restored_index_is_a_real_validated_metadata_store(self):
        store = self.result["destination_store"]
        self.assertIsInstance(store, storage_metadata.MetadataStore)
        record = store.get_manifest(self.result["object_id"])
        self.assertIsNotNone(record)
        self.assertEqual(record["content_sha256"],
                         hashlib.sha256(drill.sample_state_bytes()).hexdigest())

    def test_nothing_was_written_outside_the_workspace(self):
        for path in self.result["paths_written"]:
            self.assertTrue(Path(path).resolve().is_relative_to(self.work), path)

    def test_no_emitted_string_escapes_the_bounded_vocabulary(self):
        for trail, value in strings(self.document):
            self.assertLessEqual(len(value), max(drill.FIELD_MAX_LENGTHS.values()),
                                 trail)


class FailClosedTests(unittest.TestCase):
    """Every one of these is ``ready=false``, and none of them raises."""

    def assert_failed(self, fault):
        document = drill.evidence_from(run(self, fault=fault))
        self.assertIs(document["ready"], False, fault)
        self.assertIs(document["integrity_verified"], False, fault)
        self.assertTrue(any(p.endswith("=fail") for p in document["proofs"]), fault)
        drill.assert_evidence_is_clean(document)
        return document

    def test_a_corrupt_backup_fails_closed(self):
        document = self.assert_failed("corrupt_backup")
        self.assertEqual(document["restored_identity"], "unavailable")

    def test_a_missing_backup_fails_closed(self):
        self.assert_failed("missing_backup")

    def test_an_empty_backup_object_fails_closed(self):
        self.assert_failed("empty_backup")

    def test_a_tampered_snapshot_fails_closed_through_the_production_gate(self):
        document = self.assert_failed("tampered_snapshot")
        self.assertIn("manifest_verification_ran=fail", document["proofs"])

    def test_an_unknown_source_sha_fails_closed(self):
        document = drill.evidence_from(
            drill.run_drill(workspace=workspace(self), source_sha=None))
        self.assertIs(document["ready"], False)
        self.assertEqual(document["source_sha"], "unknown")
        self.assertIn("evidence_bound_to_source_sha=fail", document["proofs"])

    def test_a_failure_never_echoes_its_input(self):
        for fault in drill.FAULTS:
            document = drill.evidence_from(run(self, fault=fault))
            for trail, value in strings(document):
                if trail.startswith(".proofs"):
                    self.assertTrue(drill.PROOF_RE.fullmatch(value),
                                    f"{fault}:{value}")

    def test_an_unknown_fault_is_refused_rather_than_ignored(self):
        with self.assertRaises(ValueError):
            drill.run_drill(workspace=workspace(self), source_sha=SHA,
                            fault="something-else")

    def test_a_non_empty_workspace_is_refused(self):
        work = workspace(self)
        (work / "already-here.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            drill.run_drill(workspace=work, source_sha=SHA)

    def test_a_workspace_inside_the_repository_is_refused(self):
        with self.assertRaises(ValueError):
            drill.run_drill(workspace=ROOT / "CHECKPOINTS", source_sha=SHA)


class RecoveryHookTests(unittest.TestCase):
    """The hooks added to the existing recovery modules, used by the drill."""

    def test_restore_into_store_refuses_something_that_is_not_a_store(self):
        with self.assertRaises(ValueError):
            storage_recovery.restore_into_store(object(), [], {})

    def test_restore_into_store_refuses_an_incomplete_restore(self):
        work = workspace(self)
        result = drill.run_drill(workspace=work, source_sha=SHA)
        snapshot = json.loads(
            (result["backup_root"] / drill.SNAPSHOT_NAME).read_text("utf-8"))
        store = drill.JsonFileMetadataStore(work / "second-index.json")
        with self.assertRaises(ValueError):
            # No provider observation at all: every object is unrecoverable.
            storage_recovery.restore_into_store(store, [], snapshot)
        self.assertEqual(store.list_manifests(), [])

    def test_scan_objects_reports_real_digests_and_sizes(self):
        work = workspace(self)
        (work / "a.json").write_bytes(b"{}")
        entries = survival_recovery.scan_objects(work)
        self.assertEqual([e["path"] for e in entries], ["a.json"])
        self.assertEqual(entries[0]["sha256"], hashlib.sha256(b"{}").hexdigest())
        self.assertEqual(entries[0]["size_bytes"], 2)

    def test_scan_objects_feeds_the_existing_verifier(self):
        work = workspace(self)
        (work / "a.json").write_bytes(b"{}")
        manifest = survival_recovery.create_recovery_manifest(
            survival_recovery.scan_objects(work), backup_id="b", created_at="t")
        report = survival_recovery.verify_restore(manifest, manifest)
        self.assertTrue(report.success, report.reasons)

    def test_scan_objects_is_bounded(self):
        work = workspace(self)
        for n in range(3):
            (work / f"{n}.json").write_bytes(b"{}")
        with self.assertRaises(ValueError):
            survival_recovery.scan_objects(work, max_objects=2)


class CommandLineTests(unittest.TestCase):

    def test_the_cli_writes_only_the_evidence_file_it_was_given(self):
        work = workspace(self)
        out = work / "STORAGE_RESTORE_DRILL.json"
        with contextlib.redirect_stdout(io.StringIO()):
            code = drill.main(["--source-sha", SHA, "--evidence", str(out)])
        self.assertEqual(code, 0)
        document = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(tuple(document), drill.EVIDENCE_FIELDS)
        drill.assert_evidence_is_clean(document)
        self.assertIs(document["ready"], True)
        self.assertEqual([p.name for p in work.iterdir()], [out.name])

    def test_strict_exits_non_zero_when_the_drill_fails(self):
        work = workspace(self)
        out = work / "evidence.json"
        with contextlib.redirect_stdout(io.StringIO()):
            code = drill.main(["--source-sha", SHA, "--evidence", str(out),
                               "--fault", "corrupt_backup", "--strict"])
        self.assertEqual(code, 1)
        self.assertIs(json.loads(out.read_text(encoding="utf-8"))["ready"], False)

    def test_the_default_evidence_path_is_the_one_the_plan_names(self):
        self.assertEqual(drill.DEFAULT_EVIDENCE,
                         "CHECKPOINTS/evidence/STORAGE_RESTORE_DRILL.json")


if __name__ == "__main__":
    unittest.main()
