import importlib.util
import unittest
from copy import deepcopy
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "AI_SKILL_LIBRARY"
VALIDATOR = LIB / "validate_runtime.py"


def load_validator():
    if not VALIDATOR.is_file():
        return None
    spec = importlib.util.spec_from_file_location("validate_runtime", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_yaml(name):
    return yaml.safe_load((LIB / name).read_text(encoding="utf-8"))


class AgentRuntimeValidatorTests(unittest.TestCase):
    def setUp(self):
        self.module = load_validator()
        self.assertIsNotNone(self.module, "validate_runtime.py must exist before validator behavior can pass")
        self.bootstrap = load_yaml("bootstrap.yaml")
        self.runtime = load_yaml("runtime.yaml")
        self.memory = load_yaml("memory.yaml")
        self.evals = load_yaml("evals.yaml")
        self.observability = load_yaml("observability.yaml")
        self.security = load_yaml("security.yaml")

    def validate(self, **overrides):
        payload = {
            "bootstrap": deepcopy(self.bootstrap),
            "runtime": deepcopy(self.runtime),
            "memory": deepcopy(self.memory),
            "evals": deepcopy(self.evals),
            "observability": deepcopy(self.observability),
            "security": deepcopy(self.security),
        }
        payload.update(overrides)
        return self.module.validate_runtime_data(**payload)

    def test_valid_runtime_has_no_errors(self):
        errors, _ = self.validate()
        self.assertEqual(errors, [])

    def test_rejects_fast_path_with_memory_or_planner(self):
        runtime = deepcopy(self.runtime)
        runtime["profiles"]["FAST"]["memory_items"] = 1
        runtime["profiles"]["FAST"]["stages"].append("planner")
        errors, _ = self.validate(runtime=runtime)
        text = "\n".join(errors)
        self.assertIn("FAST", text)
        self.assertIn("memory_items", text)
        self.assertIn("planner", text)

    def test_rejects_unbounded_or_non_monotonic_profile_budgets(self):
        runtime = deepcopy(self.runtime)
        runtime["profiles"]["STANDARD"]["context_tokens"] = 100000
        runtime["profiles"]["DEEP"]["memory_items"] = 0
        errors, _ = self.validate(runtime=runtime)
        text = "\n".join(errors)
        self.assertIn("context_tokens", text)
        self.assertIn("monotonic", text)

    def test_rejects_memory_without_required_privacy_exclusions(self):
        memory = deepcopy(self.memory)
        memory["privacy"]["durable_exclusions"].remove("private_keys")
        errors, _ = self.validate(memory=memory)
        self.assertTrue(any("private_keys" in error for error in errors))

    def test_rejects_persistent_hidden_reasoning(self):
        observability = deepcopy(self.observability)
        observability["policy"]["persist_hidden_chain_of_thought"] = True
        errors, _ = self.validate(observability=observability)
        self.assertTrue(any("chain-of-thought" in error for error in errors))

    def test_rejects_permissive_destructive_defaults(self):
        security = deepcopy(self.security)
        security["risk_classes"]["destructive"]["default"] = "allow"
        errors, _ = self.validate(security=security)
        self.assertTrue(any("destructive" in error for error in errors))

    def test_rejects_automatic_brain_merge(self):
        evals = deepcopy(self.evals)
        evals["promotion"]["automatic_merge"] = True
        errors, _ = self.validate(evals=evals)
        self.assertTrue(any("automatic_merge" in error for error in errors))

    def test_rejects_bootstrap_missing_runtime_pointer(self):
        bootstrap = deepcopy(self.bootstrap)
        del bootstrap["paths"]["runtime"]
        errors, _ = self.validate(bootstrap=bootstrap)
        self.assertTrue(any("bootstrap" in error and "runtime" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
