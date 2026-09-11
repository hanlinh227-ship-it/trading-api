import copy
import importlib.util
import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "AI_SKILL_LIBRARY"


def load_validator():
    path = LIB / "validate_v3.py"
    spec = importlib.util.spec_from_file_location("validate_v3", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load V3 validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BrainV3ValidatorTests(unittest.TestCase):
    def load_inputs(self):
        names = ["kernel", "migration", "context", "reliability", "evidence", "orchestration", "projects", "router"]
        data = {name: yaml.safe_load((LIB / f"{name}.yaml").read_text(encoding="utf-8")) for name in names}
        data["checkpoint"] = json.loads((LIB / "checkpoint.json").read_text(encoding="utf-8"))
        return data

    def test_valid_v3_has_no_errors(self):
        validator = load_validator()
        errors, warnings = validator.validate_v3_data(**self.load_inputs(), root=ROOT)
        self.assertEqual(errors, [], (errors, warnings))

    def test_rejects_competing_ai_brain_authority(self):
        validator = load_validator()
        data = self.load_inputs()
        broken = copy.deepcopy(data)
        broken["router"]["authorities"].append({
            "scope": "ai_brain", "status": "CURRENT_AUTHORITY", "path": "AI_SKILL_LIBRARY/GITHUB_BRAIN_V2.md"
        })
        errors, _ = validator.validate_v3_data(**broken, root=ROOT)
        self.assertTrue(any("ai_brain" in err and "authority" in err for err in errors), errors)

    def test_rejects_fast_path_with_durable_memory_or_parallelism(self):
        validator = load_validator()
        data = self.load_inputs()
        broken = copy.deepcopy(data)
        broken["kernel"]["profiles"]["FAST"]["durable_memory_items"] = 1
        broken["kernel"]["profiles"]["FAST"]["orchestration"] = "parallel"
        errors, _ = validator.validate_v3_data(**broken, root=ROOT)
        joined = "\n".join(errors)
        self.assertIn("FAST", joined)
        self.assertIn("durable_memory_items", joined)
        self.assertIn("orchestration", joined)

    def test_rejects_hidden_reasoning_persistence(self):
        validator = load_validator()
        data = self.load_inputs()
        broken = copy.deepcopy(data)
        broken["evidence"]["ledger"]["persist_hidden_reasoning"] = True
        errors, _ = validator.validate_v3_data(**broken, root=ROOT)
        self.assertTrue(any("hidden reasoning" in err.lower() for err in errors), errors)

    def test_rejects_unbounded_parallelism(self):
        validator = load_validator()
        data = self.load_inputs()
        broken = copy.deepcopy(data)
        broken["orchestration"]["parallelism"]["max_parallel_tasks"] = 99
        errors, _ = validator.validate_v3_data(**broken, root=ROOT)
        self.assertTrue(any("parallel" in err.lower() for err in errors), errors)

    def test_rejects_cache_that_can_outrank_fresh_authority(self):
        validator = load_validator()
        data = self.load_inputs()
        broken = copy.deepcopy(data)
        broken["context"]["policy"]["cache_never_outranks_fresh_authority"] = False
        errors, _ = validator.validate_v3_data(**broken, root=ROOT)
        self.assertTrue(any("cache" in err.lower() and "authority" in err.lower() for err in errors), errors)

    def test_rejects_automatic_self_improvement_merge(self):
        validator = load_validator()
        data = self.load_inputs()
        broken = copy.deepcopy(data)
        broken["kernel"]["invariants"]["no_auto_merge_self_improvement"] = False
        errors, _ = validator.validate_v3_data(**broken, root=ROOT)
        self.assertTrue(any("auto" in err.lower() and "merge" in err.lower() for err in errors), errors)

    def test_trading_authority_must_remain_current_handoff(self):
        validator = load_validator()
        data = self.load_inputs()
        broken = copy.deepcopy(data)
        trading = next(row for row in broken["projects"]["projects"] if row["id"] == "trading")
        trading["authority"] = "AI_SKILL_LIBRARY/GITHUB_BRAIN_V3.md"
        errors, _ = validator.validate_v3_data(**broken, root=ROOT)
        self.assertTrue(any("trading authority" in err.lower() for err in errors), errors)


if __name__ == "__main__":
    unittest.main()
