"""Two tools, two identifier spaces, and one of them admits nothing.

The production golden worker failed twice on the same misunderstanding, so the
contract is pinned here rather than rediscovered on a runner:

* `local_runtime_staging_verify` filters the staging manifest by the manifest's
  own ``id`` and looks for the staged file under the manifest's ``filename``. It
  does NOT take a registry model_id, and passing one filters every entry out -
  producing ``total=0`` with ``INCOMPLETE``, which reads like a verification
  failure when nothing was verified at all.
* It also admits nothing. Its own output says ``admits_nothing: true``. The
  artifact reaches the trusted cache only through `intake_staged_artifact`,
  which takes the REGISTRY model_id.

Synthetic artifacts throughout: a real admitted GGUF is 639 MB and a test that
needs one is a test that does not run.
"""

import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent.parent
sys.path.insert(0, str(ROOT))

from AI_SKILL_LIBRARY.v4.local_runtime.staging import (  # noqa: E402
    IntakeStatus, cached_artifact_path, intake_staged_artifact)

_spec = importlib.util.spec_from_file_location(
    "local_runtime_staging_verify",
    ROOT / "AI_SKILL_LIBRARY/v4/tools/local_runtime_staging_verify.py")
verify = importlib.util.module_from_spec(_spec)
sys.modules["local_runtime_staging_verify"] = verify
_spec.loader.exec_module(verify)

MANIFEST = ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/staging_manifest.json"
REGISTRY_MODEL_ID = "Qwen/Qwen3-0.6B-GGUF"
MANIFEST_ID = "qwen3-0.6b-q8_0"


def _manifest_entry(entry_id):
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))["entries"]
    return next(e for e in entries if e["id"] == entry_id)


class IdentifierSpaceTests(unittest.TestCase):
    """The lookup miss that cost the first run."""

    def test_the_manifest_id_is_not_the_registry_model_id(self):
        entry = _manifest_entry(MANIFEST_ID)
        self.assertEqual(entry["hf_repo"], REGISTRY_MODEL_ID)
        self.assertNotEqual(entry["id"], REGISTRY_MODEL_ID)

    def test_a_registry_model_id_selects_nothing(self):
        entries = json.loads(MANIFEST.read_text(encoding="utf-8"))["entries"]
        selected = [e for e in entries if e["id"] == REGISTRY_MODEL_ID]
        self.assertEqual(
            selected, [],
            "passing a registry model_id as --only filters every entry out, "
            "and 'INCOMPLETE over zero rows' is not a verification failure")

    def test_every_manifest_entry_resolves_from_its_hf_repo(self):
        """The mapping the workflow uses, rather than a hand-typed table."""
        entries = json.loads(MANIFEST.read_text(encoding="utf-8"))["entries"]
        repos = [e.get("hf_repo") for e in entries]
        self.assertEqual(len(repos), len(set(repos)), "hf_repo must be unique")
        for entry in entries:
            self.assertTrue(entry.get("filename"))
            self.assertTrue(entry.get("expected_sha256"))


class StagingVerifyTests(unittest.TestCase):
    """Discovery and refusal, against a synthetic entry."""

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.staging = Path(self._tmp.name) / "staging"
        self.staging.mkdir()
        self.payload = b"GGUF" + b"\x00" * 512
        self.entry = {
            "id": "synthetic-entry",
            "filename": "synthetic.gguf",
            "expected_sha256": hashlib.sha256(self.payload).hexdigest(),
            "size_bytes": len(self.payload),
            "immutable_revision": "0" * 40,
        }

    def tearDown(self):
        self._tmp.cleanup()

    def _stage(self, payload=None):
        target = self.staging / self.entry["filename"]
        target.write_bytes(self.payload if payload is None else payload)
        return target

    def test_a_missing_file_is_reported_as_not_downloaded(self):
        row = verify.verify_entry(self.entry, self.staging)
        self.assertFalse(row["verified"])
        self.assertIn("not downloaded", row["reason"])

    def test_a_wrong_digest_fails_and_is_never_scanned(self):
        self._stage(b"GGUF" + b"\x01" * 512)
        row = verify.verify_entry(self.entry, self.staging)
        self.assertFalse(row["verified"])
        self.assertIn("sha256", row["reason"])
        # Bytes that are not what they claim must not reach the scanner.
        self.assertNotIn("structural_scan", row)

    def test_a_wrong_size_fails(self):
        short = self.payload[:-8]
        entry = dict(self.entry, expected_sha256=hashlib.sha256(short).hexdigest())
        self._stage(short)
        row = verify.verify_entry(entry, self.staging)
        self.assertFalse(row["verified"])
        self.assertIn("size", row["reason"])

    def test_a_digest_match_still_needs_a_structural_scan(self):
        """Matching bytes are necessary and not sufficient.

        The synthetic payload has the right digest by construction and is not a
        real GGUF, so this must still refuse - which is what stops a
        digest-only check from admitting a well-named file of noise.
        """
        self._stage()
        row = verify.verify_entry(self.entry, self.staging)
        self.assertEqual(row["sha256"], self.entry["expected_sha256"])
        self.assertIn("structural_scan", row)
        self.assertFalse(row["verified"])


class AdmissionTests(unittest.TestCase):
    """Verification is not admission, and the tools say so."""

    def test_the_verifier_declares_that_it_admits_nothing(self):
        source = (ROOT / "AI_SKILL_LIBRARY/v4/tools/local_runtime_staging_verify.py"
                  ).read_text(encoding="utf-8")
        self.assertIn('"admits_nothing": True', source)

    def test_the_verifier_leaves_the_cache_empty(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            cache = Path(tmp) / "cache"
            staging.mkdir()
            cache.mkdir()
            rc = verify.main(["--staging", str(staging), "--cache", str(cache),
                              "--only", MANIFEST_ID])
            self.assertEqual(rc, 1)
            self.assertEqual(list(cache.rglob("*.gguf")), [],
                             "the verifier must never populate the cache")

    def test_intake_refuses_bytes_that_do_not_match_the_record(self):
        import tempfile
        import yaml
        rows = yaml.safe_load(
            (ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml")
            .read_text(encoding="utf-8"))["models"]
        record = next(r for r in rows if r["model_id"] == REGISTRY_MODEL_ID)
        with tempfile.TemporaryDirectory() as tmp:
            staged = Path(tmp) / "wrong.gguf"
            staged.write_bytes(b"not the artifact")
            result = intake_staged_artifact(staged, record, root=Path(tmp) / "cache")
            self.assertFalse(result.verified)
            self.assertIn(result.status,
                          (IntakeStatus.SIZE_MISMATCH, IntakeStatus.DIGEST_MISMATCH,
                           IntakeStatus.FORMAT_REJECTED))

    def test_intake_refuses_a_missing_file(self):
        import tempfile
        import yaml
        rows = yaml.safe_load(
            (ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml")
            .read_text(encoding="utf-8"))["models"]
        record = next(r for r in rows if r["model_id"] == REGISTRY_MODEL_ID)
        with tempfile.TemporaryDirectory() as tmp:
            result = intake_staged_artifact(
                Path(tmp) / "absent.gguf", record, root=Path(tmp) / "cache")
            self.assertFalse(result.verified)
            self.assertEqual(result.status, IntakeStatus.MISSING)

    def test_the_accepting_statuses_are_the_dataclass_predicate(self):
        """Never a second list of which statuses count as success."""
        for status in IntakeStatus:
            expected = status in (IntakeStatus.VERIFIED, IntakeStatus.ALREADY_CACHED)
            from AI_SKILL_LIBRARY.v4.local_runtime.staging import IntakeResult
            self.assertEqual(
                IntakeResult(status=status, reason="").verified, expected, status)

    def test_the_workflow_reads_the_predicate_rather_than_listing_statuses(self):
        workflow = (ROOT / ".github/workflows/production-golden-e2e.yml"
                    ).read_text(encoding="utf-8")
        self.assertIn('intake.get("verified")', workflow)
        self.assertIn("local_runtime_intake.py", workflow)
        self.assertIn("local_runtime_staging_verify.py", workflow)


if __name__ == "__main__":
    unittest.main()


class SelectionPreviewTests(unittest.TestCase):
    """The workflow must stage what the mesh picks, not what is cheapest."""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "golden_selection_preview",
            ROOT / "AI_SKILL_LIBRARY/v4/tools/golden_selection_preview.py")
        cls.preview = importlib.util.module_from_spec(spec)
        sys.modules["golden_selection_preview"] = cls.preview
        spec.loader.exec_module(cls.preview)
        cls.report = cls.preview.preview(ROOT)

    def test_the_mesh_names_a_model_and_a_digest(self):
        self.assertEqual(self.report["status"], "SELECTED")
        self.assertTrue(self.report["selected_model_id"])
        self.assertEqual(len(self.report["artifact_sha256"]), 64)

    def test_the_selection_is_not_the_cheapest_download(self):
        """Recorded because assuming otherwise cost two runs.

        If a future measurement makes the mesh pick the small model, this test
        should be rewritten to say so - not deleted to make the workflow's old
        guess look right.
        """
        self.assertNotEqual(self.report["selected_model_id"],
                            "HuggingFaceTB/SmolLM2-360M-Instruct-GGUF")
        self.assertNotEqual(self.report["selected_model_id"],
                            "Qwen/Qwen3-0.6B-GGUF")

    def test_the_selected_model_is_admitted_and_stageable(self):
        import yaml
        rows = yaml.safe_load(
            (ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml")
            .read_text(encoding="utf-8"))["models"]
        row = next(r for r in rows
                   if r["model_id"] == self.report["selected_model_id"])
        self.assertEqual(row["lifecycle_state"], "AVAILABLE")
        self.assertEqual(row["artifact_identity"]["sha256"],
                         self.report["artifact_sha256"])
        entries = json.loads(MANIFEST.read_text(encoding="utf-8"))["entries"]
        entry = next(e for e in entries
                     if e["hf_repo"] == self.report["selected_model_id"])
        self.assertEqual(entry["expected_sha256"], self.report["artifact_sha256"])

    def test_the_preview_claims_no_selection_authority(self):
        self.assertFalse(self.preview.AUTHORITY)
        self.assertFalse(self.preview.MODEL_SELECTION_AUTHORITY)
        self.assertFalse(self.report["model_selection_authority"])

    def test_the_preview_runs_the_same_stages_as_the_real_chain(self):
        # A preview that skipped a stage could preview a different answer from
        # the one the run makes.
        self.assertEqual(self.report["routed_by"], "task_router")
        self.assertTrue(self.report["specialist_group"])

    def test_the_workflow_asks_the_mesh_rather_than_naming_a_model(self):
        workflow = (ROOT / ".github/workflows/production-golden-e2e.yml"
                    ).read_text(encoding="utf-8")
        self.assertIn("golden_selection_preview.py", workflow)
        self.assertIn("steps.selection.outputs.model_id", workflow)
        self.assertNotIn("default: \"Qwen/Qwen3-0.6B-GGUF\"", workflow)


class CacheIdentityRoundTripTests(unittest.TestCase):
    """One identity builder, and a key that changes when the artifact does.

    Run 3 failed with "no verified artifact cached for this identity" after a
    VERIFIED intake, which looks like a normalisation bug between the writer and
    the reader. It is not. Both sides build the identity with the same
    `from_record` and resolve the path with the same `cached_artifact_path`; the
    keys differed because they were different models. These tests pin the part
    that would have made it a real bug, so the next occurrence can be told apart
    from this one.
    """

    @staticmethod
    def _record(model_id):
        import yaml
        rows = yaml.safe_load(
            (ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml")
            .read_text(encoding="utf-8"))["models"]
        return next(r for r in rows if r["model_id"] == model_id)

    def test_the_writer_and_the_reader_use_one_builder(self):
        import inspect
        from AI_SKILL_LIBRARY.v4.local_runtime import staging
        write = inspect.getsource(staging.intake_staged_artifact)
        read = inspect.getsource(staging.resolve_cached)
        for source in (write, read):
            self.assertIn("from_record", source)
            self.assertIn("cached_artifact_path", source)

    def test_one_record_yields_one_path(self):
        from AI_SKILL_LIBRARY.v4.local_runtime.identity import from_record
        from AI_SKILL_LIBRARY.v4.local_runtime.staging import cached_artifact_path
        record = self._record("Qwen/Qwen3-8B-GGUF")
        first, _ = from_record(record)
        second, _ = from_record(dict(record))
        self.assertEqual(first.cache_key, second.cache_key)
        self.assertEqual(cached_artifact_path(Path("/c"), first),
                         cached_artifact_path(Path("/c"), second))

    def test_the_cache_root_passed_in_is_the_one_used(self):
        from AI_SKILL_LIBRARY.v4.local_runtime.identity import from_record
        from AI_SKILL_LIBRARY.v4.local_runtime.staging import cached_artifact_path
        identity, _ = from_record(self._record("Qwen/Qwen3-8B-GGUF"))
        self.assertTrue(
            str(cached_artifact_path(Path("/given/root"), identity))
            .startswith("/given/root"))

    def test_a_different_model_is_a_different_key(self):
        """Why run 3 refused: two correct identities, two different models."""
        from AI_SKILL_LIBRARY.v4.local_runtime.identity import from_record
        small, _ = from_record(self._record("Qwen/Qwen3-0.6B-GGUF"))
        large, _ = from_record(self._record("Qwen/Qwen3-8B-GGUF"))
        self.assertNotEqual(small.cache_key, large.cache_key)

    def test_a_different_digest_is_a_different_key(self):
        from AI_SKILL_LIBRARY.v4.local_runtime.identity import from_record
        record = self._record("Qwen/Qwen3-8B-GGUF")
        tampered = json.loads(json.dumps(record))
        tampered["artifact_identity"]["sha256"] = "b" * 64
        original, _ = from_record(record)
        changed, _ = from_record(tampered)
        self.assertNotEqual(original.cache_key, changed.cache_key)

    def test_a_contradicted_revision_is_refused_rather_than_rekeyed(self):
        """Stronger than I expected, and worth pinning.

        I wrote this expecting a different revision to yield a different cache
        key. It yields no identity at all: the row states its revision twice -
        `upstream_revision` and `artifact_identity.immutable_revision` - and
        `from_record` refuses when they disagree rather than picking one. A
        record that contradicts itself cannot name an artifact, which is the
        right answer and a better one than re-keying.
        """
        from AI_SKILL_LIBRARY.v4.local_runtime.identity import from_record
        record = self._record("Qwen/Qwen3-8B-GGUF")
        tampered = json.loads(json.dumps(record))
        tampered["artifact_identity"]["immutable_revision"] = "0" * 40
        identity, reasons = from_record(tampered)
        self.assertIsNone(identity)
        self.assertTrue(reasons)

    def test_a_consistently_different_revision_is_a_different_key(self):
        from AI_SKILL_LIBRARY.v4.local_runtime.identity import from_record
        record = self._record("Qwen/Qwen3-8B-GGUF")
        tampered = json.loads(json.dumps(record))
        tampered["artifact_identity"]["immutable_revision"] = "0" * 40
        tampered["upstream_revision"] = "0" * 40
        original, _ = from_record(record)
        changed, reasons = from_record(tampered)
        self.assertIsNotNone(changed, reasons)
        self.assertNotEqual(original.cache_key, changed.cache_key)

    def test_an_empty_cache_resolves_nothing(self):
        import tempfile
        from AI_SKILL_LIBRARY.v4.local_runtime.staging import resolve_cached
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(
                resolve_cached(Path(tmp), self._record("Qwen/Qwen3-8B-GGUF")))

    def test_staging_one_model_does_not_satisfy_another(self):
        """The invariant run 3 actually hit, stated directly."""
        import tempfile
        from AI_SKILL_LIBRARY.v4.local_runtime.identity import from_record
        from AI_SKILL_LIBRARY.v4.local_runtime.staging import (
            cached_artifact_path, resolve_cached)
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            small, _ = from_record(self._record("Qwen/Qwen3-0.6B-GGUF"))
            planted = cached_artifact_path(cache, small)
            planted.parent.mkdir(parents=True, exist_ok=True)
            planted.write_bytes(b"whatever")
            # A cache holding the small model answers nothing about the large
            # one, which is exactly what "no verified artifact cached for this
            # identity" was reporting.
            self.assertIsNone(
                resolve_cached(cache, self._record("Qwen/Qwen3-8B-GGUF")))
