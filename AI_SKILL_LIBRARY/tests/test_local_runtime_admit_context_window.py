"""A context window must come from the artifact, or admission must refuse.

`context_window_of` deliberately returns None rather than a default, because a
guessed window truncates or over-allocates at load. The renderer then wrote
`context_window: 0` for that None, which is not a refusal -- it is a guess that
happens to be invalid, and it reached the registry and failed schema validation
only afterwards. Admission should not be able to emit a record it knows is wrong.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.tools import local_runtime_admit as admit

ROOT = Path(__file__).resolve().parents[2]


class ContextWindowIsEvidenceNotADefaultTests(unittest.TestCase):
    ENTRY = {"id": "x", "family": "f", "variant": "v", "filename": "x.gguf",
             "hf_repo": "org/model"}
    RECORD = {
        "model_id": "org/model", "family": "f", "variant": "v",
        "sha256": "a" * 64, "size_bytes": 1,
        "immutable_revision": "b" * 40, "quantization": "Q4_K_M",
        "license_declared": "apache-2.0", "malware_scan_status": "pass",
        "lifecycle_state": "AVAILABLE", "admission_gaps": [], "mesh_eligible": True,
        "structural_scan": {"status": "pass"}, "capabilities": {"text_reasoning": 0.0},
    }

    def test_unknown_context_window_refuses_instead_of_writing_zero(self):
        with self.assertRaises(admit.AdmissionRefused) as caught:
            admit.render_record(self.ENTRY, self.RECORD, None, "apache-2.0")
        self.assertIn("context_window", str(caught.exception))

    def test_a_known_context_window_is_rendered(self):
        block = admit.render_record(self.ENTRY, self.RECORD, 4096, "apache-2.0")
        self.assertIn("context_window: 4096", block)
        self.assertNotIn("context_window: 0", block)

    def test_the_shipped_registry_declares_a_real_window_for_every_model(self):
        import yaml
        registry = yaml.safe_load(
            (ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml").read_text(encoding="utf-8"))
        for record in registry["models"]:
            window = record.get("context_window")
            self.assertIsInstance(window, int, record["model_id"])
            self.assertGreater(window, 0, f"{record['model_id']} carries a placeholder window")

    def test_context_window_is_read_from_the_artifact_header(self):
        # The values in the registry must be the ones the bytes declare.
        import glob
        from AI_SKILL_LIBRARY.v4.local_runtime.scanner import gguf_metadata
        found = False
        for path in glob.glob(str(ROOT / ".model-cache/models/*/*.gguf")):
            metadata = gguf_metadata(Path(path))
            architecture = metadata.get("general.architecture")
            if not architecture:
                continue
            declared = metadata.get(f"{architecture}.context_length")
            if isinstance(declared, int):
                self.assertEqual(admit.context_window_of(Path(path)), declared)
                found = True
        if not found:
            self.skipTest("no cached artifact available in this environment")


if __name__ == "__main__":
    unittest.main()
