from pathlib import Path
import importlib.util
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "AI_SKILL_LIBRARY"


def _yaml(rel: str) -> dict:
    return yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))


def _load_authority_validator():
    path = LIB / "validate_authority.py"
    spec = importlib.util.spec_from_file_location("validate_authority", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load validate_authority")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MultiCoinScannerAuthorityTests(unittest.TestCase):
    def test_trading_project_separates_scan_and_execution_authority(self):
        projects = _yaml("AI_SKILL_LIBRARY/projects.yaml")
        trading = next(row for row in projects["projects"] if row["id"] == "trading")
        self.assertEqual(trading["authority"], "docs/checkpoints/CURRENT_HANDOFF.md")
        self.assertEqual(
            trading["canonical_checkpoint"],
            "docs/checkpoints/MULTI_COIN_A_PLUS_SCANNER_1_0_20260914.md",
        )
        self.assertEqual(trading["authority_token"], "MULTI-COIN-USDT-PERP-A-PLUS-SCANNER-1.0")
        self.assertEqual(
            trading["execution_checkpoint"],
            "docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md",
        )
        self.assertEqual(trading["execution_authority_token"], "BYBIT-BTC-STATEFLOW-2.1")

    def test_handoff_names_both_scopes_and_forbids_scan_to_execution_promotion(self):
        text = (ROOT / "docs/checkpoints/CURRENT_HANDOFF.md").read_text(encoding="utf-8")
        self.assertIn("SCAN/RESEARCH AUTHORITY", text)
        self.assertIn("PRODUCTION EXECUTION AUTHORITY", text)
        self.assertIn("MULTI-COIN-USDT-PERP-A-PLUS-SCANNER-1.0", text)
        self.assertIn("BYBIT-BTC-STATEFLOW-2.1", text)
        self.assertIn("scan/research authority does not grant execution authority", text.lower())

    def test_validator_rejects_collapsed_execution_authority(self):
        validator = _load_authority_validator()
        projects = _yaml("AI_SKILL_LIBRARY/projects.yaml")
        broken = yaml.safe_load(yaml.safe_dump(projects))
        trading = next(row for row in broken["projects"] if row["id"] == "trading")
        trading["execution_checkpoint"] = trading["canonical_checkpoint"]
        trading["execution_authority_token"] = trading["authority_token"]
        checkpoint = __import__("json").loads((LIB / "checkpoint.json").read_text(encoding="utf-8"))
        errors, _warnings = validator.validate_authority_data(broken, checkpoint, root=ROOT)
        self.assertTrue(any("execution authority" in err.lower() or "execution checkpoint" in err.lower() for err in errors), errors)


if __name__ == "__main__":
    unittest.main()
