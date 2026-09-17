"""Wave selection: bounded and diverse, or it is just a download queue.

Prefetch is deliberately broad. Admission is deliberately not. These tests pin
the two rules that keep a wave from becoming "everything that was staged", and
the property that matters more than either: selecting a model grants it nothing.
"""

import json
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.tools.local_runtime_select_wave import (
    family_of,
    manifest_entry,
    select,
    slug,
    tier_of,
)

ROOT = Path(__file__).resolve().parents[2]
SELECTION = ROOT / "CHECKPOINTS/evidence/WAVE2_SELECTION_EVIDENCE.json"
MANIFEST = ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/staging_manifest.json"


def entry(repo, filename, size, present=True):
    return {"repo_id": repo, "filename": filename, "size_bytes": size,
            "weights_present_in_artifact": present, "sha256": "a" * 64,
            "source_run_id": 1, "artifact_name": "art",
            "immutable_revision": "b" * 40}


class TierTests(unittest.TestCase):
    def test_tiers_follow_the_brief(self):
        self.assertEqual(tier_of(500_000_000), "S")
        self.assertEqual(tier_of(2_000_000_000), "A")
        self.assertEqual(tier_of(5_000_000_000), "B")
        self.assertEqual(tier_of(9_000_000_000), "C")


class SlugTests(unittest.TestCase):
    def test_multi_underscore_quantization_survives(self):
        self.assertEqual(slug("ibm-granite/granite-4.2-3b-GGUF",
                              "granite-4.2-3b-Q4_K_M.gguf"), "granite-4.2-3b-gguf-q4-k-m")

    def test_an_unusual_quantization_tag_is_still_read(self):
        self.assertIn("i2-s", slug("microsoft/bitnet-b1.58-2B-4T-gguf", "ggml-model-i2_s.gguf"))

    def test_slugs_are_filesystem_and_tag_safe(self):
        for text in ("Qwen/Qwen3-VL-8B-Thinking-GGUF", "a/b c_d"):
            with self.subTest(text=text):
                self.assertRegex(slug(text, "x-Q4_0.gguf"), r"^[a-z0-9.-]+$")


class FamilyTests(unittest.TestCase):
    def test_variants_of_one_model_share_a_family(self):
        self.assertEqual(family_of("HuggingFaceTB/SmolLM2-360M-Instruct-GGUF"),
                         family_of("HuggingFaceTB/SmolLM2-1.7B-Instruct-GGUF"))

    def test_different_models_do_not(self):
        self.assertNotEqual(family_of("ibm-granite/granite-4.2-3b-GGUF"),
                            family_of("microsoft/Phi-3-mini-4k-instruct-gguf"))

    def test_a_vision_variant_is_not_the_same_family_as_the_text_model(self):
        """They answer different needs; one must not crowd out the other."""
        self.assertNotEqual(family_of("Qwen/Qwen3-VL-8B-Thinking-GGUF"),
                            family_of("Qwen/Qwen3-4B-GGUF"))


class SelectionTests(unittest.TestCase):
    def index(self, entries):
        return {"wave": "t", "entries": entries}

    def test_an_oversized_model_is_deferred_with_its_reason(self):
        chosen, deferred = select(self.index([entry("a/big", "big-Q4_K_M.gguf", 9_000_000_000)]),
                                  max_bytes=2_500_000_000, max_models=6, per_family=1)
        self.assertEqual(chosen, [])
        self.assertIn("exceeds", deferred[0]["deferred_because"])

    def test_a_second_model_of_the_same_family_is_deferred(self):
        rows = [entry("h/SmolLM2-360M-Instruct-GGUF", "s-q8_0.gguf", 300_000_000),
                entry("h/SmolLM2-1.7B-Instruct-GGUF", "s-q4_k_m.gguf", 900_000_000)]
        chosen, deferred = select(self.index(rows), max_bytes=2_500_000_000,
                                  max_models=6, per_family=1)
        self.assertEqual(len(chosen), 1)
        self.assertIn("already selected", deferred[0]["deferred_because"])

    def test_the_wave_is_bounded_by_count(self):
        rows = [entry(f"p{i}/m{i}", f"m{i}-q4_0.gguf", 100_000_000) for i in range(10)]
        chosen, deferred = select(self.index(rows), max_bytes=2_500_000_000,
                                  max_models=3, per_family=1)
        self.assertEqual(len(chosen), 3)
        self.assertTrue(all("bounded at 3" in d["deferred_because"] for d in deferred))

    def test_an_artifact_without_weights_is_never_selected(self):
        chosen, _ = select(self.index([entry("a/b", "b-q4_0.gguf", 100, present=False)]),
                           max_bytes=2_500_000_000, max_models=6, per_family=1)
        self.assertEqual(chosen, [])

    def test_smaller_models_are_considered_first(self):
        """So a wave's budget is not spent on one large artifact by accident."""
        rows = [entry("a/large", "l-q4_0.gguf", 2_000_000_000),
                entry("b/small", "s-q4_0.gguf", 300_000_000)]
        chosen, _ = select(self.index(rows), max_bytes=2_500_000_000,
                           max_models=1, per_family=1)
        self.assertEqual(chosen[0]["repo_id"], "b/small")


class ManifestEntryTests(unittest.TestCase):
    def test_a_selected_entry_records_its_licence_gap(self):
        """Selection must not look like admission.

        The prefetch index carries no licence, and the entry says so rather
        than leaving the field quietly absent.
        """
        row = manifest_entry(entry("a/b-GGUF", "b-Q4_K_M.gguf", 100))
        self.assertIn("never inferred", row["license_gap"])

    def test_provenance_is_recorded_as_pinned_at_download(self):
        row = manifest_entry(entry("a/b-GGUF", "b-Q4_K_M.gguf", 100))
        self.assertEqual(row["revision_status"], "pinned_at_download")
        self.assertEqual(len(row["immutable_revision"]), 40)


class CommittedSelectionTests(unittest.TestCase):
    def setUp(self):
        if not SELECTION.is_file():
            self.skipTest("no wave selection committed")
        self.selection = json.loads(SELECTION.read_text(encoding="utf-8"))

    def test_the_committed_wave_is_bounded(self):
        self.assertLessEqual(self.selection["selected"], 12)
        self.assertTrue(self.selection["admits_nothing"])

    def test_every_selected_model_is_a_different_family(self):
        families = [family_of(e["hf_repo"]) for e in self.selection["entries"]]
        self.assertEqual(len(families), len(set(families)))

    def test_every_deferral_gives_a_reason(self):
        for row in self.selection["deferrals"]:
            with self.subTest(repo_id=row["repo_id"]):
                self.assertTrue(row["deferred_because"].strip())

    def test_selected_models_are_in_the_transport_manifest_only(self):
        """Transport state, not governance state - they are not registry rows."""
        import yaml
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        registry = yaml.safe_load(
            (ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml").read_text(encoding="utf-8"))
        registered = {m["artifact_identity"]["sha256"] for m in registry["models"]}
        for row in self.selection["entries"]:
            with self.subTest(model=row["id"]):
                self.assertIn(row["expected_sha256"],
                              {e["expected_sha256"] for e in manifest["entries"]})
                self.assertNotIn(row["expected_sha256"], registered)


if __name__ == "__main__":
    unittest.main()
