import json
import tempfile
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.tools.discover_free_models import (
    discover,
    merge_candidates,
    parse_models_dev,
    parse_opencode_zen,
    parse_portkey_models,
)
from AI_SKILL_LIBRARY.v4.tools.model_mesh import eligible_free_candidate


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "AI_SKILL_LIBRARY/tests/fixtures/model_mesh"
OBSERVED = "2026-09-15T05:00:00Z"


class AdaptiveFreeModelMeshDiscoveryTests(unittest.TestCase):
    def _json(self, name: str):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def test_models_dev_catalog_never_implies_free_entitlement(self):
        rows = parse_models_dev(self._json("models_dev.json"), OBSERVED)
        self.assertGreaterEqual(len(rows), 3)
        by_key = {(row["provider_id"], row["model_id"]): row for row in rows}
        candidate = by_key[("openrouter", "example/free-labelled-model")]
        self.assertEqual(candidate["free_status"], "unknown")
        self.assertIsNone(candidate["free_verified_at"])
        self.assertFalse(eligible_free_candidate(candidate, data_class="PUBLIC"))

    def test_opencode_free_suffix_is_discovery_evidence_not_entitlement(self):
        rows = parse_opencode_zen(self._json("opencode_zen.json"), OBSERVED)
        candidate = next(row for row in rows if row["model_id"] == "deepseek-v4-flash-free")
        self.assertEqual(candidate["provider_id"], "opencode_zen")
        self.assertEqual(candidate["free_status"], "unknown")
        self.assertFalse(eligible_free_candidate(candidate, data_class="PUBLIC"))

    def test_portkey_zero_price_is_not_account_free_entitlement(self):
        rows = parse_portkey_models(self._json("portkey_models.json"), OBSERVED)
        candidate = next(row for row in rows if row["model_id"] == "gpt-oss-120b")
        self.assertEqual(candidate["provider_id"], "groq")
        self.assertEqual(candidate["free_status"], "unknown")
        self.assertFalse(eligible_free_candidate(candidate, data_class="PUBLIC"))

    def test_merge_candidates_dedupes_provider_model_and_preserves_evidence(self):
        models_dev = parse_models_dev(self._json("models_dev.json"), OBSERVED)
        portkey = parse_portkey_models(self._json("portkey_models.json"), OBSERVED)
        merged = merge_candidates(models_dev, portkey)
        duplicates = [row for row in merged if row["provider_id"] == "groq" and row["model_id"] == "gpt-oss-120b"]
        self.assertEqual(len(duplicates), 1)
        self.assertGreaterEqual(len(duplicates[0]["source_evidence"]), 2)
        self.assertEqual(duplicates[0]["free_status"], "unknown")

    def test_fixture_discovery_is_quarantine_only_and_writes_report(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "candidates.json"
            report = discover(output=output, fixture_dir=FIXTURES)
            self.assertTrue(output.is_file())
            self.assertEqual(report["state"], "quarantine")
            self.assertFalse(report["routing_authority"])
            self.assertFalse(report["stable_mutation"])
            self.assertGreaterEqual(len(report["candidates"]), 6)
            self.assertTrue(all(row["free_status"] == "unknown" for row in report["candidates"]))
            persisted = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(persisted, report)


if __name__ == "__main__":
    unittest.main()
