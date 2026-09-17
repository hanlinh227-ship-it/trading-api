import unittest

from AI_SKILL_LIBRARY.v4.local_runtime.identity import (
    ArtifactIdentity,
    IdentityError,
    from_record,
    missing_identity_fields,
)

SHA = "9" * 64
OTHER_SHA = "a" * 64


def identity(**kwargs):
    base = dict(
        model_id="qwen3-0.6b",
        family="qwen3",
        variant="0.6b-instruct",
        immutable_revision="0123456789abcdef0123456789abcdef01234567",
        artifact_sha256=SHA,
        artifact_format="gguf",
        quantization="Q8_0",
        artifact_size_bytes=639_000_000,
        artifact_filename="Qwen3-0.6B-Q8_0.gguf",
    )
    base.update(kwargs)
    return ArtifactIdentity(**base)


class ConstructionTests(unittest.TestCase):
    def test_a_complete_identity_constructs(self):
        self.assertEqual(identity().quantization, "Q8_0")

    def test_every_required_field_is_required(self):
        for name in ("model_id", "family", "variant", "immutable_revision",
                     "artifact_sha256", "artifact_format", "quantization"):
            with self.subTest(name=name):
                with self.assertRaises(IdentityError):
                    identity(**{name: ""})

    def test_a_floating_revision_is_refused(self):
        for revision in ("main", "latest", "HEAD", "dev"):
            with self.subTest(revision=revision):
                with self.assertRaises(IdentityError):
                    identity(immutable_revision=revision)

    def test_a_malformed_digest_is_refused(self):
        for digest in ("not-a-hash", "abc", "9" * 63, "Z" * 64):
            with self.subTest(digest=digest):
                with self.assertRaises(IdentityError):
                    identity(artifact_sha256=digest)

    def test_a_non_positive_size_is_refused(self):
        with self.assertRaises(IdentityError):
            identity(artifact_size_bytes=0)

    def test_size_may_be_absent(self):
        self.assertIsNone(identity(artifact_size_bytes=None).artifact_size_bytes)


class DistinguishabilityTests(unittest.TestCase):
    def test_quantization_changes_the_fingerprint(self):
        # The failure this type exists to prevent: Q4 and Q8 are not one model.
        self.assertNotEqual(identity(quantization="Q4_K_M").fingerprint, identity().fingerprint)

    def test_revision_changes_the_fingerprint(self):
        self.assertNotEqual(identity(immutable_revision="f" * 40).fingerprint, identity().fingerprint)

    def test_content_hash_changes_the_fingerprint(self):
        self.assertNotEqual(identity(artifact_sha256=OTHER_SHA).fingerprint, identity().fingerprint)

    def test_format_changes_the_fingerprint(self):
        self.assertNotEqual(identity(artifact_format="safetensors").fingerprint, identity().fingerprint)

    def test_filename_and_size_do_not_change_the_fingerprint(self):
        # Neither identifies content: a rename is not a different artifact.
        self.assertEqual(identity(artifact_filename="renamed.gguf").fingerprint, identity().fingerprint)
        self.assertEqual(identity(artifact_size_bytes=1).fingerprint, identity().fingerprint)

    def test_the_fingerprint_is_stable_across_instances(self):
        self.assertEqual(identity().fingerprint, identity().fingerprint)

    def test_matches_compares_by_fingerprint(self):
        self.assertTrue(identity().matches(identity()))
        self.assertFalse(identity().matches(identity(quantization="Q4_K_M")))

    def test_the_cache_key_is_never_the_model_id_alone(self):
        key = identity().cache_key
        self.assertNotEqual(key, "qwen3-0.6b")
        self.assertIn("Q8_0", key)
        self.assertNotEqual(identity(quantization="Q4_K_M").cache_key, key)

    def test_the_cache_key_is_filesystem_safe(self):
        key = identity(model_id="org/model:v1").cache_key
        self.assertNotIn("/", key)
        self.assertNotIn(":", key)


class FromRecordTests(unittest.TestCase):
    def _record(self, **overrides):
        base = {
            "model_id": "qwen3-0.6b",
            "family": "qwen3",
            "variant": "0.6b-instruct",
            "upstream_revision": "0123456789abcdef0123456789abcdef01234567",
            "artifact_sha256": SHA,
            "artifact_format": "gguf",
            "quantization": "Q8_0",
            "artifact_size_bytes": 639_000_000,
            "artifact_filename": "Qwen3-0.6B-Q8_0.gguf",
        }
        base.update(overrides)
        return base

    def test_a_complete_record_builds_an_identity(self):
        built, reasons = from_record(self._record())
        self.assertIsNotNone(built)
        self.assertEqual(reasons, ())
        self.assertEqual(built.artifact_format, "gguf")

    def test_an_incomplete_record_reports_reasons_rather_than_raising(self):
        built, reasons = from_record({"model_id": "x"})
        self.assertIsNone(built)
        self.assertTrue(reasons)
        self.assertTrue(all("absent" in reason for reason in reasons))

    def test_the_empty_registry_row_names_every_missing_field(self):
        self.assertEqual(
            set(missing_identity_fields({})),
            {"model_id", "family", "variant", "immutable_revision",
             "artifact_sha256", "artifact_format", "quantization"},
        )

    def test_a_floating_revision_in_a_record_is_reported_not_raised(self):
        built, reasons = from_record(self._record(upstream_revision="main"))
        self.assertIsNone(built)
        self.assertTrue(any("floating" in reason for reason in reasons))

    def test_format_is_normalised(self):
        built, _ = from_record(self._record(artifact_format=".GGUF"))
        self.assertEqual(built.artifact_format, "gguf")

    def test_the_legacy_artifact_hash_key_is_accepted(self):
        record = self._record()
        record["artifact_hash"] = record.pop("artifact_sha256")
        built, reasons = from_record(record)
        self.assertIsNotNone(built, reasons)

    def test_identity_is_json_safe(self):
        import json
        payload = identity().to_dict()
        self.assertEqual(json.loads(json.dumps(payload))["quantization"], "Q8_0")
        self.assertIn("fingerprint", payload)


if __name__ == "__main__":
    unittest.main()
