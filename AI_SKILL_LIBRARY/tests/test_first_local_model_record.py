from __future__ import annotations

from copy import deepcopy
import importlib.util
import re
from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"
VALIDATOR = ROOT / "AI_SKILL_LIBRARY/v4/tools/validate_open_model_universe.py"
IMMUTABLE_REVISION = "1eaf4d9657fe65ad10a51eab76a8db5b363bddaa"
ARTIFACT_SHA256 = "9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031"
ARTIFACT_SIZE_BYTES = 639446688
ARTIFACT_FILENAME = "Qwen3-0.6B-Q8_0.gguf"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_open_model_universe", VALIDATOR)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {VALIDATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def registry_document() -> dict:
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AssertionError("Open Model Universe registry root must be a mapping")
    return data


class FirstLocalModelRecordTests(unittest.TestCase):
    def _record(self) -> dict:
        rows = registry_document().get("models")
        self.assertIsInstance(rows, list)
        self.assertEqual(len(rows), 1, "first inference lane must contain exactly one canonical local model record")
        self.assertIsInstance(rows[0], dict)
        return rows[0]

    def test_qwen3_q8_record_has_immutable_artifact_identity_and_no_runtime_authority(self):
        row = self._record()
        self.assertEqual(row["model_id"], "qwen3-0.6b-q8_0-gguf")
        self.assertEqual(row["family"], "Qwen3")
        self.assertEqual(row["variant"], "0.6B-Q8_0-GGUF")
        self.assertEqual(row["base_model"], "Qwen/Qwen3-0.6B")
        self.assertEqual(row["immutable_revision"], IMMUTABLE_REVISION)
        self.assertTrue(re.fullmatch(r"[0-9a-f]{40}", row["immutable_revision"]))
        self.assertEqual(row["upstream_revision"], IMMUTABLE_REVISION)
        self.assertNotIn(row["immutable_revision"].lower(), {"main", "master", "latest", "head", "stable"})
        self.assertEqual(row["artifact"]["filename"], ARTIFACT_FILENAME)
        self.assertEqual(row["artifact"]["format"], "GGUF")
        self.assertEqual(row["artifact"]["quantization"], "Q8_0")
        self.assertEqual(row["artifact"]["sha256"], ARTIFACT_SHA256)
        self.assertEqual(row["artifact"]["size_bytes"], ARTIFACT_SIZE_BYTES)
        self.assertEqual(row["runtime_support"], ["llama_cpp"])
        self.assertEqual(row["context_window"], 32768)
        self.assertIs(row["paid_token_required"], False)
        self.assertIs(row["zero_cost_eligible"], True)
        self.assertIs(row["offline_ready"], True)
        self.assertIs(row["authority"], False)

    def test_unknown_ram_is_preserved_and_first_load_stays_isolated(self):
        row = self._record()
        hardware = row["hardware_profile"]
        self.assertIsNone(hardware["minimum_ram_gb"])
        self.assertIsNone(hardware["recommended_ram_gb"])
        self.assertIsNone(hardware["minimum_vram_gb"])
        self.assertIsNone(hardware["recommended_vram_gb"])
        self.assertIs(hardware["cpu_viable"], True)
        admission = row["safe_admission"]
        self.assertIs(admission["safe_format"], True)
        self.assertEqual(admission["pickle_risk"], "none_known")
        self.assertIs(admission["trust_remote_code_required"], False)
        self.assertIs(admission["custom_code_required"], False)
        self.assertIs(admission["provenance_verified"], True)
        self.assertIs(admission["license_verified"], True)
        self.assertIs(admission["digest_verified"], False)
        self.assertIs(admission["isolated_first_load_required"], True)
        self.assertEqual(admission["egress_required"], "acquisition_only")
        self.assertTrue(row["admission_evidence"])

    def test_runtime_bearing_record_validates_and_missing_artifact_identity_fails_closed(self):
        document = registry_document()
        validator = load_validator()
        self.assertEqual(validator.validate_document(document), [])

        broken = deepcopy(document)
        broken["models"][0]["artifact"].pop("sha256")
        errors = validator.validate_document(broken)
        self.assertTrue(any("sha256" in error or "artifact" in error for error in errors), errors)

    def test_runtime_bearing_record_rejects_floating_revision_and_unverified_admission(self):
        document = registry_document()
        validator = load_validator()

        floating = deepcopy(document)
        floating["models"][0]["immutable_revision"] = "main"
        floating["models"][0]["upstream_revision"] = "main"
        errors = validator.validate_document(floating)
        self.assertTrue(any("revision" in error or "immutable" in error for error in errors), errors)

        unverified = deepcopy(document)
        unverified["models"][0]["safe_admission"]["provenance_verified"] = False
        errors = validator.validate_document(unverified)
        self.assertTrue(any("provenance" in error or "admission" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
