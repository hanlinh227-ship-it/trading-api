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
